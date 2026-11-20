"""Case engine: commands produce events; `apply` folds events into state; `execute` adds rule-driven stalls.

Safety rules enforced here (see AGENTS.md):
  R1 one named owner      R2 two-step handoff      R3 evidence-based closure
  R4 missed deadlines escalate to a named human    R5 no AI/system decisions
R6 (hash-chained audit) is applied by the repository when events are appended.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta

from . import checks
from .barriers import BarrierClassifier, detect_distress
from .errors import DomainError
from .messaging import check_patient_text
from .model import (
    NON_HUMAN_TYPES,
    STAFF_TYPES,
    Actor,
    ActorType,
    AdminStatus,
    Barrier,
    BarrierCode,
    CaseState,
    Consult,
    DeliveryAlert,
    DistressFlag,
    Event,
    EventType,
    Handoff,
    Outcome,
    ReportReview,
    Signal,
    SignalKind,
    StageEvidence,
    Stall,
    StallReason,
)
from .pathways import Pathway

# Resolves an escalation target ("owner", "clinic_lead", "program_coordinator", "clinician") to a person id.
Resolver = Callable[[CaseState, str], str]

SYSTEM_ID = "system"
DISTRESS = "DISTRESS"


def _ev(t: EventType, actor: Actor, at: datetime, **payload: object) -> Event:
    return Event(type=t, actor_id=actor.id, actor_type=actor.type, occurred_at=at, payload=payload)


def _sys(t: EventType, at: datetime, **payload: object) -> Event:
    return Event(type=t, actor_id=SYSTEM_ID, actor_type=ActorType.SYSTEM, occurred_at=at, payload=payload)


# --------------------------------------------------------------------------------------------------
# Guards
# --------------------------------------------------------------------------------------------------
def _require_open(state: CaseState) -> None:
    if not state.is_open:
        raise DomainError("CASE_CLOSED", "The case is closed.", case_id=state.id)


def _require_staff(actor: Actor, action: str) -> None:
    if actor.type in NON_HUMAN_TYPES:
        raise DomainError("R5_HUMAN_REQUIRED", f"Only a human staff member can {action}.", actor_type=actor.type)
    if actor.type not in STAFF_TYPES:
        raise DomainError("FORBIDDEN_ROLE", f"Only care-team staff can {action}.", actor_type=actor.type)


def _require_clinician(actor: Actor, action: str) -> None:
    _require_staff(actor, action)
    if actor.type != ActorType.CLINICIAN:
        raise DomainError("R3_SIGNATURE_REQUIRED", f"A clinician must sign to {action}.", actor_type=actor.type)


# --------------------------------------------------------------------------------------------------
# Commands → events
# --------------------------------------------------------------------------------------------------
def open_case(
    *, case_id: str, patient_id: str, pathway: Pathway, trigger: Signal, owner_id: str,
    actor: Actor, warnings: Iterable[str] = (),
) -> list[Event]:
    if not owner_id:
        raise DomainError("R1_OWNER_REQUIRED", "A case cannot open without a named owner.")
    at = trigger.occurred_at
    events = [_ev(EventType.CASE_OPENED, actor, at, case_id=case_id, patient_id=patient_id,
                  pathway_id=pathway.id, pathway_version=pathway.version, owner_id=owner_id,
                  priority=pathway.priority, trigger_ref=trigger.ref)]
    events += [_ev(EventType.WARNING_ADDED, actor, at, text=w) for w in warnings]
    return events


def record_signal(state: CaseState, pathway: Pathway, s: Signal, actor: Actor) -> list[Event]:
    """Translate an ingested signal into case events. Admin status never reaches a stage (G2)."""
    _require_open(state)
    at = s.occurred_at
    if s.kind == SignalKind.ADMIN_STATUS:
        if s.admin_status is None or s.admin_status == state.admin_status:
            return []
        return [_ev(EventType.ADMIN_STATUS_CHANGED, actor, at, status=s.admin_status.value, ref=s.ref)]
    if s.kind in (SignalKind.APPOINTMENT_NOSHOW, SignalKind.APPOINTMENT_CANCELLED):
        kind = "noshow" if s.kind == SignalKind.APPOINTMENT_NOSHOW else "cancelled"
        return [_ev(EventType.APPOINTMENT_MISSED, actor, at, kind=kind, ref=s.ref)]
    if s.kind == SignalKind.REFERRAL_REJECTED:
        return [_ev(EventType.REFERRAL_REJECTED, actor, at, reason=s.reason or "unspecified", ref=s.ref)]
    events = []
    for st in pathway.stages_for(s):
        payload: dict[str, object] = {"stage": st.id, "ref": s.ref, "signal": s.kind.value}
        if s.appointment_at is not None:
            payload["appointment_at"] = s.appointment_at.isoformat()
        events.append(_ev(EventType.STAGE_REACHED, actor, at, **payload))
    if s.kind == SignalKind.REPORT_FINAL and (s.text or "").strip() and pathway.checks.report_review:
        if not any(r.ref == s.ref for r in state.reports.values()):
            events.append(_ev(EventType.REPORT_TEXT_RECEIVED, actor, at, report_id=f"rpt-{len(state.reports) + 1}",
                              ref=s.ref, text=s.text.strip()))
    return events


REPORT_FIELDS = ("completed", "prep_adequate", "polyps_removed", "pathology_pending", "next_step", "follow_up")


def review_report(state: CaseState, actor: Actor, report_id: str, findings: dict[str, object], now: datetime, *,
                  suggested_by: str | None = None, suggestion: dict[str, object] | None = None) -> list[Event]:
    """Evidence Reader, the human step (R3 + R5): a clinician confirms or corrects what the report says.

    Only confirmed findings reach the rules. The reader that suggested the values, and every field the clinician
    changed, are recorded so the AI's accuracy can be monitored from the audit log."""
    _require_open(state)
    _require_clinician(actor, "confirm what a report says")
    r = state.reports.get(report_id)
    if r is None:
        raise DomainError("NOT_FOUND", "No such report on this case.", report_id=report_id)
    if r.reviewed:
        raise DomainError("REPORT_ALREADY_REVIEWED", "This report has already been confirmed.", report_id=report_id)
    unknown = sorted(set(findings) - set(REPORT_FIELDS))
    if unknown:
        raise DomainError("VALIDATION", "Unknown report fields.", fields=unknown)
    clean = {k: findings.get(k) for k in REPORT_FIELDS}
    for k in ("completed", "prep_adequate", "pathology_pending"):
        if clean[k] is not None and not isinstance(clean[k], bool):
            raise DomainError("VALIDATION", f"{k} must be yes, no or not stated.", field=k)
    n = clean["polyps_removed"]
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 0):
        raise DomainError("VALIDATION", "polyps_removed must be a whole number.", field="polyps_removed")
    for k in ("next_step", "follow_up"):
        if clean[k] is not None:
            clean[k] = str(clean[k]).strip()[:300] or None
    corrected = sorted(k for k in REPORT_FIELDS if suggestion is not None and suggestion.get(k) != clean[k])
    return [_ev(EventType.REPORT_REVIEWED, actor, now, report_id=report_id, findings=clean,
                suggested_by=suggested_by, corrected=corrected)]


