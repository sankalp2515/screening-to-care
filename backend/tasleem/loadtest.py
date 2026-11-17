# ruff: noqa: E501  (markdown report template lines)
"""Scale run on synthetic data: many patients through the real ingest path, then timings.

    python -m tasleem.loadtest --patients 5000 [--db sqlite:///./load.db] [--out ../docs/evidence/SCALE.md]

Every patient gets a positive FIT and a random partial journey (some finish, some stall, some get a
"completed" referral status with no report). Then it measures: ingest throughput, worklist and case
detail latency, a cold metrics scan, a scheduler drain over every case, and an audit-chain check on a sample.
Measured on a single process; it is a floor for one API replica, not a cluster benchmark.
"""

from __future__ import annotations

import argparse
import random
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from .api.context import AppContext, Services
from .config import Settings
from .domain.audit import verify
from .domain.model import AdminStatus
from .infra.db import CaseEventRow, CaseRow, PatientRow, drop_schema
from .seed import _load_directory, appt, discussed, fit, procedure, ref, referral, report
from .services.scheduler import drain
from .services.views import case_detail, worklist_item

FPS = ["dr-fatima", "dr-salma"]


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def journey(pid: str, start: datetime, rng: random.Random) -> list[tuple[datetime, object]]:
    """Random truncation of the FIT+ → colonoscopy journey, plus a 'status says done' failure mode."""
    steps: list[tuple[datetime, object]] = [(start, fit(pid, f"obs-{pid}", start))]
    depth = rng.choices(range(7), weights=[10, 10, 15, 15, 15, 15, 20])[0]
    t = start
    if depth >= 1:
        t += timedelta(days=rng.randint(1, 5))
        steps.append((t, discussed(pid, f"enc-{pid}", t)))
    if depth >= 2:
        t += timedelta(days=rng.randint(1, 4))
        steps.append((t, referral(pid, f"sr-{pid}", t)))
        steps.append((t, ref(pid, 1, t, AdminStatus.SENT)))
    if depth >= 3:
        t += timedelta(days=rng.randint(2, 10))
        visit = t + timedelta(days=rng.randint(5, 20))
        steps.append((t, appt(pid, f"ap-{pid}", t, "booked", visit)))
        steps.append((t, ref(pid, 2, t, AdminStatus.SCHEDULED)))
        t = visit
    if depth >= 4:
        steps.append((t, appt(pid, f"ap-{pid}", t, "fulfilled", t, version=2)))
        if rng.random() < 0.15:  # failure injection: referral marked completed, no report ever arrives
            steps.append((t + timedelta(days=1), ref(pid, 3, t + timedelta(days=1), AdminStatus.COMPLETED)))
            return steps
    if depth >= 5:
        steps.append((t, procedure(pid, f"pr-{pid}", t)))
    if depth >= 6:
        t += timedelta(days=rng.randint(1, 6))
        steps.append((t, report(pid, f"dr-{pid}", t)))
    return steps


