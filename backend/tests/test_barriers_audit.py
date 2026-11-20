from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import T0, Case

from tasleem.domain.audit import GENESIS, StoredEvent, event_hash, verify
from tasleem.domain.barriers import KeywordBarrierClassifier, detect_distress
from tasleem.domain.model import BarrierCode, SignalKind

CLS = KeywordBarrierClassifier()


@pytest.mark.parametrize(
    "text,code",
    [
        ("I'm scared of the sedation", BarrierCode.FEAR),
        ("انا خايفة من الفحص", BarrierCode.FEAR),
        ("I don't understand the bowel prep", BarrierCode.PREP_UNCLEAR),
        ("ما فهمت التحضير", BarrierCode.PREP_UNCLEAR),
        ("There is no one to take me home after", BarrierCode.NO_ESCORT),
        ("ما في احد يوصلني", BarrierCode.NO_ESCORT),
        ("My insurance says it is not covered", BarrierCode.COST_OR_INSURANCE),
        ("I can't get leave from work that day", BarrierCode.TIME_OR_WORK),
        ("I need an interpreter", BarrierCode.LANGUAGE),
        ("I would feel better with a female doctor", BarrierCode.FEMALE_CLINICIAN),
        ("أفضل طبيبة للفحص", BarrierCode.FEMALE_CLINICIAN),
        ("Honestly I feel embarrassed with a male doctor", BarrierCode.FEMALE_CLINICIAN),
        ("Please call me back", BarrierCode.WANTS_CALLBACK),
        ("I already did it at another hospital", BarrierCode.DONE_ELSEWHERE),
    ],
)
def test_classifier_suggests_expected_code(text, code):
    s = CLS.classify(text)
    assert s is not None and s.code == code and 0 < s.confidence <= 1


def test_classifier_abstains_on_unrelated_text():
    assert CLS.classify("ok thanks") is None


@pytest.mark.parametrize("text", ["I saw blood", "black stool since Monday", "I am terrified", "فيه نزيف",
                                  "شفت الدم", "I can't cope anymore"])
def test_distress_detected(text):
    assert detect_distress(text)


@pytest.mark.parametrize("text", ["I live in Spain", "عدم وجود موعد", "bloodwork is fine? no, it's the bus"])
def test_distress_whole_word_matching(text):
    # "pain" inside "Spain", "دم" inside "عدم" must not match; "bloodwork" is not "blood".
    assert detect_distress(text) == []


def _stored(fit) -> list[StoredEvent]:
    c = Case(fit)
    c.signal(SignalKind.PATIENT_INVITED, T0)
    c.tick(T0.replace(day=20))
    out, prev = [], GENESIS
    for i, e in enumerate(c.events, start=1):
        payload = e.model_dump(mode="json")["payload"]
        h = event_hash(prev, "c1", i, e.type.value, e.actor_id, e.actor_type.value, e.occurred_at, payload)
        out.append(StoredEvent("c1", i, e.type.value, e.actor_id, e.actor_type.value, e.occurred_at, payload, prev, h))
        prev = h
    return out


def test_audit_chain_verifies(fit):
    ev = _stored(fit)
    v = verify(ev)
    assert v.ok and v.checked == len(ev)


def test_audit_detects_tampered_payload(fit):
    ev = _stored(fit)
    ev[1] = replace(ev[1], payload={**ev[1].payload, "ref": "forged"})
    v = verify(ev)
    assert not v.ok and v.broken_at_seq == 2


def test_audit_detects_deleted_and_reordered_events(fit):
    ev = _stored(fit)
    assert verify(ev[:1] + ev[2:]).broken_at_seq == 3
    swapped = [ev[0], ev[2], ev[1]] + ev[3:]
    assert not verify(swapped).ok


@pytest.mark.parametrize("text,flag", [
    ("No bleeding, just nervous", False),
    ("بدون نزيف، بس خايف شوي", False),
    ("Not bleeding much but it hurts", True),       # "not" is not a denial: a red flag is never cleared on a guess
    ("No bleeding yesterday, but blood today", True),  # one denied mention does not hide another
    ("I saw blood", True),
])
def test_denied_symptoms_are_not_red_flags_but_doubt_still_is(text, flag):
    """TSL-186: an explicit denial ('no bleeding') is not distress; anything less certain still flags."""
    assert bool(detect_distress(text)) is flag


def test_audit_anchor_detects_rewritten_history():
    """TSL-173: a root published earlier no longer matches once any event before it is changed, even if the
    attacker recomputes that case's own chain."""
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from tasleem.api.app import create_app
    from tasleem.audit_anchor import anchor
    from tasleem.config import Settings
    from tasleem.infra.db import CaseEventRow

    app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True, rate_limit_per_second=0))
    with TestClient(app) as c:
        published = c.get("/v1/program/audit-anchor", headers={"X-Demo-User": "coord-sara"}).json()
        assert published["cases"] > 5 and len(published["root"]) == 64
        assert c.get("/v1/program/audit-anchor", headers={"X-Demo-User": "dr-fatima"}).status_code == 403
        with app.state.ctx.sessions() as s:
            as_of = datetime.fromisoformat(published["as_of"])
            assert anchor(s, as_of)["root"] == published["root"]          # stable for the same moment
            # A rewrite that recomputes a case's own chain (so per-case verification passes) still ends in a
            # different head hash for that case. Simulate exactly that: the head of one chain changes.
            q = select(CaseEventRow).order_by(CaseEventRow.case_id, CaseEventRow.seq.desc())
            head = s.execute(q).scalars().first()
            head.hash = "0" * 64
            s.commit()
            assert anchor(s, as_of)["root"] != published["root"]
    _ = UTC