def add_warning(state: CaseState, actor: Actor, at: datetime, text: str) -> list[Event]:
    """A rule-based warning on an open case (for example a repeat FIT). It informs; it never closes or decides."""
    _require_open(state)
    if text in state.warnings:
        return []
    return [_ev(EventType.WARNING_ADDED, actor, at, text=text)]


def trigger_repeated(state: CaseState, s: Signal, actor: Actor) -> list[Event]:
    _require_open(state)
    return [_ev(EventType.TRIGGER_REPEATED, actor, s.occurred_at, ref=s.ref)]


def offer_handoff(state: CaseState, actor: Actor, to_id: str, reason: str, now: datetime) -> list[Event]:
    _require_open(state)
    _require_staff(actor, "hand off a case")
    # The person a stall is escalated to (R4) must be able to reassign it, or escalation only adds a watcher:
    # found by the AI-user run, where the clinic lead could see a stuck case but was refused the handoff.
    # R2 is unchanged: the owner stays owner until the receiver accepts.
    escalated_to_actor = any(s.escalated_to == actor.id for s in state.stalls.values())
    if actor.id != state.owner_id and actor.type != ActorType.COORDINATOR and not escalated_to_actor:
        raise DomainError("R2_NOT_OWNER", "Only the current owner, a coordinator, or the person the case is "
                                          "escalated to can offer a handoff.")
    if state.pending_handoff is not None:
        raise DomainError("R2_HANDOFF_PENDING", "A handoff is already waiting for acceptance.",
                          to_id=state.pending_handoff.to_id)
    if to_id == state.owner_id:
        raise DomainError("R2_HANDOFF_SELF", "The case is already owned by this person.")
    if not reason.strip():
        raise DomainError("VALIDATION", "A handoff needs a reason.")
    return [_ev(EventType.HANDOFF_OFFERED, actor, now, to_id=to_id, reason=reason)]


