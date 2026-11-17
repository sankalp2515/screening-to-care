"""What can this person do on this case right now, and what is the next step?

Every answer comes from dry-running the real engine command, so the UI can never offer an action the
engine would refuse (and a rule change in engine.py shows up here without a second copy of the rule).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from . import engine
from .errors import DomainError
from .model import Actor, BarrierCode, CaseState, Outcome, StallReason
from .pathways import Pathway

PROBE = "__probe__"

# Inputs the closure form must collect for each outcome (beyond the case state itself).
CLOSE_INPUTS: dict[Outcome, list[str]] = {
    Outcome.COMPLETED_WITH_REPORT: [],
    Outcome.COMPLETED_ELSEWHERE: ["evidence_ref"],
    Outcome.PLAN_CHANGED: ["reason"],
    Outcome.INFORMED_REFUSAL: ["evidence_ref", "reason"],
    Outcome.UNREACHABLE: [],
}

# Deterministic "what to do now" per stall, in plain words. Ordered by clinical urgency.
NEXT_STEP: list[tuple[str, str, str]] = [
    ("DISTRESS", "clinician", "Call the patient today. A message suggests symptoms or distress."),
    (StallReason.CLOSED_WITHOUT_EVIDENCE, "owner",
     "Malaffi says completed but no colonoscopy report exists. Ask the GI centre for the report or rebook."),
    (StallReason.REFERRAL_REJECTED, "owner", "Fix what the GI centre asked for and resend the referral."),
    (StallReason.BOOKED_NOT_ATTENDED, "navigator", "Reach the patient, record what got in the way, and rebook."),
    (StallReason.CONSULT_NO_PROCEDURE, "owner", "Seen by the specialist but no procedure: confirm the plan."),
    (StallReason.REPORT_NOT_COMMUNICATED, "owner", "The result is back. Tell the patient and record it."),
    (StallReason.HANDOFF_NOT_ACCEPTED, "owner", "Your handoff is waiting. Chase the receiver or withdraw."),
    (StallReason.CONSULT_UNANSWERED, "owner", "An e-consult is unanswered. Chase the specialist."),
    (StallReason.STEP_OVERDUE, "owner", "The next step is overdue. Contact the patient or the next service."),
]


def _check(fn: Callable[[], object]) -> dict[str, Any]:
    try:
        fn()
        return {"allowed": True}
    except DomainError as e:
        return {"allowed": False, "code": e.code, "message": e.message}


def available_actions(state: CaseState, pathway: Pathway, actor: Actor, now: datetime) -> dict[str, Any]:
    """Dry-run each command for `actor`. Nothing is written."""
    close = []
    for outcome, inputs in CLOSE_INPUTS.items():
        res = _check(lambda o=outcome: engine.close_case(state, pathway, actor, o, evidence_ref="probe",
                                                         reason="probe", now=now))
        close.append({"outcome": outcome.value, "requires": inputs, **res})

    out: dict[str, Any] = {
        "offer_handoff": _check(lambda: engine.offer_handoff(state, actor, PROBE, "probe", now)),
        "accept_handoff": _check(lambda: engine.accept_handoff(state, actor, now)),
        "reject_handoff": _check(lambda: engine.reject_handoff(state, actor, "probe", now)),
        "log_contact": _check(lambda: engine.log_contact(state, actor, "phone", "reached", now)),
        "request_consult": _check(lambda: engine.request_consult(state, pathway, actor, PROBE, PROBE, "probe", now)),
        "message_patient": _check(lambda: engine.send_patient_message(state, actor, "Please call the clinic.", "en",
                                                                      now)),
        "close": close,
        "barriers": {
            b.id: {
                "confirm": _check(lambda b=b: engine.confirm_barrier(state, pathway, actor, b.id,
                                                                     b.suggested_code or BarrierCode.OTHER, now)),
                "resolve": _check(lambda b=b: engine.resolve_barrier(state, actor, b.id, "probe", now)),
            } for b in state.barriers.values()
        },
        "distress": {
            d.id: _check(lambda d=d: engine.resolve_distress(state, actor, d.id, "probe", now))
            for d in state.open_distress
        },
        "consults": {
            k.id: _check(lambda k=k: engine.answer_consult(state, actor, k.id, "probe", now))
            for k in state.consults.values() if k.answer is None
        },
    }
    return out


def next_step(state: CaseState, pathway: Pathway) -> dict[str, Any] | None:
    """The single most urgent thing to do on this case, chosen by fixed rules (not by AI)."""
    if not state.is_open:
        return None
    if state.open_distress:
        _, who, text = NEXT_STEP[0]
        return {"reason": "DISTRESS", "who": who, "text": text, "provenance": "computed"}
    for reason, who, text in NEXT_STEP[1:]:
        if reason.value in state.stalls:
            return {"reason": reason.value, "who": who, "text": text, "provenance": "computed"}
    if state.open_delivery_alerts:
        return {"reason": "PATIENT_NOT_REACHED", "who": "navigator",
                "text": "Messages in Sahatna and by SMS were not delivered. Call the patient.",
                "provenance": "computed"}
    open_barriers = [b for b in state.barriers.values() if b.status == "reported"]
    if open_barriers:
        return {"reason": "BARRIER_TO_CONFIRM", "who": "navigator",
                "text": "The patient told us what got in the way. Review the suggestion and confirm it.",
                "provenance": "computed"}
    if all(s in state.stages for s in pathway.closure.completion_stages):
        return {"reason": "READY_TO_CLOSE", "who": "owner",
                "text": "All required evidence is in. Review and close the case.", "provenance": "computed"}
    nxt = pathway.next_stage(set(state.stages))
    if nxt is not None:
        return {"reason": "WAITING", "who": "system", "text": f"On track. Waiting for: {nxt.label}.",
                "provenance": "computed"}
    return None
