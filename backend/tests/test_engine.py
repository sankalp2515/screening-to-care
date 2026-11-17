"""Safety rules R1-R5 and every stall check, on the pure engine."""

from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import AI, COORD, FP, FP2, INTEG, NAV, PATIENT, SYS, T0, Case, resolver, sig

from tasleem.domain import checks, engine
from tasleem.domain.barriers import KeywordBarrierClassifier
from tasleem.domain.errors import DomainError
from tasleem.domain.model import AdminStatus, BarrierCode, EventType, Outcome, SignalKind, StallReason

D = timedelta(days=1)
CLS = KeywordBarrierClassifier()


def to_booked(c: Case, start: object = None) -> Case:
    c.signal(SignalKind.PATIENT_INVITED, T0 + 1 * D)
    c.signal(SignalKind.RESULT_DISCUSSED, T0 + 3 * D)
    c.signal(SignalKind.REFERRAL_SENT, T0 + 4 * D)
    c.signal(SignalKind.REFERRAL_ACCEPTED, T0 + 5 * D)
    c.signal(SignalKind.APPOINTMENT_BOOKED, T0 + 6 * D, appointment_at=start or T0 + 12 * D)
    return c


def to_complete(c: Case) -> Case:
    to_booked(c)
    c.signal(SignalKind.APPOINTMENT_ATTENDED, T0 + 12 * D)
    c.signal(SignalKind.PROCEDURE_COMPLETED, T0 + 12 * D, codes=["73761001"])
    c.signal(SignalKind.REPORT_FINAL, T0 + 14 * D, codes=["18746-8"])
    c.signal(SignalKind.OUTCOME_COMMUNICATED, T0 + 15 * D)
    return c


# ---- triggers ------------------------------------------------------------------------------------
def test_triggers(registry):
    fitp = registry.get("fit-positive-colonoscopy")
    a1c = registry.get("hba1c-diabetes-range")
    assert fitp.trigger.matches(sig(SignalKind.LAB_RESULT, T0, codes=["29771-3"], interpretation=["POS"]))
    assert not fitp.trigger.matches(sig(SignalKind.LAB_RESULT, T0, codes=["29771-3"], interpretation=["NEG"]))
    assert not fitp.trigger.matches(sig(SignalKind.LAB_RESULT, T0, codes=["4548-4"], interpretation=["POS"]))
    assert a1c.trigger.matches(sig(SignalKind.LAB_RESULT, T0, codes=["4548-4"], value=6.5))
    assert not a1c.trigger.matches(sig(SignalKind.LAB_RESULT, T0, codes=["4548-4"], value=6.4))


# ---- R1 ------------------------------------------------------------------------------------------
def test_r1_case_cannot_open_without_owner(fit):
    trig = sig(SignalKind.LAB_RESULT, T0, codes=["29771-3"], interpretation=["POS"])
    with pytest.raises(DomainError) as e:
        engine.open_case(case_id="c", patient_id="p1", pathway=fit, trigger=trig, owner_id="", actor=INTEG)
    assert e.value.code == "R1_OWNER_REQUIRED"


def test_priority_comes_from_pathway_not_ai(fit):
    c = Case(fit)
    assert c.state.priority == fit.priority
    assert c.state.owner_id == "dr-fp"


# ---- verified vs reported progress ---------------------------------------------------------------
def test_admin_status_never_advances_a_verified_stage(fit):
    c = Case(fit)
    c.signal(SignalKind.ADMIN_STATUS, T0 + D, admin_status=AdminStatus.COMPLETED)
    assert c.state.admin_status == AdminStatus.COMPLETED
    assert c.state.stages == {}


def test_closed_without_evidence_is_flagged_after_grace_and_clears_on_report(fit):
    c = to_booked(Case(fit))
    c.signal(SignalKind.APPOINTMENT_ATTENDED, T0 + 12 * D)
    c.signal(SignalKind.ADMIN_STATUS, T0 + 13 * D, admin_status=AdminStatus.COMPLETED)
    c.tick(T0 + 15 * D)
    assert "CLOSED_WITHOUT_EVIDENCE" not in c.state.stalls  # within the 3-day grace
    c.tick(T0 + 16 * D + timedelta(minutes=1))
    stall = c.state.stalls["CLOSED_WITHOUT_EVIDENCE"]
    assert stall.level == 1 and stall.escalated_to == "dr-fp"  # R4: named human
    c.signal(SignalKind.REPORT_FINAL, T0 + 17 * D, codes=["18746-8"])
    assert "CLOSED_WITHOUT_EVIDENCE" not in c.state.stalls