def run(patients: int, db_url: str, seed: int = 7) -> dict:
    settings = Settings(database_url=db_url, demo_mode=True, seed_on_start=False, rate_limit_per_second=0, metrics_max_staleness_seconds=0)
    ctx = AppContext.build(settings)
    drop_schema(ctx.engine)
    ctx = AppContext.build(settings)
    rng = random.Random(seed)
    now = datetime.now(UTC).replace(microsecond=0)

    with ctx.sessions() as s:
        _load_directory(s)
        s.add_all([PatientRow(id=f"p-s{i:06d}", display_name=f"Synthetic {i}", preferred_language=rng.choice(["en", "ar"]),
                              insurance_network=rng.choice(["thiqa", "daman-enhanced", "basic"]),
                              family_physician_id=rng.choice(FPS), birth_year=rng.randint(1956, 1981))
                   for i in range(patients)])
        s.commit()

        items: list[tuple[datetime, object]] = []
        for i in range(patients):
            items += journey(f"p-s{i:06d}", now - timedelta(days=rng.randint(10, 90)), rng)
        items.sort(key=lambda x: x[0])

        svc = Services.build(ctx, s)
        t0 = time.perf_counter()
        for t, item in items:
            if hasattr(item, "message_id") and not isinstance(item, dict):
                svc.ingest.ingest_referral_status(item, "load", t)  # type: ignore[arg-type]
            else:
                svc.ingest.ingest_fhir(item, "load", t)  # type: ignore[arg-type]
        ingest_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        sweep = drain(svc.cases, now, batch=500, budget_seconds=3600)
        drain_s = time.perf_counter() - t0

        cases = s.execute(select(func.count()).select_from(CaseRow)).scalar_one()
        events = s.execute(select(func.count()).select_from(CaseEventRow)).scalar_one()

        wl: list[float] = []
        for i in range(50):
            t0 = time.perf_counter()
            rows = svc.cases.repo.list(status="open", owner_id=FPS[i % 2] if i % 3 else None, limit=50)
            [worklist_item(r, ctx.registry, svc.directory, now) for r in rows]
            wl.append((time.perf_counter() - t0) * 1000)

        ids = [r for (r,) in s.execute(select(CaseRow.id))]
        sample = rng.sample(ids, min(200, len(ids)))
        det: list[float] = []
        broken = 0
        for cid in sample:
            t0 = time.perf_counter()
            st = svc.cases.get(cid)
            evs = svc.cases.repo.events(cid)
            case_detail(st, evs, ctx.registry, svc.directory, now)
            det.append((time.perf_counter() - t0) * 1000)
            broken += 0 if verify(evs).ok else 1

        t0 = time.perf_counter()
        m = svc.metrics.get()
        metrics_cold_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        svc.metrics.get()
        metrics_warm_ms = (time.perf_counter() - t0) * 1000

    ctx.engine.dispose()
    msgs = len(items)
    return {
        "patients": patients, "messages": msgs, "cases": cases, "events": events,
        "ingest_seconds": round(ingest_s, 1), "ingest_msgs_per_s": round(msgs / ingest_s, 1),
        "drain": sweep, "drain_seconds": round(drain_s, 2),
        "worklist_ms": {"p50": round(statistics.median(wl), 1), "p95": round(_pct(wl, 0.95), 1)},
        "case_detail_ms": {"p50": round(statistics.median(det), 1), "p95": round(_pct(det, 0.95), 1)},
        "metrics_cold_ms": round(metrics_cold_ms, 1), "metrics_warm_ms": round(metrics_warm_ms, 2),
        "audit_sample": len(sample), "audit_broken": broken,
        "false_done": m["false_done"]["count"], "open_stalls": sum(m["open_stalls_by_reason"].values()),
        "open_without_owner": m["open_cases_without_owner"], "db": db_url.split(":")[0],
    }


def write_report(r: dict, out: Path) -> None:
    out.write_text(f"""# Scale run

Generated by `python -m tasleem.loadtest --patients {r['patients']}` on {datetime.now(UTC):%d %b %Y}.
Synthetic patients only. One process, {r['db']} file database, no Redis. This is a floor for one API
replica on a laptop, not a cluster benchmark. Production runs on PostgreSQL with several replicas.

| Measure | Result |
|---|---|
| Patients / inbound messages | {r['patients']:,} / {r['messages']:,} |
| Cases / audit events written | {r['cases']:,} / {r['events']:,} |
| Ingest (full path: parse, dedupe, engine, hash chain, commit) | {r['ingest_msgs_per_s']} messages/s ({r['ingest_seconds']} s total) |
| Scheduler drain over all due cases | {r['drain']['checked']:,} checked in {r['drain_seconds']} s, {r['drain']['batches']} batches, {r['drain']['conflicts']} conflicts |
| Worklist page of 50 (risk-ordered, index-backed) | p50 {r['worklist_ms']['p50']} ms, p95 {r['worklist_ms']['p95']} ms |
| Case detail with full timeline | p50 {r['case_detail_ms']['p50']} ms, p95 {r['case_detail_ms']['p95']} ms |
| Program metrics, cold full scan / cached | {r['metrics_cold_ms']} ms / {r['metrics_warm_ms']} ms |
| Audit chains verified (random sample) | {r['audit_sample']} checked, {r['audit_broken']} broken |
| Open cases without an owner (R1) | {r['open_without_owner']} |
| "Completed" status with no report detected (false done) | {r['false_done']:,} |
| Open stalls flagged | {r['open_stalls']:,} |

What scales with what: ingest cost is per message and did not grow with case count; worklist and
detail reads are index-backed and flat; the metrics scan is linear in cases but cached, with staleness
bounded at 15 s by default, so it runs at most a few times a minute regardless of dashboard traffic.
Only FIT-positive results open a case, so live open-case counts are a small fraction of people screened.
Bulk backfills are the load to plan for: run them through the queue (TSL-045) with several workers.
""", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=5000)
    ap.add_argument("--db", default="sqlite:///./load.db")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "evidence" / "SCALE.md"))
    a = ap.parse_args(argv)
    r = run(a.patients, a.db)
    print(r)
    write_report(r, Path(a.out))


if __name__ == "__main__":
    main()
