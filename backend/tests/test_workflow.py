"""Real-workflow features: personal inbox, org scoping, action hints, outbound notifications, live scenarios."""

from __future__ import annotations

import json

from conftest import as_

FP = as_("dr-fatima")
SALMA = as_("dr-salma")
ALL = as_("coord-sara")


def _case(client, pid: str) -> dict:
    items = client.get("/v1/cases?status=all&limit=500", headers=ALL).json()["items"]
    return next(i for i in items if i["patient"]["id"] == pid)


def test_whoami_for_staff_and_patient(client):
    me = client.get("/v1/me", headers=FP).json()
    assert me["role"] == "family_physician" and me["sees_all_cases"] is False
    assert client.get("/v1/me", headers=ALL).json()["sees_all_cases"] is True
    assert client.get("/v1/me", headers=as_("p-noura")).json()["role"] == "patient"


def test_inbox_groups_work_by_why(client):
    work = client.get("/v1/me/work", headers=FP).json()
    kinds = {s["kind"]: s for s in work["sections"]}
    escalated = {i["patient"]["id"] for i in kinds["escalated"]["items"]}
    assert "p-rajesh" in escalated  # the false-done case reaches its owner
    assert work["needs_action"] > 0
    salma = {s["kind"]: s for s in client.get("/v1/me/work", headers=SALMA).json()["sections"]}
    assert any(i["patient"]["id"] == "p-fatma" for i in salma["handoff"]["items"])
    assert any(i["patient"]["id"] == "p-sunita" for i in salma["distress"]["items"])
    assert client.get("/v1/me/work", headers=as_("p-noura")).status_code == 403


def test_org_scoping_hides_other_clinics_patients(client):
    mine = {i["patient"]["id"] for i in client.get("/v1/cases?status=all", headers=FP).json()["items"]}
    assert "p-rajesh" in mine and "p-sunita" not in mine and "p-grace" not in mine
    everyone = {i["patient"]["id"] for i in client.get("/v1/cases?status=all", headers=ALL).json()["items"]}
    assert {"p-sunita", "p-grace", "p-rajesh", "p-john"} <= everyone
    # Pulled into a case by a handoff: dr-salma (other clinic) can see Fatma's case offered to her.
    fatma = _case(client, "p-fatma")["id"]
    assert client.get(f"/v1/cases/{fatma}", headers=SALMA).status_code == 200
    # Commands are scoped too.
    sunita = _case(client, "p-sunita")["id"]
    r = client.post(f"/v1/cases/{sunita}/contact-attempts", headers=FP, json={"channel": "phone", "result": "reached"})
    assert r.status_code == 404


def test_actions_mirror_the_engine(client):
    cid = _case(client, "p-rajesh")["id"]
    d = client.get(f"/v1/cases/{cid}", headers=FP).json()
    assert d["next_step"]["reason"] == "CLOSED_WITHOUT_EVIDENCE" and d["next_step"]["person"]["id"] == "dr-fatima"
    close = {c["outcome"]: c for c in d["actions"]["close"]}
    assert close["COMPLETED_WITH_REPORT"]["allowed"] is False
    assert close["COMPLETED_WITH_REPORT"]["code"] == "R3_EVIDENCE_REQUIRED"
    assert close["INFORMED_REFUSAL"]["requires"] == ["evidence_ref", "reason"]
    # The navigator is told they cannot close (R3/R5 signature), before trying.
    nav = client.get(f"/v1/cases/{cid}", headers=as_("nav-aisha")).json()
    assert all(not c["allowed"] for c in nav["actions"]["close"])
    # A case that is ready: the hint says allowed and the real command succeeds.
    leila = _case(client, "p-leila")["id"]
    ld = client.get(f"/v1/cases/{leila}", headers=SALMA).json()
    assert ld["next_step"]["reason"] == "READY_TO_CLOSE"
    assert {c["outcome"]: c for c in ld["actions"]["close"]}["COMPLETED_WITH_REPORT"]["allowed"] is True
    ok = client.post(f"/v1/cases/{leila}/close", headers=SALMA, json={"outcome": "COMPLETED_WITH_REPORT"})
    assert ok.status_code == 200