# ---- stall checks --------------------------------------------------------------------------------
def test_noshow_flags_booked_not_attended_and_rebooking_clears(fit):
    c = to_booked(Case(fit))
    c.signal(SignalKind.APPOINTMENT_NOSHOW, T0 + 12 * D)
    assert "BOOKED_NOT_ATTENDED" in c.state.stalls
    c.signal(SignalKind.APPOINTMENT_BOOKED, T0 + 13 * D, appointment_at=T0 + 20 * D)
    assert "BOOKED_NOT_ATTENDED" not in c.state.stalls


def test_appointment_time_passed_without_attendance(fit):
    c = to_booked(Case(fit), start=T0 + 12 * D)
    c.tick(T0 + 12 * D + timedelta(hours=23))
    assert "BOOKED_NOT_ATTENDED" not in c.state.stalls
    c.tick(T0 + 13 * D + timedelta(hours=1))
    assert "BOOKED_NOT_ATTENDED" in c.state.stalls


def test_step_overdue_and_escalation_ladder_is_named_and_capped(fit):
    c = Case(fit)
    c.tick(T0 + 3 * D + timedelta(hours=1))  # PATIENT_INVITED sla 3 days
    s = c.state.stalls["STEP_OVERDUE"]
    assert (s.level, s.escalated_to, s.stage) == (1, "dr-fp", "PATIENT_INVITED")
    c.tick(T0 + 6 * D + timedelta(hours=2))
    assert (c.state.stalls["STEP_OVERDUE"].level, c.state.stalls["STEP_OVERDUE"].escalated_to) == (2, "lead")
    c.tick(T0 + 9 * D + timedelta(hours=3))
    assert (c.state.stalls["STEP_OVERDUE"].level, c.state.stalls["STEP_OVERDUE"].escalated_to) == (3, "coord")
    n = c.state.escalation_count
    c.tick(T0 + 30 * D)
    assert c.state.stalls["STEP_OVERDUE"].level == 3 and c.state.escalation_count == n  # capped
    c.signal(SignalKind.PATIENT_INVITED, T0 + 30 * D)
    assert "STEP_OVERDUE" not in c.state.stalls


def test_consult_no_procedure(fit):
    c = to_booked(Case(fit))
    c.signal(SignalKind.APPOINTMENT_ATTENDED, T0 + 12 * D)
    c.tick(T0 + 34 * D)
    assert "CONSULT_NO_PROCEDURE" in c.state.stalls


def test_report_not_communicated(fit):
    c = to_complete(Case(fit))
    assert c.state.stalls == {}
    c2 = to_booked(Case(fit))
    c2.signal(SignalKind.REPORT_FINAL, T0 + 14 * D, codes=["18746-8"])
    c2.tick(T0 + 22 * D)
    assert "REPORT_NOT_COMMUNICATED" in c2.state.stalls


def test_referral_rejected_clears_on_new_referral(fit):
    c = Case(fit)
    c.signal(SignalKind.REFERRAL_SENT, T0 + D)
    c.signal(SignalKind.REFERRAL_REJECTED, T0 + 2 * D, reason="incomplete")
    assert "REFERRAL_REJECTED" in c.state.stalls
    c.signal(SignalKind.REFERRAL_SENT, T0 + 3 * D)
    assert "REFERRAL_REJECTED" not in c.state.stalls


# ---- R2 handoff ----------------------------------------------------------------------------------
def test_r2_two_step_handoff(fit):
    c = Case(fit)
    c.run(engine.offer_handoff(c.state, FP, "dr-fp2", "patient moved", T0 + D), T0 + D)
    assert c.state.owner_id == "dr-fp"  # sender stays owner
    with pytest.raises(DomainError) as e:
        engine.accept_handoff(c.state, NAV, T0 + D)
    assert e.value.code == "R2_NOT_HANDOFF_TARGET"
    with pytest.raises(DomainError) as e:
        engine.offer_handoff(c.state, FP, "nav", "again", T0 + D)
    assert e.value.code == "R2_HANDOFF_PENDING"
    c.run(engine.accept_handoff(c.state, FP2, T0 + D), T0 + D)
    assert c.state.owner_id == "dr-fp2" and c.state.pending_handoff is None


