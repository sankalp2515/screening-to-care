"""Score arm results against ground truth. Pure functions; no arm sees the truth."""

from __future__ import annotations

import statistics
from datetime import timedelta
from typing import Any

from .arms import Alert, ArmResult
from .cohort import CLEAN, SCENARIOS, Cohort

TOL = timedelta(seconds=1)


def _qualifying(alerts: list[Alert], truth, scenario: str) -> list[Alert]:
    if truth.stopped_at is None:
        return []
    out = [a for a in alerts if a.at >= truth.stopped_at - TOL]
    if scenario == "DISTRESS":  # must reach someone within a day to count
        out = [a for a in out if a.at - truth.stopped_at <= timedelta(hours=24)]
    return out


def per_case(c: Cohort, r: ArmResult) -> list[dict[str, Any]]:
    rows = []
    for pid, t in c.truths.items():
        alerts = sorted(r.alerts.get(pid, []), key=lambda a: a.at)
        q = _qualifying(alerts, t, t.scenario)
        first = q[0] if q else None
        rows.append({
            "patient": pid, "scenario": t.scenario, "arm": r.name,
            "stopped_at": t.stopped_at.isoformat() if t.stopped_at else "",
            "detected": bool(first) if t.scenario not in CLEAN else "",
            "latency_days": round((first.at - t.stopped_at).total_seconds() / 86400, 2) if first else "",
            "first_reason": first.reason if first else "",
            "right_reason": (any(a.reason in t.expected_reasons for a in q) if q else False)
            if t.scenario not in CLEAN else "",
            "alerted_to": first.to_id if first else "",
            "alerts_total": len(alerts),
            "false_alert": (len(alerts) > 0) if t.scenario in CLEAN else "",
            "believed_done": r.believed_done.get(pid),
            "truly_complete": t.truly_complete,
        })
    return rows


def _pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def _q(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))], 1)


def summarize(c: Cohort, r: ArmResult, rows: list[dict[str, Any]]) -> dict[str, Any]:
    fail = [x for x in rows if x["scenario"] not in CLEAN]
    clean = [x for x in rows if x["scenario"] in CLEAN]
    by: dict[str, Any] = {}
    for sc in SCENARIOS:
        if sc in CLEAN:
            continue
        xs = [x for x in fail if x["scenario"] == sc]
        lat = [x["latency_days"] for x in xs if x["detected"]]
        by[sc] = {"n": len(xs), "detected_pct": _pct(sum(1 for x in xs if x["detected"]), len(xs)),
                  "median_days": _q(lat, 0.5), "p90_days": _q(lat, 0.9),
                  "right_reason_pct": _pct(sum(1 for x in xs if x["right_reason"]), len(xs))}
    lat_all = [x["latency_days"] for x in fail if x["detected"]]
    believed = [x for x in rows if x["believed_done"] is not None]
    out: dict[str, Any] = {
        "arm": r.name,
        "failures": len(fail),
        "detected_pct": _pct(sum(1 for x in fail if x["detected"]), len(fail)),
        "median_days": _q(lat_all, 0.5), "p90_days": _q(lat_all, 0.9),
        "right_reason_pct": _pct(sum(1 for x in fail if x["right_reason"]), len(fail)),
        "clean": len(clean),
        "false_alert_pct": _pct(sum(1 for x in clean if x["false_alert"]), len(clean)),
        "alerts_per_100": round(100 * sum(x["alerts_total"] for x in rows) / len(rows), 1),
        "counted_done": sum(1 for x in believed if x["believed_done"]) if believed else None,
        "false_done": sum(1 for x in believed if x["believed_done"] and not x["truly_complete"]) if believed else None,
        "truly_complete": sum(1 for x in rows if x["truly_complete"]),
        "by_scenario": by,
        "reminders_sent": r.reminders_sent,
        "ingest_errors": r.ingest_errors,
        "open_without_owner": r.open_without_owner,
    }
    labelled = [t for t in c.truths.values() if t.barrier_label]
    if r.barrier_suggestion or r.name.startswith("C"):
        correct = sum(1 for t in labelled if r.barrier_suggestion.get(t.pid) == t.barrier_label)
        abstain = sum(1 for t in labelled if r.barrier_suggestion.get(t.pid) is None)
        out["barrier"] = {"n": len(labelled), "correct": correct, "abstained": abstain,
                          "wrong": len(labelled) - correct - abstain}
    no_fp = [t.pid for t in c.truths.values() if not t.has_fp]
    if r.owners:
        out["no_fp_owned"] = sum(1 for pid in no_fp if r.owners.get(pid))
        out["no_fp_total"] = len(no_fp)
    return out


def median_or_none(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 1) if xs else None
