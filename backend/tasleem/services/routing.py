"""Who must act (assignments) and who must be told (outbox), derived from case state and new events.

Both are pure functions of data already decided by the engine. They never decide anything themselves.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ..domain.actions import next_step
from ..domain.model import CaseState, Event, EventType
from ..domain.pathways import Pathway
from .directory import Directory
from .views import STALL_LABELS, patient_view_for

Assignment = tuple[str, str, str, datetime]  # person_id, kind, ref, since

# Events after which the patient's plain-language status in Sahatna changes.
PATIENT_FACING = {EventType.CASE_OPENED, EventType.STAGE_REACHED, EventType.APPOINTMENT_MISSED,
                  EventType.CASE_CLOSED}


def assignments(state: CaseState, directory: Directory) -> list[Assignment]:
    if not state.is_open:
        return []
    out: list[Assignment] = [(state.owner_id, "owner", "-", state.opened_at)]
    for s in state.stalls.values():
        # The owner stays accountable for every stall; escalation adds the next person on the ladder (R4).
        out.append((state.owner_id, "escalated", s.reason.value, s.flagged_at))
        out.append((s.escalated_to, "escalated", s.reason.value, s.last_escalated_at))
    if state.pending_handoff:
        out.append((state.pending_handoff.to_id, "handoff", "-", state.pending_handoff.offered_at))
    for k in state.consults.values():
        if k.answer is None:
            out.append((k.to_id, "consult", k.id, k.asked_at))
    for d in state.open_distress:
        out.append((d.routed_to, "distress", d.id, d.flagged_at))
    if state.open_delivery_alerts:
        nav = directory.person_for_role(state, "navigator")
        for a in state.open_delivery_alerts:
            out.append((nav, "task", a.id, a.flagged_at))
    for b in state.barriers.values():
        if b.status == "confirmed" and b.assignee_role:
            who = directory.person_for_role(state, b.assignee_role)
            out.append((who, "task", b.id, b.due_at or b.reported_at))
    # one row per (person, kind, ref)
    seen: dict[tuple[str, str, str], Assignment] = {}
    for a in out:
        seen.setdefault((a[0], a[1], a[2]), a)
    return list(seen.values())


def _task(state: CaseState, owner: str, title: str, description: str, at: datetime, urgent: bool,
          code: str) -> dict[str, Any]:
    """FHIR R4 Task for the recipient's EMR / Malaffi worklist inbox."""
    return {
        "resourceType": "Task", "status": "requested", "intent": "order",
        "priority": "urgent" if urgent else "routine",
        "code": {"coding": [{"system": "urn:tasleem:task", "code": code}], "text": title},
        "description": description,
        "for": {"reference": f"Patient/{state.patient_id}"},
        "owner": {"reference": f"Practitioner/{owner}"},
        "focus": {"reference": f"urn:tasleem:case:{state.id}"},
        "authoredOn": at.isoformat(),
    }


def outbox(state: CaseState, pathway: Pathway, events: Sequence[Event], first_seq: int,
           directory: Directory) -> list[dict[str, Any]]:
    """Notifications implied by newly written events. The patient gets at most one update per write."""
    msgs: list[dict[str, Any]] = []
    patient_seq: int | None = None
    step = next_step(state, pathway)
    for i, e in enumerate(events):
        seq = first_seq + i
        p = e.payload
        if e.type == EventType.ESCALATED:
            reason = p["reason"]
            urgent = reason == "DISTRESS"
            label = "Patient message needs a clinician" if urgent else STALL_LABELS.get(reason, reason)
            title = f"{label} (level {p['level']})"
            desc = (step or {}).get("text") or label
            msgs.append(dict(event_seq=seq, channel="emr_inbox", recipient_id=p["to_id"],
                             template="distress_alert" if urgent else "stall_escalation", urgent=urgent,
                             payload=_task(state, p["to_id"], title, desc, e.occurred_at, urgent,
                                           "distress" if urgent else "stall")))
        elif e.type == EventType.HANDOFF_OFFERED:
            msgs.append(dict(event_seq=seq, channel="emr_inbox", recipient_id=p["to_id"], template="handoff_offer",
                             urgent=False, payload=_task(state, p["to_id"], "Case offered to you",
                                                         f"Accept or decline. Reason: {p['reason']}",
                                                         e.occurred_at, False, "handoff")))
        elif e.type == EventType.CONSULT_REQUESTED:
            msgs.append(dict(event_seq=seq, channel="emr_inbox", recipient_id=p["to_id"], template="econsult_request",
                             urgent=False, payload=_task(state, p["to_id"], "E-consult question", p["question"],
                                                         e.occurred_at, False, "econsult")))
        elif e.type == EventType.BARRIER_CONFIRMED:
            who = directory.person_for_role(state, p["assignee_role"])
            msgs.append(dict(event_seq=seq, channel="emr_inbox", recipient_id=who, template="barrier_task",
                             urgent=False, payload=_task(state, who, f"Help needed: {p['code']}", p["action"],
                                                         e.occurred_at, False, "barrier")))
        elif e.type == EventType.PATIENT_MESSAGE_SENT:
            msgs.append(dict(event_seq=seq, channel="sahatna", recipient_id=state.patient_id,
                             template="care_team_message", urgent=False,
                             payload=_communication(state, p["language"], p["text"])))
        elif e.type == EventType.DELIVERY_FAILED:
            nav = directory.person_for_role(state, "navigator")
            msgs.append(dict(event_seq=seq, channel="emr_inbox", recipient_id=nav, template="patient_not_reached",
                             urgent=False, payload=_task(state, nav, "Patient not reached by message",
                                                         "Sahatna and SMS messages were not delivered. Call the "
                                                         "patient.", e.occurred_at, False, "call")))
        if e.type in PATIENT_FACING:
            patient_seq = seq
    if patient_seq is not None:
        pat = directory.patient(state.patient_id)
        lang = pat.preferred_language if pat else "en"
        view = patient_view_for(state, pathway, lang) if state.is_open else None
        text = view["message"] if view else {"en": "Your follow-up is complete. Thank you.",
                                              "ar": "اكتملت متابعتك. شكراً لك."}.get(lang, "")
        msgs.append(dict(event_seq=patient_seq, channel="sahatna", recipient_id=state.patient_id,
                         template="patient_update", urgent=False, payload=_communication(state, lang, text)))
    for m in msgs:
        m["recipient_role"] = _role(m["recipient_id"], m["channel"], directory)
    return msgs


def _role(recipient_id: str, channel: str, directory: Directory) -> str:
    """Lets the notifier choose channels per kind of person without reading the directory itself."""
    if channel == "sahatna":
        return "patient"
    p = directory.person(recipient_id)
    return p.role if p else "unknown"


def _communication(state: CaseState, lang: str, text: str) -> dict[str, Any]:
    """FHIR R4 Communication for the patient's Sahatna inbox. Plain language only: never result values
    or diagnoses (IFHAS 4.9.2.3)."""
    return {
        "resourceType": "Communication", "status": "in-progress",
        "subject": {"reference": f"Patient/{state.patient_id}"},
        "about": [{"reference": f"urn:tasleem:case:{state.id}"}],
        "language": lang,
        "payload": [{"contentString": text}],
    }