def accept_handoff(state: CaseState, actor: Actor, now: datetime) -> list[Event]:
    _require_open(state)
    _require_staff(actor, "accept a handoff")
    h = state.pending_handoff
    if h is None or h.to_id != actor.id:
        raise DomainError("R2_NOT_HANDOFF_TARGET", "Only the person the case was offered to can accept it.")
    return [_ev(EventType.HANDOFF_ACCEPTED, actor, now, from_id=state.owner_id, to_id=actor.id)]


def reject_handoff(state: CaseState, actor: Actor, reason_code: str, now: datetime) -> list[Event]:
    _require_open(state)
    _require_staff(actor, "reject a handoff")
    h = state.pending_handoff
    if h is None or h.to_id != actor.id:
        raise DomainError("R2_NOT_HANDOFF_TARGET", "Only the person the case was offered to can reject it.")
    if not reason_code.strip():
        raise DomainError("VALIDATION", "A rejection needs a reason code.")
    return [_ev(EventType.HANDOFF_REJECTED, actor, now, to_id=actor.id, reason_code=reason_code)]


def report_barrier(
    state: CaseState, actor: Actor, *, barrier_id: str, distress_id: str, codes: Sequence[BarrierCode],
    text: str | None, now: datetime, classifier: BarrierClassifier, resolver: Resolver,
) -> list[Event]:
    _require_open(state)
    if actor.type in NON_HUMAN_TYPES:
        raise DomainError("R5_HUMAN_REQUIRED", "Barriers are reported by the patient or the care team.")
    text = (text or "").strip() or None
    if not codes and not text:
        raise DomainError("VALIDATION", "Report at least one barrier code or a message.")
    events = [_ev(EventType.BARRIER_REPORTED, actor, now, barrier_id=barrier_id,
                  codes=[c.value for c in codes], text=text)]
    if text:
        sug = classifier.classify(text)
        if sug is not None:
            events.append(Event(type=EventType.BARRIER_SUGGESTED, actor_id=sug.model, actor_type=ActorType.AI,
                                occurred_at=now, payload={"barrier_id": barrier_id, "code": sug.code.value,
                                                          "confidence": sug.confidence}))
        matched = detect_distress(text)
        if matched:
            to = resolver(state, "clinician")
            events.append(_sys(EventType.DISTRESS_FLAGGED, now, distress_id=distress_id,
                               barrier_id=barrier_id, matched=matched, routed_to=to))
            events.append(_sys(EventType.ESCALATED, now, reason=DISTRESS, level=1, to_id=to))
    return events


def confirm_barrier(
    state: CaseState, pathway: Pathway, actor: Actor, barrier_id: str, code: BarrierCode, now: datetime,
) -> list[Event]:
    _require_open(state)
    _require_staff(actor, "confirm a barrier")
    b = state.barriers.get(barrier_id)
    if b is None:
        raise DomainError("NOT_FOUND", "Unknown barrier.", barrier_id=barrier_id)
    if b.status != "reported":
        raise DomainError("BARRIER_STATE", f"Barrier is already {b.status}.")
    if any(d.barrier_id == barrier_id for d in state.open_distress):
        raise DomainError("DISTRESS_FIRST", "This message reports a symptom. A clinician must address it before "
                          "anything else; it is not a barrier.", barrier_id=barrier_id)
    pb = pathway.playbooks.get(code) or pathway.playbooks[BarrierCode.OTHER]
    return [_ev(EventType.BARRIER_CONFIRMED, actor, now, barrier_id=barrier_id, code=code.value,
                assignee_role=pb.assignee_role, action=pb.action,
                due_at=(now + timedelta(days=pb.due_days)).isoformat())]


def resolve_barrier(state: CaseState, actor: Actor, barrier_id: str, note: str, now: datetime) -> list[Event]:
    _require_open(state)
    _require_staff(actor, "resolve a barrier")
    b = state.barriers.get(barrier_id)
    if b is None:
        raise DomainError("NOT_FOUND", "Unknown barrier.", barrier_id=barrier_id)
    if b.status == "resolved":
        raise DomainError("BARRIER_STATE", "Barrier is already resolved.")
    return [_ev(EventType.BARRIER_RESOLVED, actor, now, barrier_id=barrier_id, note=note)]


