"""AI-user simulation (tasleem.bench.personas) and the work-routing gaps it found.

Each test is a job to be done that failed before the fix: the case said a named person must act, but that
person's work list did not show it, or the person was not allowed to make the decision.
"""

from fastapi.testclient import TestClient

from tasleem.bench.personas import PERSONAS, ScriptedBrain, checks, make_world, run

STAFF_ROLES = {"family_physician", "clinic_lead", "gi_specialist"}


def H(user: str) -> dict[str, str]:
    return {"X-Demo-User": user}


def case_of(client: TestClient, patient: str) -> dict:
    items = client.get("/v1/cases", headers=H("coord-sara")).json()["items"]
    cid = next(i["id"] for i in items if i["patient"]["id"] == patient)
    return client.get(f"/v1/cases/{cid}", headers=H("coord-sara")).json()


def work_ids(client: TestClient, user: str, kind: str | None = None) -> set[str]:
    secs = client.get("/v1/me/work", headers=H(user)).json()["sections"]
    return {i["id"] for s in secs if kind in (None, s["kind"]) for i in s["items"]}


def roles(client: TestClient) -> dict[str, str]:
    return {p["id"]: p["role"] for p in client.get("/v1/directory/people").json()["staff"]}


def test_missed_appointment_is_in_the_navigators_work_list(client: TestClient) -> None:
    """Noura missed her colonoscopy. The case says Aisha (navigator) must reach her and rebook, so Aisha's work
    list must show it. Before the fix it was empty."""
    noura = case_of(client, "p-noura")
    assert noura["next_step"]["who"] == "navigator" and noura["next_step"]["person"]["id"] == "nav-aisha"
    assert noura["id"] in work_ids(client, "nav-aisha", "task")


def test_patient_reply_waits_in_the_navigators_list_until_confirmed(client: TestClient) -> None:
    """Yousef says the date clashes with his shift. The AI suggestion must be confirmed by a person (R5); that
    person (the navigator) must see it. After confirming, the playbook task stays with the navigator."""
    yousef = case_of(client, "p-yousef")
    r = client.post(f"/v1/cases/{yousef['id']}/barriers", headers=H("p-yousef"),
                    json={"codes": ["TIME_OR_WORK"], "text": "I have a shift that day, I need another date"})
    assert r.status_code == 200
    assert yousef["id"] in work_ids(client, "nav-aisha", "task")
    bid = next(b["id"] for b in case_of(client, "p-yousef")["barriers"] if b["status"] == "reported")
    r = client.post(f"/v1/cases/{yousef['id']}/barriers/{bid}/confirm", headers=H("nav-aisha"),
                    json={"code": "TIME_OR_WORK"})
    assert r.status_code == 200, r.text
    b = next(b for b in r.json()["barriers"] if b["id"] == bid)
    assert b["status"] == "confirmed" and b["assignee_role"] == "navigator"
    assert yousef["id"] in work_ids(client, "nav-aisha", "task")


def test_done_elsewhere_without_a_family_physician_reaches_a_clinician(client: TestClient) -> None:
    """John had his colonoscopy abroad and has no family physician, so the programme coordinator owns his case.
    Only a clinician can accept evidence from another provider (R3). Before the fix the report sat with the
    coordinator, and confirming it assigned the clinician task to the coordinator too."""
    john = case_of(client, "p-john")
    who = roles(client)
    assert who[john["owner"]["id"]] == "program_coordinator"
    r = client.post(f"/v1/cases/{john['id']}/barriers", headers=H("p-john"),
                    json={"codes": ["DONE_ELSEWHERE"], "text": "I already had it done in Kochi, I have the report"})
    assert r.status_code == 200
    clinicians_seeing = {u for u, role in who.items() if role in STAFF_ROLES and john["id"] in work_ids(client, u)}
    assert clinicians_seeing, "a clinician must see a 'done elsewhere' report"

    bid = next(b["id"] for b in case_of(client, "p-john")["barriers"] if b["status"] == "reported")
    r = client.post(f"/v1/cases/{john['id']}/barriers/{bid}/confirm", headers=H("coord-sara"),
                    json={"code": "DONE_ELSEWHERE"})
    assert r.status_code == 200, r.text
    task_holders = {u for u in who if john["id"] in work_ids(client, u, "task")}
    assert task_holders and all(who[u] in STAFF_ROLES for u in task_holders), task_holders


def test_scripted_ai_users_pass_every_check() -> None:
    """The whole simulation offline: every persona's job check and every safety invariant holds."""
    world, tc = make_world()
    try:
        res = run(world, ScriptedBrain(), rounds=1, steps=2)
        results = checks(world)
    finally:
        tc.__exit__(None, None, None)
    failed = [f"{c.persona}: {c.check} ({c.detail})" for c in results if not c.passed]
    assert not failed, failed
    assert len(res["memory"]) == len(PERSONAS)
    assert not [c for c in world.calls if c.status >= 500]


def my_message(client: TestClient, patient: str) -> str:
    return client.get("/v1/me/cases?lang=en", headers=H(patient)).json()["items"][0]["message"]


def test_attended_without_a_report_does_not_read_as_finished(client: TestClient) -> None:
    """Rajesh's AI user read "Thank you for attending. Your care team will follow up." as "I'm all set", while
    no colonoscopy report exists. The companion must say the follow-up is not finished."""
    msg = my_message(client, "p-rajesh")
    assert "not finished" in msg and "result" not in msg.lower()


def test_companion_acknowledges_a_report_and_stops_the_old_prompt(client: TestClient) -> None:
    """John said he had the test abroad and was still told to book a visit; Fatma asked for a call and was not
    told it arrived. After reporting, the companion says it was received and who acts."""
    john = case_of(client, "p-john")
    assert "book a visit" in my_message(client, "p-john")
    client.post(f"/v1/cases/{john['id']}/barriers", headers=H("p-john"),
                json={"codes": ["DONE_ELSEWHERE"], "text": "I had it in Kochi"})
    msg = my_message(client, "p-john")
    assert "doctor will review" in msg and "book a visit" not in msg

    fatma = case_of(client, "p-fatma")
    client.post(f"/v1/cases/{fatma['id']}/barriers", headers=H("p-fatma"),
                json={"codes": ["WANTS_CALLBACK"], "text": ""})
    assert "will call you" in my_message(client, "p-fatma")
    ar = client.get("/v1/me/cases?lang=ar", headers=H("p-fatma")).json()["items"][0]["message"]
    assert ar.startswith("شكراً")


def test_clinic_lead_can_reassign_a_case_escalated_to_them(client: TestClient) -> None:
    """Dr. Hessa's AI user saw stuck cases escalated to her and was refused the handoff (R2_NOT_OWNER)."""
    items = [i for i in client.get("/v1/me/work", headers=H("dr-hessa")).json()["sections"]
             if i["kind"] == "escalated"][0]["items"]
    cid = next(i["id"] for i in items
               if any((s.get("escalated_to") or {}).get("id") == "dr-hessa"
                      for s in client.get(f"/v1/cases/{i['id']}", headers=H("dr-hessa")).json()["stalls"]))
    before = client.get(f"/v1/cases/{cid}", headers=H("dr-hessa")).json()
    assert before["actions"]["offer_handoff"]["allowed"] is True
    r = client.post(f"/v1/cases/{cid}/handoff", headers=H("dr-hessa"),
                    json={"to": "dr-salma", "reason": "Dr. Fatima is on leave this week"})
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["owner"]["id"] == before["owner"]["id"]          # R2: the sender stays owner
    assert after["pending_handoff"]["to_id"] == "dr-salma"
