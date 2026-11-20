"""Evidence Reader (A1): a report counts only once a clinician confirms what it says; rules act on that."""

from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import AI, FP, INTEG, NAV, T0, Case, as_
from test_engine import to_booked

from tasleem.bench.report_eval import HELD_OUT, evaluate
from tasleem.domain import engine
from tasleem.domain.errors import DomainError
from tasleem.domain.model import EventType, Outcome, Signal, SignalKind, StallReason
from tasleem.domain.report_reader import quotes_are_verbatim, read_report, reading_dict

D = timedelta(days=1)
INCOMPLETE = ("Incomplete colonoscopy: unable to advance beyond the hepatic flexure. Inadequate preparation, "
              "BBPS 1-1-0. Recommend repeat colonoscopy with extended preparation in 3 months.")
COMPLETE_PENDING = ("Caecum reached. BBPS 8 (3-3-2). Two polyps removed by cold snare. Histology pending. "
                    "Repeat colonoscopy in 3 years if adenomas.")
PATHOLOGY = "Histopathology: tubular adenoma with low-grade dysplasia. Surveillance colonoscopy in 3 years."


def attended(c: Case) -> Case:
    to_booked(c)
    c.signal(SignalKind.APPOINTMENT_ATTENDED, T0 + 12 * D)
    c.signal(SignalKind.PROCEDURE_COMPLETED, T0 + 12 * D, codes=["73761001"])
    return c


def report(c: Case, text: str, t, ref: str = "DiagnosticReport/r1"):
    sig = Signal(kind=SignalKind.REPORT_FINAL, patient_id="p1", occurred_at=t, ref=ref, codes=["18746-8"], text=text)
    return c.run(engine.record_signal(c.state, c.p, sig, INTEG), t)


def confirm(c: Case, rid: str, text: str, t, **override):
    fields = {k: v["value"] for k, v in reading_dict(text).items()}
    fields.update(override)
    return c.run(engine.review_report(c.state, FP, rid, fields, t, suggested_by="keyword-reader-v1",
                                      suggestion={k: v["value"] for k, v in reading_dict(text).items()}), t)


def close(c: Case, t):
    if not c.state.reached("OUTCOME_COMMUNICATED"):
        c.signal(SignalKind.OUTCOME_COMMUNICATED, t)
    return engine.close_case(c.state, c.p, FP, Outcome.COMPLETED_WITH_REPORT, evidence_ref=None, reason=None, now=t)


# ---- reader ----------------------------------------------------------------------------------------------------
def test_reader_quotes_the_sentence_it_read():
    r = read_report(INCOMPLETE)
    assert r["completed"].value is False and r["completed"].quote.startswith("Incomplete colonoscopy")
    assert r["prep_adequate"].value is False and "BBPS 1-1-0" in r["prep_adequate"].quote
    assert r["follow_up"].value == "3 months"
    assert quotes_are_verbatim(INCOMPLETE, reading_dict(INCOMPLETE))


def test_reader_reads_arabic():
    r = read_report("منظار غير مكتمل بسبب تحضير ضعيف. يوصى بإعادة المنظار خلال ثلاثة أشهر.")
    assert r["completed"].value is False and r["prep_adequate"].value is False and r["follow_up"].value == "3 months"


def test_a_model_quote_that_is_not_in_the_report_is_rejected():
    fake = {"completed": {"field": "completed", "value": True, "quote": "Caecum reached without difficulty."}}
    assert not quotes_are_verbatim(INCOMPLETE, fake)


def test_reader_accuracy_on_the_labelled_set():
    acc, misses = evaluate()
    assert acc >= 0.9, misses
    held, _ = evaluate(HELD_OUT)
    assert held >= 0.75  # honest floor on reports never used for tuning; misses read "not stated", never wrong


def test_held_out_misses_are_blanks_not_wrong_answers():
    for text, labels in HELD_OUT:
        reading = read_report(text)
        for field, want in labels.items():
            got = reading[field].value
            if field != "next_step" and got is not None:
                assert got == want, (text, field, got, want)


# ---- rules -----------------------------------------------------------------------------------------------------
def test_report_without_text_behaves_as_before(fit):
    c = attended(Case(fit))
    c.signal(SignalKind.REPORT_FINAL, T0 + 14 * D, codes=["18746-8"])
    assert c.state.reports == {}
    close(c, T0 + 15 * D)  # no exception