def test_outbox_notifies_named_people_and_never_leaks_results_to_patients(client):
    sunita = _case(client, "p-sunita")["id"]
    notes = client.get(f"/v1/cases/{sunita}/notifications", headers=SALMA).json()["items"]
    urgent = [n for n in notes if n["template"] == "distress_alert"]
    assert urgent and urgent[0]["recipient"] == "dr-salma" and urgent[0]["urgent"] is True
    assert urgent[0]["payload"]["resourceType"] == "Task" and urgent[0]["payload"]["priority"] == "urgent"

    pulled = client.get("/v1/integration/outbox?limit=1000").json()["items"]
    patient_msgs = [n for n in pulled if n["channel"] == "sahatna"]
    assert patient_msgs, "patients get plain-language updates in Sahatna"
    blob = json.dumps([n["payload"] for n in patient_msgs], ensure_ascii=False)
    for leak in ("29771-3", "4548-4", "8480-6", "7.2", "162", "POS"):
        assert leak not in blob  # IFHAS 4.9.2.3: no result values or codes in patient messages

    ids = [n["id"] for n in pulled[:5]]
    assert client.post("/v1/integration/outbox/ack", json={"ids": ids}).json()["acknowledged"] == len(ids)
    again = {n["id"] for n in client.get("/v1/integration/outbox?limit=1000").json()["items"]}
    assert not set(ids) & again


def test_scenario_false_done_then_report_clears_it(client):
    out = client.post("/v1/demo/scenarios/false-done").json()
    stalls = [s["reason"] for s in out["case"]["stalls"]]
    assert stalls == ["CLOSED_WITHOUT_EVIDENCE"] and out["case"]["progress"]["gap"] is True
    assert out["case"]["owner"]["id"] == "dr-fatima"
    fixed = client.post("/v1/demo/scenarios/report-arrives", json={"case_id": out["case_id"]}).json()
    assert all(s["reason"] != "CLOSED_WITHOUT_EVIDENCE" for s in fixed["case"]["stalls"])


def test_scenarios_cover_the_loop(client):
    ids = {s["id"] for s in client.get("/v1/demo/scenarios").json()["items"]}
    assert {"false-done", "new-positive-fit", "missed-colonoscopy", "distress-message",
            "raised-blood-pressure", "report-arrives"} <= ids

    fit = client.post("/v1/demo/scenarios/new-positive-fit", json={"no_family_physician": True}).json()
    assert fit["case"]["owner"]["id"] == "coord-sara" and fit["case"]["warnings"]
    assert any(n["channel"] == "sahatna" for n in fit["case"]["notifications"])

    missed = client.post("/v1/demo/scenarios/missed-colonoscopy").json()["case"]
    assert "BOOKED_NOT_ATTENDED" in [s["reason"] for s in missed["stalls"]]
    assert missed["barriers"][0]["suggested_code"] == "TIME_OR_WORK"
    assert missed["barriers"][0]["status"] == "reported"  # AI suggested; a human must confirm (R5)

    distress = client.post("/v1/demo/scenarios/distress-message").json()["case"]
    assert distress["distress"] and distress["next_step"]["reason"] == "DISTRESS"

    bp = client.post("/v1/demo/scenarios/raised-blood-pressure").json()["case"]
    assert bp["pathway"]["id"] == "hypertension-screening" and bp["owner"]["id"] == "dr-fatima"

    assert client.post("/v1/demo/scenarios/nope").status_code == 404


def test_obesity_pathway_is_configuration_only(client):
    """TSL-187: a fourth IFHAS finding from one YAML file. A screening BMI of 30 or more opens a case with the
    family physician as owner; every patient message in every pathway passes the message policy."""
    from datetime import UTC, datetime

    from tasleem.domain.messaging import check_patient_text
    from tasleem.domain.pathways import PathwayRegistry
    from tasleem.seed import LOINC, _cc, _iso

    now = datetime.now(UTC)
    bmi = {"resourceType": "Observation", "id": "obs-bmi-khalfan", "status": "final",
           "subject": {"reference": "Patient/p-khalfan"}, "code": _cc(LOINC, "39156-5"),
           "effectiveDateTime": _iso(now), "valueQuantity": {"value": 33.4, "unit": "kg/m2"}}
    res = client.post("/v1/ingest/fhir", json=bmi).json()["results"][0]
    opened = next(e for e in res["effects"] if e["effect"] == "opened")
    assert opened["pathway_id"] == "obesity-screening" and opened["owner_id"]
    for p in PathwayRegistry.from_dir("pathways").all():
        for stage, texts in p.patient_messages.items():
            for lang, text in texts.items():
                assert check_patient_text(text) == [], (p.id, stage, lang, text)
