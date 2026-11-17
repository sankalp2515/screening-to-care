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