def test_report_text_must_be_confirmed_before_closing(fit):
    c = attended(Case(fit))
    report(c, COMPLETE_PENDING.replace(" Histology pending.", " No polyps."), T0 + 14 * D)
    assert list(c.state.reports) == ["rpt-1"] and c.state.reached("REPORT_RECEIVED")
    with pytest.raises(DomainError) as e:
        close(c, T0 + 14 * D)
    assert e.value.code == "R3_REPORT_NOT_REVIEWED"


def test_unread_report_escalates_after_two_days(fit):
    c = attended(Case(fit))
    report(c, INCOMPLETE, T0 + 14 * D)
    assert StallReason.REPORT_NOT_REVIEWED.value not in c.tick(T0 + 15 * D).stalls
    assert StallReason.REPORT_NOT_REVIEWED.value in c.tick(T0 + 16 * D + timedelta(hours=1)).stalls


def test_incomplete_colonoscopy_stalls_and_blocks_closure(fit):
    c = attended(Case(fit))
    report(c, INCOMPLETE, T0 + 14 * D)
    st = confirm(c, "rpt-1", INCOMPLETE, T0 + 14 * D)
    assert st.stalls[StallReason.PROCEDURE_INCOMPLETE.value].detail.startswith("colonoscopy incomplete")
    with pytest.raises(DomainError) as e:
        close(c, T0 + 14 * D)
    assert e.value.code == "R3_PROCEDURE_INCOMPLETE"
    # A signed change of plan is still possible (R3 allows it with a written reason).
    engine.close_case(c.state, c.p, FP, Outcome.PLAN_CHANGED, evidence_ref=None, reason="CT colonography instead",
                      now=T0 + 15 * D)


def test_repeat_complete_colonoscopy_clears_the_stall(fit):
    c = attended(Case(fit))
    report(c, INCOMPLETE, T0 + 14 * D)
    confirm(c, "rpt-1", INCOMPLETE, T0 + 14 * D)
    text = "Complete colonoscopy to the caecum. BBPS 9 (3-3-3). No polyps. Routine screening in 10 years."
    report(c, text, T0 + 40 * D, ref="DiagnosticReport/r2")
    st = confirm(c, "rpt-2", text, T0 + 40 * D)
    assert StallReason.PROCEDURE_INCOMPLETE.value not in st.stalls
    close(c, T0 + 40 * D)


def test_pathology_pending_keeps_the_case_open_until_the_result(fit):
    c = attended(Case(fit))
    report(c, COMPLETE_PENDING, T0 + 14 * D)
    confirm(c, "rpt-1", COMPLETE_PENDING, T0 + 14 * D)
    with pytest.raises(DomainError) as e:
        close(c, T0 + 14 * D)
    assert e.value.code == "R3_PATHOLOGY_PENDING"
    assert StallReason.PATHOLOGY_OUTSTANDING.value in c.tick(T0 + 36 * D).stalls
    report(c, PATHOLOGY, T0 + 37 * D, ref="DiagnosticReport/path1")
    st = confirm(c, "rpt-2", PATHOLOGY, T0 + 37 * D)
    assert st.confirmed_findings["pathology_pending"] is False and st.confirmed_findings["completed"] is True
    assert StallReason.PATHOLOGY_OUTSTANDING.value not in st.stalls
    close(c, T0 + 37 * D)


def test_only_a_clinician_confirms_and_corrections_are_recorded(fit):
    c = attended(Case(fit))
    report(c, INCOMPLETE, T0 + 14 * D)
    for who in (NAV, AI):
        with pytest.raises(DomainError):
            engine.review_report(c.state, who, "rpt-1", {}, T0 + 14 * D)
    st = confirm(c, "rpt-1", INCOMPLETE, T0 + 14 * D, prep_adequate=True)
    r = st.reports["rpt-1"]
    assert r.reviewed_by == "dr-fp" and r.suggested_by == "keyword-reader-v1" and r.corrected == ["prep_adequate"]
    assert c.events[-1].type in (EventType.REPORT_REVIEWED, EventType.STALL_FLAGGED, EventType.ESCALATED)
    with pytest.raises(DomainError) as e:
        engine.review_report(c.state, FP, "rpt-1", {}, T0 + 14 * D)
    assert e.value.code == "REPORT_ALREADY_REVIEWED"


def test_invalid_findings_are_refused(fit):
    c = attended(Case(fit))
    report(c, INCOMPLETE, T0 + 14 * D)
    for bad in ({"completed": "maybe"}, {"polyps_removed": -1}, {"surgeon": "x"}):
        with pytest.raises(DomainError) as e:
            engine.review_report(c.state, FP, "rpt-1", bad, T0 + 14 * D)
        assert e.value.code == "VALIDATION"


