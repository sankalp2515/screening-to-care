"""Deadline scheduler as its own process: `python -m tasleem.workers.scheduler`.

Runs the same `drain` the API can run in-process, so deadlines keep being checked when the API is
scaled to zero or restarted, and several schedulers can run side by side (SKIP LOCKED + optimistic
versions turn any overlap into a counted conflict, never a double escalation).
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import threading
from datetime import UTC, datetime

from ..api.context import AppContext, Services
from ..config import get_settings
from ..services.scheduler import drain

log = logging.getLogger("tasleem.scheduler")


def run_once(ctx: AppContext) -> dict[str, int]:
    with ctx.sessions() as session:
        return drain(Services.build(ctx, session).cases, datetime.now(UTC), ctx.settings.scheduler_batch_size,
                     ctx.settings.scheduler_budget_seconds)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interval", type=int, default=None, help="seconds between drains (default from settings)")
    ap.add_argument("--once", action="store_true", help="run one drain and exit (cron / Kubernetes CronJob)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    ctx = AppContext.build(settings)
    interval = args.interval or settings.scheduler_interval_seconds or 300
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        while not stop.is_set():
            try:
                result = run_once(ctx)
                log.info("drain %s", json.dumps(result))
            except Exception:  # keep the worker alive; the next drain retries
                log.exception("scheduler drain failed")
            if args.once:
                break
            stop.wait(interval)
    finally:
        ctx.engine.dispose()


if __name__ == "__main__":
    main()
