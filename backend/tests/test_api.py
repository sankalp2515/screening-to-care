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
    # Noura missed her appointment and already told us why, so she sees that her message was received.
    assert item["direction"] == "rtl" and item["message"].startswith("شكراً لإخبارنا")
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


def test_female_doctor_preference_reaches_a_named_navigator(client):
    """Abu Dhabi evidence (BMC Cancer 2021): embarrassment, above all with a male endoscopist, stops women
    attending. The patient can say so in one tap; a navigator gets the rebooking task (R4: a named human)."""
    cid = _case(client, "p-yousef")["id"]
    opts = client.get("/v1/me/cases?lang=ar", headers=as_("p-yousef")).json()["items"][0]["barrier_options"]
    assert any(o["code"] == "FEMALE_CLINICIAN" and "طبيبة" in o["label"] for o in opts)
    r = client.post(f"/v1/cases/{cid}/barriers", headers=as_("p-yousef"), json={"codes": ["FEMALE_CLINICIAN"]}).json()
    assert r["routed_to_human"] is True
    bid = r["barrier"]["id"]
    d = client.post(f"/v1/cases/{cid}/barriers/{bid}/confirm", headers=as_("nav-aisha"),
                    json={"code": "FEMALE_CLINICIAN"}).json()
    b = next(x for x in d["barriers"] if x["id"] == bid)
    assert b["status"] == "confirmed" and b["assignee_role"] == "navigator"
    assert "female endoscopist" in str(b).lower()


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
    assert out["seeded"] is True and out["cases"] == 14


def test_working_days_follow_the_uae_week():
    from tasleem.services.views import working_days_between
    NONE = frozenset()  # the week arithmetic alone; holidays have their own test
    fri = datetime(2026, 11, 20, 9, tzinfo=UTC)  # Friday
    assert working_days_between(fri, fri, holidays=NONE) == 0
    assert working_days_between(fri, fri + timedelta(days=1), holidays=NONE) == 0   # Saturday
    assert working_days_between(fri, fri + timedelta(days=3), holidays=NONE) == 1   # Monday
    assert working_days_between(fri, fri + timedelta(days=7), holidays=NONE) == 5   # next Friday
    assert working_days_between(fri, fri + timedelta(days=45), holidays=NONE) == 31  # six weeks on, then Monday


def test_working_days_skip_uae_public_holidays():
    """TSL-164: National Day week. Mon 30 Nov to Fri 4 Dec 2026 has 5 weekdays, of which 1-3 Dec are holidays."""
    from tasleem.services.views import working_days_between
    sun = datetime(2026, 11, 29, 9, tzinfo=UTC)
    assert working_days_between(sun, sun + timedelta(days=5)) == 2
    assert working_days_between(sun, sun + timedelta(days=5), holidays=frozenset()) == 5


def test_programme_reports_the_national_guideline_on_verified_evidence(client):
    """UAE national CRC guideline (2022): >= 90% referred after a positive FIT, and colonoscopy within 31
    working days of referral. Both are counted from clinical evidence, never from referral status."""
    m = client.get("/v1/program/metrics", headers=ALL).json()
    g = next(x for x in m["guideline"] if x["pathway_id"] == "fit-positive-colonoscopy")
    assert "National Guideline" in g["source"]
    by_id = {t["id"]: t for t in g["targets"]}
    referred, window = by_id["referred"], by_id["colonoscopy_31_working_days"]
    fit_cases = m["by_pathway"]["fit-positive-colonoscopy"]
    funnel = {f["stage"]: f["count"] for f in fit_cases["funnel"]}
    assert referred["due"] == fit_cases["cases"] and referred["met"] == funnel["REFERRED"]
    assert referred["status"] in ("below", "acceptable", "desirable") and referred["acceptable"] == 0.9
    assert window["window_working_days"] == 31
    assert window["met"] <= window["due"] and window["met"] + window["pending"] <= funnel["REFERRED"]
    # Other pathways carry no guideline block, so nothing is invented for them.
    assert [x["pathway_id"] for x in m["guideline"]] == ["fit-positive-colonoscopy"]


