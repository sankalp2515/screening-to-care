"""The whole real workflow across every service, for one patient, in the order it happens in a clinic.

HL7 from the lab and the GI centre -> connector -> case-core rules -> notifier channels -> agent draft ->
a person sends -> evidence arrives -> a clinician closes -> the audit chain verifies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import as_
from fastapi.testclient import TestClient

from tasleem.api.app import create_app
from tasleem.config import Settings
from tasleem.seed import comm, discussed, referral
from tasleem_agent.app import AgentSettings
from tasleem_agent.app import create_app as agent_app
from tasleem_common.http import ServiceClient
from tasleem_connector.app import ConnectorSettings
from tasleem_connector.app import create_app as connector_app
from tasleem_notifier.app import NotifierSettings, build_notifier

FATIMA, AISHA, PATIENT = as_("dr-fatima"), as_("nav-aisha"), as_("p-hamad")


def hl7_time(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y%m%d%H%M%S+0000")


def msh(kind: str, ctrl: str, t: datetime) -> str:
    return f"MSH|^~\\&|SRC|FAC|MALAFFI|DOH|{hl7_time(t)}||{kind}|{ctrl}|P|2.5.1"


def test_screening_to_care_loop_across_all_services():
    core_app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True,
                                   rate_limit_per_second=0, metrics_max_staleness_seconds=0))
    with TestClient(core_app) as core:
        to_core = ServiceClient(client=core)
        hl7 = TestClient(connector_app(ConnectorSettings(demo_mode=True), to_core))
        agent = TestClient(agent_app(AgentSettings(database_url="sqlite://", rate_limit_per_second=0), to_core))
        notifier = build_notifier(NotifierSettings(database_url="sqlite://", demo_mode=True), to_core)
        # Daytime in Abu Dhabi (10:00), at or before the real clock: routine patient messages are held
        # during quiet hours (21:00-08:00 local), which a night-time test run would otherwise hit.
        real = datetime.now(UTC)
        now = real.replace(hour=6, minute=0, second=0, microsecond=0)
        if now > real:
            now -= timedelta(days=1)
        t0 = now - timedelta(days=14) + timedelta(hours=1)

        def send_hl7(text: str) -> None:
            r = hl7.post("/v1/hl7", content=text.encode())
            assert "MSA|AA" in r.text, r.text

        def fhir(resource: dict) -> None:
            assert core.post("/v1/ingest/fhir", json=resource).status_code == 200

        # 1. The lab's positive FIT arrives as HL7 ORU. A case opens with a named owner (R1).
        send_hl7("\r".join([msh("ORU^R01", "E2E-LAB-1", t0), "PID|1||p-hamad",
                            f"OBX|1|ST|29771-3^FIT^LN||Positive|||A|||F|||{hl7_time(t0)}"]))
        cases = core.get("/v1/cases", params={"pathway": "fit-positive-colonoscopy"}, headers=FATIMA).json()
        cid = next(i["id"] for i in cases["items"] if i["patient"]["id"] == "p-hamad")
        notifier.run_once(t0 + timedelta(hours=1))
        invite = [m for m in notifier.provider.sent if m.recipient_id == "p-hamad" and m.channel == "sahatna_push"]
        assert invite, "the patient is invited in Sahatna"
        assert "Positive" not in str(invite[-1].body)  # never the result (IFHAS 4.9.2.3)

        # 2. Invited, discussed in person, referred; the GI centre accepts and books (REF + SIU over HL7).
        fhir(comm("p-hamad", "e2e-inv", t0 + timedelta(days=1), "result-invitation"))
        fhir(discussed("p-hamad", "e2e-enc", t0 + timedelta(days=2)))
        fhir(referral("p-hamad", "e2e-sr", t0 + timedelta(days=2)))
        fhir({"resourceType": "Task", "id": "e2e-task", "status": "accepted", "intent": "order",
              "for": {"reference": "Patient/p-hamad"}, "meta": {"lastUpdated": (t0 + timedelta(days=3)).isoformat()}})
        appt_at = now - timedelta(days=2)
        sch = f"SCH|E2E-APT||||||||||^^^{hl7_time(appt_at)}"
        send_hl7("\r".join([msh("SIU^S12", "E2E-SIU-1", t0 + timedelta(days=4)), sch, "PID|1||p-hamad"]))

        # 3. The patient does not attend. The GI centre sends a no-show; the rules flag the stall (R4).
        send_hl7("\r".join([msh("SIU^S26", "E2E-SIU-2", appt_at + timedelta(hours=3)), sch, "PID|1||p-hamad"]))
        core.post("/v1/system/tick", headers=FATIMA, json={"now": now.isoformat()})
        detail = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()
        assert any(s["reason"] == "BOOKED_NOT_ATTENDED" for s in detail["stalls"])
        notifier.run_once(now)
        assert any(m.channel == "emr_task" and m.recipient_id == "dr-fatima" for m in notifier.provider.sent)

        # 4. The patient says why in Sahatna; the navigator confirms; the navigator gets the playbook task.
        mine = core.get("/v1/me/cases", headers=PATIENT).json()["items"]
        assert any(c["case_id"] == cid for c in mine)
        b = core.post(f"/v1/cases/{cid}/barriers", headers=PATIENT, json={"codes": ["FEAR"]}).json()
        core.post(f"/v1/cases/{cid}/barriers/{b['barrier']['id']}/confirm", headers=AISHA, json={"code": "FEAR"})
        work = {s["kind"]: s["count"] for s in core.get("/v1/me/work", headers=AISHA).json()["sections"]}
        assert work["task"] >= 1

        # 5. The agent drafts a message; the navigator reads it and sends it; it reaches Sahatna.
        d = agent.post(f"/v1/cases/{cid}/outreach-draft", headers=AISHA).json()
        assert d["draft"]["template"] == "FEAR" and d["draft"]["language"] == "ar"
        assert core.post(d["send_with"]["path"], headers=AISHA, json=d["send_with"]["body"]).status_code == 200
        notifier.run_once(now + timedelta(minutes=5))
        assert any(m.channel == "sahatna_push" and m.recipient_id == "p-hamad"
                   and d["draft"]["text"] in str(m.body) for m in notifier.provider.sent)

        # 6. Rebooked and attended; the colonoscopy report arrives over HL7; the outcome is communicated.
        later = now + timedelta(days=7)
        sch2 = f"SCH|E2E-APT2||||||||||^^^{hl7_time(later)}"
        send_hl7("\r".join([msh("SIU^S12", "E2E-SIU-3", now), sch2, "PID|1||p-hamad"]))
        fhir({"resourceType": "Appointment", "id": "E2E-APT2", "status": "fulfilled",
              "meta": {"lastUpdated": later.isoformat(), "versionId": "9"},
              "participant": [{"actor": {"reference": "Patient/p-hamad"}}]})
        fhir({"resourceType": "Procedure", "id": "e2e-proc", "status": "completed",
              "subject": {"reference": "Patient/p-hamad"}, "code": {"coding": [{"code": "73761001"}]},
              "performedDateTime": later.isoformat()})
        send_hl7("\r".join([msh("ORU^R01", "E2E-LAB-2", later + timedelta(days=1)), "PID|1||p-hamad",
                            f"OBR|1|O2|F2|18746-8^Colonoscopy study^LN|||||||||||||||||{hl7_time(later)}||||F"]))
        fhir(comm("p-hamad", "e2e-out", later + timedelta(days=2), "outcome-notification"))

        # 7. Only a person closes, only with the evidence (R3, R5); the audit chain verifies (R6).
        acts = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()["actions"]["close"]
        assert next(a for a in acts if a["outcome"] == "COMPLETED_WITH_REPORT")["allowed"]
        closed = core.post(f"/v1/cases/{cid}/close", headers=FATIMA, json={"outcome": "COMPLETED_WITH_REPORT"})
        assert closed.status_code == 200 and closed.json()["outcome"]["care_completed"] is True
        audit = core.get(f"/v1/cases/{cid}/audit", headers=FATIMA).json()
        assert audit["verification"]["ok"] and audit["verification"]["checked"] > 15
        assert {"integration", "system", "navigator", "clinician", "patient"} <= {
            e["actor_type"] for e in audit["events"]}
        # The AI draft is not an actor in the case: a person sent it, and the event records which draft.
        sent = [e for e in core.get(f"/v1/cases/{cid}", headers=FATIMA).json()["timeline"]
                if e["type"] == "PATIENT_MESSAGE_SENT"]
        assert sent[-1]["actor"] == "nav-aisha" and sent[-1]["payload"]["ai_draft_id"] == d["draft_id"]
        notifier.run_once(later + timedelta(days=3))
        assert any(m.channel == "sahatna_push" and m.recipient_id == "p-hamad" for m in notifier.provider.sent[-3:])
