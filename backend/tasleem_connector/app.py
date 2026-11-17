"""Connector HTTP API (port 8030).

  POST /v1/hl7   body: one HL7 v2 message (ER7 text). Answer: an HL7 ACK (text), with HTTP status
                 200 for AA, 422 for AR/AE content errors, 503 when case-core is unreachable (retry).

Interface engines (Rhapsody, Mirth, InterSystems) usually relay MLLP traffic to HTTPS; a raw MLLP
listener is not part of this build.
"""

from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

from tasleem_common.http import ServiceClient, ServiceError

from .hl7 import MAX_BYTES, HL7Error, Message, ack, parse
from .mapping import to_core

log = logging.getLogger("tasleem.connector")
HL7_MEDIA = "application/hl7-v2"


class ConnectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONNECTOR_", env_file=".env", extra="ignore")

    core_url: str = "http://localhost:8000"
    core_integration_key: str | None = None  # the "connector" key in TASLEEM_INTEGRATION_KEYS
    inbound_key: str | None = None  # what senders present in X-Connector-Key
    demo_mode: bool = False


@lru_cache
def get_settings() -> ConnectorSettings:
    return ConnectorSettings()


def create_app(settings: ConnectorSettings | None = None, core: ServiceClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    if not settings.demo_mode and not settings.inbound_key:
        raise RuntimeError("CONNECTOR_INBOUND_KEY is required outside demo mode")
    if core is None:
        headers = {"x-integration-key": settings.core_integration_key} if settings.core_integration_key else {}
        core = ServiceClient(settings.core_url, headers=headers, timeout=10.0, retries=3)

    app = FastAPI(title="Tasleem HL7 Connector", version="0.2.0",
                  description="HL7 v2 ORU / REF / SIU to FHIR R4, forwarded to Tasleem case-core.")

    def sender(x_connector_key: str | None = Header(default=None)) -> None:
        if not settings.inbound_key:
            return  # demo only (enforced at start-up)
        if not x_connector_key or not hmac.compare_digest(x_connector_key, settings.inbound_key):
            raise HTTPException(401, {"code": "CONNECTOR_KEY", "message": "Sender key required."})

    def reply(msg: Message | None, code: str, text: str, status: int) -> PlainTextResponse:
        return PlainTextResponse(ack(msg, code, text, datetime.now(UTC)), status_code=status, media_type=HL7_MEDIA)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/hl7", dependencies=[Depends(sender)])
    async def hl7(request: Request) -> PlainTextResponse:
        raw = await request.body()
        if len(raw) > MAX_BYTES:
            return reply(None, "AR", "message too large", 413)
        try:
            msg = parse(raw)
        except (HL7Error, UnicodeDecodeError) as exc:
            return reply(None, "AR", f"unparseable: {exc}", 422)
        try:
            forwards = to_core(msg)
        except HL7Error as exc:
            return reply(msg, "AR" if "unsupported" in str(exc) else "AE", str(exc), 422)
        results = []
        for f in forwards:
            path = "/v1/ingest/fhir" if f.kind == "fhir" else "/v1/ingest/referral-status"
            try:
                r = core.request("POST", path, json=f.body, headers={"x-message-id": f.message_id})
            except ServiceError as exc:
                log.warning("case-core unavailable for %s: %s", msg.control_id, exc)
                return reply(msg, "AE", "temporarily unavailable, retry", 503)
            if r.status_code >= 400:
                detail = (r.json().get("error") or {}).get("message", "rejected") if r.headers.get(
                    "content-type", "").startswith("application/json") else "rejected"
                return reply(msg, "AE", detail, 422)
            results.append(r.json())
        n = sum(len(x.get("results", [x])) for x in results)
        return reply(msg, "AA", f"accepted {n} item(s)" if forwards else "accepted, nothing tracked", 200)

    return app


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name == "app":  # `uvicorn tasleem_connector.app:app`
        return create_app()
    raise AttributeError(name)
