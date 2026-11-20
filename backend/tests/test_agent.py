"""AI agent: suggest-only, grounded, policy-checked, and scoped exactly like the person asking."""

from __future__ import annotations

import pytest
from conftest import as_
from fastapi.testclient import TestClient

from tasleem.api.app import create_app
from tasleem.config import Settings
from tasleem.domain.messaging import check_patient_text
from tasleem_agent.app import AgentSettings
from tasleem_agent.app import create_app as agent_app
from tasleem_agent.assist import Brief, Draft, Sentence
from tasleem_agent.templates import OUTREACH
from tasleem_common.http import ServiceClient

FATIMA, SALMA, AISHA = as_("dr-fatima"), as_("dr-salma"), as_("nav-aisha")


class FakeLLM:
    """Returns whatever the test wants, to prove validators catch bad model output."""

    name = "fake-llm"

    def __init__(self, brief: Brief | None = None, draft: str | None = None) -> None:
        self.brief, self.draft = brief, draft

    def structured(self, system, user, schema):
        if schema is Brief:
            return self.brief
        if schema is Draft and self.draft is not None:
            return Draft(text=self.draft)
        return None


@pytest.fixture
def core():
    app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True, rate_limit_per_second=0))
    with TestClient(app) as c:
        yield c


def _agent(core, llm=None) -> TestClient:
    s = AgentSettings(database_url="sqlite://", rate_limit_per_second=0)
    return TestClient(agent_app(s, ServiceClient(client=core), llm))


def _case(core, pid: str) -> str:
    items = core.get("/v1/cases", params={"limit": 500}, headers=as_("coord-sara")).json()["items"]
    return next(i["id"] for i in items if i["patient"]["id"] == pid)


@pytest.mark.parametrize("key", sorted(OUTREACH))
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_every_approved_template_passes_the_message_policy(key, lang):
    assert check_patient_text(OUTREACH[key][lang]) == []


def test_assist_shows_sense_decide_act_handoff(core):
    cid = _case(core, "p-rajesh")  # the false-done case
    with _agent(core) as a:
        r = a.get(f"/v1/cases/{cid}/assist", headers=FATIMA).json()
    case = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()
    seqs = {e["seq"] for e in case["timeline"]}
    assert any(f["id"] == "gap" for f in r["sense"])  # Malaffi says more than the evidence shows
    assert all(set(f["cites"]) <= seqs for f in r["sense"])  # every fact points at real audit events
    assert r["decide"]["next_step"] == case["next_step"]  # the decision is the rules', copied verbatim
    assert r["act"]["brief"]["source"] == "extractive" and r["act"]["brief"]["provenance"] == "computed"
    assert r["hand_off"]["to"]["id"] == case["next_step"]["person"]["id"]


def test_hallucinated_brief_is_rejected_and_rules_text_is_used(core):
    cid = _case(core, "p-rajesh")
    bad = Brief(sentences=[Sentence(text="The colonoscopy was done on day 99 and was normal.", cites=[9999])])
    with _agent(core, FakeLLM(brief=bad)) as a:
        b = a.post(f"/v1/cases/{cid}/brief", headers=FATIMA).json()
    assert b["source"] == "extractive" and b["rejected_llm_output"]
    assert any("unknown citations" in p for p in b["rejected_llm_output"])


def test_grounded_llm_brief_is_accepted_and_labelled_ai(core):
    cid = _case(core, "p-rajesh")
    case = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()
    seq = next(e["seq"] for e in case["timeline"] if e["type"] == "STALL_FLAGGED")
    good = Brief(sentences=[Sentence(text="Malaffi shows the referral as completed but no report has arrived.",
                                     cites=[seq])])
    with _agent(core, FakeLLM(brief=good)) as a:
        b = a.post(f"/v1/cases/{cid}/brief", headers=FATIMA).json()
    assert b["source"] == "llm" and b["provenance"] == "ai_suggestion" and b["model"] == "fake-llm"


def test_outreach_draft_then_a_person_sends_it(core):
    cid = core.post("/v1/demo/scenarios/missed-colonoscopy").json()["case_id"]
    with _agent(core) as a:
        d = a.post(f"/v1/cases/{cid}/outreach-draft", headers=AISHA, json={"language": "en"}).json()
        assert d["draft"]["template"] == "TIME_OR_WORK" and d["requires_approval"] is True
        audit = a.get(f"/v1/drafts/{d['draft_id']}", headers=AISHA).json()
        assert audit["kind"] == "outreach" and audit["requested_by"] == "nav-aisha"
    sent = core.post(d["send_with"]["path"], headers=AISHA, json=d["send_with"]["body"])
    assert sent.status_code == 200
    ev = [e for e in sent.json()["timeline"] if e["type"] == "PATIENT_MESSAGE_SENT"][-1]
    assert ev["actor"] == "nav-aisha" and ev["payload"]["ai_draft_id"] == d["draft_id"]


def test_unsafe_llm_draft_is_replaced_by_the_template(core):
    cid = core.post("/v1/demo/scenarios/missed-colonoscopy").json()["case_id"]
    with _agent(core, FakeLLM(draft="Your result is positive, so please rebook. Nothing to worry about.")) as a:
        d = a.post(f"/v1/cases/{cid}/outreach-draft", headers=AISHA, json={"language": "en"}).json()
    assert d["source"] == "template" and d["rejected_llm_output"]
    assert d["draft"]["text"] == OUTREACH["TIME_OR_WORK"]["en"]


