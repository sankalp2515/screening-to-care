"""Live demo scenarios (demo mode only). Each one plays a short, realistic Malaffi feed for a NEW synthetic
patient through the real ingest path, then lets the real rules run. Nothing here bypasses the engine:
the scenarios only send the messages a hospital, lab or patient would send.

Used by the UI's "Malaffi feed simulator" so a judge can trigger a failure and watch Tasleem catch it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .domain.errors import DomainError
from .domain.model import Actor, ActorType, AdminStatus
from .infra.db import PatientRow
from .seed import SOURCE, appt, bp, fit, fit_journey, procedure, ref, report

NAMES = ["Hind", "Saeed", "Layla", "Arjun", "Amal", "Tariq", "Priya", "Nasser", "Huda", "Imran"]


def _new_patient(svc: Any, lang: str = "ar", fp: str | None = "dr-fatima", tag: str = "") -> str:
    pid = f"p-demo-{tag}{uuid.uuid4().hex[:6]}"
    name = NAMES[int(pid[-2:], 16) % len(NAMES)]
    svc.session.add(PatientRow(id=pid, display_name=f"{name} (demo, 55)", preferred_language=lang,
                               insurance_network="Thiqa", family_physician_id=fp, birth_year=1971))
    svc.session.commit()
    return pid


def _send(svc: Any, items: list[tuple[datetime, Any]]) -> list[dict[str, Any]]:
    log = []
    for t, item in sorted(items, key=lambda x: x[0]):
        if isinstance(item, dict):
            r = svc.ingest.ingest_fhir(item, SOURCE, t)
            log.append({"at": t.isoformat(), "source": "Malaffi (FHIR)", "message": item["resourceType"],
                        "status": r[0]["status"] if isinstance(r, list) and r else None})
        else:
            svc.ingest.ingest_referral_status(item, SOURCE, t)
            log.append({"at": t.isoformat(), "source": "Malaffi (HL7 REF)", "message": f"REF {item.status.value}"})
    return log


def _case_id(svc: Any, pid: str) -> str:
    cases = svc.cases.repo.find_open_for_patient(pid)
    if not cases:
        raise DomainError("NOT_FOUND", "Scenario did not open a case.")
    return cases[0].id


def false_done(svc: Any, now: datetime, _: dict) -> dict[str, Any]:
    pid = _new_patient(svc)
    d = lambda n: now - timedelta(days=n)  # noqa: E731
    items = fit_journey(pid, d(24), "ATTENDED", booked_for=d(8))
    items.append((d(4), ref(pid, 4, d(4), AdminStatus.COMPLETED)))
    log = _send(svc, items)
    cid = _case_id(svc, pid)
    svc.cases.evaluate(cid, now)
    return {"patient_id": pid, "case_id": cid, "feed": log,
            "story": "Malaffi marked the referral COMPLETED 4 days ago. No colonoscopy or report was ever sent. "
                     "Tasleem flags 'Marked completed without a report' and escalates to the family physician."}


def report_arrives(svc: Any, now: datetime, body: dict) -> dict[str, Any]:
    cid = body.get("case_id")
    if not cid:
        raise DomainError("VALIDATION", "Pass the case_id of a false-done case.")
    st = svc.cases.get(cid)
    pid = st.patient_id
    tag = uuid.uuid4().hex[:4]
    items = [(now - timedelta(hours=2), procedure(pid, f"proc-{pid}-{tag}", now - timedelta(hours=2))),
             (now - timedelta(hours=1), report(pid, f"dr-{pid}-{tag}", now - timedelta(hours=1)))]
    log = _send(svc, items)
    svc.cases.evaluate(cid, now)
    return {"patient_id": pid, "case_id": cid, "feed": log,
            "story": "The GI centre sends the procedure and the report. The stall clears on evidence, not on status."}


def new_positive_fit(svc: Any, now: datetime, body: dict) -> dict[str, Any]:
    pid = _new_patient(svc, fp=None if body.get("no_family_physician") else "dr-fatima")
    log = _send(svc, [(now, fit(pid, f"obs-fit-{pid}", now))])
    cid = _case_id(svc, pid)
    return {"patient_id": pid, "case_id": cid, "feed": log,
            "story": "A positive FIT arrives from the lab via Malaffi. A case opens with a named owner (the family "
                     "physician, or the programme coordinator if there is none) and Sahatna gets a plain-language "
                     "invitation, with no result value in it."}


def missed_colonoscopy(svc: Any, now: datetime, _: dict) -> dict[str, Any]:
    pid = _new_patient(svc, lang="en")
    d = lambda n: now - timedelta(days=n)  # noqa: E731
    items = fit_journey(pid, d(20), "REF_SCHEDULED", booked_for=d(2))
    items.append((d(2), appt(pid, f"apt-{pid}", d(2), "noshow", d(2), version=2)))
    log = _send(svc, items)
    cid = _case_id(svc, pid)
    svc.cases.evaluate(cid, now)
    svc.cases.report_barrier(cid, Actor(id=pid, type=ActorType.PATIENT), [],
                             "I work night shifts and could not get leave that day", now)
    log.append({"at": now.isoformat(), "source": "Sahatna (patient)", "message": "Free-text reply"})
    return {"patient_id": pid, "case_id": cid, "feed": log,
            "story": "The patient missed the colonoscopy and replied in Sahatna. Tasleem flags 'Booked but not "
                     "attended', suggests TIME_OR_WORK (AI suggestion, a human confirms) and the navigator gets "
                     "the playbook task after confirmation."}


def distress_message(svc: Any, now: datetime, _: dict) -> dict[str, Any]:
    pid = _new_patient(svc, lang="en")
    d = lambda n: now - timedelta(days=n)  # noqa: E731
    log = _send(svc, fit_journey(pid, d(12), "REF_SCHEDULED", booked_for=now + timedelta(days=5)))
    cid = _case_id(svc, pid)
    svc.cases.report_barrier(cid, Actor(id=pid, type=ActorType.PATIENT), [],
                             "There was blood again today and I am really scared", now)
    log.append({"at": now.isoformat(), "source": "Sahatna (patient)", "message": "Free-text reply"})
    return {"patient_id": pid, "case_id": cid, "feed": log,
            "story": "A patient writes about bleeding. Tasleem routes it to a clinician immediately and blocks "
                     "closure until a clinician records what was done."}


def raised_blood_pressure(svc: Any, now: datetime, _: dict) -> dict[str, Any]:
    pid = _new_patient(svc)
    log = _send(svc, [(now, bp(pid, f"obs-bp-{pid}", now, 158))])
    cid = _case_id(svc, pid)
    return {"patient_id": pid, "case_id": cid, "feed": log,
            "story": "A different screening finding (blood pressure 158 mmHg) opens a case on a pathway added "
                     "by configuration only. Same engine, same safety rules."}


def unreachable_patient(svc: Any, now: datetime, _: dict) -> dict[str, Any]:
    # The notifier's sandbox treats "p-demo-unreach-*" as a patient with no Sahatna app and no working
    # mobile number, so the invitation fails on every channel and comes back as a navigator call task.
    pid = _new_patient(svc, lang="en", tag="unreach-")
    log = _send(svc, [(now, fit(pid, f"obs-fit-{pid}", now))])
    cid = _case_id(svc, pid)
    return {"patient_id": pid, "case_id": cid, "feed": log,
            "story": "A positive FIT opens a case and the patient is invited in Sahatna. This patient has no app "
                     "and no working mobile number. When the notifier runs, both channels fail and the case gets "
                     "a navigator task: 'Patient not reached by message. Call the patient.'"}


SCENARIOS: dict[str, tuple[str, str, Callable[[Any, datetime, dict], dict[str, Any]]]] = {
    "false-done": ("Malaffi says completed, colonoscopy never happened",
                   "The headline failure Tasleem exists to catch.", false_done),
    "report-arrives": ("GI centre sends the report (needs case_id)",
                       "Resolves a false-done case on evidence.", report_arrives),
    "new-positive-fit": ("New positive FIT from the lab",
                         "Shows a case opening with a named owner and a Sahatna invitation.", new_positive_fit),
    "missed-colonoscopy": ("Patient misses the colonoscopy and replies",
                           "Barrier capture, AI suggestion, human confirmation, navigator task.", missed_colonoscopy),
    "distress-message": ("Patient reports bleeding and fear",
                         "Distress reaches a clinician the same minute.", distress_message),
    "raised-blood-pressure": ("Raised screening blood pressure",
                              "A second disease on configuration only.", raised_blood_pressure),
    "unreachable-patient": ("Patient cannot be reached by app or SMS",
                            "Channel fallback ends in a human call task (run the notifier).", unreachable_patient),
}


def list_scenarios() -> list[dict[str, str]]:
    return [{"id": k, "title": v[0], "why": v[1]} for k, v in SCENARIOS.items()]


def run(svc: Any, scenario: str, now: datetime, body: dict | None = None) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise DomainError("NOT_FOUND", f"Unknown scenario '{scenario}'.", known=list(SCENARIOS))
    return SCENARIOS[scenario][2](svc, now, body or {})
