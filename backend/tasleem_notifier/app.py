"""Notifier HTTP API (port 8010) and its background worker loop.

Endpoints:
  GET  /healthz, /readyz
  GET  /v1/policy                     channel matrix: who is reached how (public, no case data)
  GET  /v1/notifications?case_id=     delivery trail (operations key; demo: open)
  POST /v1/receipts                   provider callback: delivered / read / failed (HMAC-signed)
  POST /v1/run-once                   run one cycle now (operations key; demo: optional time travel)
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select, text

from tasleem_common.http import ServiceClient

from .adapters import SandboxProvider, WebhookProvider, verify_signature
from .policy import Policy
from .service import Notifier
from .store import DeliveryRow, NotificationRow, make_store

log = logging.getLogger("tasleem.notifier")


class NotifierSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIFIER_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./notifier.db"
    core_url: str = "http://localhost:8000"
    core_integration_key: str | None = None  # the "notifier" key in TASLEEM_INTEGRATION_KEYS
    poll_seconds: int = 0  # > 0 runs the worker loop inside the API process
    policy_file: Path | None = None
    provider: Literal["sandbox", "webhook"] = "sandbox"
    webhooks: dict[str, str] = {}
    webhook_secret: str | None = None  # signs outgoing webhooks and verifies incoming receipts
    allow_insecure_webhooks: bool = False
    sandbox_no_app: list[str] = ["p-demo-unreach-*"]
    sandbox_no_phone: list[str] = ["p-demo-unreach-*"]
    ops_key: str | None = None
    demo_mode: bool = False
    # Browser origins allowed to call this service (the Lovable UI). Use explicit origins in production.
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> NotifierSettings:
    return NotifierSettings()


def build_notifier(settings: NotifierSettings, core: ServiceClient | None = None) -> Notifier:
    _, sessions = make_store(settings.database_url)
    if settings.provider == "webhook":
        if not settings.webhook_secret:
            raise RuntimeError("NOTIFIER_WEBHOOK_SECRET is required with the webhook provider")
        provider: Any = WebhookProvider(settings.webhooks, settings.webhook_secret, settings.allow_insecure_webhooks)
    else:
        provider = SandboxProvider(no_app=list(settings.sandbox_no_app), no_phone=list(settings.sandbox_no_phone))
    if core is None:
        headers = {"x-integration-key": settings.core_integration_key} if settings.core_integration_key else {}
        core = ServiceClient(settings.core_url, headers=headers)
    return Notifier(sessions, Policy.load(settings.policy_file), provider, core)


class ReceiptIn(BaseModel):
    delivery_id: int = Field(ge=1)
    status: Literal["delivered", "read", "failed"]


class RunIn(BaseModel):
    now: datetime | None = None
    force_digest: bool = False


def _delivery(d: DeliveryRow) -> dict[str, Any]:
    return {"id": d.id, "step": d.step, "channel": d.channel, "status": d.status, "provider_ref": d.provider_ref,
            "detail": d.detail, "at": d.updated_at}


def create_app(settings: NotifierSettings | None = None, core: ServiceClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    if not settings.demo_mode and not settings.ops_key:
        raise RuntimeError("NOTIFIER_OPS_KEY is required outside demo mode")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.notifier = build_notifier(settings, core)
        task = asyncio.create_task(_loop(app.state.notifier, settings.poll_seconds)) if settings.poll_seconds else None
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Tasleem Notifier", version="0.2.0", lifespan=lifespan,
                  description="Channel routing and delivery for Tasleem notifications.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"],
                       allow_headers=["*"])

    def notifier(request: Request) -> Notifier:
        return request.app.state.notifier

    def ops(x_ops_key: str | None = Header(default=None)) -> None:
        if settings.demo_mode and not settings.ops_key:
            return
        if not x_ops_key or not settings.ops_key or not hmac.compare_digest(x_ops_key, settings.ops_key):
            raise HTTPException(401, {"code": "OPS_KEY", "message": "Operations key required."})

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz(n: Notifier = Depends(notifier)) -> dict[str, str]:
        with n.sessions() as s:
            s.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/v1/policy")
    def policy(n: Notifier = Depends(notifier)) -> dict[str, Any]:
        p = n.policy
        return {"timezone_offset_hours": p.timezone_offset_hours, "quiet_hours": p.quiet_hours.model_dump(),
                "digest_hour": p.digest_hour,
                "channels": {k: v.model_dump() for k, v in p.channels.items()}, "recipients": p.matrix()}

    @app.get("/v1/notifications", dependencies=[Depends(ops)])
    def notifications(case_id: str | None = Query(default=None, max_length=64),
                      recipient_id: str | None = Query(default=None, max_length=64),
                      limit: int = Query(100, ge=1, le=500), n: Notifier = Depends(notifier)) -> dict[str, Any]:
        with n.sessions() as s:
            q = select(NotificationRow).order_by(NotificationRow.id.desc()).limit(limit)
            if case_id:
                q = q.where(NotificationRow.case_id == case_id)
            if recipient_id:
                q = q.where(NotificationRow.recipient_id == recipient_id)
            rows = s.execute(q).scalars().all()
            dels = s.execute(select(DeliveryRow).where(DeliveryRow.notification_id.in_([r.id for r in rows]))
                             .order_by(DeliveryRow.step, DeliveryRow.id)).scalars().all()
            by: dict[int, list[DeliveryRow]] = {}
            for d in dels:
                by.setdefault(d.notification_id, []).append(d)
            return {"items": [{"outbox_id": r.outbox_id, "case_id": r.case_id, "recipient_id": r.recipient_id,
                               "recipient_role": r.recipient_role, "template": r.template, "urgent": r.urgent,
                               "status": r.status, "next_at": r.next_at,
                               "deliveries": [_delivery(d) for d in by.get(r.id, [])]} for r in rows]}

    @app.post("/v1/receipts")
    async def receipts(request: Request, x_tasleem_signature: str | None = Header(default=None),
                       n: Notifier = Depends(notifier)) -> dict[str, Any]:
        raw = await request.body()
        if settings.webhook_secret:
            if not verify_signature(settings.webhook_secret, raw, x_tasleem_signature):
                raise HTTPException(401, {"code": "SIGNATURE", "message": "Bad or missing signature."})
        elif not settings.demo_mode:
            raise HTTPException(401, {"code": "SIGNATURE", "message": "Receipts must be signed."})
        try:
            body = ReceiptIn.model_validate(json.loads(raw or b"{}"))
        except ValueError as exc:
            raise HTTPException(422, {"code": "VALIDATION", "message": str(exc)[:300]}) from None
        out = n.receipt(body.delivery_id, body.status, datetime.now(UTC))
        if out is None:
            raise HTTPException(404, {"code": "NOT_FOUND", "message": "Unknown delivery."})
        return out

    @app.post("/v1/run-once", dependencies=[Depends(ops)])
    def run_once(body: RunIn | None = None, n: Notifier = Depends(notifier)) -> dict[str, Any]:
        body = body or RunIn()
        if body.now is not None and not settings.demo_mode:
            raise HTTPException(403, {"code": "FORBIDDEN", "message": "Time travel is demo-only."})
        now = body.now.astimezone(UTC) if body.now else datetime.now(UTC)
        result = n.run_once(now)
        if body.force_digest:
            result["digests"] += n.run_digest(now, force=True)
        return result

    return app


async def _loop(n: Notifier, every: int) -> None:
    while True:
        await asyncio.sleep(every)
        try:
            result = await asyncio.to_thread(n.run_once, datetime.now(UTC))
            if any(result.values()):
                log.info("notifier cycle %s", result)
        except Exception:  # keep the loop alive; the next cycle retries
            log.exception("notifier cycle failed")


def __getattr__(name: str) -> FastAPI:
    if name == "app":  # `uvicorn tasleem_notifier.app:app`
        return create_app()
    raise AttributeError(name)
