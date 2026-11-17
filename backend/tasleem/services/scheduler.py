"""Deadline scheduler. Touches only cases whose next_check_at is due (index-backed, SKIP LOCKED on Postgres)."""

from __future__ import annotations

import time
from datetime import datetime

from ..infra.repository import CaseRepository, ConcurrencyError
from .cases import CaseService


def tick(cases: CaseService, now: datetime, limit: int = 500) -> dict[str, int]:
    repo = CaseRepository(cases.s)
    due = repo.due_case_ids(now, limit)
    checked = events = conflicts = 0
    for case_id in due:
        try:
            _, n = cases.evaluate(case_id, now)
            checked += 1
            events += n
        except ConcurrencyError:
            conflicts += 1  # another worker or request updated it; it will be re-evaluated next tick
            cases.s.rollback()
    return {"due": len(due), "checked": checked, "events": events, "conflicts": conflicts}


def drain(cases: CaseService, now: datetime, batch: int = 500, budget_seconds: float = 30.0) -> dict[str, int]:
    """Run ticks until no case is due or the time budget is spent, so a backlog never waits a whole interval.

    Safe with several workers: on Postgres each batch is claimed with SKIP LOCKED, and the optimistic
    version check turns any overlap into a counted conflict, never a double escalation.
    """
    started = time.monotonic()
    total = {"due": 0, "checked": 0, "events": 0, "conflicts": 0, "batches": 0}
    while True:
        r = tick(cases, now, batch)
        total["batches"] += 1
        for k in ("due", "checked", "events", "conflicts"):
            total[k] += r[k]
        if r["due"] < batch or r["checked"] == 0 or time.monotonic() - started > budget_seconds:
            return total
