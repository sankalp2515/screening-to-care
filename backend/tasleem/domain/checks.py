"""Deterministic stall detection. Pure functions of (state, pathway, now)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .model import AdminStatus, CaseState, StallReason
from .pathways import Pathway


@dataclass(frozen=True)
class Condition:
    reason: StallReason
    stage: str | None
    detail: str


def _days(d: float) -> timedelta:
    return timedelta(days=d)


def _at(state: CaseState, stage: str | None) -> datetime | None:
    if stage and stage in state.stages:
        return state.stages[stage].reached_at
    return None


def _any_reached(state: CaseState, *stages: str | None) -> bool:
    return any(s is not None and s in state.stages for s in stages)


def evaluate(state: CaseState, p: Pathway, now: datetime) -> dict[StallReason, Condition]:
    """Return every stall condition that is currently true. Empty for closed cases."""
    if not state.is_open:
        return {}
    c = p.checks
    out: dict[StallReason, Condition] = {}

    def add(reason: StallReason, stage: str | None, detail: str) -> None:
        out[reason] = Condition(reason, stage, detail)

    # 1. Next expected step overdue (only for stages with a plain deadline).
    nxt = p.next_stage(set(state.stages))
    if nxt is not None and nxt.sla_days is not None:
        due = state.last_progress_at + _days(nxt.sla_days)
        if now > due:
            add(StallReason.STEP_OVERDUE, nxt.id, f"'{nxt.label}' expected by {due.date().isoformat()}")

    # 2. Booked but not attended (missed, cancelled, or appointment time passed with no attendance evidence).
    if c.booked_stage and state.reached(c.booked_stage) and not _any_reached(
        state, c.attended_stage, c.procedure_stage, c.report_stage
    ):
        if state.appointment_missed:
            add(
                StallReason.BOOKED_NOT_ATTENDED,
                c.attended_stage,
                "missed the appointment" if state.appointment_missed == "noshow" else "the appointment was cancelled",
            )
        elif state.appointment_at and now > state.appointment_at + timedelta(hours=c.attended_grace_hours):
            add(StallReason.BOOKED_NOT_ATTENDED, c.attended_stage,
                f"appointment on {state.appointment_at.date().isoformat()} has no attendance record")

    # 3. Attended but no procedure.
    attended_at = _at(state, c.attended_stage)
    if attended_at and not _any_reached(state, c.procedure_stage, c.report_stage):
        if now > attended_at + _days(c.consult_no_procedure_days):
            add(StallReason.CONSULT_NO_PROCEDURE, c.procedure_stage,
                f"attended {attended_at.date().isoformat()}, no procedure recorded")

    # 4. The false-done detector: referral system says completed, but there is no clinical evidence.
    if (
        c.evidence_stage
        and state.admin_status == AdminStatus.COMPLETED
        and not state.reached(c.evidence_stage)
        and state.admin_status_at is not None
        and now >= state.admin_status_at + _days(c.admin_completed_grace_days)
    ):
        add(StallReason.CLOSED_WITHOUT_EVIDENCE, c.evidence_stage,
            "referral marked completed, but no report has been received")

    # 5. Report received but outcome not communicated.
    report_at = _at(state, c.report_stage)
    if report_at and c.communicated_stage and not state.reached(c.communicated_stage):
        if now > report_at + _days(c.report_not_communicated_days):
            add(StallReason.REPORT_NOT_COMMUNICATED, c.communicated_stage,
                f"report received {report_at.date().isoformat()}, not yet communicated")

    # 6. Handoff not accepted.
    h = state.pending_handoff
    if h and now > h.offered_at + _days(c.handoff_accept_days):
        add(StallReason.HANDOFF_NOT_ACCEPTED, None, f"handoff to {h.to_id} not accepted")

    # 7. Referral rejected and no new referral or acceptance since.
    rej = state.referral_rejected_at
    if rej is not None:
        newer = [ev.reached_at for ev in state.stages.values() if ev.signal in
                 ("REFERRAL_SENT", "REFERRAL_ACCEPTED") and ev.reached_at > rej]
        if not newer:
            add(StallReason.REFERRAL_REJECTED, None,
                f"referral rejected: {state.referral_rejected_reason or 'no reason given'}")

    # 8. E-consult unanswered.
    late = [k for k in state.consults.values() if k.answer is None and now > k.due_at]
    if late:
        add(StallReason.CONSULT_UNANSWERED, None, f"{len(late)} e-consult question(s) unanswered")

    # 9. Evidence Reader: a free-text report nobody has confirmed, or one that says the loop is not closed.
    if c.report_review:
        unread = state.unreviewed_reports
        late = [r for r in unread if now > r.received_at + _days(c.report_review_days)]
        if late:
            add(StallReason.REPORT_NOT_REVIEWED, c.report_stage,
                f"report received {late[0].received_at.date().isoformat()}, not yet confirmed by a clinician")
        f = state.confirmed_findings
        if not unread and (f.get("completed") is False or f.get("prep_adequate") is False):
            why = "incomplete" if f.get("completed") is False else "had inadequate bowel preparation"
            add(StallReason.PROCEDURE_INCOMPLETE, c.procedure_stage, f"colonoscopy {why}: rebook the procedure")
        if f.get("pathology_pending") is True:
            reviewed = [r.reviewed_at for r in state.reports.values() if r.reviewed_at is not None]
            since = max(reviewed) if reviewed else state.last_progress_at
            if now > since + _days(c.pathology_result_days):
                add(StallReason.PATHOLOGY_OUTSTANDING, c.report_stage,
                    f"pathology awaited since {since.date().isoformat()}")

    return out


def next_check_at(state: CaseState, p: Pathway, now: datetime) -> datetime | None:
    """Earliest future moment at which `evaluate` could change or a stall is due to re-escalate.

    Stored on the case row so the scheduler only touches cases that are due.
    """
    if not state.is_open:
        return None
    c = p.checks
    times: list[datetime] = []
    nxt = p.next_stage(set(state.stages))
    if nxt is not None and nxt.sla_days is not None:
        times.append(state.last_progress_at + _days(nxt.sla_days))
    if state.appointment_at:
        times.append(state.appointment_at + timedelta(hours=c.attended_grace_hours))
    attended_at = _at(state, c.attended_stage)
    if attended_at:
        times.append(attended_at + _days(c.consult_no_procedure_days))
    if state.admin_status_at:
        times.append(state.admin_status_at + _days(c.admin_completed_grace_days))
    report_at = _at(state, c.report_stage)
    if report_at:
        times.append(report_at + _days(c.report_not_communicated_days))
    if state.pending_handoff:
        times.append(state.pending_handoff.offered_at + _days(c.handoff_accept_days))
    times.extend(k.due_at for k in state.consults.values() if k.answer is None)
    if c.report_review:
        times.extend(r.received_at + _days(c.report_review_days) for r in state.unreviewed_reports)
        times.extend(r.reviewed_at + _days(c.pathology_result_days) for r in state.reports.values()
                     if r.reviewed_at is not None)
    for s in state.stalls.values():
        times.append(s.last_escalated_at + _days(c.reescalate_after_days))
    # +1 second so a check at exactly the deadline is evaluated strictly after it.
    future = [t + timedelta(seconds=1) for t in times if t + timedelta(seconds=1) > now]
    return min(future) if future else None