def resolve_distress(state: CaseState, actor: Actor, distress_id: str, note: str, now: datetime) -> list[Event]:
    _require_open(state)
    _require_clinician(actor, "clear a distress flag")
    d = state.distress.get(distress_id)
    if d is None or d.resolved:
        raise DomainError("NOT_FOUND", "No open distress flag with this id.", distress_id=distress_id)
    if not note.strip():
        raise DomainError("VALIDATION", "Record what was done.")
    return [_ev(EventType.DISTRESS_RESOLVED, actor, now, distress_id=distress_id, note=note)]


def log_contact(state: CaseState, actor: Actor, channel: str, result: str, now: datetime) -> list[Event]:
    _require_open(state)
    _require_staff(actor, "log a contact attempt")
    return [_ev(EventType.CONTACT_ATTEMPTED, actor, now, channel=channel, result=result)]


def request_consult(
    state: CaseState, pathway: Pathway, actor: Actor, consult_id: str, to_id: str, question: str, now: datetime,
) -> list[Event]:
    _require_open(state)
    _require_staff(actor, "request an e-consult")
    if not question.strip():
        raise DomainError("VALIDATION", "The consult question is empty.")
    due = now + timedelta(days=pathway.checks.consult_answer_days)
    return [_ev(EventType.CONSULT_REQUESTED, actor, now, consult_id=consult_id, to_id=to_id,
                question=question, due_at=due.isoformat())]


def answer_consult(state: CaseState, actor: Actor, consult_id: str, answer: str, now: datetime, *,
                   covers: Iterable[str] = ()) -> list[Event]:
    """The consulted specialist answers, or the person named as their cover while they are away (TSL-160)."""
    _require_open(state)
    _require_staff(actor, "answer an e-consult")
    k = state.consults.get(consult_id)
    if k is None:
        raise DomainError("NOT_FOUND", "Unknown consult.", consult_id=consult_id)
    on_behalf_of = None
    if k.to_id != actor.id:
        if k.to_id not in set(covers):
            raise DomainError("NOT_CONSULT_TARGET", "Only the consulted specialist, or their named cover, can answer.")
        on_behalf_of = k.to_id
    if k.answer is not None:
        raise DomainError("CONSULT_STATE", "Already answered.")
    if not answer.strip():
        raise DomainError("VALIDATION", "The answer is empty.")
    extra = {"on_behalf_of": on_behalf_of} if on_behalf_of else {}
    return [_ev(EventType.CONSULT_ANSWERED, actor, now, consult_id=consult_id, answer=answer, **extra)]


def record_consent(state: CaseState, actor: Actor, now: datetime) -> list[Event]:
    _require_open(state)
    if actor.type in NON_HUMAN_TYPES:
        raise DomainError("R5_HUMAN_REQUIRED", "Consent is given by a person.")
    return [_ev(EventType.CONSENT_RECORDED, actor, now)]


def send_patient_message(state: CaseState, actor: Actor, text: str, language: str, now: datetime, *,
                         ai_draft_id: str | None = None) -> list[Event]:
    """A care-team member sends a plain-language message to the patient (e.g. an approved AI draft).

    R5: the sender is always a human. An AI draft only becomes a message when a person sends it, and the
    event records both the person and the draft it came from.
    """
    _require_open(state)
    _require_staff(actor, "send a message to the patient")
    problems = check_patient_text(text)
    if problems:
        raise DomainError("IFHAS_MESSAGE_POLICY", problems[0].detail,
                          violations=[{"code": v.code, "detail": v.detail} for v in problems])
    if language not in ("en", "ar"):
        raise DomainError("VALIDATION", "Language must be 'en' or 'ar'.")
    return [_ev(EventType.PATIENT_MESSAGE_SENT, actor, now, text=text.strip(), language=language,
                ai_draft_id=ai_draft_id, ai_assisted=ai_draft_id is not None)]


