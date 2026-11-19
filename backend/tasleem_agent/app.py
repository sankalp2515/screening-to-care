"""Agent HTTP API (port 8020).

  GET  /v1/cases/{id}/assist          sense -> decide -> act -> hand off, in one response
  POST /v1/cases/{id}/brief           cited case brief for the clinician
  POST /v1/cases/{id}/outreach-draft  plain-language patient message draft (policy-checked)
  POST /v1/translate                  patient reply translated for staff (LLM only; else unavailable)
  POST /v1/barrier-suggestion         LLM barrier code suggestion (TSL-110; off unless it beats keywords)
  GET  /v1/drafts/{id}                what the agent drafted, for audit

The caller's identity header is forwarded to case-core on every read, so org scoping applies unchanged:
a clinic that cannot see a case through case-core cannot see it through the agent either.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import JSON, DateTime, Engine, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from tasleem_common.http import ServiceClient, ServiceError
from tasleem_common.ratelimit import RateLimiter

from .assist import draft_outreach, facts, make_brief, translate
from .classify import suggest_barrier
from .providers import CachedProvider, LLMProvider, make_provider, with_cache


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", extra="ignore")

    core_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./agent.db"
    # offline (default) | claude (ANTHROPIC_API_KEY) | groq (GROQ_API_KEY) | gemini (GEMINI_API_KEY)
    # | nvidia (NVIDIA_API_KEY) | openai_compat (AGENT_LLM_BASE_URL + AGENT_LLM_API_KEY)
    # | azure_openai (AGENT_LLM_BASE_URL = https://<resource>.openai.azure.com/openai/v1 + AZURE_OPENAI_API_KEY)
    llm_provider: Literal["offline", "claude", "groq", "gemini", "nvidia", "openrouter", "azure_openai",
                          "openai_compat"] = "offline"
    llm_model: str = ""  # empty: the provider's default model (Azure: the deployment name)
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: float = 20.0
    # Reasoning models only (gpt-5*, o*): minimal | low | medium | high. Short drafting tasks need little.
    llm_reasoning_effort: str = "low"
    # Same case state, same reply: free model tiers allow few calls a day. 0 turns the cache off.
    llm_cache_entries: int = 512
    # After a rate-limit reply, skip the model for this long and use templates at once.
    llm_cooldown_seconds: float = 60.0
    # Drafting calls can cost money: a tighter limit than case-core.
    rate_limit_per_second: float = 2.0
    rate_limit_burst: int = 10
    # Browser origins allowed to call this service (the Lovable UI). Use explicit origins in production.
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()


class Base(DeclarativeBase):
    pass


class DraftRow(Base):
    """Append-only log of what the agent produced and for whom. The case event of a sent message carries
    the draft id, so an auditor can compare the draft with what a person actually sent."""

    __tablename__ = "agent_drafts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    requested_by: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DraftIn(BaseModel):
    language: Literal["en", "ar"] | None = None


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    target: Literal["en", "ar"] = "en"


def make_engine(url: str) -> Engine:
    """SQLite for tests and local runs; a server database gets a self-healing pool.

    Cloud networks drop idle TCP connections (Azure outbound flows after about 4 minutes), so a pooled
    connection can be dead when a draft is saved after a slow model call. Pre-ping replaces a dead
    connection at checkout, recycling retires connections before the idle limit, and TCP keepalives
    stop the network from treating an open connection as idle.
    """
    if url.startswith("sqlite"):
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    connect_args: dict[str, Any] = {}
    if url.startswith("postgresql"):
        connect_args = {"keepalives": 1, "keepalives_idle": 60, "keepalives_interval": 15, "keepalives_count": 4}
    return create_engine(url, pool_pre_ping=True, pool_recycle=POOL_RECYCLE_SECONDS, connect_args=connect_args)


POOL_RECYCLE_SECONDS = 180


def create_app(settings: AgentSettings | None = None, core: ServiceClient | None = None,
               llm: LLMProvider | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    core = core or ServiceClient(settings.core_url, timeout=5.0, retries=1)
    llm = llm or with_cache(make_provider(settings.llm_provider, settings.llm_model, settings.llm_timeout_seconds,
                                          base_url=settings.llm_base_url,
                                          api_key=settings.llm_api_key.get_secret_value(),
                                          reasoning_effort=settings.llm_reasoning_effort),
                            settings.llm_cache_entries, settings.llm_cooldown_seconds)
    limiter = RateLimiter(settings.rate_limit_per_second, settings.rate_limit_burst)

    app = FastAPI(title="Tasleem Agent", version="0.2.0",
                  description="Suggest-only assistant: cited briefs and policy-checked patient drafts.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"],
                       allow_headers=["*"])

    @app.middleware("http")
    async def limit(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path.startswith("/v1/"):
            who = request.headers.get("x-demo-user") or request.headers.get("authorization") or (
                request.client.host if request.client else "?")
            ok, wait = limiter.allow(who)
            if not ok:
                return JSONResponse(status_code=429, headers={"Retry-After": str(max(1, round(wait)))},
                                    content={"error": {"code": "RATE_LIMITED", "message": "Too many requests."}})
        resp = await call_next(request)
        resp.headers.setdefault("Cache-Control", "no-store")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        return resp

    def caller(x_demo_user: str | None = Header(default=None),
               authorization: str | None = Header(default=None)) -> dict[str, str]:
        if x_demo_user:
            return {"X-Demo-User": x_demo_user}
        if authorization:
            return {"Authorization": authorization}
        raise HTTPException(401, {"code": "AUTH_REQUIRED", "message": "Identify yourself as for case-core."})

    def core_get(path: str, who: dict[str, str]) -> dict[str, Any]:
        try:
            return core.json("GET", path, headers=who)
        except ServiceError as exc:
            if exc.status in (401, 403, 404):  # same answer case-core gave; nothing extra revealed
                raise HTTPException(exc.status, (exc.body or {}).get("error") if isinstance(exc.body, dict)
                                    else None) from None
            raise HTTPException(503, {"code": "CORE_UNAVAILABLE", "message": "Case service unavailable."}) from None

    def policy_check(who: dict[str, str]) -> Any:
        def check(t: str) -> dict[str, Any]:
            try:
                return core.json("POST", "/v1/policy/patient-message-check", json={"text": t}, headers=who)
            except ServiceError:
                return {"ok": False, "violations": [{"code": "POLICY_UNAVAILABLE", "detail": "Policy check failed."}]}
        return check

    def record(case_id: str, kind: str, who: dict[str, str], source: str, model: str, content: dict) -> str:
        did = f"drf_{uuid.uuid4().hex[:16]}"
        with sessions() as s:
            s.add(DraftRow(id=did, case_id=case_id, kind=kind, requested_by=next(iter(who.values()))[:64],
                           source=source, model=model, content=content, created_at=datetime.now(UTC)))
            s.commit()
        return did

    def brief_for(case_id: str, case: dict, who: dict[str, str]) -> dict[str, Any]:
        b = make_brief(case, llm)
        b["draft_id"] = record(case_id, "brief", who, b["source"], b["model"], b)
        return b

    def outreach_for(case_id: str, case: dict, language: str | None, who: dict[str, str]) -> dict[str, Any]:
        lang = language or (case["patient"].get("language") if case["patient"].get("language") in ("en", "ar")
                            else "en")
        d = draft_outreach(case, lang, llm, policy_check(who))
        if d.get("draft"):
            did = record(case_id, "outreach", who, d["source"], d["model"], d)
            d["draft_id"] = did
            d["requires_approval"] = True
            d["send_with"] = {"method": "POST", "path": f"/v1/cases/{case_id}/patient-messages",
                              "body": {"text": d["draft"]["text"], "language": lang, "ai_draft_id": did}}
        return d

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        out: dict[str, Any] = {"status": "ok", "llm": llm.name}
        if isinstance(llm, CachedProvider):
            out["llm_cache"] = llm.stats()
        return out

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        with sessions() as s:
            s.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/v1/cases/{case_id}/assist")
    def assist(case_id: str, who: dict[str, str] = Depends(caller)) -> dict[str, Any]:
        case = core_get(f"/v1/cases/{case_id}", who)
        return {
            "case_id": case_id,
            "sense": [f.model_dump() for f in facts(case)],
            "decide": {"next_step": case.get("next_step"),
                       "note": "Chosen by case-core's fixed rules. The agent cannot change it."},
            "act": {"brief": brief_for(case_id, case, who),
                    "patient_message": outreach_for(case_id, case, None, who)},
            "hand_off": {"to": (case.get("next_step") or {}).get("person"),
                         "note": "Nothing is sent or changed until this person acts in Tasleem."},
            "llm": llm.name,
        }

    @app.post("/v1/cases/{case_id}/brief")
    def brief(case_id: str, who: dict[str, str] = Depends(caller)) -> dict[str, Any]:
        return brief_for(case_id, core_get(f"/v1/cases/{case_id}", who), who)

    @app.post("/v1/cases/{case_id}/outreach-draft")
    def outreach(case_id: str, body: DraftIn | None = None, who: dict[str, str] = Depends(caller)) -> dict[str, Any]:
        return outreach_for(case_id, core_get(f"/v1/cases/{case_id}", who), (body or DraftIn()).language, who)

    @app.post("/v1/translate")
    def translate_reply(body: TranslateIn, who: dict[str, str] = Depends(caller)) -> dict[str, Any]:
        core_get("/v1/me", who)  # only identified staff or patients may spend model calls
        return translate(body.text, body.target, llm)

    @app.post("/v1/barrier-suggestion")
    def barrier_suggestion(body: TranslateIn, who: dict[str, str] = Depends(caller)) -> dict[str, Any]:
        core_get("/v1/me", who)
        s = suggest_barrier(body.text, llm)
        if s is None:
            return {"available": False, "why": "No model configured; case-core's keyword classifier applies."}
        return {"available": True, "code": None if s.code == "none" else s.code, "confidence": s.confidence,
                "provenance": "ai_suggestion", "model": llm.name, "requires_confirmation": True}

    @app.get("/v1/drafts/{draft_id}")
    def get_draft(draft_id: str, who: dict[str, str] = Depends(caller)) -> dict[str, Any]:
        with sessions() as s:
            row = s.get(DraftRow, draft_id)
        if row is None:
            raise HTTPException(404, {"code": "NOT_FOUND", "message": "Unknown draft."})
        core_get(f"/v1/cases/{row.case_id}", who)  # same visibility as the case itself
        return {"id": row.id, "case_id": row.case_id, "kind": row.kind, "requested_by": row.requested_by,
                "source": row.source, "model": row.model, "content": row.content, "created_at": row.created_at}

    return app


def __getattr__(name: str) -> FastAPI:
    if name == "app":  # `uvicorn tasleem_agent.app:app`
        return create_app()
    raise AttributeError(name)
