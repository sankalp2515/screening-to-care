"""Per-replica token-bucket rate limiter shared by every Tasleem service.

A floor against a runaway client or script, not a distributed quota: production also limits at the
API gateway.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    def __init__(self, rate_per_second: float, burst: int, max_keys: int = 50_000) -> None:
        self.rate = rate_per_second
        self.burst = burst
        self.max_keys = max_keys
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Returns (allowed, seconds until one token is available)."""
        if self.rate <= 0:
            return True, 0.0
        now = time.monotonic() if now is None else now
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                if len(self._buckets) >= self.max_keys:  # bound memory under a key-spraying client
                    self._buckets.clear()
                b = self._buckets[key] = _Bucket(tokens=float(self.burst), updated=now)
            b.tokens = min(self.burst, b.tokens + (now - b.updated) * self.rate)
            b.updated = now
            if b.tokens >= 1:
                b.tokens -= 1
                return True, 0.0
            return False, (1 - b.tokens) / self.rate
