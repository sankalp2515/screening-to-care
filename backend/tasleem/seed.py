"""Synthetic demo data. Every name, organization and record is fictional.

Scenarios are replayed through the real ingest path in chronological order, with a daily scheduler tick,
so stall detection and escalation times are what a live system would have produced.

    python -m tasleem.seed            # seed if empty
    python -m tasleem.seed --reset    # drop everything and reseed
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from .domain.model import Actor, ActorType, AdminStatus, BarrierCode, Outcome
from .infra.db import OrganizationRow, PatientRow, PractitionerRow, create_schema, drop_schema
from .services.fhir import PURPOSE_INVITE, PURPOSE_OUTCOME, REASON_RESULT_DISCUSSION, ReferralStatusMessage
from .services.scheduler import tick

SOURCE = "malaffi-sim"
LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
PURPOSE = "urn:tasleem:communication-purpose"

ORGS = [
    dict(id="org-ghaf", name="Ghaf Family Health Centre (demo)", kind="primary_care", services=[],
         insurance_networks=["Thiqa", "Enhanced", "Basic"]),
    dict(id="org-samar", name="Samar Family Clinic (demo)", kind="primary_care", services=[],
         insurance_networks=["Enhanced", "Basic"]),
    # "female_endoscopist": a female endoscopist is on the list, for patients who ask for one (TSL-165).
    dict(id="org-falaj", name="Falaj GI Centre (demo)", kind="gi_centre",
         services=["colonoscopy", "female_endoscopist"],
         insurance_networks=["Thiqa", "Enhanced"]),
    dict(id="org-dana", name="Dana Endoscopy Clinic (demo)", kind="gi_centre", services=["colonoscopy"],
         insurance_networks=["Basic", "Enhanced"]),
    dict(id="org-program", name="Screening Program Office (demo)", kind="program", services=[],
         insurance_networks=[]),
]
PEOPLE = [
    dict(id="dr-hessa", name="Dr. Hessa (clinic lead)", role="clinic_lead", org_id="org-ghaf", lead_id=None),
    dict(id="coord-sara", name="Sara (program coordinator)", role="program_coordinator", org_id="org-program",
         lead_id=None),
    dict(id="dr-fatima", name="Dr. Fatima (family physician)", role="family_physician", org_id="org-ghaf",
         lead_id="dr-hessa"),
    dict(id="dr-salma", name="Dr. Salma (family physician)", role="family_physician", org_id="org-samar",
         lead_id="dr-hessa"),
    dict(id="nav-aisha", name="Aisha (care navigator)", role="navigator", org_id="org-ghaf", lead_id="dr-hessa"),
    dict(id="dr-omar", name="Dr. Omar (gastroenterologist)", role="gi_specialist", org_id="org-falaj",
         lead_id=None),
    dict(id="dr-lina", name="Dr. Lina (gastroenterologist)", role="gi_specialist", org_id="org-dana", lead_id=None),
]
PATIENTS = [
    dict(id="p-noura", display_name="Noura A. (52)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-fatima", birth_year=1974),
    dict(id="p-rajesh", display_name="Rajesh K. (58)", preferred_language="en", insurance_network="Basic",
         family_physician_id="dr-fatima", birth_year=1968),
    dict(id="p-ahmed", display_name="Ahmed S. (64)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-fatima", birth_year=1962),
    dict(id="p-grace", display_name="Grace O. (49)", preferred_language="en", insurance_network="Enhanced",
         family_physician_id="dr-salma", birth_year=1977),
    dict(id="p-yousef", display_name="Yousef H. (55)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-fatima", birth_year=1971),
    dict(id="p-leila", display_name="Leila M. (61)", preferred_language="en", insurance_network="Enhanced",
         family_physician_id="dr-salma", birth_year=1965),
    dict(id="p-salem", display_name="Salem R. (67)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-fatima", birth_year=1959),
    dict(id="p-fatma", display_name="Fatma N. (70)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-fatima", birth_year=1956),
    dict(id="p-sunita", display_name="Sunita P. (53)", preferred_language="en", insurance_network="Basic",
         family_physician_id="dr-salma", birth_year=1973),
    dict(id="p-hamad", display_name="Hamad J. (46)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-fatima", birth_year=1980),
    dict(id="p-khalfan", display_name="Khalfan B. (51)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-salma", birth_year=1975),
    dict(id="p-khalid", display_name="Khalid M. (57)", preferred_language="en", insurance_network="Thiqa",
         family_physician_id="dr-fatima", birth_year=1969),
    dict(id="p-mariam", display_name="Mariam S. (62)", preferred_language="ar", insurance_network="Thiqa",
         family_physician_id="dr-salma", birth_year=1964),
    dict(id="p-john", display_name="John D. (59)", preferred_language="en", insurance_network="Enhanced",
         family_physician_id=None, birth_year=1967),
]


# ---- FHIR builders --------------------------------------------------------------------------------
def _iso(t: datetime) -> str:
    return t.isoformat()


def _cc(system: str, code: str) -> dict[str, Any]:
    return {"coding": [{"system": system, "code": code}]}


def fit(pid: str, rid: str, t: datetime, positive: bool = True) -> dict:
    return {"resourceType": "Observation", "id": rid, "status": "final", "subject": {"reference": f"Patient/{pid}"},
            "code": _cc(LOINC, "29771-3"), "effectiveDateTime": _iso(t),
            "interpretation": [_cc("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                                   "POS" if positive else "NEG")]}


def hba1c(pid: str, rid: str, t: datetime, value: float) -> dict:
    return {"resourceType": "Observation", "id": rid, "status": "final", "subject": {"reference": f"Patient/{pid}"},
            "code": _cc(LOINC, "4548-4"), "effectiveDateTime": _iso(t),
            "valueQuantity": {"value": value, "unit": "%"}}


def bp(pid: str, rid: str, t: datetime, systolic: float) -> dict:
    return {"resourceType": "Observation", "id": rid, "status": "final", "subject": {"reference": f"Patient/{pid}"},
            "category": [_cc("http://terminology.hl7.org/CodeSystem/observation-category", "vital-signs")],
            "code": _cc(LOINC, "8480-6"), "effectiveDateTime": _iso(t),
            "valueQuantity": {"value": systolic, "unit": "mm[Hg]"}}


def comm(pid: str, rid: str, t: datetime, purpose: str) -> dict:
    return {"resourceType": "Communication", "id": rid, "status": "completed",
            "subject": {"reference": f"Patient/{pid}"}, "category": [_cc(PURPOSE, purpose)], "sent": _iso(t)}


def discussed(pid: str, rid: str, t: datetime) -> dict:
    return {"resourceType": "Encounter", "id": rid, "status": "finished", "subject": {"reference": f"Patient/{pid}"},
            "reasonCode": [_cc(PURPOSE, REASON_RESULT_DISCUSSION)], "period": {"start": _iso(t)}}


def referral(pid: str, rid: str, t: datetime) -> dict:
    return {"resourceType": "ServiceRequest", "id": rid, "status": "active", "intent": "order",
            "subject": {"reference": f"Patient/{pid}"}, "code": _cc(SNOMED, "73761001"), "authoredOn": _iso(t)}


def task(pid: str, rid: str, t: datetime, status: str, reason: str | None = None) -> dict:
    r = {"resourceType": "Task", "id": rid, "status": status, "intent": "order", "for": {"reference": f"Patient/{pid}"},
         "meta": {"lastUpdated": _iso(t)}}
    if reason:
        r["statusReason"] = {"text": reason}
    return r


def appt(pid: str, rid: str, t: datetime, status: str, start: datetime, version: int = 1) -> dict:
    return {"resourceType": "Appointment", "id": rid, "status": status, "start": _iso(start),
            "meta": {"lastUpdated": _iso(t), "versionId": str(version)},
            "participant": [{"actor": {"reference": f"Patient/{pid}"}, "status": "accepted"}]}


def procedure(pid: str, rid: str, t: datetime) -> dict:
    return {"resourceType": "Procedure", "id": rid, "status": "completed", "subject": {"reference": f"Patient/{pid}"},
            "code": _cc(SNOMED, "73761001"), "performedDateTime": _iso(t)}


def report(pid: str, rid: str, t: datetime, text: str | None = None) -> dict:
    r = {"resourceType": "DiagnosticReport", "id": rid, "status": "final",
         "subject": {"reference": f"Patient/{pid}"}, "code": _cc(LOINC, "18746-8"), "issued": _iso(t)}
    if text:
        r["conclusion"] = text  # free text, read by the Evidence Reader
    return r


# Synthetic report texts (no real patient wording).
# Written the way real reports are: no "incomplete", no "caecum", no "repeat". Keyword rules read one finding
# of six from it (the Boston score); the model reads all six, each with its sentence.
KHALID_REPORT = ("Indication: positive FIT. Examination limited to the sigmoid colon: the scope could not be passed "
                 "beyond 40 cm because of solid faecal residue. Boston score 3 (1-1-1). No lesions seen in the "
                 "segments examined. Re-scope in 3 months after an extended two-day preparation.")
MARIAM_REPORT = ("Indication: positive FIT. Caecum reached and identified by the appendiceal orifice. "
                 "Bowel preparation BBPS 8 (3-3-2). Two polyps removed by cold snare, 6 mm and 9 mm. "
                 "Histology pending. Repeat colonoscopy in 3 years if adenomas are confirmed.")


def careplan(pid: str, rid: str, t: datetime) -> dict:
    return {"resourceType": "CarePlan", "id": rid, "status": "active", "intent": "plan",
            "subject": {"reference": f"Patient/{pid}"}, "period": {"start": _iso(t)}}


def ref(pid: str, n: int, t: datetime, status: AdminStatus) -> ReferralStatusMessage:
    return ReferralStatusMessage(message_id=f"REF-{pid}-{n}", referral_id=f"sr-{pid}", patient_id=pid,
                                 status=status, occurred_at=t, service="colonoscopy")


def fit_journey(pid: str, start: datetime, upto: str, *, booked_for: datetime | None = None) -> list[tuple]:
    """Standard FIT+ journey steps up to (and including) `upto`. Returns timeline items."""
    d = lambda n: start + timedelta(days=n)  # noqa: E731
    steps = [
        ("FIT", d(0), fit(pid, f"obs-fit-{pid}", d(0))),
        ("PATIENT_INVITED", d(1), comm(pid, f"com-inv-{pid}", d(1), PURPOSE_INVITE)),
        ("RESULT_DISCUSSED", d(4), discussed(pid, f"enc-{pid}", d(4))),
        ("REFERRED", d(5), referral(pid, f"sr-{pid}", d(5))),
        ("REF_SENT", d(5), ref(pid, 1, d(5), AdminStatus.SENT)),
        ("REFERRAL_ACCEPTED", d(7), task(pid, f"task-{pid}", d(7), "accepted")),
        ("REF_ACCEPTED", d(7), ref(pid, 2, d(7), AdminStatus.ACCEPTED)),
        ("BOOKED", d(9), appt(pid, f"apt-{pid}", d(9), "booked", booked_for or d(16))),
        ("REF_SCHEDULED", d(9), ref(pid, 3, d(9), AdminStatus.SCHEDULED)),
        ("ATTENDED", d(16), appt(pid, f"apt-{pid}", d(16), "fulfilled", booked_for or d(16), version=2)),
        ("PROCEDURE_DONE", d(16), procedure(pid, f"proc-{pid}", d(16))),
        ("REPORT_RECEIVED", d(19), report(pid, f"dr-{pid}", d(19))),
        ("REF_COMPLETED", d(19), ref(pid, 4, d(19), AdminStatus.COMPLETED)),
        ("OUTCOME_COMMUNICATED", d(21), comm(pid, f"com-out-{pid}", d(21), PURPOSE_OUTCOME)),
    ]
    out = []
    for name, t, payload in steps:
        out.append((t, payload))
        if name == upto:
            break
    return out


def _case_of(svc: Any, pid: str, pathway_id: str | None = None) -> str:
    for c in svc.cases.repo.find_open_for_patient(pid):
        if pathway_id is None or c.pathway_id == pathway_id:
            return c.id
    raise LookupError(pid)


def _confirm_reading(svc: Any, pid: str, clinician: str, t: datetime) -> None:
    """A clinician accepts the keyword reader's reading of the patient's first report unchanged."""
    from .domain.report_reader import READER_ID, reading_dict

    cid = _case_of(svc, pid)
    st = svc.cases.get(cid)
    r = next(iter(st.reports.values()))
    fields = {k: v["value"] for k, v in reading_dict(r.text).items()}
    svc.cases.review_report(cid, Actor(id=clinician, type=ActorType.CLINICIAN), r.id, fields, t,
                            suggested_by=READER_ID, suggestion=fields)


def _staff(pid: str, t: ActorType) -> Actor:
    return Actor(id=pid, type=t)


def build_timeline(now: datetime) -> list[tuple[datetime, Any]]:
    """Items are (time, FHIR dict | REF message | callable(svc, t))."""
    n = lambda days: now - timedelta(days=days)  # noqa: E731
    fatima = _staff("dr-fatima", ActorType.CLINICIAN)
    aisha = _staff("nav-aisha", ActorType.NAVIGATOR)
    items: list[tuple[datetime, Any]] = []

    # 1. Noura: booked, missed the colonoscopy; tells us she is scared and has no escort.
    items += fit_journey("p-noura", n(30), "REF_SCHEDULED", booked_for=n(6))
    items.append((n(6), appt("p-noura", "apt-p-noura", n(6), "noshow", n(6), version=2)))
    items.append((n(1), lambda svc, t: svc.cases.report_barrier(
        _case_of(svc, "p-noura"), Actor(id="p-noura", type=ActorType.PATIENT),
        [BarrierCode.FEAR, BarrierCode.NO_ESCORT],
        "انا خايفة من التخدير وما في احد يوصلني البيت", t)))

    # 2. Rajesh: Malaffi says COMPLETED; no colonoscopy report exists (the false-done case).
    items += fit_journey("p-rajesh", n(30), "ATTENDED")
    items.append((n(13), ref("p-rajesh", 4, n(13), AdminStatus.COMPLETED)))

    # 3. Ahmed: GI centre rejected the referral as incomplete.
    items += fit_journey("p-ahmed", n(15), "REF_SENT")
    items.append((n(8), task("p-ahmed", "task-p-ahmed", n(8), "rejected",
                             "Incomplete referral: no recent haemoglobin result")))

    # 4. Grace: report received, outcome never communicated.
    items += fit_journey("p-grace", n(45), "REF_COMPLETED")

    # 5. Yousef: on track, colonoscopy booked for next week.
    items += fit_journey("p-yousef", n(12), "REF_SCHEDULED", booked_for=n(-4))

    # 6. Leila: complete and ready for the owner to close.
    items += fit_journey("p-leila", n(28), "OUTCOME_COMMUNICATED")

    # 7. Salem: complete and closed on evidence.
    items += fit_journey("p-salem", n(35), "OUTCOME_COMMUNICATED")
    items.append((n(10), lambda svc, t: svc.cases.close(
        _case_of(svc, "p-salem"), fatima, Outcome.COMPLETED_WITH_REPORT, None, None, t)))

    # 8. Fatma: owner offered a handoff to another clinic; nobody accepted it.
    items += fit_journey("p-fatma", n(10), "PATIENT_INVITED")
    items.append((n(6), lambda svc, t: svc.cases.offer_handoff(
        _case_of(svc, "p-fatma"), fatima, "dr-salma", "Patient moved to Samar Family Clinic catchment", t)))

    # 9. Sunita: booked, then writes that she saw blood and is terrified (distress → clinician now).
    items += fit_journey("p-sunita", n(20), "REF_SCHEDULED", booked_for=n(-3))
    items.append((n(1), lambda svc, t: svc.cases.report_barrier(
        _case_of(svc, "p-sunita"), Actor(id="p-sunita", type=ActorType.PATIENT), [],
        "I saw blood in the toilet this morning and I am terrified", t)))

    # 10. Hamad: HbA1c 7.2 %, invited, never came to discuss it (pathway B).
    items.append((n(20), hba1c("p-hamad", "obs-a1c-p-hamad", n(20), 7.2)))
    items.append((n(18), comm("p-hamad", "com-inv-p-hamad", n(18), PURPOSE_INVITE)))

    # 11. Khalfan: screening blood pressure 162 mmHg, invited, review never happened (pathway C, config only).
    items.append((n(25), bp("p-khalfan", "obs-bp-p-khalfan", n(25), 162)))
    items.append((n(23), comm("p-khalfan", "com-inv-p-khalfan", n(23), PURPOSE_INVITE)))

    # 13. Khalid: Malaffi says COMPLETED and a report arrived, but the report says the colonoscopy was incomplete
    #     with inadequate preparation. The Evidence Reader reads it; Dr Fatima has not confirmed it yet.
    items += fit_journey("p-khalid", n(20), "PROCEDURE_DONE")
    items.append((n(1), report("p-khalid", "dr-p-khalid", n(1), KHALID_REPORT)))
    items.append((n(1), ref("p-khalid", 4, n(1), AdminStatus.COMPLETED)))

    # 14. Mariam: complete colonoscopy, two polyps removed, histology pending. Dr Salma confirmed the reading
    #     25 days ago; the pathology has still not arrived, so the case stays open and escalates.
    items += fit_journey("p-mariam", n(45), "PROCEDURE_DONE")
    items.append((n(26), report("p-mariam", "dr-p-mariam", n(26), MARIAM_REPORT)))
    items.append((n(25), lambda svc, t: _confirm_reading(svc, "p-mariam", "dr-salma", t)))

    # Noura agreed to be contacted by Sahatna before any outreach (judge finding, 20 Nov: the switch showed off).
    items.append((n(29), lambda svc, t: svc.cases.record_consent(
        _case_of(svc, "p-noura"), Actor(id="p-noura", type=ActorType.PATIENT), t)))

    # 12. John: no registered family physician → coordinator owns the case, with a warning (R1).
    items += fit_journey("p-john", n(3), "PATIENT_INVITED")

    # Dr. Fatima asks a GI specialist about Ahmed after his referral was rejected. Dr. Omar is away this week
    # (set in seed()), so the question waits in Dr. Lina's list as his named cover (TSL-160).
    items.append((n(2), lambda svc, t: svc.cases.request_consult(
        _case_of(svc, "p-ahmed"), fatima, "dr-omar",
        "His referral was rejected by the GI centre. Could he be seen at Falaj, and does he need a new referral?", t)))

    # A lab sends a positive FIT under a hospital record number Tasleem cannot match to anyone. It is stored,
    # never dropped, and waits in the coordinator's unmatched queue for a person to match or dismiss (TSL-161).
    items.append((n(1), fit("mrn-skmc-88213", "obs-unmatched-88213", n(1))))

    # Navigator logs a call attempt on Ahmed's case.
    items.append((n(5), lambda svc, t: svc.cases.log_contact(_case_of(svc, "p-ahmed"), aisha, "phone",
                                                            "no_answer", t)))
    return items


def _load_directory(session: Any) -> None:
    session.add_all([OrganizationRow(**o) for o in ORGS])
    session.flush()
    # leads first so the self-referencing foreign key is satisfied
    for p in sorted(PEOPLE, key=lambda x: x["lead_id"] is not None):
        session.add(PractitionerRow(**p))
        session.flush()
    session.add_all([PatientRow(**p) for p in PATIENTS])
    session.commit()


def seed(ctx: Any, now: datetime | None = None) -> dict[str, Any]:
    from .api.context import Services

    now = now or datetime.now(UTC)
    with ctx.sessions() as session:
        _load_directory(session)
        svc = Services.build(ctx, session)
        items = sorted(build_timeline(now), key=lambda x: x[0])
        start_day = min(t for t, _ in items).replace(hour=6, minute=0, second=0, microsecond=0)
        ticks = [start_day + timedelta(days=i) for i in range((now - start_day).days + 1)]
        ingested = commands = 0
        ti = 0
        for t, item in items:
            while ti < len(ticks) and ticks[ti] <= t:
                tick(svc.cases, ticks[ti])
                ti += 1
            if callable(item):
                item(svc, t)
                commands += 1
            elif isinstance(item, ReferralStatusMessage):
                svc.ingest.ingest_referral_status(item, SOURCE, t)
                ingested += 1
            else:
                svc.ingest.ingest_fhir(item, SOURCE, t)
                ingested += 1
        while ti < len(ticks):
            tick(svc.cases, ticks[ti])
            ti += 1
        result = tick(svc.cases, now)
        # Dr. Omar is on leave this week with Dr. Lina as his named cover (TSL-160).
        svc.directory.set_absence("dr-omar", now + timedelta(days=6), "dr-lina")
        n_cases = len(svc.cases.repo.all_rows())
    ctx.cache.clear()
    return {"seeded": True, "messages": ingested, "commands": commands, "cases": n_cases, "final_tick": result}


def seed_if_empty(ctx: Any) -> dict[str, Any]:
    with ctx.sessions() as session:
        has = session.execute(select(PatientRow.id).limit(1)).first()
    return {"seeded": False} if has else seed(ctx)


def reset_and_seed(ctx: Any) -> dict[str, Any]:
    drop_schema(ctx.engine)
    create_schema(ctx.engine)
    ctx.cache.clear()
    return seed(ctx)


def main(argv: list[str] | None = None) -> None:
    from .api.context import AppContext
    from .config import get_settings

    ap = argparse.ArgumentParser(description="Seed Tasleem with synthetic demo data.")
    ap.add_argument("--reset", action="store_true", help="drop all data first")
    args = ap.parse_args(argv)
    ctx = AppContext.build(get_settings())
    print(reset_and_seed(ctx) if args.reset else seed_if_empty(ctx))


if __name__ == "__main__":
    main()
