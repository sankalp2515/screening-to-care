"""End-to-end through HTTP, on the seeded synthetic demo (SQLite in memory)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from conftest import as_
from sqlalchemy import update

from tasleem.infra.db import CaseEventRow
from tasleem.infra.repository import CaseRepository, ConcurrencyError
from tasleem.seed import comm, report

FP = as_("dr-fatima")
ALL = as_("coord-sara")  # programme coordinator: sees every case


def _case(client, patient_id: str, status: str = "all") -> dict:
    items = client.get(f"/v1/cases?status={status}", headers=ALL).json()["items"]
    return next(i for i in items if i["patient"]["id"] == patient_id)


def _now() -> datetime:
    return datetime.now(UTC)


def test_health_and_auth(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    r = client.get("/v1/cases")
    assert r.status_code == 401 and r.json()["error"]["code"] == "AUTH_REQUIRED"
    assert client.get("/v1/cases", headers=as_("nobody")).status_code == 401
    assert client.get("/v1/cases", headers=as_("p-noura")).status_code == 403  # patients can't see worklists


def test_worklist_puts_stalled_cases_first_and_shows_the_gap(client):
    items = client.get("/v1/cases", headers=FP).json()["items"]
    stalled = [bool(i["stalls"]) for i in items]
    assert stalled == sorted(stalled, reverse=True)
    rajesh = _case(client, "p-rajesh")
    assert rajesh["progress"]["gap"] is True
    assert rajesh["progress"]["reported"]["admin_status"] == "COMPLETED"
    assert [s["reason"] for s in rajesh["stalls"]] == ["CLOSED_WITHOUT_EVIDENCE"]


def test_every_seeded_stall_type_and_safety_scenario_present(client):
    items = client.get("/v1/cases?status=all", headers=ALL).json()["items"]
    reasons = {s["reason"] for i in items for s in i["stalls"]}
    assert {"BOOKED_NOT_ATTENDED", "CLOSED_WITHOUT_EVIDENCE", "REFERRAL_REJECTED", "REPORT_NOT_COMMUNICATED",
            "HANDOFF_NOT_ACCEPTED", "STEP_OVERDUE"} <= reasons
    assert any(i["distress_open"] for i in items)
    assert any(i["status"] == "closed" for i in items)
    john = client.get(f"/v1/cases/{_case(client, 'p-john')['id']}", headers=ALL).json()
    assert john["owner"]["id"] == "coord-sara" and john["warnings"]  # R1 fallback is visible
    hamad = _case(client, "p-hamad")
    assert hamad["pathway"]["id"] == "hba1c-diabetes-range" and hamad["stalls"]


def test_false_done_case_cannot_close_until_evidence_arrives(client):
    cid = _case(client, "p-rajesh")["id"]
    r = client.post(f"/v1/cases/{cid}/close", headers=FP, json={"outcome": "COMPLETED_WITH_REPORT"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "R3_EVIDENCE_REQUIRED"

    m1 = client.get("/v1/program/metrics", headers=FP).json()
    assert m1["false_done"]["count"] == 1
    assert client.get("/v1/program/metrics", headers=FP).json()["cached"] is True

    t = _now()
    res = client.post("/v1/ingest/fhir", json=report("p-rajesh", "dr-late-rajesh", t)).json()["results"][0]
    assert res["status"] == "applied"
    detail = client.get(f"/v1/cases/{cid}", headers=FP).json()
    assert detail["stalls"] == [] or all(s["reason"] != "CLOSED_WITHOUT_EVIDENCE" for s in detail["stalls"])

    client.post("/v1/ingest/fhir", json=comm("p-rajesh", "com-out-late", t, "outcome-notification"))
    closed = client.post(f"/v1/cases/{cid}/close", headers=FP, json={"outcome": "COMPLETED_WITH_REPORT"}).json()
    assert closed["status"] == "closed" and closed["outcome"]["care_completed"] is True

    m2 = client.get("/v1/program/metrics", headers=FP).json()
    assert m2["cached"] is False  # write invalidated the cache
    assert m2["false_done"]["count"] == 0


def test_ingest_is_idempotent_and_validates(client):
    body = report("p-grace", "dr-dup", _now())
    first = client.post("/v1/ingest/fhir", json=body).json()["results"][0]
    again = client.post("/v1/ingest/fhir", json=body).json()["results"][0]
    assert first["duplicate"] is False and again["duplicate"] is True
    assert again["effects"] == first["effects"]

    unmatched = client.post("/v1/ingest/fhir", json=report("p-unknown", "dr-x", _now())).json()["results"][0]
    assert unmatched["status"] == "unmatched"

    bad = client.post("/v1/ingest/fhir", json={"resourceType": "Observation", "id": "o1", "status": "final"})
    assert bad.status_code == 422 and bad.json()["error"]["details"]["field"] == "subject"

    ignored = client.post("/v1/ingest/fhir", json={"resourceType": "Medication", "id": "m1"}).json()["results"][0]
    assert ignored["status"] == "ignored"


def test_patient_view_is_plain_language_without_result_values(client):
    r = client.get("/v1/me/cases", headers=as_("p-noura"))
    item = r.json()["items"][0]
    assert item["direction"] == "rtl" and "لاحظنا" in item["message"]
    raw = json.dumps(r.json(), ensure_ascii=False)
    for forbidden in ("29771-3", "POS", "positive", "colonoscopy report", "interpretation"):
        assert forbidden not in raw
    assert {o["code"] for o in item["barrier_options"]} >= {"FEAR", "NO_ESCORT", "WANTS_CALLBACK"}
    en = client.get("/v1/me/cases?lang=en", headers=as_("p-noura")).json()["items"][0]
    assert en["direction"] == "ltr"


def test_patients_can_only_act_on_their_own_case(client):
    other = _case(client, "p-yousef")["id"]
    r = client.post(f"/v1/cases/{other}/barriers", headers=as_("p-noura"), json={"codes": ["FEAR"]})
    # Same answer as a case that does not exist: another patient's case is not revealed.
    assert r.status_code == 404
    assert client.post(f"/v1/me/cases/{other}/consent", headers=as_("p-noura")).status_code == 404


def test_barrier_flow_and_consent(client):
    cid = _case(client, "p-yousef")["id"]
    r = client.post(f"/v1/cases/{cid}/barriers", headers=as_("p-yousef"),
                    json={"text": "I need an interpreter for the instructions"}).json()
    bid = r["barrier"]["id"]
    assert r["routed_to_human"] is True and r["barrier"]["suggested_code"] in ("LANGUAGE", "PREP_UNCLEAR")
    d = client.post(f"/v1/cases/{cid}/barriers/{bid}/confirm", headers=as_("nav-aisha"),
                    json={"code": "LANGUAGE"}).json()
    b = next(x for x in d["barriers"] if x["id"] == bid)
    assert b["status"] == "confirmed" and b["assignee_role"] == "navigator"
    assert client.post(f"/v1/me/cases/{cid}/consent", headers=as_("p-yousef")).json()["consent_given"] is True


def test_distress_blocks_closure_until_a_clinician_resolves(client):
    cid = _case(client, "p-sunita")["id"]
    # Another clinic cannot see it at all (org scoping), and the answer does not reveal it exists.
    assert client.get(f"/v1/cases/{cid}", headers=FP).status_code == 404
    detail = client.get(f"/v1/cases/{cid}", headers=as_("dr-salma")).json()
    did = detail["distress"][0]["id"]
    assert detail["distress"][0]["routed_to"] == "dr-salma"
    r = client.post(f"/v1/cases/{cid}/close", headers=as_("dr-salma"),
                    json={"outcome": "PLAN_CHANGED", "reason": "x"})
    assert r.json()["error"]["code"] == "R3_DISTRESS_OPEN"
    r = client.post(f"/v1/cases/{cid}/distress/{did}/resolve", headers=ALL, json={"note": "called"})
    assert r.json()["error"]["code"] == "R3_SIGNATURE_REQUIRED"
    ok = client.post(f"/v1/cases/{cid}/distress/{did}/resolve", headers=as_("dr-salma"),
                     json={"note": "Called; urgent GI review booked"})
    assert ok.status_code == 200 and ok.json()["distress"][0]["resolved"] is True


def test_handoff_over_http(client):
    cid = _case(client, "p-fatma")["id"]
    assert client.post(f"/v1/cases/{cid}/handoff/accept", headers=as_("nav-aisha")).status_code == 409
    d = client.post(f"/v1/cases/{cid}/handoff/accept", headers=as_("dr-salma")).json()
    assert d["owner"]["id"] == "dr-salma"
    assert all(s["reason"] != "HANDOFF_NOT_ACCEPTED" for s in d["stalls"])


def test_referral_options_respect_insurance_network(client):
    cid = _case(client, "p-rajesh")["id"]
    opts = client.get(f"/v1/cases/{cid}/referral-options", headers=FP).json()["options"]
    assert [o["org_id"] for o in opts] == ["org-dana"]


def test_consult_bridge(client):
    cid = _case(client, "p-yousef")["id"]
    r = client.post(f"/v1/cases/{cid}/consults", headers=FP, json={"to": "dr-omar", "question": "Stop aspirin?"})
    kid = r.json()["consult_id"]
    assert client.post(f"/v1/cases/{cid}/consults/{kid}/answer", headers=FP, json={"answer": "x"}).status_code == 409
    d = client.post(f"/v1/cases/{cid}/consults/{kid}/answer", headers=as_("dr-omar"),
                    json={"answer": "No need to stop low-dose aspirin."}).json()
    assert d["consults"][0]["answer"]


def test_scheduler_tick_flags_due_cases_only(client):
    yousef = _case(client, "p-yousef")
    assert yousef["stalls"] == []
    future = (_now() + timedelta(days=7)).isoformat()
    out = client.post("/v1/system/tick", headers=FP, json={"now": future}).json()
    assert out["due"] >= 1
    assert "BOOKED_NOT_ATTENDED" in {s["reason"] for s in _case(client, "p-yousef")["stalls"]}


def test_audit_chain_verifies_and_detects_tampering(client):
    cid = _case(client, "p-noura")["id"]
    a = client.get(f"/v1/cases/{cid}/audit", headers=FP).json()
    assert a["verification"]["ok"] is True and a["verification"]["checked"] >= 10
    ctx = client.app.state.ctx
    with ctx.sessions() as s:
        s.execute(update(CaseEventRow).where(CaseEventRow.case_id == cid, CaseEventRow.seq == 3)
                  .values(payload={"forged": True}))
        s.commit()
    v = client.get(f"/v1/cases/{cid}/audit", headers=FP).json()["verification"]
    assert v["ok"] is False and v["broken_at_seq"] == 3


def test_optimistic_locking(client):
    cid = _case(client, "p-leila")["id"]
    ctx = client.app.state.ctx
    with ctx.sessions() as s:
        repo = CaseRepository(s)
        st = repo.get(cid)
        p = ctx.registry.get(st.pathway_id)
        from tasleem.domain import engine
        from tasleem.domain.model import Actor, ActorType

        new, evs = engine.execute(st, engine.log_contact(st, Actor(id="nav-aisha", type=ActorType.NAVIGATOR),
                                                         "phone", "reached", _now()), p, _now(), lambda *_: "x")
        try:
            repo.save(new, st.version - 1, evs, p, None)  # stale version
            raise AssertionError("expected ConcurrencyError")
        except ConcurrencyError:
            s.rollback()


def test_close_completed_case_and_reset_demo(client):
    cid = _case(client, "p-leila")["id"]
    d = client.post(f"/v1/cases/{cid}/close", headers=as_("dr-salma"), json={"outcome": "COMPLETED_WITH_REPORT"})
    assert d.status_code == 200 and d.json()["outcome"]["signed_by"] == "dr-salma"
    people = client.get("/v1/directory/people").json()
    assert {p["id"] for p in people["staff"]} >= {"dr-fatima", "nav-aisha", "coord-sara"}
    out = client.post("/v1/admin/reset-demo").json()
    assert out["seeded"] is True and out["cases"] == 12
