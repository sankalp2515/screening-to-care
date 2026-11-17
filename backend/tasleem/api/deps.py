from __future__ import annotations

import hmac
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, Request

from ..domain.errors import NotFound
from ..domain.model import Actor, ActorType
from .context import AppContext, Services


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_services(ctx: AppContext = Depends(get_ctx)) -> Iterator[Services]:
    session = ctx.sessions()
    try:
        yield Services.build(ctx, session)
    finally:
        session.close()


def utcnow() -> datetime:
    return datetime.now(UTC)


def _auth_error(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=401, detail={"code": code, "message": message})


def current_actor(
    ctx: AppContext = Depends(get_ctx),
    svc: Services = Depends(get_services),
    x_demo_user: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Actor:
    """Demo mode: guest identity from X-Demo-User. Production: OIDC bearer token (validated at the gateway)."""
    if ctx.settings.demo_mode:
        if not x_demo_user:
            raise _auth_error("AUTH_REQUIRED", "Choose a demo persona (X-Demo-User header).")
        try:
            actor = svc.directory.actor_for(x_demo_user)
        except NotFound:
            raise _auth_error("UNKNOWN_IDENTITY", f"No demo persona '{x_demo_user}'.") from None
        # Callers can never claim machine identities (R5).
        if actor.type in (ActorType.AI, ActorType.SYSTEM, ActorType.INTEGRATION):
            raise _auth_error("FORBIDDEN_IDENTITY", "Machine identities cannot be used by callers.")
        return actor
    if not authorization:
        raise _auth_error("AUTH_REQUIRED", "Bearer token required.")
    # Production integration point: validate the JWT (Entra ID / UAE Pass) and map claims to an Actor.
    raise _auth_error("OIDC_NOT_CONFIGURED", "OIDC validation is not configured in this build.")


def require_staff(actor: Actor = Depends(current_actor)) -> Actor:
    if actor.type not in (ActorType.CLINICIAN, ActorType.NAVIGATOR, ActorType.COORDINATOR):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Care-team access only."})
    return actor


def require_patient(actor: Actor = Depends(current_actor)) -> Actor:
    if actor.type != ActorType.PATIENT:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Patient access only."})
    return actor


# What each calling service may do. A leaked notifier key cannot inject clinical evidence, and a leaked
# connector key cannot read patient notifications.
INTEGRATION_SCOPES: dict[str, frozenset[str]] = {
    "connector": frozenset({"ingest"}),
    "malaffi": frozenset({"ingest"}),
    "notifier": frozenset({"outbox"}),
}


def _match_key(ctx: AppContext, presented: str | None) -> tuple[str, frozenset[str]] | None:
    if not presented:
        return None
    for name, key in ctx.settings.integration_keys.items():
        if key and hmac.compare_digest(presented.encode(), key.encode()):
            return name, INTEGRATION_SCOPES.get(name, frozenset())
    legacy = ctx.settings.integration_key
    if legacy and hmac.compare_digest(presented.encode(), legacy.encode()):
        return "malaffi", frozenset({"ingest", "outbox"})
    return None


def integration(scope: str) -> Callable[..., str]:
    """Dependency factory: the caller must hold a key with `scope`. Returns the caller's name, which
    becomes the integration actor id on events."""

    def dep(ctx: AppContext = Depends(get_ctx), x_integration_key: str | None = Header(default=None)) -> str:
        configured = bool(ctx.settings.integration_key or ctx.settings.integration_keys)
        if not configured:
            if ctx.settings.demo_mode:
                return "malaffi"
            raise HTTPException(status_code=401, detail={"code": "INTEGRATION_KEY",
                                                         "message": "Integration key must be configured."})
        hit = _match_key(ctx, x_integration_key)
        if hit is None:
            raise HTTPException(status_code=401, detail={"code": "INTEGRATION_KEY",
                                                         "message": "Invalid integration key."})
        name, scopes = hit
        if scope not in scopes:
            raise HTTPException(status_code=403, detail={"code": "INTEGRATION_SCOPE",
                                                         "message": f"This key may not use '{scope}'."})
        return name

    return dep


require_integration = integration("ingest")
require_outbox = integration("outbox")


def require_demo(ctx: AppContext = Depends(get_ctx)) -> None:
    if not ctx.settings.demo_mode:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not available."})