def test_r2_reject_keeps_owner_and_unaccepted_offer_stalls(fit):
    c = Case(fit)
    c.run(engine.offer_handoff(c.state, FP, "dr-fp2", "x", T0), T0)
    c.run(engine.reject_handoff(c.state, FP2, "NOT_MY_CATCHMENT", T0 + D), T0 + D)
    assert c.state.owner_id == "dr-fp"
    c.run(engine.offer_handoff(c.state, FP, "dr-fp2", "x", T0 + D), T0 + D)
    c.tick(T0 + 3 * D + timedelta(hours=1))
    assert "HANDOFF_NOT_ACCEPTED" in c.state.stalls


def test_r2_only_owner_or_coordinator_can_offer(fit):
    c = Case(fit)
    with pytest.raises(DomainError) as e:
        engine.offer_handoff(c.state, NAV, "dr-fp2", "x", T0)
    assert e.value.code == "R2_NOT_OWNER"
    assert engine.offer_handoff(c.state, COORD, "dr-fp2", "x", T0)


# ---- R3 / R5 closure -----------------------------------------------------------------------------
def test_r3_completed_needs_report_and_communication(fit):
    c = to_booked(Case(fit))
    with pytest.raises(DomainError) as e:
        engine.close_case(c.state, fit, FP, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None, now=T0)
    assert e.value.code == "R3_EVIDENCE_REQUIRED"
    assert e.value.details["missing_stages"] == ["REPORT_RECEIVED", "OUTCOME_COMMUNICATED"]
    c = to_complete(Case(fit))
    with pytest.raises(DomainError) as e:
        engine.close_case(c.state, fit, NAV, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None, now=T0)
    assert e.value.code == "R3_SIGNATURE_REQUIRED"
    c.run(engine.close_case(c.state, fit, FP, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None,
                            now=T0 + 16 * D), T0 + 16 * D)
    assert c.state.status == "closed" and c.state.closed_by == "dr-fp"


@pytest.mark.parametrize("actor", [AI, SYS, INTEG, PATIENT])
def test_r5_non_staff_can_never_close(fit, actor):
    c = to_complete(Case(fit))
    with pytest.raises(DomainError) as e:
        engine.close_case(c.state, fit, actor, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None, now=T0)
    assert e.value.code in ("R5_HUMAN_REQUIRED", "FORBIDDEN_ROLE")


@pytest.mark.parametrize(
    "outcome,evidence,reason,code",
    [
        (Outcome.COMPLETED_ELSEWHERE, None, None, "R3_EVIDENCE_REQUIRED"),
        (Outcome.INFORMED_REFUSAL, None, "declined", "R3_EVIDENCE_REQUIRED"),
        (Outcome.INFORMED_REFUSAL, "DocumentReference/1", None, "R3_REASON_REQUIRED"),
        (Outcome.PLAN_CHANGED, None, "  ", "R3_REASON_REQUIRED"),
        (Outcome.UNREACHABLE, None, None, "R3_CONTACT_ATTEMPTS"),
    ],
)
def test_r3_outcome_requirements(fit, outcome, evidence, reason, code):
    c = Case(fit)
    with pytest.raises(DomainError) as e:
        engine.close_case(c.state, fit, FP, outcome, evidence_ref=evidence, reason=reason, now=T0)
    assert e.value.code == code


def test_r3_non_completion_outcomes_need_a_clinician(fit):
    c = Case(fit)
    with pytest.raises(DomainError) as e:
        engine.close_case(c.state, fit, COORD, Outcome.PLAN_CHANGED, evidence_ref=None, reason="x", now=T0)
    assert e.value.code == "R3_SIGNATURE_REQUIRED"


def test_r3_unreachable_after_attempts_and_escalation(fit):
    c = Case(fit)
    c.tick(T0 + 4 * D)  # escalation
    for i in range(3):
        c.run(engine.log_contact(c.state, NAV, "phone", "no_answer", T0 + (4 + i) * D), T0 + (4 + i) * D)
    c.run(engine.close_case(c.state, fit, FP, Outcome.UNREACHABLE, evidence_ref=None, reason=None, now=T0 + 8 * D),
          T0 + 8 * D)
    assert c.state.outcome == Outcome.UNREACHABLE