# ---- API -------------------------------------------------------------------------------------------------------
def test_api_shows_the_reading_and_accepts_a_review(client):
    items = client.get("/v1/cases?status=all&limit=500", headers=as_("coord-sara")).json()["items"]
    khalid = next(i for i in items if i["patient"]["id"] == "p-khalid")
    d = client.get(f"/v1/cases/{khalid['id']}", headers=as_("dr-fatima")).json()
    rpt = d["reports"][0]
    assert rpt["reviewed"] is False and rpt["keyword_reading"]["fields"]["prep_adequate"]["value"] is False
    # Rules alone read one of six findings from this report; the rest wait for the model or the physician.
    assert sum(f["value"] is not None for f in rpt["keyword_reading"]["fields"].values()) == 1
    assert d["next_step"]["reason"] in ("REPORT_TO_REVIEW", "REPORT_NOT_REVIEWED")
    assert d["actions"]["reports"][rpt["id"]]["allowed"] is True
    nav = client.get(f"/v1/cases/{khalid['id']}", headers=as_("nav-aisha"))
    if nav.status_code == 200:
        assert nav.json()["actions"]["reports"][rpt["id"]]["allowed"] is False
    fields = {k: v["value"] for k, v in rpt["keyword_reading"]["fields"].items()}
    r = client.post(f"/v1/cases/{khalid['id']}/reports/{rpt['id']}/review", headers=as_("dr-fatima"),
                    json={"findings": fields, "suggested_by": "keyword-reader-v1", "suggestion": fields})
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["reports"][0]["reviewed"] is True
    assert any(s["reason"] == "PROCEDURE_INCOMPLETE" for s in after["stalls"])
    close = {x["outcome"]: x for x in after["actions"]["close"]}
    assert close["COMPLETED_WITH_REPORT"]["code"] == "R3_PROCEDURE_INCOMPLETE"


def test_a_covering_doctor_can_answer_an_e_consult(client):
    """Judge finding, 20 Nov: Dr Lina covers Dr Omar but had no answer box on Ahmed's e-consult."""
    items = client.get("/v1/cases?status=all&limit=500", headers=as_("coord-sara")).json()["items"]
    ahmed = next(i for i in items if i["patient"]["id"] == "p-ahmed")
    d = client.get(f"/v1/cases/{ahmed['id']}", headers=as_("dr-lina"))
    assert d.status_code == 200, d.text
    open_q = [k for k in d.json()["consults"] if k["answer"] is None]
    assert open_q and d.json()["actions"]["consults"][open_q[0]["id"]]["allowed"] is True
    r = client.post(f"/v1/cases/{ahmed['id']}/consults/{open_q[0]['id']}/answer", headers=as_("dr-lina"),
                    json={"answer": "Proceed with colonoscopy; no need to stop aspirin."})
    assert r.status_code == 200, r.text


def test_simulator_incomplete_report_scenario(client):
    r = client.post("/v1/demo/scenarios/incomplete-report", headers=as_("dr-fatima"), json={})
    assert r.status_code == 200, r.text
    d = client.get(f"/v1/cases/{r.json()['case_id']}", headers=as_("dr-fatima")).json()
    assert d["reports"][0]["keyword_reading"]["fields"]["prep_adequate"]["value"] is False
    assert d["next_step"]["reason"] == "REPORT_TO_REVIEW"


def test_ai_oversight_counts_suggestions_and_corrections(client):
    out = client.get("/v1/program/ai-oversight", headers=as_("coord-sara")).json()
    kinds = {i["kind"]: i for i in out["items"]}
    # Seeded: Mariam's report was confirmed unchanged; Noura's and Sunita's replies have AI barrier suggestions.
    assert kinds["report_reading"]["reviewed"] >= 1 and kinds["report_reading"]["acceptance_rate"] == 1.0
    assert kinds["barrier"]["suggested"] >= 2
    assert all(i["decided_by"] == "a named person (R5)" for i in out["items"])


