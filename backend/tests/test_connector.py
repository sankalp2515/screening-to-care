"""HL7 v2 connector: parsing, mapping to FHIR / referral status, idempotency and ACK codes."""

from __future__ import annotations

import pytest
from conftest import as_
from fastapi.testclient import TestClient

from tasleem.api.app import create_app
from tasleem.config import Settings
from tasleem_common.http import ServiceClient
from tasleem_connector.app import ConnectorSettings
from tasleem_connector.app import create_app as connector_app
from tasleem_connector.hl7 import HL7Error, parse, ts

SARA, FATIMA = as_("coord-sara"), as_("dr-fatima")


def msh(kind: str, ctrl: str, when: str = "20261117093000") -> str:
    return f"MSH|^~\\&|LAB|SKMC|MALAFFI|DOH|{when}||{kind}|{ctrl}|P|2.5.1"


def oru_fit(pid: str, ctrl: str, flag: str = "A") -> str:
    return "\r".join([
        msh("ORU^R01^ORU_R01", ctrl), f"PID|1||{pid}^^^MALAFFI||DOE^JANE",
        "OBR|1|ORD1|FIL1|29771-3^FIT^LN|||20261117090000",
        f"OBX|1|ST|29771-3^Hemoglobin.gastrointestinal^LN||Positive||Negative|{flag}|||F|||20261117090000",
    ])


@pytest.fixture
def core():
    app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True, rate_limit_per_second=0))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def conn(core):
    with TestClient(connector_app(ConnectorSettings(demo_mode=True), ServiceClient(client=core))) as c:
        yield c


def _hl7(c, text: str, **headers):
    return c.post("/v1/hl7", content=text.encode(), headers={"content-type": "application/hl7-v2", **headers})


def _open_cases(core, pid: str) -> list[dict]:
    items = core.get("/v1/cases", params={"limit": 500}, headers=SARA).json()["items"]
    return [i for i in items if i["patient"]["id"] == pid]


# ---- parser --------------------------------------------------------------------------------------
def test_parser_handles_framing_escapes_and_components():
    m = parse("\x0b" + msh("ORU^R01", "C1") + "\rPID|1||p-1^^^MR~ALT||A\\S\\B\r\x1c\r")
    assert m.type == ("ORU", "R01") and m.control_id == "C1"
    pid = m.first("PID")
    assert pid.get(3) == "p-1" and pid.get(3, rep=2) == "ALT" and pid.get(5) == "A^B"
    assert ts("20261117093000").isoformat() == "2026-11-17T09:30:00+04:00"
    assert ts("202611170930+0000").utcoffset().total_seconds() == 0


@pytest.mark.parametrize("bad", ["", "PID|1||x", "MSH|^~\\&|A|B|C|D|2026||ORU^R01||P|2.5", "MSH|^~\\&\rbad seg|x"])
def test_parser_rejects_malformed_input(bad):
    with pytest.raises(HL7Error):
        parse(bad)


# ---- mapping into case-core ----------------------------------------------------------------------
def test_positive_fit_over_hl7_opens_a_case_once(core, conn):
    assert not _open_cases(core, "p-hamad") or all(c["pathway"]["id"] != "fit-positive-colonoscopy"
                                                   for c in _open_cases(core, "p-hamad"))
    r = _hl7(conn, oru_fit("p-hamad", "LAB-0001"))
    assert r.status_code == 200 and "MSA|AA|LAB-0001" in r.text
    again = _hl7(conn, oru_fit("p-hamad", "LAB-0001"))  # the lab resends the same message
    assert "MSA|AA" in again.text
    fit = [c for c in _open_cases(core, "p-hamad") if c["pathway"]["id"] == "fit-positive-colonoscopy"]
    assert len(fit) == 1 and fit[0]["owner"]["id"] == "dr-fatima"
    detail = core.get(f"/v1/cases/{fit[0]['id']}", headers=FATIMA).json()
    assert sum(e["type"] == "CASE_OPENED" for e in detail["timeline"]) == 1


def test_negative_or_preliminary_results_open_nothing(core, conn):
    neg = oru_fit("p-hamad", "LAB-0002", flag="N").replace("||Positive||", "||Negative||")
    assert "MSA|AA" in _hl7(conn, neg).text
    prelim = oru_fit("p-hamad", "LAB-0003").replace("|||F|||", "|||P|||")
    assert "MSA|AA" in _hl7(conn, prelim).text
    assert all(c["pathway"]["id"] != "fit-positive-colonoscopy" for c in _open_cases(core, "p-hamad"))


