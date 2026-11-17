from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import __version__
from ..config import Settings, get_settings
from ..domain.errors import DomainError, NotFound
from ..infra.repository import ConcurrencyError
from ..services.fhir import IngestValidationError
from . import routes
from .context import AppContext, Services
from .deps import utcnow
from .security import EXEMPT_PATHS, SECURITY_HEADERS, RateLimiter, caller_key

log = logging.getLogger("tasleem")


def _err(status: int, code: str, message: str, **details: object) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})


async def _scheduler_loop(ctx: AppContext, interval: int) -> None:
    from ..services.scheduler import drain

    while True:
        await asyncio.sleep(interval)
        try:
            def run() -> dict:
                with ctx.sessions() as session:
                    return drain(Services.build(ctx, session).cases, utcnow(), ctx.settings.scheduler_batch_size,
                                 ctx.settings.scheduler_budget_seconds)
            result = await asyncio.to_thread(run)
            if result["events"]:
                log.info("scheduler tick %s", result)
        except Exception:  # keep the loop alive; errors are logged
            log.exception("scheduler tick failed")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if not settings.demo_mode:
        problems = settings.check_production_safety()
        if problems:
            raise RuntimeError("Unsafe production configuration: " + " ".join(problems))
    limiter = RateLimiter(settings.rate_limit_per_second, settings.rate_limit_burst)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ctx = AppContext.build(settings)
        app.state.ctx = ctx
        if settings.seed_on_start:
            from ..seed import seed_if_empty

            seed_if_empty(ctx)
        task = None
        if settings.scheduler_interval_seconds > 0:
            task = asyncio.create_task(_scheduler_loop(ctx, settings.scheduler_interval_seconds))
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        ctx.engine.dispose()

    app = FastAPI(title="Tasleem API", version=__version__, lifespan=lifespan,
                  description="Verified screening-to-care follow-through beside Malaffi and Sahatna.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_request_bytes:
            resp = _err(413, "PAYLOAD_TOO_LARGE", "Request body too large.", limit=settings.max_request_bytes)
            resp.headers["x-request-id"] = rid
            return resp
        if not request.url.path.startswith(EXEMPT_PATHS):
            ok, wait = limiter.allow(caller_key(request))
            if not ok:
                resp = _err(429, "RATE_LIMITED", "Too many requests. Slow down and retry.",
                            retry_after_seconds=round(wait, 2))
                resp.headers["Retry-After"] = str(max(1, round(wait)))
                resp.headers["x-request-id"] = rid
                return resp
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        if not request.url.path.startswith(("/docs", "/redoc")):
            for k, v in SECURITY_HEADERS.items():
                response.headers.setdefault(k, v)
        return response

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        status = 404 if exc.code == "NOT_FOUND" else 403 if exc.code in ("FORBIDDEN", "FORBIDDEN_ROLE") else \
            422 if exc.code == "VALIDATION" else 409
        return _err(status, exc.code, exc.message, **exc.details)

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound) -> JSONResponse:
        return _err(404, "NOT_FOUND", str(exc), what=exc.what, id=exc.ident)

    @app.exception_handler(ConcurrencyError)
    async def conflict(_: Request, exc: ConcurrencyError) -> JSONResponse:
        return _err(409, "CONCURRENT_UPDATE", "The case changed while you were editing it. Reload and retry.")

    @app.exception_handler(IngestValidationError)
    async def ingest_invalid(_: Request, exc: IngestValidationError) -> JSONResponse:
        return _err(422, "INVALID_RESOURCE", exc.message, field=exc.field)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _err(422, "VALIDATION", "Request validation failed.", errors=jsonable_encoder(exc.errors()))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return _err(exc.status_code, exc.detail["code"], exc.detail.get("message", ""))
        return _err(exc.status_code, "HTTP_ERROR", str(exc.detail))

    for r in (routes.health, routes.ingest, routes.cases, routes.me, routes.program, routes.system,
              routes.integration, routes.demo, routes.policy):
        app.include_router(r)
    return app


def __getattr__(name: str) -> FastAPI:
    """`uvicorn tasleem.api.app:app` keeps working, but the app (and its production-safety check) is
    built only when a server asks for it, not whenever a module imports this file."""
    if name == "app":
        return create_app()
    raise AttributeError(name)