def record_delivery_failure(state: CaseState, actor: Actor, outbox_id: int, channels: Sequence[str],
                            now: datetime) -> list[Event]:
    """A delivery service reports that a patient message reached no channel. A fact, not a decision:
    it creates a call task for a navigator. Idempotent per outbox message."""
    if actor.type != ActorType.INTEGRATION:
        raise DomainError("FORBIDDEN_ROLE", "Only a delivery integration reports delivery failures.")
    if not state.is_open:
        return []
    alert_id = f"out-{outbox_id}"
    if alert_id in state.delivery_alerts:
        return []
    return [_ev(EventType.DELIVERY_FAILED, actor, now, alert_id=alert_id, outbox_id=outbox_id,
                channels=list(channels))]


def close_case(
    state: CaseState, pathway: Pathway, actor: Actor, outcome: Outcome, *, evidence_ref: str | None,
    reason: str | None, now: datetime,
) -> list[Event]:
    """R3 + R5: close only with the evidence or signature the outcome requires, and only by a human."""
    _require_open(state)
    _require_staff(actor, "close a case")
    if state.open_distress:
        raise DomainError("R3_DISTRESS_OPEN", "A clinician must address the open distress flag first.",
                          distress_ids=[d.id for d in state.open_distress])
    if state.pending_handoff is not None:
        raise DomainError("R2_HANDOFF_PENDING", "Resolve the pending handoff before closing.")
    evidence_ref = (evidence_ref or "").strip() or None
    reason = (reason or "").strip() or None

    if outcome == Outcome.COMPLETED_WITH_REPORT:
        _require_report_closes_loop(state)
        missing = [s for s in pathway.closure.completion_stages if not state.reached(s)]
        if missing:
            raise DomainError("R3_EVIDENCE_REQUIRED", "Required clinical evidence has not been received.",
                              missing_stages=missing)
        if actor.type not in (ActorType.CLINICIAN, ActorType.COORDINATOR):
            raise DomainError("R3_SIGNATURE_REQUIRED", "A clinician or coordinator must sign this closure.")
    else:
        _require_clinician(actor, f"close as {outcome.value}")
        if outcome in (Outcome.COMPLETED_ELSEWHERE, Outcome.INFORMED_REFUSAL) and not evidence_ref:
            raise DomainError("R3_EVIDENCE_REQUIRED", f"{outcome.value} needs a document reference.")
        if outcome in (Outcome.PLAN_CHANGED, Outcome.INFORMED_REFUSAL) and not reason:
            raise DomainError("R3_REASON_REQUIRED", f"{outcome.value} needs a written clinical reason.")
        if outcome == Outcome.UNREACHABLE:
            need = pathway.closure.min_contact_attempts_for_unreachable
            if state.contact_attempts < need or state.escalation_count < 1:
                raise DomainError("R3_CONTACT_ATTEMPTS",
                                  f"UNREACHABLE needs at least {need} contact attempts and one escalation.",
                                  contact_attempts=state.contact_attempts,
                                  escalations=state.escalation_count)
    return [_ev(EventType.CASE_CLOSED, actor, now, outcome=outcome.value, evidence_ref=evidence_ref,
                reason=reason, signed_by=actor.id)]


def _require_report_closes_loop(state: CaseState) -> None:
    """R3, Evidence Reader: a report closes the loop only once a clinician has confirmed it says so."""
    if state.unreviewed_reports:
        raise DomainError("R3_REPORT_NOT_REVIEWED", "A clinician must confirm what the report says first.",
                          report_ids=[r.id for r in state.unreviewed_reports])
    f = state.confirmed_findings
    if f.get("completed") is False or f.get("prep_adequate") is False:
        raise DomainError("R3_PROCEDURE_INCOMPLETE",
                          "The report says the colonoscopy was incomplete or the preparation inadequate; "
                          "repeat it, or close with a signed change of plan.")
    if f.get("pathology_pending") is True:
        raise DomainError("R3_PATHOLOGY_PENDING", "The pathology result has not arrived yet.")


# --------------------------------------------------------------------------------------------------
# Fold
# --------------------------------------------------------------------------------------------------
def _dt(v: object) -> datetime:
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v))