def test_unknown_patient_is_accepted_and_held_for_review(conn):
    r = _hl7(conn, oru_fit("p-nobody", "LAB-0004"))
    assert r.status_code == 200 and "MSA|AA" in r.text


def test_ref_status_is_admin_only_and_rejection_flags_a_stall(core, conn):
    _hl7(conn, oru_fit("p-hamad", "LAB-0005"))
    cid = next(c["id"] for c in _open_cases(core, "p-hamad") if c["pathway"]["id"] == "fit-positive-colonoscopy")
    rf1 = "RF1|{st}|R|COL^colonoscopy|||SR-HAMAD-1|20261117100000|||{reason}"
    ok = _hl7(conn, "\r".join([msh("REF^I12", "REF-1"), "PID|1||p-hamad", rf1.format(st="A", reason="")]))
    assert "MSA|AA" in ok.text
    detail = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()
    assert detail["progress"]["reported"]["admin_status"] == "ACCEPTED"
    assert detail["progress"]["verified"]["stage"] != "REFERRAL_ACCEPTED"  # status is not evidence
    rej = _hl7(conn, "\r".join([msh("REF^I13", "REF-2"), "PID|1||p-hamad",
                                rf1.format(st="R", reason="^Incomplete referral: no recent haemoglobin")]))
    assert "MSA|AA" in rej.text
    detail = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()
    assert any(s["reason"] == "REFERRAL_REJECTED" for s in detail["stalls"])


def test_siu_booking_and_no_show(core, conn):
    _hl7(conn, oru_fit("p-hamad", "LAB-0006"))
    cid = next(c["id"] for c in _open_cases(core, "p-hamad") if c["pathway"]["id"] == "fit-positive-colonoscopy")
    sch = "SCH|APT-H1||||||||||^^^20261201080000"
    assert "MSA|AA" in _hl7(conn, "\r".join([msh("SIU^S12", "SIU-1"), sch, "PID|1||p-hamad"])).text
    d = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()
    assert d["appointment_at"].startswith("2026-12-01")
    assert "MSA|AA" in _hl7(conn, "\r".join([msh("SIU^S26", "SIU-2", "20261201120000"), sch,
                                             "PID|1||p-hamad"])).text
    assert core.get(f"/v1/cases/{cid}", headers=FATIMA).json()["appointment_missed"] == "noshow"


def test_ack_codes_for_errors(core):
    with TestClient(connector_app(ConnectorSettings(demo_mode=True), ServiceClient(client=core))) as c:
        assert _hl7(c, "garbage").status_code == 422 and "MSA|AR" in _hl7(c, "garbage").text
        adt = "\r".join([msh("ADT^A01", "ADT-1"), "PID|1||p-hamad"])
        assert "MSA|AR" in _hl7(c, adt).text
        no_pid = "\r".join([msh("ORU^R01", "X-1"), "OBX|1|ST|29771-3^^LN||Positive|||A|||F"])
        r = _hl7(c, no_pid)
        assert r.status_code == 422 and "MSA|AE" in r.text and "PID-3" in r.text


def test_core_outage_returns_ae_503_so_the_sender_retries():
    class Down:
        def request(self, *a, **k):
            from tasleem_common.http import ServiceError

            raise ServiceError("down")

    with TestClient(connector_app(ConnectorSettings(demo_mode=True), Down())) as c:  # type: ignore[arg-type]
        r = _hl7(c, oru_fit("p-hamad", "LAB-9"))
    assert r.status_code == 503 and "MSA|AE" in r.text and "retry" in r.text


def test_sender_key_is_required_when_configured(core):
    s = ConnectorSettings(demo_mode=False, inbound_key="facility-key")
    with TestClient(connector_app(s, ServiceClient(client=core))) as c:
        assert _hl7(c, oru_fit("p-hamad", "LAB-10")).status_code == 401
        assert _hl7(c, oru_fit("p-hamad", "LAB-10"), **{"x-connector-key": "facility-key"}).status_code == 200
    with pytest.raises(RuntimeError):
        connector_app(ConnectorSettings(demo_mode=False))
