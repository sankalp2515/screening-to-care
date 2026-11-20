"""Case-core additions: patient messages under the IFHAS policy, delivery-failure loop, teach-back,
metrics filters, usage metering, scoped integration keys, hardening and migrations."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import as_
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from tasleem.api.app import create_app
from tasleem.config import Settings
from tasleem.domain.messaging import check_patient_text
from tasleem.infra.db import Base
from tasleem.migrate import migrate

ROOT = Path(__file__).resolve().parents[1]
FATIMA, SALMA, AISHA, SARA = as_("dr-fatima"), as_("dr-salma"), as_("nav-aisha"), as_("coord-sara")


def _case(c: TestClient, pid: str) -> dict:
    items = c.get("/v1/cases", params={"status": "all", "limit": 500}, headers=SARA).json()["items"]
    return next(i for i in items if i["patient"]["id"] == pid and i["status"] == "open")


# ---- message policy ------------------------------------------------------------------------------
@pytest.mark.parametrize("text,code", [
    ("Your FIT result was 9.2, please come in.", "RESULT_VALUE"),
    ("Blood pressure 162/95 needs review.", "RESULT_VALUE"),
    ("Your test was positive.", "RESULT_DISCLOSURE"),
    ("We found a polyp.", "RESULT_DISCLOSURE"),
    ("نتيجة الفحص إيجابي", "RESULT_DISCLOSURE"),
    ("نتائجك لدى طبيبك وسيتواصل معك", "RESULT_DISCLOSURE"),
    ("You are fine, nothing to worry about.", "CLINICAL_ADVICE"),
    ("Book here: www.example.com/book", "LINK"),
    ("", "EMPTY"),
])
def test_message_policy_blocks_disclosure_and_advice(text, code):
    assert code in {v.code for v in check_patient_text(text)}


def test_message_policy_allows_logistics():
    for ok in ("Your appointment is on 21 Nov at 9:30. Please bring your Emirates ID.",
               "Please call the clinic if anything could stop you from attending.",
               "يرجى الاتصال بالعيادة إذا كان هناك ما يمنعك من الحضور."):
        assert check_patient_text(ok) == [], ok


def test_staff_send_patient_message_goes_to_sahatna_with_provenance(client):
    cid = _case(client, "p-yousef")["id"]
    r = client.post(f"/v1/cases/{cid}/patient-messages", headers=FATIMA,
                    json={"text": "Please call the clinic to confirm your appointment.", "language": "ar",
                          "ai_draft_id": "drf_abc123"})
    assert r.status_code == 200, r.text
    ev = [e for e in r.json()["timeline"] if e["type"] == "PATIENT_MESSAGE_SENT"][-1]
    assert ev["actor"] == "dr-fatima" and ev["payload"]["ai_assisted"] is True  # R5: a person sent it
    note = [n for n in r.json()["notifications"] if n["template"] == "care_team_message"][-1]
    assert note["channel"] == "sahatna" and note["recipient_role"] == "patient"


def test_message_that_discloses_a_result_is_refused(client):
    cid = _case(client, "p-yousef")["id"]
    r = client.post(f"/v1/cases/{cid}/patient-messages", headers=FATIMA,
                    json={"text": "Your result is positive, we need to talk.", "language": "en"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "IFHAS_MESSAGE_POLICY"
    assert client.post("/v1/policy/patient-message-check", headers=FATIMA,
                       json={"text": "Your result is positive"}).json()["ok"] is False


def test_patients_and_other_clinics_cannot_send(client):
    cid = _case(client, "p-yousef")["id"]
    body = {"text": "Please call the clinic.", "language": "en"}
    assert client.post(f"/v1/cases/{cid}/patient-messages", headers=as_("p-yousef"), json=body).status_code == 403
    assert client.post(f"/v1/cases/{cid}/patient-messages", headers=SALMA, json=body).status_code == 404


# ---- delivery failure -> navigator call task -----------------------------------------------------
def test_patient_unreached_by_any_channel_becomes_navigator_task(client):
    cid = client.post("/v1/demo/scenarios/unreachable-patient").json()["case_id"]
    out = client.get(f"/v1/cases/{cid}/notifications", headers=FATIMA).json()["items"]
    sahatna = next(m for m in out if m["channel"] == "sahatna")
    r = client.post("/v1/integration/delivery-failures",
                    json={"outbox_id": sahatna["id"], "channels": ["sahatna_push", "sms_nudge"]})
    assert r.json() == {"recorded": True, "case_id": cid, "navigator_task": True}
    again = client.post("/v1/integration/delivery-failures", json={"outbox_id": sahatna["id"], "channels": ["x"]})
    assert again.status_code == 200  # idempotent
    detail = client.get(f"/v1/cases/{cid}", headers=AISHA).json()
    assert detail["next_step"]["reason"] == "PATIENT_NOT_REACHED"
    assert sum(e["type"] == "DELIVERY_FAILED" for e in detail["timeline"]) == 1
    work = {s["kind"]: s for s in client.get("/v1/me/work", headers=AISHA).json()["sections"]}
    assert any(i["id"] == cid for i in work["task"]["items"])
    # A person calling clears the task, whatever the result.
    client.post(f"/v1/cases/{cid}/contact-attempts", headers=AISHA, json={"channel": "phone", "result": "reached"})
    assert client.get(f"/v1/cases/{cid}", headers=AISHA).json()["next_step"]["reason"] != "PATIENT_NOT_REACHED"


def test_staff_alert_failure_is_not_a_case_event(client):
    cid = client.post("/v1/demo/scenarios/distress-message").json()["case_id"]
    emr = next(m for m in client.get(f"/v1/cases/{cid}/notifications", headers=FATIMA).json()["items"]
               if m["channel"] == "emr_inbox")
    r = client.post("/v1/integration/delivery-failures", json={"outbox_id": emr["id"], "channels": ["emr_task"]})
    assert r.json()["recorded"] is False


# ---- teach-back ----------------------------------------------------------------------------------
def test_prep_teach_back_wrong_answers_open_barriers(client):
    cid = _case(client, "p-yousef")["id"]
    q = client.get(f"/v1/me/cases/{cid}/prep-check", headers=as_("p-yousef")).json()
    assert q["direction"] == "rtl" and len(q["questions"]) == 3
    assert "correct" not in str(q)  # answers never reach the client
    r = client.post(f"/v1/me/cases/{cid}/prep-check", headers=as_("p-yousef"),
                    json={"answers": {"diet": "day_before", "home": "drive", "unfinished": "call"}}).json()
    assert r["follow_up_needed"] and r["barrier_codes"] == ["NO_ESCORT"]
    ok = client.post(f"/v1/me/cases/{cid}/prep-check", headers=as_("p-yousef"),
                     json={"answers": {"diet": "day_before", "home": "adult", "unfinished": "call"}}).json()
    assert ok["all_correct"] and ok["barrier_id"] is None
    assert client.get(f"/v1/me/cases/{cid}/prep-check", headers=as_("p-noura")).status_code == 404
    hamad = _case(client, "p-hamad")["id"]  # HbA1c pathway has no bowel preparation
    assert client.get(f"/v1/me/cases/{hamad}/prep-check", headers=as_("p-hamad")).status_code == 404


# ---- programme view ------------------------------------------------------------------------------
def test_metrics_filter_by_provider_and_language(client):
    all_ = client.get("/v1/program/metrics", headers=SARA).json()["cases"]["total"]
    ghaf = client.get("/v1/program/metrics", params={"org": "org-ghaf"}, headers=SARA).json()
    samar = client.get("/v1/program/metrics", params={"org": "org-samar"}, headers=SARA).json()["cases"]["total"]
    assert ghaf["filters"]["org"] == "org-ghaf" and ghaf["cases"]["total"] + samar <= all_
    ar = client.get("/v1/program/metrics", params={"language": "ar"}, headers=SARA).json()["cases"]["total"]
    en = client.get("/v1/program/metrics", params={"language": "en"}, headers=SARA).json()["cases"]["total"]
    assert 0 < ar < all_ and ar + en == all_


def test_usage_metering_is_coordinator_only(client):
    from datetime import UTC, datetime

    month = datetime.now(UTC).strftime("%Y-%m")
    r = client.get("/v1/program/usage", params={"month": month}, headers=SARA).json()
    assert r["active_cases"] >= 12 and {o["org_id"] for o in r["by_org"]} >= {"org-ghaf", "org-samar"}
    assert client.get("/v1/program/usage", params={"month": month}, headers=FATIMA).status_code == 403
    assert client.get("/v1/program/usage", params={"month": "2026-13"}, headers=SARA).status_code == 422


# ---- integration keys, hardening -----------------------------------------------------------------
def test_integration_keys_are_scoped_per_service():
    s = Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True, rate_limit_per_second=0,
                 integration_keys={"connector": "conn-key", "notifier": "notif-key"})
    with TestClient(create_app(s)) as c:
        obs = {"resourceType": "Observation", "id": "o1", "status": "final", "subject": {"reference": "Patient/x"},
               "code": {"coding": [{"code": "29771-3"}]}, "effectiveDateTime": "2026-11-01T08:00:00+00:00"}
        assert c.post("/v1/ingest/fhir", json=obs).status_code == 401
        assert c.post("/v1/ingest/fhir", json=obs, headers={"x-integration-key": "wrong"}).status_code == 401
        assert c.post("/v1/ingest/fhir", json=obs, headers={"x-integration-key": "notif-key"}).status_code == 403
        assert c.post("/v1/ingest/fhir", json=obs, headers={"x-integration-key": "conn-key"}).status_code == 200
        assert c.get("/v1/integration/outbox", headers={"x-integration-key": "conn-key"}).status_code == 403
        assert c.get("/v1/integration/outbox", headers={"x-integration-key": "notif-key"}).status_code == 200


def test_unsafe_production_config_refuses_to_start():
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        create_app(Settings(database_url="sqlite://", demo_mode=False))
    ok = Settings(database_url="postgresql+psycopg://u:p@db/x", demo_mode=False, cors_origins=["https://app"],
                  integration_keys={"connector": "k"}, auto_create_schema=False)
    assert create_app(ok) is not None  # builds; connects only when served


def test_demo_mode_is_off_by_default():
    assert Settings(_env_file=None).demo_mode is False


def test_rate_limit_and_security_headers():
    s = Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True, rate_limit_per_second=1,
                 rate_limit_burst=3)
    with TestClient(create_app(s)) as c:
        codes = [c.get("/v1/me", headers=FATIMA).status_code for _ in range(5)]
        assert codes[:3] == [200, 200, 200] and 429 in codes[3:]
        limited = c.get("/v1/me", headers=FATIMA)
        assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
        assert c.get("/v1/me", headers=SALMA).status_code == 200  # buckets are per caller
        assert all(c.get("/healthz").status_code == 200 for _ in range(10))  # probes are never limited
        h = c.get("/v1/me", headers=AISHA).headers
        assert h["cache-control"] == "no-store" and h["x-content-type-options"] == "nosniff"


# ---- migrations ----------------------------------------------------------------------------------
def test_alembic_migrations_match_the_models(tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    assert migrate(url) == "upgraded"
    engine = create_engine(url)
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diffs == [], f"models and migrations differ: {diffs}"


def test_migrate_stamps_a_database_created_by_create_all(tmp_path):
    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert migrate(url) == "stamped"
    assert migrate(url) == "upgraded"  # now managed; no-op upgrade


def test_migrate_upgrades_a_v01_database_missing_new_columns(tmp_path):
    """A database built by v0.1 create_all lacks outbox.recipient_role: stamping must not hide that."""
    from sqlalchemy import inspect, text

    url = f"sqlite:///{(tmp_path / 'v01.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE outbox DROP COLUMN recipient_role"))
    assert "recipient_role" not in {c["name"] for c in inspect(engine).get_columns("outbox")}
    engine.dispose()
    assert migrate(url) == "stamped"
    engine = create_engine(url)
    assert "recipient_role" in {c["name"] for c in inspect(engine).get_columns("outbox")}
    engine.dispose()


# ---- architecture fitness ------------------------------------------------------------------------
SATELLITES = ("tasleem_notifier", "tasleem_agent", "tasleem_connector", "tasleem_common")
CORE_RUNTIME = ("api", "domain", "services", "infra", "workers")


def _imports(pkg_dir: Path) -> set[str]:
    names: set[str] = set()
    for f in pkg_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


def test_service_boundaries_hold():
    """Satellites reach case-core only over HTTP; case-core never depends on a satellite."""
    for pkg in SATELLITES:
        assert "tasleem" not in _imports(ROOT / pkg), f"{pkg} imports case-core internals"
    for pkg in ("tasleem_notifier", "tasleem_agent", "tasleem_connector"):
        others = set(SATELLITES) - {pkg, "tasleem_common"}
        assert not (_imports(ROOT / pkg) & others), f"{pkg} imports another service"
    for sub in CORE_RUNTIME:
        bad = _imports(ROOT / "tasleem" / sub) & {"tasleem_notifier", "tasleem_agent", "tasleem_connector"}
        assert not bad, f"case-core {sub} imports {bad}"
