"""HTTP client for calls between services: timeouts, bounded retries with jittered backoff, request ids.

Retries are only safe because every core endpoint a satellite calls is idempotent (ingest is keyed by
message id, outbox ack and delivery-failure reports are keyed by outbox id).
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from typing import Any

import httpx

log = logging.getLogger("tasleem.http")
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class ServiceError(Exception):
    """The other service answered with a non-retryable error, or retries ran out."""

    def __init__(self, message: str, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class ServiceClient:
    def __init__(self, base_url: str = "", *, headers: dict[str, str] | None = None, timeout: float = 5.0,
                 retries: int = 3, backoff: float = 0.2, client: httpx.Client | None = None,
                 sleep: Any = time.sleep) -> None:
        # `client` lets tests pass a Starlette TestClient (an httpx.Client) bound to the other app.
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)
        self._headers = headers or {}
        self.retries = retries
        self.backoff = backoff
        self._sleep = sleep

    def request(self, method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None,
                headers: dict[str, str] | None = None, content: str | bytes | None = None) -> httpx.Response:
        h = {"x-request-id": uuid.uuid4().hex, **self._headers, **(headers or {})}
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                r = self._client.request(method, path, json=json, params=params, headers=h, content=content)
            except httpx.TransportError as exc:  # connection refused, timeout, reset
                last = exc
            else:
                if r.status_code not in RETRY_STATUS:
                    return r
                last = ServiceError(f"{method} {path} -> {r.status_code}", r.status_code, _body(r))
            if attempt < self.retries:
                delay = self.backoff * (2 ** attempt) * (0.5 + random.random())
                log.warning("retrying %s %s in %.2fs (%s)", method, path, delay, last)
                self._sleep(delay)
        if isinstance(last, ServiceError):
            raise last
        raise ServiceError(f"{method} {path} failed: {last}") from last

    def json(self, method: str, path: str, **kw: Any) -> Any:
        r = self.request(method, path, **kw)
        if r.status_code >= 400:
            raise ServiceError(f"{method} {path} -> {r.status_code}", r.status_code, _body(r))
        return r.json()

    def close(self) -> None:
        self._client.close()


def _body(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError:
        return r.text[:500]