def test_cover_while_away_routes_work_but_keeps_the_owner(client):
    """TSL-160: an owner on leave must not leave cases waiting on an absent person. Their work list and new
    escalations go to a named cover; ownership does not move (R1), and nothing about the case changes."""
    rajesh = _case(client, "p-rajesh")["id"]
    assert client.get(f"/v1/cases/{rajesh}", headers=as_("dr-salma")).status_code == 404  # another clinic
    until = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    r = client.put("/v1/me/absence", headers=FP, json={"until": until, "cover_id": "dr-salma"})
    assert r.status_code == 200 and r.json()["cover_id"] == "dr-salma"
    work = client.get("/v1/me/work", headers=as_("dr-salma")).json()
    assert [c["id"] for c in work["covering"]] == ["dr-fatima"]
    ids = {i["id"] for s in work["sections"] for i in s["items"]}
    assert rajesh in ids
    detail = client.get(f"/v1/cases/{rajesh}", headers=as_("dr-salma")).json()
    assert detail["owner"]["id"] == "dr-fatima"                      # R1: the owner is unchanged
    assert detail["owner"]["away"]["cover"]["id"] == "dr-salma"      # and everyone sees who covers
    # Coming back ends the cover.
    client.put("/v1/me/absence", headers=FP, json={"until": None})
    assert client.get("/v1/me/work", headers=as_("dr-salma")).json()["covering"] == []
    assert client.get(f"/v1/cases/{rajesh}", headers=as_("dr-salma")).status_code == 404


def test_cover_must_be_a_present_colleague(client):
    until = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    for body in ({"until": until, "cover_id": "dr-fatima"}, {"until": until, "cover_id": "nobody"},
                 {"until": past, "cover_id": "dr-salma"}):
        assert client.put("/v1/me/absence", headers=FP, json=body).status_code in (400, 422)
    client.put("/v1/me/absence", headers=as_("dr-salma"), json={"until": until, "cover_id": "dr-hessa"})
    r = client.put("/v1/me/absence", headers=FP, json={"until": until, "cover_id": "dr-salma"})
    assert r.status_code in (400, 422) and "away too" in r.text


def test_escalations_resolve_to_the_cover(client):
    """R4 with absences: the resolver names the cover, following at most three links and never a circle."""
    from tasleem.services.directory import Directory
    ctx = client.app.state.ctx
    session = ctx.sessions()
    d = Directory(session, ctx.cache)
    until = datetime.now(UTC) + timedelta(days=2)
    d.set_absence("dr-fatima", until, "dr-salma")
    d.set_absence("dr-salma", until, "dr-fatima")  # a circle must not loop
    assert d.acting_for("dr-fatima") in ("dr-salma", "dr-fatima")
    d.set_absence("dr-salma", None, None)
    assert d.acting_for("dr-fatima") == "dr-salma"
    d.set_absence("dr-fatima", None, None)
    assert d.acting_for("dr-fatima") == "dr-fatima"
    session.close()


def test_unmatched_messages_wait_for_a_person_and_are_never_dropped(client):
    """TSL-161: a positive FIT for a record number nobody knows is stored and queued; a coordinator matches it to a
    patient (the case then opens with a named owner, R1) or dismisses it. Each decision is recorded."""
    assert client.get("/v1/integration/unmatched", headers=FP).status_code == 403  # coordinator only
    q = client.get("/v1/integration/unmatched", headers=ALL).json()
    item = next(i for i in q["items"] if i["patient_ref"] == "mrn-skmc-88213")
    assert item["signals"][0]["kind"] == "LAB_RESULT"
    before = {c["id"] for c in client.get("/v1/cases?status=all&limit=200", headers=ALL).json()["items"]}
    r = client.post(f"/v1/integration/unmatched/{item['id']}/resolve", headers=ALL,
                    json={"action": "match", "patient_id": "p-khalfan"}).json()
    assert r["status"] == "matched" and r["resolution"]["by"] == "coord-sara"
    assert any(e["effect"] == "opened" for e in r["effects"])
    after = client.get("/v1/cases?status=all&limit=200", headers=ALL).json()["items"]
    new = [c for c in after if c["id"] not in before]
    assert len(new) == 1 and new[0]["owner"]["id"]
    assert all(i["id"] != item["id"] for i in client.get("/v1/integration/unmatched", headers=ALL).json()["items"])
    # Resolving twice, or matching to a patient who does not exist, is refused.
    assert client.post(f"/v1/integration/unmatched/{item['id']}/resolve", headers=ALL,
                       json={"action": "dismiss"}).status_code == 404