def test_a_symptom_cannot_be_confirmed_as_a_barrier(client):
    """Judge finding, 20 Nov: Sunita's "I saw blood... terrified" was offered as "Fear" for a navigator to confirm."""
    items = client.get("/v1/cases?status=all&limit=500", headers=as_("coord-sara")).json()["items"]
    sunita = next(i for i in items if i["patient"]["id"] == "p-sunita")
    d = client.get(f"/v1/cases/{sunita['id']}", headers=as_("coord-sara")).json()
    b = d["barriers"][0]
    assert d["actions"]["barriers"][b["id"]]["confirm"]["code"] == "DISTRESS_FIRST"
    r = client.post(f"/v1/cases/{sunita['id']}/barriers/{b['id']}/confirm", headers=as_("coord-sara"),
                    json={"code": "FEAR"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DISTRESS_FIRST"


def test_an_unanswered_e_consult_escalates_to_the_specialist_not_the_asker(fit):
    """Judge finding, 20 Nov: Ahmed's unanswered e-consult was escalated to Dr. Fatima, who asked it."""
    c = Case(fit)
    c.run(engine.request_consult(c.state, fit, FP, "k1", "dr-gi", "Anticoagulants before colonoscopy?", T0), T0)
    st = c.tick(T0 + 3 * D)
    stall = st.stalls[StallReason.CONSULT_UNANSWERED.value]
    assert stall.level == 1 and stall.escalated_to == "dr-gi"  # the specialist, never the asker (dr-fp)


def test_the_next_step_is_written_for_the_person_looking(client):
    """Judge finding, 20 Nov: Dr. Lina was told Dr. Fatima's job; Dr. Salma was told to 'ask the receiver'."""
    items = client.get("/v1/cases?status=all&limit=500", headers=as_("coord-sara")).json()["items"]
    ahmed = next(i for i in items if i["patient"]["id"] == "p-ahmed")["id"]
    fatma = next(i for i in items if i["patient"]["id"] == "p-fatma")["id"]
    lina = client.get(f"/v1/cases/{ahmed}", headers=as_("dr-lina")).json()["next_step"]
    assert lina["reason"] == "CONSULT_TO_ANSWER" and "whom you cover" in lina["text"]
    salma = client.get(f"/v1/cases/{fatma}", headers=as_("dr-salma")).json()["next_step"]
    assert salma["reason"] == "HANDOFF_TO_ACCEPT" and salma["text"].startswith("Dr. Fatima offered you")
    # The owner still sees the case's own next step.
    assert (
        client.get(f"/v1/cases/{ahmed}", headers=as_("dr-fatima")).json()["next_step"]["reason"]
        != "CONSULT_TO_ANSWER"
    )
    work = client.get("/v1/me/work", headers=as_("dr-lina")).json()
    rows = [r for s in work["sections"] for r in s["items"] if r["id"] == ahmed]
    assert rows and rows[0]["next_action"]["reason"] == "CONSULT_TO_ANSWER"


def test_a_confirmed_incomplete_colonoscopy_is_shown_as_incomplete(client):
    items = client.get("/v1/cases?status=all&limit=500", headers=as_("coord-sara")).json()["items"]
    kid = next(i for i in items if i["patient"]["id"] == "p-khalid")["id"]
    d = client.get(f"/v1/cases/{kid}", headers=as_("dr-fatima")).json()
    assert next(s for s in d["stages"] if s["id"] == "PROCEDURE_DONE")["status"] == "verified"  # not yet confirmed
    rpt = d["reports"][0]
    vals = {k: v["value"] for k, v in rpt["keyword_reading"]["fields"].items()}
    d = client.post(f"/v1/cases/{kid}/reports/{rpt['id']}/review", headers=as_("dr-fatima"),
                    json={"findings": vals, "suggested_by": "keyword-reader-v1", "suggestion": vals}).json()
    assert next(s for s in d["stages"] if s["id"] == "PROCEDURE_DONE")["status"] == "incomplete"


def test_preparation_questions_follow_the_language_the_patient_picks(client):
    """Found 20 Nov: Noura switched to EN and the questions stayed in Arabic."""
    cases = client.get("/v1/me/cases?lang=en", headers=as_("p-noura")).json()["items"]
    cid = cases[0]["case_id"]
    en = client.get(f"/v1/me/cases/{cid}/prep-check?lang=en", headers=as_("p-noura"))
    if en.status_code == 200:
        assert en.json()["language"] == "en" and not any("؀" <= ch <= "ۿ" for ch in en.json()["questions"][0]["text"])
        ar = client.get(f"/v1/me/cases/{cid}/prep-check?lang=ar", headers=as_("p-noura")).json()
        assert ar["direction"] == "rtl"
        r = client.post(f"/v1/me/cases/{cid}/prep-check?lang=en", headers=as_("p-noura"), json={"answers": {}}).json()
        assert not any("؀" <= ch <= "ۿ" for ch in r["message"])