def apply(state: CaseState | None, e: Event) -> CaseState:
    p = e.payload
    t = e.type
    at = e.occurred_at
    if t == EventType.CASE_OPENED:
        if state is not None:
            raise ValueError("case already opened")
        return CaseState(
            id=p["case_id"], patient_id=p["patient_id"], pathway_id=p["pathway_id"],
            pathway_version=p["pathway_version"], owner_id=p["owner_id"], priority=p["priority"],
            trigger_ref=p["trigger_ref"], opened_at=at, updated_at=at, last_progress_at=at, version=1,
        )
    if state is None:
        raise ValueError(f"{t} before CASE_OPENED")
    s = state.model_copy(deep=True)
    s.version += 1
    s.updated_at = max(s.updated_at, at)

    if t == EventType.WARNING_ADDED:
        s.warnings.append(p["text"])
    elif t == EventType.TRIGGER_REPEATED:
        pass
    elif t == EventType.STAGE_REACHED:
        stage = p["stage"]
        if stage not in s.stages:
            s.stages[stage] = StageEvidence(reached_at=at, ref=p["ref"], signal=p["signal"], by=e.actor_id)
        elif p["signal"] in ("REFERRAL_SENT", "REFERRAL_ACCEPTED"):
            # a fresh referral after a rejection: keep the latest evidence time
            s.stages[stage] = StageEvidence(reached_at=at, ref=p["ref"], signal=p["signal"], by=e.actor_id)
        s.last_progress_at = max(s.last_progress_at, at)
        if "appointment_at" in p:
            s.appointment_at = _dt(p["appointment_at"])
            s.appointment_missed = None
        if p["signal"] == "APPOINTMENT_ATTENDED":
            s.appointment_missed = None
    elif t == EventType.APPOINTMENT_MISSED:
        s.appointment_missed = p["kind"]
    elif t == EventType.ADMIN_STATUS_CHANGED:
        s.admin_status = AdminStatus(p["status"])
        s.admin_status_at = at
    elif t == EventType.REFERRAL_REJECTED:
        s.referral_rejected_at = at
        s.referral_rejected_reason = p["reason"]
    elif t == EventType.HANDOFF_OFFERED:
        s.pending_handoff = Handoff(to_id=p["to_id"], reason=p["reason"], offered_by=e.actor_id, offered_at=at)
    elif t == EventType.HANDOFF_ACCEPTED:
        s.owner_id = p["to_id"]
        s.pending_handoff = None
    elif t == EventType.HANDOFF_REJECTED:
        s.pending_handoff = None
    elif t == EventType.STALL_FLAGGED:
        s.stalls[p["reason"]] = Stall(reason=StallReason(p["reason"]), stage=p.get("stage"),
                                      detail=p.get("detail", ""), flagged_at=at, level=1,
                                      last_escalated_at=at, escalated_to=p["escalated_to"])
    elif t == EventType.STALL_CLEARED:
        s.stalls.pop(p["reason"], None)
    elif t == EventType.ESCALATED:
        s.escalation_count += 1
        st = s.stalls.get(p["reason"])
        if st is not None:
            st.level = p["level"]
            st.last_escalated_at = at
            st.escalated_to = p["to_id"]
    elif t == EventType.BARRIER_REPORTED:
        s.barriers[p["barrier_id"]] = Barrier(id=p["barrier_id"], reported_codes=[BarrierCode(c) for c in p["codes"]],
                                              text=p.get("text"), reported_by=e.actor_id, reported_at=at)
    elif t == EventType.BARRIER_SUGGESTED:
        b = s.barriers[p["barrier_id"]]
        b.suggested_code = BarrierCode(p["code"])
        b.suggested_confidence = p["confidence"]
        b.suggested_model = e.actor_id
    elif t == EventType.BARRIER_CONFIRMED:
        b = s.barriers[p["barrier_id"]]
        b.confirmed_code = BarrierCode(p["code"])
        b.confirmed_by = e.actor_id
        b.assignee_role = p["assignee_role"]
        b.action = p["action"]
        b.due_at = _dt(p["due_at"])
        b.status = "confirmed"
    elif t == EventType.BARRIER_RESOLVED:
        b = s.barriers[p["barrier_id"]]
        b.status = "resolved"
        b.resolution_note = p.get("note")
    elif t == EventType.DISTRESS_FLAGGED:
        s.distress[p["distress_id"]] = DistressFlag(id=p["distress_id"], barrier_id=p.get("barrier_id"),
                                                    matched=p["matched"], flagged_at=at, routed_to=p["routed_to"])
    elif t == EventType.DISTRESS_RESOLVED:
        d = s.distress[p["distress_id"]]
        d.resolved = True
        d.resolved_by = e.actor_id
        d.note = p.get("note")
    elif t == EventType.CONTACT_ATTEMPTED:
        s.contact_attempts += 1
        # A person has now tried to reach the patient directly; the "not reached by message" task is done.
        for a in s.delivery_alerts.values():
            if not a.resolved:
                a.resolved = True
                a.resolved_by = e.actor_id
    elif t == EventType.PATIENT_MESSAGE_SENT:
        s.messages_sent += 1
    elif t == EventType.DELIVERY_FAILED:
        s.delivery_alerts[p["alert_id"]] = DeliveryAlert(id=p["alert_id"], channels=p["channels"], flagged_at=at)
    elif t == EventType.CONSULT_REQUESTED:
        s.consults[p["consult_id"]] = Consult(id=p["consult_id"], to_id=p["to_id"], asked_by=e.actor_id,
                                              question=p["question"], asked_at=at, due_at=_dt(p["due_at"]))
    elif t == EventType.CONSULT_ANSWERED:
        k = s.consults[p["consult_id"]]
        k.answer = p["answer"]
        k.answered_at = at
    elif t == EventType.REPORT_TEXT_RECEIVED:
        s.reports[p["report_id"]] = ReportReview(id=p["report_id"], ref=p["ref"], text=p["text"], received_at=at)
    elif t == EventType.REPORT_REVIEWED:
        r = s.reports[p["report_id"]]
        r.findings = dict(p["findings"])
        r.reviewed_by = e.actor_id
        r.reviewed_at = at
        r.suggested_by = p.get("suggested_by")
        r.corrected = list(p.get("corrected") or [])
        s.last_progress_at = max(s.last_progress_at, at)
    elif t == EventType.CONSENT_RECORDED:
        s.consent_at = at
    elif t == EventType.CASE_CLOSED:
        s.status = "closed"
        s.outcome = Outcome(p["outcome"])
        s.outcome_evidence_ref = p.get("evidence_ref")
        s.outcome_reason = p.get("reason")
        s.closed_at = at
        s.closed_by = p["signed_by"]
        s.stalls = {}
    else:  # pragma: no cover - exhaustive over EventType
        raise ValueError(f"unhandled event {t}")
    return s


