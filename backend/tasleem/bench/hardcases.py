# ruff: noqa: E501  (markdown report text)
"""Labelled hard cases (TSL-063): messy inputs, wrong codes, out-of-order and duplicate delivery,
English and Arabic barrier and distress messages, and safety-rule attacks.

    python -m tasleem.bench.hardcases          # writes docs/evidence/HARD_CASES.md

Each case states its expected result *before* running. A case that fails stays in the report with its
actual result: known limits are listed, not removed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ..api.app import create_app
from ..config import Settings
from ..domain.barriers import KeywordBarrierClassifier, detect_distress
from ..seed import appt, comm, fit, hba1c, procedure, ref, report
from ..services.fhir import PURPOSE_INVITE

EVIDENCE = Path(__file__).resolve().parents[3] / "docs" / "evidence"
LAB = {"X-Integration-Key": ""}  # demo mode: no key configured
FP = {"X-Demo-User": "dr-fatima"}
NOW = datetime.now(UTC)


@dataclass
class HardCase:
    id: str
    category: str
    description: str
    expected: str
    run: Callable[[TestClient], str]
    note: str = ""


def _post(c: TestClient, body: Any) -> Any:
    return c.post("/v1/ingest/fhir", json=body, headers=LAB)


def _status(c: TestClient, body: Any) -> str:
    r = _post(c, body)
    if r.status_code != 200:
        err = r.json().get("error", {})
        return f"{r.status_code} {err.get('details', {}).get('field') or err.get('code')}"
    return r.json()["results"][0]["status"]


def _case(c: TestClient, pid: str) -> dict | None:
    items = c.get("/v1/cases?status=open&limit=500", headers=FP).json()["items"]
    hit = [i for i in items if i["patient"]["id"] == pid]
    return c.get(f"/v1/cases/{hit[0]['id']}", headers=FP).json() if hit else None


def _stall_reasons(c: TestClient, pid: str) -> str:
    d = _case(c, pid)
    return ",".join(sorted(s["reason"] for s in d["stalls"])) or "none" if d else "no case"


def _tick(c: TestClient, at: datetime) -> None:
    c.post("/v1/system/tick", headers=FP, json={"now": at.isoformat()})


# ---- ingest --------------------------------------------------------------------------------------
def i_missing_subject(c):
    b = fit("p-yousef", "hc-1", NOW)
    del b["subject"]
    return _status(c, b)


def i_missing_type(c):
    b = fit("p-yousef", "hc-2", NOW)
    del b["resourceType"]
    return _status(c, b)


def i_missing_id(c):
    b = fit("p-yousef", "hc-3", NOW)
    del b["id"]
    return _status(c, b)


def i_bad_date(c):
    b = fit("p-yousef", "hc-4", NOW)
    b["effectiveDateTime"] = "16/11/2026 9am"
    return _status(c, b)


def i_wrong_type_field(c):
    b = fit("p-yousef", "hc-5", NOW)
    b["code"] = "29771-3"  # a bare string where a CodeableConcept belongs
    return _status(c, b)


def i_wrong_code(c):
    b = fit("p-hc-a", "hc-6", NOW)
    b["code"]["coding"][0]["code"] = "2345-7"  # glucose, not FIT
    _status(c, b)
    return "case opened" if _case(c, "p-hc-a") else "no case"


def i_negative(c):
    _status(c, fit("p-hc-b", "hc-7", NOW, positive=False))
    return "case opened" if _case(c, "p-hc-b") else "no case"


def i_preliminary(c):
    b = fit("p-hc-c", "hc-8", NOW)
    b["status"] = "preliminary"
    return _status(c, b)


def i_unknown_patient(c):
    return _status(c, fit("p-not-registered", "hc-9", NOW))


def i_duplicate(c):
    _post(c, fit("p-hc-d", "hc-10", NOW))
    r = _post(c, fit("p-hc-d", "hc-10", NOW)).json()["results"][0]
    return "duplicate" if r["duplicate"] else "applied twice"


def i_booked_no_start(c):
    b = appt("p-yousef", "hc-11", NOW, "booked", NOW)
    del b["start"]
    return _status(c, b)


def i_unused_resource(c):
    return _status(c, {"resourceType": "MedicationRequest", "id": "hc-12", "status": "active",
                       "subject": {"reference": "Patient/p-yousef"}})


def i_empty_bundle(c):
    return _status(c, {"resourceType": "Bundle", "type": "transaction", "entry": []})


def i_bundle(c):
    t = NOW - timedelta(days=1)
    body = {"resourceType": "Bundle", "type": "transaction", "entry": [
        {"resource": fit("p-hc-e", "hc-13a", t)},
        {"resource": comm("p-hc-e", "hc-13b", t + timedelta(hours=3), PURPOSE_INVITE)}]}
    _post(c, body)
    d = _case(c, "p-hc-e")
    return "invited" if d and any(s["id"] == "PATIENT_INVITED" and s["reached"] for s in d["stages"]) else "not invited"


def i_out_of_order_trigger(c):
    t = NOW - timedelta(days=2)
    _post(c, comm("p-hc-f", "hc-14b", t + timedelta(hours=5), PURPOSE_INVITE))  # arrives first
    _post(c, fit("p-hc-f", "hc-14a", t))
    d = _case(c, "p-hc-f")
    return "invited" if d and any(s["id"] == "PATIENT_INVITED" and s["reached"] for s in d["stages"]) else "not invited"


def i_report_before_procedure(c):
    t = NOW - timedelta(days=3)
    _post(c, fit("p-hc-g", "hc-15a", t))
    _post(c, report("p-hc-g", "hc-15c", t + timedelta(days=2)))      # report lands first
    _post(c, procedure("p-hc-g", "hc-15b", t + timedelta(days=1)))
    d = _case(c, "p-hc-g")
    got = {s["id"] for s in d["stages"] if s["reached"]}
    return "both recorded" if {"PROCEDURE_DONE", "REPORT_RECEIVED"} <= got else ",".join(sorted(got))


def i_admin_completed_no_report(c):
    t = NOW - timedelta(days=10)
    _post(c, fit("p-hc-h", "hc-16a", t))
    c.post("/v1/ingest/referral-status", headers=LAB,
           json=ref("p-hc-h", 4, t + timedelta(days=2), "COMPLETED").model_dump(mode="json"))
    _tick(c, NOW)
    return "flagged" if "CLOSED_WITHOUT_EVIDENCE" in _stall_reasons(c, "p-hc-h") else _stall_reasons(c, "p-hc-h")


def i_ref_other_service(c):
    t = NOW - timedelta(days=1)
    _post(c, fit("p-hc-i", "hc-17a", t))
    m = ref("p-hc-i", 4, t, "COMPLETED").model_dump(mode="json")
    m["service"] = "cardiology"
    c.post("/v1/ingest/referral-status", headers=LAB, json=m)
    d = _case(c, "p-hc-i")
    return d["progress"]["reported"]["admin_status"]


def i_naive_datetime(c):
    b = fit("p-hc-j", "hc-18", NOW)
    b["effectiveDateTime"] = NOW.replace(tzinfo=None).isoformat()
    _status(c, b)
    return "case opened" if _case(c, "p-hc-j") else "no case"


def i_hba1c_below(c):
    _post(c, hba1c("p-hc-k", "hc-19", NOW, 6.4))
    return "case opened" if _case(c, "p-hc-k") else "no case"


def i_hba1c_at(c):
    _post(c, hba1c("p-hc-l", "hc-20", NOW, 6.5))
    return "case opened" if _case(c, "p-hc-l") else "no case"


def i_oversize(c):
    b = fit("p-yousef", "hc-21", NOW)
    b["note"] = [{"text": "x" * 1_200_000}]
    return str(_post(c, b).status_code)


def i_not_object(c):
    return str(_post(c, ["not", "an", "object"]).status_code)


# ---- safety --------------------------------------------------------------------------------------
def _seeded(c, pid):
    items = c.get("/v1/cases?status=open&limit=500", headers={"X-Demo-User": "coord-sara"}).json()["items"]
    return next(i["id"] for i in items if i["patient"]["id"] == pid)


def s_close_false_done(c):
    r = c.post(f"/v1/cases/{_seeded(c, 'p-rajesh')}/close", headers=FP, json={"outcome": "COMPLETED_WITH_REPORT"})
    return f"{r.status_code} {r.json()['error']['code']}"


def s_patient_close(c):
    r = c.post(f"/v1/cases/{_seeded(c, 'p-leila')}/close", headers={"X-Demo-User": "p-leila"},
               json={"outcome": "COMPLETED_WITH_REPORT"})
    return str(r.status_code)


def s_navigator_signs(c):
    # Same clinic as the case, so visibility is not what blocks it: only the signature rule.
    r = c.post(f"/v1/cases/{_seeded(c, 'p-noura')}/close", headers={"X-Demo-User": "nav-aisha"},
               json={"outcome": "PLAN_CHANGED", "reason": "patient prefers CT colonography"})
    return f"{r.status_code} {r.json()['error']['code']}"


def s_wrong_accept(c):
    r = c.post(f"/v1/cases/{_seeded(c, 'p-fatma')}/handoff/accept", headers={"X-Demo-User": "nav-aisha"})
    return f"{r.status_code} {r.json()['error']['code']}"


def s_patient_other_case(c):
    r = c.post(f"/v1/cases/{_seeded(c, 'p-noura')}/barriers", headers={"X-Demo-User": "p-sunita"},
               json={"codes": ["FEAR"]})
    return str(r.status_code)


def s_distress_blocks_close(c):
    cid = _seeded(c, "p-sunita")
    r = c.post(f"/v1/cases/{cid}/close", headers={"X-Demo-User": "dr-salma"}, json={"outcome": "INFORMED_REFUSAL", "reason": "declined"})
    return f"{r.status_code} {r.json()['error']['code']}"


def s_other_clinic_reads(c):
    r = c.get(f"/v1/cases/{_seeded(c, 'p-sunita')}", headers=FP)
    return f"{r.status_code} {r.json()['error']['code']}"


def s_outsider_accepts(c):
    r = c.post(f"/v1/cases/{_seeded(c, 'p-fatma')}/handoff/accept", headers={"X-Demo-User": "dr-omar"})
    return f"{r.status_code} {r.json()['error']['code']}"


def s_refusal_not_care(c):
    cid = _seeded(c, "p-yousef")
    r = c.post(f"/v1/cases/{cid}/close", headers=FP,
               json={"outcome": "INFORMED_REFUSAL", "reason": "Patient declined after full discussion",
                     "evidence_ref": "DocumentReference/signed-refusal-1"})
    return "care_completed=" + str(r.json()["outcome"]["care_completed"]).lower()


def s_patient_message_e2e(c):
    r = c.post(f"/v1/cases/{_seeded(c, 'p-noura')}/barriers", headers={"X-Demo-User": "p-noura"},
               json={"text": "عندي نزيف"})
    return "distress routed" if r.json()["distress_flagged"] else "not routed"


# ---- text: barrier suggestions and distress ------------------------------------------------------
CLS = KeywordBarrierClassifier()


def _bar(text):
    return lambda c: (CLS.classify(text).code.value if CLS.classify(text) else "none")


def _dis(text):
    return lambda c: ("flag" if detect_distress(text) else "no flag")


BARRIER_CASES = [
    ("I am really scared of the camera test", "FEAR"),
    ("والله خايف من المنظار", "FEAR"),
    ("I don't understand what to drink the night before", "PREP_UNCLEAR"),
    ("وش اسوي في التحضير؟ ما فهمت", "PREP_UNCLEAR"),
    ("Nobody can take me home after the sedation", "NO_ESCORT"),
    ("ما في احد يوصلني", "NO_ESCORT"),
    ("I can't get a taxi that early", "TRANSPORT"),
    ("Is this covered by my insurance?", "COST_OR_INSURANCE"),
    ("My manager won't give me the day off", "TIME_OR_WORK"),
    ("I need an Urdu interpreter", "LANGUAGE"),
    ("Can someone call me please", "WANTS_CALLBACK"),
    ("I did it in India last month", "DONE_ELSEWHERE"),
    ("ok thanks", "none"),
    ("I'll think about it", "none"),
    ("My kids are sick this week", "none"),
]
BARRIER_NOTES = {
    "My manager won't give me the day off": "Cue words absent ('manager', 'day off'); human confirms the code anyway",
    "I did it in India last month": "No cue ('in India'); human confirms the code anyway",
    "My kids are sick this week": "Arguably TIME_OR_WORK; abstaining sends it to a human, which is safe",
}
DISTRESS_CASES = [
    ("I saw blood when I went to the toilet", "flag"),
    ("Black stool for two days", "flag"),
    ("فيه دم مع البراز", "flag"),
    ("صار عندي نزيف", "flag"),
    ("I fainted this morning", "flag"),
    ("I feel hopeless about all of this", "flag"),
    ("انا منهار", "flag"),
    ("The pain is unbearable", "flag"),
    ("I had a blood test last week", "flag"),
    ("No bleeding, just nervous", "no flag"),
    ("عدم الحضور بسبب الدوام", "no flag"),
    ("Booked for Spain trip, can we move it?", "no flag"),
]
# Held-out set written on 17 Nov 2026 *before* the pain-severity rule was added, to check that the rule
# generalises beyond the one phrase (H56) that exposed the gap. Kept separate so the history is visible.
DISTRESS_CASES += [
    ("The pain is getting worse and worse", "flag"),
    ("I have terrible stomach pain since yesterday", "flag"),
    ("Worst pain I have ever had", "flag"),
    ("الالم ما يتحمل", "flag"),
    ("وجع شديد في بطني", "flag"),
    ("Mild pain after the injection, nothing else", "no flag"),
    ("I'm worried the procedure will cause pain", "no flag"),
]
DISTRESS_NOTES = {
    "The pain is unbearable": "Missed in v0.1 (no cue word); fixed in v0.2 by the pain-severity rule",
    "I had a blood test last week": "Over-flag by design: high recall; a clinician sees it and clears it",
    "No bleeding, just nervous": "Negation not handled: over-flag, safe direction",
}


def cases() -> list[HardCase]:
    out = [
        HardCase("H01", "ingest", "Observation without subject", "422 subject", i_missing_subject),
        HardCase("H02", "ingest", "Resource without resourceType", "422 resourceType", i_missing_type),
        HardCase("H03", "ingest", "Resource without id", "422 id", i_missing_id),
        HardCase("H04", "ingest", "Unreadable date string", "422 resource", i_bad_date),
        HardCase("H05", "ingest", "Code sent as a bare string, not a CodeableConcept", "422 resource",
                 i_wrong_type_field, "Found by this set: was silently read as 'no code'; fixed 16 Nov"),
        HardCase("H06", "ingest", "Positive result with a non-FIT LOINC code", "no case", i_wrong_code),
        HardCase("H07", "ingest", "Negative FIT", "no case", i_negative),
        HardCase("H08", "ingest", "Preliminary FIT result", "ignored", i_preliminary),
        HardCase("H09", "ingest", "Patient not in directory", "unmatched", i_unknown_patient),
        HardCase("H10", "ingest", "Same message delivered twice", "duplicate", i_duplicate),
        HardCase("H11", "ingest", "Booked appointment without start time", "422 start", i_booked_no_start),
        HardCase("H12", "ingest", "Resource type no pathway uses", "ignored", i_unused_resource),
        HardCase("H13", "ingest", "Empty bundle", "422 entry", i_empty_bundle),
        HardCase("H14", "ingest", "Bundle with FIT and invitation", "invited", i_bundle),
        HardCase("H15", "ingest", "Invitation delivered before the FIT it follows", "invited", i_out_of_order_trigger,
                 "Found by the benchmark: was dropped; now replayed when the case opens"),
        HardCase("H16", "ingest", "Report delivered before the procedure record", "both recorded",
                 i_report_before_procedure),
        HardCase("H17", "ingest", "Referral status COMPLETED, no report for 8 days", "flagged",
                 i_admin_completed_no_report),
        HardCase("H18", "ingest", "Referral status for another service on a FIT case", "NONE", i_ref_other_service),
        HardCase("H19", "ingest", "Timestamp without timezone", "case opened", i_naive_datetime,
                 "Treated as UTC; Malaffi feeds should send offsets"),
        HardCase("H20", "ingest", "HbA1c 6.4 % (below threshold)", "no case", i_hba1c_below),
        HardCase("H21", "ingest", "HbA1c 6.5 % (at threshold)", "case opened", i_hba1c_at),
        HardCase("H22", "ingest", "Body over 1 MB", "413", i_oversize),
        HardCase("H23", "ingest", "JSON array instead of a resource", "422", i_not_object,
                 "Rejected by request validation before the adapter"),
        HardCase("H24", "safety", "Close the false-done case as completed", "409 R3_EVIDENCE_REQUIRED",
                 s_close_false_done),
        HardCase("H25", "safety", "Patient tries to close their own case", "403", s_patient_close),
        HardCase("H26", "safety", "Navigator signs a clinical closure", "409 R3_SIGNATURE_REQUIRED", s_navigator_signs),
        HardCase("H27", "safety", "Someone other than the handoff target accepts", "409 R2_NOT_HANDOFF_TARGET",
                 s_wrong_accept),
        HardCase("H28", "safety", "Patient reports a barrier on another patient's case", "404", s_patient_other_case,
                 "Changed 17 Nov from 403: same answer as a missing case, so the case's existence is not revealed"),
        HardCase("H29", "safety", "Close while a distress flag is open", "409 R3_DISTRESS_OPEN",
                 s_distress_blocks_close),
        HardCase("H30", "safety", "Signed informed refusal closes, but is never counted as care",
                 "care_completed=false", s_refusal_not_care, "First attempt without the signed document was refused (R3)"),
        HardCase("H31", "safety", "Arabic bleeding message through the API", "distress routed", s_patient_message_e2e),
        HardCase("H32", "safety", "Clinician from another clinic opens a patient's case", "404 NOT_FOUND",
                 s_other_clinic_reads, "Org scoping: same answer as a missing case, so existence is not revealed"),
        HardCase("H33", "safety", "Specialist outside the case tries to accept its handoff", "404 NOT_FOUND",
                 s_outsider_accepts),
    ]
    n = len(out)
    for i, (text, exp) in enumerate(BARRIER_CASES):
        out.append(HardCase(f"H{n + i + 1:02d}", "barrier", text, exp, _bar(text), BARRIER_NOTES.get(text, "")))
    n = len(out)
    for i, (text, exp) in enumerate(DISTRESS_CASES):
        out.append(HardCase(f"H{n + i + 1:02d}", "distress", text, exp, _dis(text), DISTRESS_NOTES.get(text, "")))
    return out


EXTRA_PATIENTS = ["p-hc-a", "p-hc-b", "p-hc-c", "p-hc-d", "p-hc-e", "p-hc-f", "p-hc-g", "p-hc-h", "p-hc-i",
                  "p-hc-j", "p-hc-k", "p-hc-l"]


def run_all() -> list[tuple[HardCase, str]]:
    from ..infra.db import PatientRow

    app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True, rate_limit_per_second=0,
                              metrics_max_staleness_seconds=0))
    results = []
    with TestClient(app, raise_server_exceptions=False) as c:
        ctx = app.state.ctx
        with ctx.sessions() as s:
            s.add_all([PatientRow(id=p, display_name=p, preferred_language="en", insurance_network="thiqa",
                                  family_physician_id="dr-fatima") for p in EXTRA_PATIENTS])
            s.commit()
        for hc in cases():
            try:
                actual = hc.run(c)
            except Exception as exc:  # a crash is a result, not a skip
                actual = f"crash: {type(exc).__name__}"
            results.append((hc, actual))
    return results


def write(results: list[tuple[HardCase, str]], path: Path) -> dict[str, Any]:
    passed = sum(1 for hc, a in results if a == hc.expected)
    by: dict[str, list[int]] = {}
    for hc, a in results:
        by.setdefault(hc.category, [0, 0])
        by[hc.category][0] += a == hc.expected
        by[hc.category][1] += 1
    lines = [
        "# Hard cases",
        "",
        f"Run: `python -m tasleem.bench.hardcases` ({datetime.now(UTC):%d %b %Y}). "
        f"**{passed} of {len(results)} match the expected result.** Expected results were written before running; "
        "misses stay in the table with the reason.",
        "",
        "| Category | Passed |",
        "|---|---|",
        *[f"| {k} | {v[0]} / {v[1]} |" for k, v in by.items()],
        "",
        "Labels for barrier and distress texts were written by the team, not by independent clinicians. "
        "That is a limit; an independent labelled set is the first thing to add in a pilot.",
        "",
        "| # | Category | Input | Expected | Actual | Result | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for hc, a in results:
        ok = "pass" if a == hc.expected else "**miss**"
        lines.append(f"| {hc.id} | {hc.category} | {hc.description} | {hc.expected} | {a} | {ok} | {hc.note} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"passed": passed, "total": len(results), "by_category": by}


def main() -> None:
    res = run_all()
    summary = write(res, EVIDENCE / "HARD_CASES.md")
    print(summary)
    for hc, a in res:
        if a != hc.expected:
            print("MISS", hc.id, hc.description, "| expected", hc.expected, "| actual", a)


if __name__ == "__main__":
    main()
