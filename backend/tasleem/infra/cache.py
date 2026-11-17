"""Cache abstraction. Only aggregates and reference data are cached; clinical case state never is."""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def incr(self, key: str) -> int: ...
    def get_int(self, key: str) -> int: ...
    def clear(self) -> None: ...


class InMemoryTTLCache:
    """Process-local cache for development, tests and single-instance demos."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float | None, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires is not None and expires < time.monotonic():
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + ttl_seconds, value)

    def incr(self, key: str) -> int:
        with self._lock:
            _, value = self._data.get(key, (None, 0))
            value = int(value) + 1
            self._data[key] = (None, value)
            return value

    def get_int(self, key: str) -> int:
        v = self.get(key)
        return int(v) if v is not None else 0

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisCache:
    """Shared cache for multi-instance deployments. Values are JSON-encoded."""

    def __init__(self, url: str, prefix: str = "tasleem:") -> None:
        import redis  # optional dependency

        self._r = redis.Redis.from_url(url, decode_responses=True)
        self._p = prefix

    def get(self, key: str) -> Any | None:
        raw = self._r.get(self._p + key)
        return None if raw is None else json.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._r.set(self._p + key, json.dumps(value, default=str), ex=ttl_seconds)

    def incr(self, key: str) -> int:
        return int(self._r.incr(self._p + key))

    def get_int(self, key: str) -> int:
        raw = self._r.get(self._p + key)
        return int(raw) if raw is not None else 0

    def clear(self) -> None:
        for k in self._r.scan_iter(self._p + "*"):
            self._r.delete(k)


def make_cache(redis_url: str | None) -> Cache:
    return RedisCache(redis_url) if redis_url else InMemoryTTLCache()


WRITE_VERSION_KEY = "write_version"