def test_a_repeat_fit_never_cancels_the_colonoscopy(client):
    """TSL-163: a negative FIT after a positive one adds a rule-based warning naming the UAE guideline; the case
    stays open, keeps its owner and still needs colonoscopy evidence to close (R3)."""
    from tasleem.seed import fit
    cid = _case(client, "p-noura")["id"]
    before = client.get(f"/v1/cases/{cid}", headers=ALL).json()
    later = datetime.now(UTC).isoformat()
    neg = fit("p-noura", "obs-repeat-neg-noura", datetime.now(UTC), positive=False)
    r = client.post("/v1/ingest/fhir", json=neg)
    assert r.status_code in (200, 201, 202), r.text
    after = client.get(f"/v1/cases/{cid}", headers=ALL).json()
    assert any("does not cancel the colonoscopy" in w for w in after["warnings"])
    assert after["status"] == before["status"] == "open" and after["owner"]["id"] == before["owner"]["id"]
    assert after["progress"] == before["progress"]
    close = client.post(f"/v1/cases/{cid}/close", headers=FP, json={"outcome": "COMPLETED_WITH_REPORT"})
    assert close.status_code == 409 and close.json()["error"]["code"].startswith("R3"), later


def test_referral_options_put_a_female_endoscopist_first_when_asked(client):
    """TSL-165: once a patient asks for a female doctor, in-network centres with a female endoscopist come first."""
    cid = _case(client, "p-noura")["id"]
    plain = client.get(f"/v1/cases/{cid}/referral-options", headers=FP).json()
    assert plain["prefer_female"] is False
    client.post(f"/v1/cases/{cid}/barriers", headers=as_("p-noura"), json={"codes": ["FEMALE_CLINICIAN"]})
    asked = client.get(f"/v1/cases/{cid}/referral-options", headers=FP).json()
    assert asked["prefer_female"] is True and asked["options"][0]["female_endoscopist"] is True


def test_programme_csv_export_is_pseudonymous(client):
    """TSL-182: the programme lead can take the numbers to their own reports; no patient names leave Tasleem."""
    assert client.get("/v1/program/export.csv", headers=FP).status_code == 403
    r = client.get("/v1/program/export.csv", headers=ALL)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("case_id,patient_ref,pathway") and len(lines) > 5
    assert "Rajesh" not in r.text and "Noura" not in r.text
    assert any(",yes," in ln for ln in lines[1:])  # the false "done" is visible in the export too


def test_offline_demo_bundle_matches_the_api_shape(client):
    """TSL-180: the no-backend demo replays a recorded bundle. If the API adds or drops a field, the bundle must be
    re-recorded (`python -m tasleem.demo_bundle`), or the offline demo silently shows an old product."""
    import json
    from pathlib import Path

    bundle = json.loads((Path(__file__).parents[2] / "frontend/demo/demo-bundle.json").read_text(encoding="utf-8"))
    recorded = next(iter(next(iter(bundle["cases"].values()))["detail_by_persona"].values()))
    live = client.get(f"/v1/cases/{_case(client, 'p-rajesh')['id']}", headers=FP).json()
    assert set(live) == set(recorded), {"api_only": set(live) - set(recorded), "bundle_only": set(recorded) - set(live)}
    assert {o["code"] for o in bundle["patient_cases"]["p-noura"]["ar"]["items"][0]["barrier_options"]} >= {
        "FEMALE_CLINICIAN"}
