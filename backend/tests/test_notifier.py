"""Notifier: channel per kind of person, fallback, quiet hours, digest, receipts, at-least-once hand-over.

Runs against the real case-core app through a TestClient, so the outbox contract is tested end to end.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import yaml
from conftest import as_
from fastapi.testclient import TestClient
from sqlalchemy import select

from tasleem.api.app import create_app
from tasleem.config import Settings
from tasleem_common.http import ServiceClient
from tasleem_notifier.adapters import SMS_NUDGE, Outgoing, SandboxProvider, WebhookProvider, verify_signature
from tasleem_notifier.app import NotifierSettings, build_notifier
from tasleem_notifier.app import create_app as notifier_app
from tasleem_notifier.policy import DEFAULT_POLICY, Policy
from tasleem_notifier.store import DeliveryRow, NotificationRow

# 10:00 in Abu Dhabi (06:00 UTC): outside quiet hours, after the 07:00 digest hour.
DAY = datetime(2026, 11, 17, 6, 0, tzinfo=UTC)


@pytest.fixture
def core():
    app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True,
                              rate_limit_per_second=0, metrics_max_staleness_seconds=0))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def notifier(core):
    return build_notifier(NotifierSettings(database_url="sqlite://", demo_mode=True), ServiceClient(client=core))


def _rows(n, case_id: str) -> list[NotificationRow]:
    with n.sessions() as s:
        return list(s.execute(select(NotificationRow).where(NotificationRow.case_id == case_id)
                              .order_by(NotificationRow.id)).scalars())


def _deliveries(n, notification_id: int) -> list[DeliveryRow]:
    with n.sessions() as s:
        return list(s.execute(select(DeliveryRow).where(DeliveryRow.notification_id == notification_id)
                              .order_by(DeliveryRow.step)).scalars())


# ---- policy (pure) -------------------------------------------------------------------------------
def test_each_kind_of_person_has_its_own_channels():
    p = Policy.load()
    assert [s.channel for s in p.steps_for("patient", False)[0]] == ["sahatna_push", "sms_nudge"]
    assert p.steps_for("family_physician", False) == (p.route("family_physician").steps, False)
    steps, parallel = p.steps_for("family_physician", True)
    assert parallel and [s.channel for s in steps] == ["emr_task", "sms_page"]
    assert [s.channel for s in p.steps_for("navigator", False)[0]] == ["worklist"]
    assert [s.channel for s in p.steps_for("program_coordinator", False)[0]] == ["email_digest"]
    assert p.route("someone_new") == p.route("default")


def test_quiet_hours_hold_routine_patient_messages_only():
    p = Policy.load()
    late = datetime(2026, 11, 17, 19, 30, tzinfo=UTC)  # 23:30 local
    release = p.quiet_until("patient", False, late)
    assert release is not None and release.astimezone(p.tz).hour == 8 and release > late
    assert p.quiet_until("patient", True, late) is None  # urgent never waits
    assert p.quiet_until("family_physician", False, late) is None  # staff inboxes are not held
    assert p.quiet_until("patient", False, DAY) is None


def test_policy_rejects_staff_channel_for_patients(tmp_path: Path):
    data = yaml.safe_load(DEFAULT_POLICY.read_text(encoding="utf-8"))
    data["recipients"]["patient"]["steps"] = [{"channel": "emr_task"}]
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="staff channel"):
        Policy.load(bad)


# ---- flows against case-core ---------------------------------------------------------------------
def test_patient_gets_sahatna_then_sms_and_sms_carries_no_content(core, notifier):
    cid = core.post("/v1/demo/scenarios/new-positive-fit").json()["case_id"]
    notifier.run_once(DAY)
    patient = next(r for r in _rows(notifier, cid) if r.recipient_role == "patient")
    assert patient.status == "waiting"  # pushed; waiting to be opened
    assert [d.channel for d in _deliveries(notifier, patient.id)] == ["sahatna_push"]
    notifier.run_once(DAY + timedelta(hours=25))  # not opened in 24 h -> SMS nudge
    patient = next(r for r in _rows(notifier, cid) if r.recipient_role == "patient")
    assert patient.status == "done"
    assert [d.channel for d in _deliveries(notifier, patient.id)] == ["sahatna_push", "sms_nudge"]
    sms = [m for m in notifier.provider.sent if m.channel == "sms_nudge" and m.recipient_id == patient.recipient_id]
    assert sms and sms[-1].body["text"] in SMS_NUDGE.values() and cid not in json.dumps(sms[-1].body)


def test_read_receipt_stops_the_fallback(core, notifier):
    cid = core.post("/v1/demo/scenarios/new-positive-fit").json()["case_id"]
    notifier.run_once(DAY)
    patient = next(r for r in _rows(notifier, cid) if r.recipient_role == "patient")
    push = _deliveries(notifier, patient.id)[0]
    assert notifier.receipt(push.id, "read", DAY + timedelta(hours=1))["notification_status"] == "done"
    notifier.run_once(DAY + timedelta(hours=30))
    assert [d.channel for d in _deliveries(notifier, patient.id)] == ["sahatna_push"]


def test_distress_pages_the_clinician_on_every_urgent_channel(core, notifier):
    cid = core.post("/v1/demo/scenarios/distress-message").json()["case_id"]
    notifier.run_once(DAY)
    alert = next(r for r in _rows(notifier, cid) if r.template == "distress_alert")
    assert alert.urgent and alert.status == "done"
    assert sorted(d.channel for d in _deliveries(notifier, alert.id)) == ["emr_task", "sms_page"]
    page = next(m for m in notifier.provider.sent if m.channel == "sms_page" and m.recipient_id == alert.recipient_id)
    assert "blood" not in json.dumps(page.body).lower()  # the page says "check your inbox", nothing else


def test_unreachable_patient_comes_back_as_a_navigator_task_once(core, notifier):
    cid = core.post("/v1/demo/scenarios/unreachable-patient").json()["case_id"]
    first = notifier.run_once(DAY)
    assert first["reported_unreached"] == 1
    patient = next(r for r in _rows(notifier, cid) if r.recipient_role == "patient")
    assert patient.status == "exhausted" and not patient.report_pending
    assert [d.status for d in _deliveries(notifier, patient.id)] == ["failed", "failed"]
    detail = core.get(f"/v1/cases/{cid}", headers=as_("nav-aisha")).json()
    assert detail["next_step"]["reason"] == "PATIENT_NOT_REACHED"
    assert notifier.run_once(DAY + timedelta(hours=1))["reported_unreached"] == 0


def test_coordinator_gets_one_digest_per_day(core, notifier):
    core.post("/v1/demo/scenarios/new-positive-fit", json={"no_family_physician": True})
    early = datetime(2026, 11, 17, 1, 0, tzinfo=UTC)  # 05:00 local, before digest hour
    assert notifier.run_once(early)["digests"] == 0
    assert notifier.run_once(DAY)["digests"] >= 1
    core.post("/v1/demo/scenarios/new-positive-fit", json={"no_family_physician": True})
    assert notifier.run_once(DAY + timedelta(hours=2))["digests"] == 0  # tomorrow's digest
    digests = [m for m in notifier.provider.sent if m.channel == "email_digest" and m.recipient_id == "coord-sara"]
    assert len(digests) == 1 and digests[0].body["items"]


def test_handover_is_at_least_once_and_never_duplicates(core, notifier):
    assert notifier.pull(DAY) > 0
    assert core.get("/v1/integration/outbox", params={"status": "pending"}).json()["items"] == []
    with notifier.sessions() as s:
        before = len(s.execute(select(NotificationRow)).scalars().all())
    # Simulate "stored but the ack was lost": put one message back to pending in case-core.
    from tasleem.infra.db import OutboxRow

    with core.app.state.ctx.sessions() as cs:
        row = cs.execute(select(OutboxRow).limit(1)).scalar_one()
        row.status = "pending"
        cs.commit()
    assert notifier.pull(DAY) == 0  # pulled again, stored once
    with notifier.sessions() as s:
        assert len(s.execute(select(NotificationRow)).scalars().all()) == before


# ---- providers -----------------------------------------------------------------------------------
def test_webhook_provider_signs_requires_https_and_retries_on_5xx():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["sig"] = req.headers["x-tasleem-signature"]
        seen["body"] = req.content
        seen["key"] = req.headers["idempotency-key"]
        return httpx.Response(503 if b"fail" in req.content else 200, json={"id": "gw-1", "status": "delivered"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    wp = WebhookProvider({"sms_nudge": "https://gw.example/sms"}, "s3cret", client=client)
    ok = wp.send(Outgoing("sms_nudge", "p-1", "42:1:sms_nudge", {"text": "hi"}))
    assert ok.status == "delivered" and ok.provider_ref == "gw-1" and seen["key"] == "42:1:sms_nudge"
    assert verify_signature("s3cret", seen["body"], seen["sig"])
    assert wp.send(Outgoing("sms_nudge", "p-1", "k", {"text": "fail"})).status == "retry"
    assert wp.send(Outgoing("emr_task", "p-1", "k", {})).status == "failed"  # no endpoint configured
    with pytest.raises(ValueError, match="https"):
        WebhookProvider({"sms_nudge": "http://gw.example"}, "s")


def test_sandbox_simulates_unreachable_patients():
    sb = SandboxProvider(no_app=["p-demo-unreach-*"], no_phone=["p-demo-unreach-*"])
    assert sb.send(Outgoing("sahatna_push", "p-demo-unreach-1", "k", {})).status == "failed"
    assert sb.send(Outgoing("sahatna_push", "p-noura", "k", {})).status == "sent"


def test_notifier_api_policy_and_signed_receipts(core):
    s = NotifierSettings(database_url="sqlite://", demo_mode=False, ops_key="ops", webhook_secret="whs")
    with TestClient(notifier_app(s, ServiceClient(client=core))) as c:
        assert c.get("/v1/policy").json()["recipients"][0]["recipient"] == "patient"
        assert c.get("/v1/notifications").status_code == 401
        assert c.post("/v1/run-once", headers={"x-ops-key": "ops"}).status_code == 200
        body = json.dumps({"delivery_id": 1, "status": "read"}).encode()
        assert c.post("/v1/receipts", content=body).status_code == 401
        import hashlib
        import hmac

        sig = "sha256=" + hmac.new(b"whs", body, hashlib.sha256).hexdigest()
        r = c.post("/v1/receipts", content=body, headers={"x-tasleem-signature": sig})
        assert r.status_code == 200 and r.json()["status"] == "read"
        trail = c.get("/v1/notifications", headers={"x-ops-key": "ops"}).json()["items"]
        assert trail and all("deliveries" in t for t in trail)


def test_notifier_refuses_to_start_without_ops_key():
    with pytest.raises(RuntimeError):
        notifier_app(NotifierSettings(database_url="sqlite://", demo_mode=False))


def test_new_messages_after_a_core_reset_are_not_mistaken_for_old_ones(core, notifier):
    """Found on the Docker stack, 17 Nov: reset-demo restarts case-core's outbox ids. Keying on the id made
    the notifier ack new messages as duplicates and never deliver them."""
    notifier.run_once(DAY)
    assert core.post("/v1/admin/reset-demo").status_code == 200
    cid = core.post("/v1/demo/scenarios/unreachable-patient").json()["case_id"]
    assert notifier.run_once(DAY)["reported_unreached"] == 1
    assert core.get(f"/v1/cases/{cid}", headers=as_("nav-aisha")).json()["next_step"]["reason"] == "PATIENT_NOT_REACHED"
