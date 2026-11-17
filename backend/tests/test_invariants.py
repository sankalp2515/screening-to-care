"""Randomized command sequences: R1, R3, R4 and R5 must hold after every step.

A seeded random walk over every command, with random (including machine and wrong) actors. Commands the engine
refuses are fine; what must never happen is an accepted state that breaks a rule.
Set TASLEEM_INVARIANT_RUNS to run more sequences.
"""

from __future__ import annotations

import os
import random
from datetime import timedelta

from conftest import AI, COORD, FP, FP2, INTEG, NAV, PATIENT, SYS, T0, Case

from tasleem.domain import engine
from tasleem.domain.barriers import KeywordBarrierClassifier
from tasleem.domain.errors import DomainError
from tasleem.domain.model import (
    NON_HUMAN_TYPES,
    STAFF_TYPES,
    ActorType,
    AdminStatus,
    BarrierCode,
    EventType,
    Outcome,
    SignalKind,
)

RUNS = int(os.environ.get("TASLEEM_INVARIANT_RUNS", "2000"))
STEPS = 14
ACTORS = [FP, FP2, NAV, COORD, PATIENT, AI, SYS, INTEG]
TEXTS = ["scared", "no one to take me home", "I saw blood", "ok", "ما فهمت التحضير", "call me"]
CLS = KeywordBarrierClassifier()
D = timedelta(days=1)

AI_ALLOWED = {EventType.BARRIER_SUGGESTED}
HUMAN_DECISIONS = {EventType.CASE_CLOSED, EventType.HANDOFF_ACCEPTED, EventType.BARRIER_CONFIRMED,
                   EventType.DISTRESS_RESOLVED, EventType.HANDOFF_OFFERED}


def _random_command(rng: random.Random, c: Case, now):
    st, p = c.state, c.p
    a = rng.choice(ACTORS)
    k = rng.randrange(12)
    if k == 0:
        kind = rng.choice([SignalKind.PATIENT_INVITED, SignalKind.RESULT_DISCUSSED, SignalKind.REFERRAL_SENT,
                           SignalKind.REFERRAL_ACCEPTED, SignalKind.APPOINTMENT_ATTENDED,
                           SignalKind.APPOINTMENT_NOSHOW, SignalKind.REFERRAL_REJECTED,
                           SignalKind.OUTCOME_COMMUNICATED])
        return engine.record_signal(st, p, _sig(kind, now), INTEG)
    if k == 1:
        return engine.record_signal(st, p, _sig(SignalKind.APPOINTMENT_BOOKED, now, appointment_at=now + 3 * D), INTEG)
    if k == 2:
        return engine.record_signal(st, p, _sig(SignalKind.REPORT_FINAL, now, codes=["18746-8"]), INTEG)
    if k == 3:
        return engine.record_signal(st, p, _sig(SignalKind.ADMIN_STATUS, now,
                                                admin_status=rng.choice(list(AdminStatus))), INTEG)
    if k == 4:
        return engine.offer_handoff(st, a, rng.choice(["dr-fp", "dr-fp2", "nav"]), "r", now)
    if k == 5:
        return rng.choice([engine.accept_handoff, lambda s, x, n: engine.reject_handoff(s, x, "NO", n)])(st, a, now)
    if k == 6:
        codes = rng.sample(list(BarrierCode), rng.randrange(0, 3))
        return engine.report_barrier(st, a, barrier_id=f"b{st.version}", distress_id=f"d{st.version}", codes=codes,
                                     text=rng.choice(TEXTS + [None]), now=now, classifier=CLS, resolver=_resolver)
    if k == 7 and st.barriers:
        return engine.confirm_barrier(st, p, a, rng.choice(list(st.barriers)), rng.choice(list(BarrierCode)), now)
    if k == 8 and st.distress:
        return engine.resolve_distress(st, a, rng.choice(list(st.distress)), "done", now)
    if k == 9:
        return engine.log_contact(st, a, "phone", "no_answer", now)
    if k == 10:
        return engine.request_consult(st, p, a, f"k{st.version}", "dr-gi", "q?", now)
    return engine.close_case(st, p, a, rng.choice(list(Outcome)), evidence_ref=rng.choice([None, "Doc/1"]),
                             reason=rng.choice([None, "clinical reason"]), now=now)


def _sig(kind, t, **kw):
    from conftest import sig

    return sig(kind, t, **kw)


def _resolver(state, target):
    from conftest import resolver

    return resolver(state, target)


def _check(c: Case) -> None:
    st, p = c.state, c.p
    # R1: an open case always has a named owner.
    if st.is_open:
        assert st.owner_id
    # R3: closure only with what the outcome requires, signed by human staff.
    if not st.is_open:
        closed = [e for e in c.events if e.type == EventType.CASE_CLOSED]
        assert len(closed) == 1
        assert closed[0].actor_type in STAFF_TYPES
        assert not st.open_distress
        if st.outcome == Outcome.COMPLETED_WITH_REPORT:
            assert all(s in st.stages for s in p.closure.completion_stages)
        else:
            assert closed[0].actor_type == ActorType.CLINICIAN
        if st.outcome in (Outcome.COMPLETED_ELSEWHERE, Outcome.INFORMED_REFUSAL):
            assert st.outcome_evidence_ref
        if st.outcome in (Outcome.PLAN_CHANGED, Outcome.INFORMED_REFUSAL):
            assert st.outcome_reason
    for i, e in enumerate(c.events):
        # R5: machines never take human decisions; AI only suggests.
        if e.actor_type == ActorType.AI:
            assert e.type in AI_ALLOWED
        if e.type in HUMAN_DECISIONS:
            assert e.actor_type not in NON_HUMAN_TYPES and e.actor_type != ActorType.PATIENT
        # R4: every flagged stall escalates to a named person in the same step.
        if e.type == EventType.STALL_FLAGGED:
            nxt = c.events[i + 1]
            assert nxt.type == EventType.ESCALATED and nxt.payload["to_id"]


def test_invariants_hold_across_random_command_sequences(fit):
    rng = random.Random(20261116)
    accepted = refused = 0
    for _ in range(RUNS):
        c = Case(fit)
        now = T0
        for _ in range(STEPS):
            now = now + timedelta(hours=rng.choice([1, 12, 24, 72, 120]))
            if not c.state.is_open:
                break
            try:
                cmd = _random_command(rng, c, now)
            except DomainError:
                refused += 1
                continue
            c.run(cmd or [], now)
            accepted += 1
            _check(c)
        assert engine.replay(c.events).model_dump() == c.state.model_dump()
    assert accepted > RUNS and refused > RUNS  # both paths were exercised
