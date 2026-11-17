"""HTTP hardening shared by every route: rate limiting and response headers.

The rate limiter is a per-replica token bucket keyed by caller identity (demo persona, integration key
fingerprint or client IP). It is a floor against a runaway client or script, not a distributed quota:
production puts the API gateway's limiter in front of it.
"""

from __future__ import annotations

import hashlib

from starlette.requests import Request

from tasleem_common.ratelimit import RateLimiter

__all__ = ["EXEMPT_PATHS", "SECURITY_HEADERS", "RateLimiter", "caller_key"]

# Health probes and docs are never limited, so an orchestrator can always see the process.
EXEMPT_PATHS = ("/healthz", "/readyz", "/docs", "/openapi.json", "/redoc")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # Case data must never be stored by browsers or shared caches.
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def caller_key(request: Request) -> str:
    """Identity used for limiting. Secrets are hashed so they never sit in memory as dictionary keys."""
    user = request.headers.get("x-demo-user")
    if user:
        return f"user:{user}"
    secret = request.headers.get("x-integration-key") or request.headers.get("authorization")
    if secret:
        return "key:" + hashlib.sha256(secret.encode()).hexdigest()[:16]
    return f"ip:{request.client.host if request.client else 'unknown'}"
