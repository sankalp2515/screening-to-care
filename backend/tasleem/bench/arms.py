"""The three arms. Each sees the same delivered messages and returns, per patient, the staff alerts it
raised (time, reason, named recipient) and what it believes about completion at the horizon.

A  Reminders only (status quo): appointment reminders to the patient. No staff alerts by design.
B  Malaffi referral status only: sees FIT results and REF statuses. Generous rules, checked daily:
   - positive FIT with no referral SENT after 14 days            -> alert the family physician
   - referral CANCELLED                                          -> alert at the next daily check
   - SENT / ACCEPTED / SCHEDULED unchanged for 30 days           -> alert
   - COMPLETED counts as done; no further alerts
C  Tasleem: the real engine through the real ingest path with daily scheduler runs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..api.context import AppContext, Services
from ..config import Settings
from ..domain.model import Actor, ActorType, AdminStatus, CaseState
from ..infra.db import CaseRow, PatientRow
from ..seed import _load_directory
from ..services.fhir import ReferralStatusMessage
from ..services.scheduler import drain
from .cohort import Cohort


@dataclass
class Alert:
    at: datetime
    reason: str
    to_id: str | None


@dataclass
class ArmResult:
    name: str
    alerts: dict[str, list[Alert]] = field(default_factory=lambda: defaultdict(list))
    believed_done: dict[str, bool | None] = field(default_factory=dict)
    barrier_suggestion: dict[str, str | None] = field(default_factory=dict)
    distress_to_clinician: dict[str, datetime | None] = field(default_factory=dict)
    reminders_sent: int = 0
    open_without_owner: int | None = None
    owners: dict[str, str] = field(default_factory=dict)
    ingest_errors: int = 0


def _days(c: Cohort) -> list[datetime]:
    first = c.base.replace(hour=6, minute=0, second=0, microsecond=0)
    out, d = [], first
    while d <= c.horizon:
        out.append(d)
        d += timedelta(days=1)
    return out


# ---- Arm A ----------------------------------------------------------------------------------------
def run_reminders(c: Cohort) -> ArmResult:
    r = ArmResult("A: reminders only")
    for d in c.deliveries:
        if d.kind == "fhir" and d.payload.get("resourceType") == "Appointment" and d.payload["status"] == "booked":
            start = datetime.fromisoformat(d.payload["start"])
            if start - timedelta(days=2) <= c.horizon:
                r.reminders_sent += 1
    for pid in c.truths:
        r.believed_done[pid] = None  # a reminder system has no notion of completion
        r.alerts[pid] = []
    return r


# ---- Arm B ----------------------------------------------------------------------------------------
def run_status_only(c: Cohort, no_referral_days: int = 14, stale_days: int = 30,
                    name: str = "B: Malaffi status only", repeat: bool = False) -> ArmResult:
    """`repeat` re-alerts every threshold period while nothing changes (a stricter monitor). The headline
    benchmark uses the single-alert form; the real-world-fit run tries both."""
    r = ArmResult(name)
    per: dict[str, list] = defaultdict(list)
    seen: set[str] = set()
    for d in c.deliveries:
        if d.key in seen:
            continue
        if d.kind == "ref" or (d.kind == "fhir" and d.payload.get("resourceType") == "Observation"):
            seen.add(d.key)
            per[d.pid].append(d)
    days = _days(c)
    for pid in c.truths:
        owner = next(p["family_physician_id"] for p in c.patients if p["id"] == pid) or "program-coordinator"
        msgs = per.get(pid, [])
        fit_at: datetime | None = None
        status: AdminStatus | None = None
        status_at: datetime | None = None
        alerted: set[tuple] = set()
        i = 0
        for day in days:
            while i < len(msgs) and msgs[i].at <= day:
                m = msgs[i]
                if m.kind == "fhir":
                    fit_at = fit_at or datetime.fromisoformat(m.payload["effectiveDateTime"])
                else:
                    msg: ReferralStatusMessage = m.payload
                    status, status_at = msg.status, m.at
                i += 1
            if fit_at is None or status == AdminStatus.COMPLETED:
                continue
            if status is None and day - fit_at > timedelta(days=no_referral_days):
                key = ("NO_REFERRAL", (day - fit_at).days // no_referral_days if repeat else 0)
                if key not in alerted:
                    alerted.add(key)
                    r.alerts[pid].append(Alert(day, "NO_REFERRAL", owner))
            elif status == AdminStatus.CANCELLED:
                key = ("CANCELLED", status_at)
                if key not in alerted:
                    alerted.add(key)
                    r.alerts[pid].append(Alert(day, "REFERRAL_CANCELLED", owner))
            elif status is not None and status_at is not None and day - status_at > timedelta(days=stale_days):
                key = ("STALE", status, status_at, (day - status_at).days // stale_days if repeat else 0)
                if key not in alerted:
                    alerted.add(key)
                    r.alerts[pid].append(Alert(day, f"STATUS_{status.value}_STALE", owner))
        r.believed_done[pid] = status == AdminStatus.COMPLETED
        r.alerts.setdefault(pid, [])
    return r


# ---- Arm C ----------------------------------------------------------------------------------------
def run_tasleem(c: Cohort) -> ArmResult:
    r = ArmResult("C: Tasleem")
    ctx = AppContext.build(Settings(database_url="sqlite://", demo_mode=True, metrics_max_staleness_seconds=0,
                                         rate_limit_per_second=0))
    days = _days(c)
    with ctx.sessions() as s:
        _load_directory(s)
        s.add_all([PatientRow(**p) for p in c.patients])
        s.commit()
        svc = Services.build(ctx, s)
        di = 0
        for d in c.deliveries:
            while di < len(days) and days[di] <= d.at:
                drain(svc.cases, days[di], batch=1000, budget_seconds=600)
                di += 1
            try:
                if d.kind == "fhir":
                    svc.ingest.ingest_fhir(d.payload, "malaffi-sim", d.at)
                elif d.kind == "ref":
                    svc.ingest.ingest_referral_status(d.payload, "malaffi-sim", d.at)
                else:
                    cases = svc.cases.repo.find_open_for_patient(d.pid)
                    if cases:
                        svc.cases.report_barrier(cases[0].id, Actor(id=d.pid, type=ActorType.PATIENT), [],
                                                 d.payload, d.at)
            except Exception:  # counted, never hidden: a crash on messy input is a finding
                s.rollback()
                r.ingest_errors += 1
        while di < len(days):
            drain(svc.cases, days[di], batch=1000, budget_seconds=600)
            di += 1

        clinicians = {p.id for p in svc.directory.people() if p.role in ("family_physician", "gi_specialist",
                                                                           "clinic_lead")}
        rows = s.query(CaseRow).all()
        r.open_without_owner = sum(1 for row in rows if row.status == "open" and not row.owner_id)
        for row in rows:
            st = CaseState.model_validate(row.state_json)
            pid = st.patient_id
            p = ctx.registry.get(st.pathway_id)
            r.owners[pid] = st.owner_id
            r.believed_done[pid] = all(x in st.stages for x in p.closure.completion_stages)
            for e in svc.cases.repo.events(st.id):
                if e.type == "ESCALATED" and e.payload.get("level") == 1:
                    r.alerts[pid].append(Alert(e.occurred_at, e.payload["reason"], e.payload.get("to_id")))
                    if e.payload["reason"] == "DISTRESS" and e.payload.get("to_id") in clinicians:
                        r.distress_to_clinician.setdefault(pid, e.occurred_at)
                elif e.type == "BARRIER_SUGGESTED":
                    r.barrier_suggestion.setdefault(pid, e.payload["code"])
        for pid in c.truths:
            r.alerts.setdefault(pid, [])
            r.believed_done.setdefault(pid, False)
    ctx.engine.dispose()
    return r