def test_closed_case_refuses_commands(fit):
    c = to_complete(Case(fit))
    c.run(engine.close_case(c.state, fit, FP, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None,
                            now=T0 + 16 * D), T0 + 16 * D)
    with pytest.raises(DomainError) as e:
        engine.log_contact(c.state, NAV, "phone", "reached", T0 + 17 * D)
    assert e.value.code == "CASE_CLOSED"
    assert checks.next_check_at(c.state, fit, T0 + 17 * D) is None


# ---- barriers, distress --------------------------------------------------------------------------
def test_free_text_gets_ai_suggestion_then_human_confirms_playbook(fit):
    c = to_booked(Case(fit))
    evs = engine.report_barrier(c.state, PATIENT, barrier_id="b1", distress_id="d1", codes=[],
                                text="I don't understand the bowel prep instructions", now=T0 + 7 * D,
                                classifier=CLS, resolver=resolver)
    c.run(evs, T0 + 7 * D)
    sug = [e for e in evs if e.type == EventType.BARRIER_SUGGESTED][0]
    assert sug.actor_type.value == "ai"
    b = c.state.barriers["b1"]
    assert b.suggested_code == BarrierCode.PREP_UNCLEAR and b.status == "reported"
    with pytest.raises(DomainError):
        engine.confirm_barrier(c.state, fit, AI, "b1", BarrierCode.PREP_UNCLEAR, T0 + 7 * D)
    c.run(engine.confirm_barrier(c.state, fit, NAV, "b1", BarrierCode.PREP_UNCLEAR, T0 + 7 * D), T0 + 7 * D)
    b = c.state.barriers["b1"]
    assert (b.status, b.assignee_role, b.confirmed_by) == ("confirmed", "navigator", "nav")


def test_distress_routes_to_clinician_and_blocks_closure(fit):
    c = to_complete(Case(fit, owner="nav"))  # owner is not a clinician
    evs = engine.report_barrier(c.state, PATIENT, barrier_id="b1", distress_id="d1", codes=[],
                                text="There is blood and I am terrified", now=T0 + 16 * D, classifier=CLS,
                                resolver=resolver)
    c.run(evs, T0 + 16 * D)
    d = c.state.distress["d1"]
    assert d.routed_to == "dr-fp" and {"blood", "terrified"} <= set(d.matched)
    with pytest.raises(DomainError) as e:
        engine.close_case(c.state, fit, FP, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None, now=T0)
    assert e.value.code == "R3_DISTRESS_OPEN"
    with pytest.raises(DomainError) as e:
        engine.resolve_distress(c.state, NAV, "d1", "called", T0 + 16 * D)
    assert e.value.code == "R3_SIGNATURE_REQUIRED"
    c.run(engine.resolve_distress(c.state, FP, "d1", "Called, booked urgent review", T0 + 16 * D), T0 + 16 * D)
    c.run(engine.close_case(c.state, fit, FP, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None,
                            now=T0 + 17 * D), T0 + 17 * D)
    assert c.state.status == "closed"


def test_barrier_needs_codes_or_text(fit):
    c = Case(fit)
    with pytest.raises(DomainError):
        engine.report_barrier(c.state, PATIENT, barrier_id="b", distress_id="d", codes=[], text="  ", now=T0,
                              classifier=CLS, resolver=resolver)


# ---- consult bridge ------------------------------------------------------------------------------
def test_consult_unanswered_and_only_target_answers(fit):
    c = Case(fit)
    c.run(engine.request_consult(c.state, fit, FP, "k1", "dr-gi", "Anticoagulants before colonoscopy?", T0), T0)
    with pytest.raises(DomainError) as e:
        engine.answer_consult(c.state, NAV, "k1", "x", T0)
    assert e.value.code == "NOT_CONSULT_TARGET"
    c.tick(T0 + 2 * D + timedelta(hours=1))
    assert "CONSULT_UNANSWERED" in c.state.stalls


# ---- event sourcing ------------------------------------------------------------------------------
def test_replay_reproduces_state(fit):
    c = to_complete(Case(fit))
    c.tick(T0 + 40 * D)
    assert engine.replay(c.events).model_dump() == c.state.model_dump()


def test_next_check_is_the_earliest_deadline(fit):
    c = Case(fit)
    nxt = checks.next_check_at(c.state, fit, T0)
    assert nxt == T0 + 3 * D + timedelta(seconds=1)
    assert StallReason.STEP_OVERDUE not in checks.evaluate(c.state, fit, nxt - timedelta(seconds=2))
    assert StallReason.STEP_OVERDUE in checks.evaluate(c.state, fit, nxt)