def replay(events: Iterable[Event]) -> CaseState:
    state: CaseState | None = None
    for e in events:
        state = apply(state, e)
    if state is None:
        raise ValueError("no events")
    return state


# --------------------------------------------------------------------------------------------------
# Rule-driven stall reconciliation (R4)
# --------------------------------------------------------------------------------------------------
def reconcile_stalls(state: CaseState, pathway: Pathway, now: datetime, resolver: Resolver) -> list[Event]:
    if not state.is_open:
        return []
    active = checks.evaluate(state, pathway, now)
    ladder = pathway.escalation_ladder
    reesc = timedelta(days=pathway.checks.reescalate_after_days)
    events: list[Event] = []
    for reason in list(state.stalls):
        if StallReason(reason) not in active:
            events.append(_sys(EventType.STALL_CLEARED, now, reason=reason))
    for reason, cond in active.items():
        existing = state.stalls.get(reason.value)
        if existing is None:
            # An unanswered e-consult goes first to the specialist it was sent to (or their cover), not back to
            # the person who asked it (judge finding, 20 Nov). Later levels follow the pathway's ladder.
            first = "consult_target" if reason == StallReason.CONSULT_UNANSWERED else ladder[0]
            to = resolver(state, first)
            events.append(_sys(EventType.STALL_FLAGGED, now, reason=reason.value, stage=cond.stage,
                               detail=cond.detail, escalated_to=to))
            events.append(_sys(EventType.ESCALATED, now, reason=reason.value, level=1, to_id=to))
        elif now - existing.last_escalated_at >= reesc and existing.level < len(ladder):
            level = existing.level + 1
            to = resolver(state, ladder[level - 1])
            events.append(_sys(EventType.ESCALATED, now, reason=reason.value, level=level, to_id=to))
    return events


def execute(
    state: CaseState | None, events: Sequence[Event], pathway: Pathway, now: datetime, resolver: Resolver,
) -> tuple[CaseState, list[Event]]:
    """Apply command events, then reconcile stalls. Returns the new state and every event to persist."""
    out: list[Event] = []
    for e in events:
        state = apply(state, e)
        out.append(e)
    if state is None:
        raise ValueError("execute needs an existing state or a CASE_OPENED event")
    for e in reconcile_stalls(state, pathway, now, resolver):
        state = apply(state, e)
        out.append(e)
    return state, out
