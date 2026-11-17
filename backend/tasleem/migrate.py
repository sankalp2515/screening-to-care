"""Bring the case-core database to the latest schema: `python -m tasleem.migrate`.

- Empty database: `alembic upgrade head`.
- Database created earlier by `create_all` (demo and early builds) with no alembic_version table:
  check it has the baseline tables, `stamp` it at the baseline revision (0001), then upgrade, so
  existing data is kept and later changes (such as new columns) are still applied.
- Already managed: `upgrade head` (no-op when current).
Run it once per deploy, before new API replicas start (an init container or a release step).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .config import get_settings
from .infra.db import make_engine

ROOT = Path(__file__).resolve().parent.parent
BASELINE = "0001"
BASELINE_TABLES = {"organizations", "practitioners", "patients", "cases", "case_events", "inbound_messages",
                   "case_assignments", "outbox"}


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    return cfg


def migrate(url: str) -> str:
    engine = make_engine(url, statement_timeout_ms=0)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    cfg = alembic_config(url)
    if tables and "alembic_version" not in tables:
        missing = BASELINE_TABLES - tables
        if missing:
            raise SystemExit(f"Unmanaged database is missing tables {sorted(missing)}; refusing to stamp it.")
        command.stamp(cfg, BASELINE)
        command.upgrade(cfg, "head")
        return "stamped"
    command.upgrade(cfg, "head")
    return "upgraded"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=None, help="database URL (default TASLEEM_DATABASE_URL)")
    args = ap.parse_args(argv)
    print(migrate(args.url or get_settings().database_url))


if __name__ == "__main__":
    main()
