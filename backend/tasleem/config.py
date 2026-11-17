from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_PATHWAYS = Path(__file__).resolve().parent.parent / "pathways"


class Settings(BaseSettings):
    """Runtime configuration. Every field can be set with a TASLEEM_ environment variable."""

    model_config = SettingsConfigDict(env_prefix="TASLEEM_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./tasleem.db"
    redis_url: str | None = None
    # Demo mode enables guest identities (X-Demo-User), time travel and the reset endpoint. Off by default
    # (secure by default): docker-compose, tests and the benchmark switch it on explicitly.
    demo_mode: bool = False
    # Legacy single key: grants every integration scope. Prefer integration_keys.
    integration_key: str | None = None
    # One key per calling service, each limited to its scopes (see deps.INTEGRATION_SCOPES), e.g.
    # TASLEEM_INTEGRATION_KEYS='{"connector": "...", "notifier": "..."}'.
    integration_keys: dict[str, str] = {}
    # > 0 runs the deadline scheduler inside the API process every N seconds.
    scheduler_interval_seconds: int = 0
    seed_on_start: bool = False
    pathways_dir: Path = _DEFAULT_PATHWAYS
    cors_origins: list[str] = ["*"]
    # Per-identity token bucket inside each replica. The gateway should also rate limit; this is the floor.
    rate_limit_per_second: float = 20.0
    rate_limit_burst: int = 60
    # SQLite / demo: create tables at start-up. Postgres in production: run `python -m tasleem.migrate`.
    auto_create_schema: bool = True
    metrics_ttl_seconds: int = 60
    # Program metrics may lag writes by at most this many seconds. Under steady ingest every write
    # bumps the cache version; without this bound each dashboard read would rescan every case.
    metrics_max_staleness_seconds: int = 15
    # Scheduler drains due cases in batches until none are left or this time budget is used.
    scheduler_batch_size: int = 500
    scheduler_budget_seconds: float = 30.0
    # Requests larger than this are rejected with 413 before they are parsed.
    max_request_bytes: int = 1_000_000
    # Postgres only: abort any single SQL statement that runs longer than this.
    db_statement_timeout_ms: int = 5000
    db_pool_size: int = 10
    db_max_overflow: int = 20


    def check_production_safety(self) -> list[str]:
        """Settings that are only acceptable in a demo. The API refuses to start with any of them when
        demo mode is off."""
        problems = []
        if "*" in self.cors_origins:
            problems.append("TASLEEM_CORS_ORIGINS must list explicit origins (no '*').")
        if not (self.integration_key or self.integration_keys):
            problems.append("Set TASLEEM_INTEGRATION_KEYS so ingest and outbox endpoints are protected.")
        if self.database_url.startswith("sqlite"):
            problems.append("Use PostgreSQL (TASLEEM_DATABASE_URL) outside demo mode.")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