def test_no_draft_when_a_clinician_must_call(core):
    cid = core.post("/v1/demo/scenarios/distress-message").json()["case_id"]
    with _agent(core) as a:
        d = a.post(f"/v1/cases/{cid}/outreach-draft", headers=FATIMA).json()
    assert d["draft"] is None and "clinician" in d["why"]


def test_agent_sees_only_what_the_caller_sees(core):
    cid = _case(core, "p-rajesh")  # Ghaf clinic
    with _agent(core) as a:
        assert a.get(f"/v1/cases/{cid}/assist", headers=SALMA).status_code == 404  # Samar clinic
        assert a.get(f"/v1/cases/{cid}/assist").status_code == 401
        d = a.post(f"/v1/cases/{cid}/brief", headers=FATIMA).json()
        assert a.get(f"/v1/drafts/{d['draft_id']}", headers=SALMA).status_code == 404


def test_translation_is_unavailable_offline(core):
    with _agent(core) as a:
        r = a.post("/v1/translate", headers=FATIMA, json={"text": "أنا خائفة", "target": "en"}).json()
    assert r["available"] is False


def test_agent_cannot_write_to_cases(core):
    """The agent's only write path is its own draft log; every case-core call it makes is a read or the
    read-only policy check."""
    import inspect

    import tasleem_agent.app as mod

    src = inspect.getsource(mod)
    assert 'core.json("POST"' in src and src.count('core.json("POST"') == 1
    assert "/v1/policy/patient-message-check" in src


def test_llm_barrier_vocabulary_mirrors_case_core():
    from tasleem.domain.model import BarrierCode
    from tasleem_agent.classify import CODES

    assert set(CODES) - {"none"} == {c.value for c in BarrierCode}


def test_barrier_suggestion_offline_defers_to_keywords(core):
    with _agent(core) as a:
        r = a.post("/v1/barrier-suggestion", headers=AISHA, json={"text": "I am scared of the sedation"}).json()
    assert r["available"] is False


# ---- Evidence Reader: model reading must quote the report verbatim ----------------------------------------------
class ReaderLLM:
    name = "fake-reader"

    def __init__(self, reading) -> None:
        self.reading = reading

    def structured(self, system, user, schema):
        from tasleem_agent.report_reading import ReportReading
        return self.reading if schema is ReportReading else None


def test_report_reading_keeps_verbatim_quotes_and_drops_invented_ones(core):
    from tasleem_agent.report_reading import BoolReading, ReportReading, TextReading
    cid = _case(core, "p-khalid")
    rid = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()["reports"][0]["id"]
    reading = ReportReading(
        completed=BoolReading(value=False, quote="Examination limited to the sigmoid colon: the scope could not be passed beyond 40 cm because of solid faecal residue."),
        prep_adequate=BoolReading(value=True, quote="Bowel preparation was excellent."),  # not in the report
        follow_up=TextReading(value="3 months", quote=None),  # a value with no quote
    )
    with _agent(core, ReaderLLM(reading)) as a:
        r = a.post(f"/v1/cases/{cid}/reports/{rid}/reading", headers=FATIMA).json()
    assert r["available"] is True and r["reader"] == "fake-reader" and r["requires_confirmation"] is True
    assert r["fields"]["completed"]["value"] is False
    assert r["fields"]["prep_adequate"]["value"] is None and r["fields"]["follow_up"]["value"] is None
    assert set(r["dropped"]) == {"prep_adequate", "follow_up"}
    # Nothing changed on the case: the reading is a suggestion until a clinician confirms it in case-core.
    assert core.get(f"/v1/cases/{cid}", headers=FATIMA).json()["reports"][0]["reviewed"] is False


def test_report_reading_without_a_model_returns_the_keyword_reading(core):
    cid = _case(core, "p-khalid")
    rid = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()["reports"][0]["id"]
    with _agent(core) as a:
        r = a.post(f"/v1/cases/{cid}/reports/{rid}/reading", headers=FATIMA).json()
    assert r["available"] is False and r["reader"] == "keyword-reader-v1"
    assert r["fields"]["prep_adequate"]["value"] is False and r["fields"]["completed"]["value"] is None


def test_report_reading_respects_case_scoping(core):
    cid = _case(core, "p-khalid")  # Dr Fatima's clinic
    with _agent(core) as a:
        assert a.post(f"/v1/cases/{cid}/reports/rpt-1/reading", headers=SALMA).status_code == 404


def test_rebook_draft_after_an_incomplete_report_is_confirmed(core):
    cid = _case(core, "p-khalid")
    rpt = core.get(f"/v1/cases/{cid}", headers=FATIMA).json()["reports"][0]
    with _agent(core) as a:
        assert a.post(f"/v1/cases/{cid}/reports/{rpt['id']}/rebook-draft", headers=FATIMA).status_code == 409  # not confirmed
        vals = {k: v["value"] for k, v in rpt["keyword_reading"]["fields"].items()}
        vals.update(completed=False, follow_up="3 months", next_step="Re-scope after an extended two-day preparation")
        core.post(f"/v1/cases/{cid}/reports/{rpt['id']}/review", headers=FATIMA,
                  json={"findings": vals, "suggested_by": "keyword-reader-v1", "suggestion": vals})
        r = a.post(f"/v1/cases/{cid}/reports/{rpt['id']}/rebook-draft", headers=FATIMA).json()
    assert r["requires_approval"] is True and r["source"] == "template"
    assert "Khalid M." in r["text"] and "3 months" in r["text"] and "incomplete" in r["text"]
