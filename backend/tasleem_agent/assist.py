"""What the agent produces. Pure functions over the case JSON returned by case-core, plus an optional LLM
step whose output must pass deterministic validators before anyone sees it.

Agent loop, in the workshop's words:
  sense   - the case as case-core recorded it (facts with event numbers)
  decide  - case-core's deterministic next step (computed by rules, never by the model)
  act     - drafts only: a cited brief and a patient message
  hand off - a named person reviews and sends; case-core records who did it
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from .providers import LLMProvider
from .templates import OUTREACH

NUM = re.compile(r"\d+")


# ---- sense: facts with citations -----------------------------------------------------------------
class Fact(BaseModel):
    id: str
    text: str
    cites: list[int]


def _first(timeline: list[dict[str, Any]], type_: str, **match: Any) -> int | None:
    for e in timeline:
        if e["type"] == type_ and all(e["payload"].get(k) == v for k, v in match.items()):
            return int(e["seq"])
    return None


def _day(ts: str | None) -> str:
    return (ts or "")[:10]


def facts(case: dict[str, Any]) -> list[Fact]:
    """Extractive, deterministic. Every fact names the audit-log events (seq) it rests on."""
    tl = case.get("timeline", [])
    out: list[Fact] = []
    opened = _first(tl, "CASE_OPENED") or 1
    out.append(Fact(id="opened", cites=[opened],
                    text=f"Case opened on {_day(tl[0]['at'] if tl else None)} on the pathway "
                         f"'{case['pathway']['name']}'. Owner: {case['owner']['name']}."))
    prog = case["progress"]
    v = prog["verified"]
    if v["stage"]:
        label = next((s["label"] for s in case["stages"] if s["id"] == v["stage"]), v["stage"])
        seq = _first(tl, "STAGE_REACHED", stage=v["stage"])
        out.append(Fact(id="verified", cites=[seq] if seq else [],
                        text=f"Furthest verified step: {label} (step {v['step']} of {v['of']})."))
    r = prog["reported"]
    if prog.get("gap"):
        seq = _first(tl, "ADMIN_STATUS_CHANGED", status=r["admin_status"])
        out.append(Fact(id="gap", cites=[seq] if seq else [],
                        text=f"Malaffi referral status says {r['admin_status']}, which is further than the "
                             f"clinical evidence shows."))
    for s in case.get("stalls", []):
        seq = _first(tl, "STALL_FLAGGED", reason=s["reason"])
        out.append(Fact(id=f"stall:{s['reason']}", cites=[seq] if seq else [],
                        text=f"Stalled: {s['label']}. Escalation level {s['level']}, currently with "
                             f"{s['escalated_to']['name']}."))
    if case.get("appointment_missed"):
        seq = _first(tl, "APPOINTMENT_MISSED")
        out.append(Fact(id="missed", cites=[seq] if seq else [],
                        text="The appointment was missed" + (" (no-show)." if case["appointment_missed"] == "noshow"
                                                              else " (cancelled).")))
    symptom_ids = {d.get("barrier_id") for d in case.get("distress", []) if not d.get("resolved")}
    labels = {"FEAR": "fear or worry", "NO_ESCORT": "no one to take them home", "PREP_UNCLEAR": "preparation unclear",
              "TRANSPORT": "transport", "COST_OR_INSURANCE": "cost or insurance", "TIME_OR_WORK": "time off work",
              "LANGUAGE": "language", "FEMALE_CLINICIAN": "asks for a female doctor",
              "WANTS_CALLBACK": "asks for a call", "DONE_ELSEWHERE": "says it was done elsewhere", "OTHER": "other"}
    for b in case.get("barriers", []):
        if b["status"] == "resolved" or b["id"] in symptom_ids:
            continue  # a symptom is never described as a barrier (judge finding, 20 Nov)
        code = b.get("confirmed_code") or ", ".join(b.get("reported_codes") or []) or b.get("suggested_code")
        how = "confirmed by staff" if b.get("confirmed_code") else (
            "reported by the patient" if b.get("reported_codes") else "AI suggestion, not yet confirmed")
        seq = _first(tl, "BARRIER_REPORTED", barrier_id=b["id"])
        words = ", ".join(labels.get(x.strip(), x.strip().lower()) for x in str(code).split(","))
        out.append(Fact(id=f"barrier:{b['id']}", cites=[seq] if seq else [],
                        text=f"What got in the way: {words} ({how})."))
    for d in case.get("distress", []):
        if not d.get("resolved"):
            seq = _first(tl, "DISTRESS_FLAGGED", distress_id=d["id"])
            out.append(Fact(id=f"distress:{d['id']}", cites=[seq] if seq else [],
                            text="Open distress flag: a patient message needs a clinician."))
    if case.get("contact_attempts"):
        seqs = [int(e["seq"]) for e in tl if e["type"] == "CONTACT_ATTEMPTED"]
        out.append(Fact(id="contacts", cites=seqs[-3:],
                        text=f"Contact attempts logged: {case['contact_attempts']}."))
    return out


# ---- act: brief ----------------------------------------------------------------------------------
class Sentence(BaseModel):
    text: str = Field(max_length=400)
    cites: list[int] = Field(default_factory=list)


class Brief(BaseModel):
    sentences: list[Sentence] = Field(max_length=6)


BRIEF_SYSTEM = (
    "You write a short case brief for a family physician in Abu Dhabi. Use only the numbered facts given. "
    "Each sentence must list the event numbers (cites) of the facts it uses. Do not add facts, numbers, "
    "dates, diagnoses, advice or priorities that are not in the facts. At most five plain sentences."
)


def validate_brief(brief: Brief, fs: list[Fact]) -> list[str]:
    """Reject anything the facts do not support: unknown citations or numbers that are not in the facts."""
    allowed_cites = {c for f in fs for c in f.cites}
    allowed_nums = {n for f in fs for n in NUM.findall(f.text)} | {str(c) for c in allowed_cites}
    problems = []
    if not brief.sentences:
        problems.append("empty brief")
    for s in brief.sentences:
        if not s.cites:
            problems.append(f"uncited sentence: {s.text[:60]}")
        bad = [c for c in s.cites if c not in allowed_cites]
        if bad:
            problems.append(f"unknown citations {bad}")
        extra = [n for n in NUM.findall(s.text) if n not in allowed_nums]
        if extra:
            problems.append(f"numbers not in the facts: {extra}")
    return problems


def make_brief(case: dict[str, Any], llm: LLMProvider) -> dict[str, Any]:
    fs = facts(case)
    step = case.get("next_step")
    base = Brief(sentences=[Sentence(text=f.text, cites=f.cites) for f in fs])
    source, model, rejected = "extractive", "rules", []
    user = "\n".join(f"- [{','.join(map(str, f.cites)) or '-'}] {f.text}" for f in fs)
    out = llm.structured(BRIEF_SYSTEM, f"Facts:\n{user}", Brief)
    if out is not None:
        rejected = validate_brief(out, fs)
        if not rejected:
            base, source, model = out, "llm", llm.name
    return {
        "provenance": "ai_suggestion" if source == "llm" else "computed",
        "source": source, "model": model, "rejected_llm_output": rejected or None,
        "sentences": [s.model_dump() for s in base.sentences],
        # The decision stays with the rules: copied from case-core, never generated.
        "next_step": step,
    }


# ---- act: patient message draft ------------------------------------------------------------------
class Draft(BaseModel):
    text: str = Field(max_length=600)


DRAFT_SYSTEM = (
    "You adapt an approved message from a care team to a patient. Keep the meaning, keep it under three "
    "short sentences, write in the requested language, warm and plain. Never mention results, numbers, "
    "diagnoses, medicines or reassurance about health. Never add links. If unsure, return the approved "
    "message unchanged."
)


def choose_template(case: dict[str, Any]) -> tuple[str | None, str]:
    """(template key, why). None = no message should be drafted; a person must act instead."""
    if case["status"] != "open":
        return None, "The case is closed."
    if any(not d.get("resolved") for d in case.get("distress", [])):
        return None, "Open distress flag: a clinician must call the patient. No message is drafted."
    reason = (case.get("next_step") or {}).get("reason")
    if reason == "PATIENT_NOT_REACHED":
        return None, "Messages are not reaching this patient. A navigator must call."
    if reason in ("REPORT_TO_REVIEW", "REPORT_NOT_REVIEWED"):
        return None, "A report has arrived. Confirm what it says first; the next message depends on it."
    if reason == "PROCEDURE_INCOMPLETE":
        return None, ("The colonoscopy must be rebooked. Arrange the new date with the GI centre, then explain it to "
                      "the patient by phone or in person: a message must not describe the result.")
    if reason in ("CLOSED_WITHOUT_EVIDENCE", "PATHOLOGY_PENDING", "PATHOLOGY_OUTSTANDING"):
        # Judge finding, 20 Nov: Rajesh attended; the missing piece is the GI centre's report, not the patient.
        return None, ("The patient has nothing to do right now: the gap is with the GI centre. "
                      "Use E-consult to ask the GI centre for the report.")
    open_b = [b for b in case.get("barriers", []) if b["status"] != "resolved"]
    if open_b:
        b = open_b[-1]
        code = b.get("confirmed_code") or (b.get("reported_codes") or [None])[0] or b.get("suggested_code")
        if code in OUTREACH:
            words = {
                "FEAR": "fear or worry",
                "NO_ESCORT": "no one to take them home",
                "PREP_UNCLEAR": "the preparation is unclear",
                "TRANSPORT": "transport",
                "COST_OR_INSURANCE": "cost or insurance",
                "TIME_OR_WORK": "time off work",
                "LANGUAGE": "language",
                "FEMALE_CLINICIAN": "asks for a female doctor",
                "WANTS_CALLBACK": "asks for a call",
                "DONE_ELSEWHERE": "says it was done elsewhere",
            }.get(code, "something else")
            return code, f"Drafted for what the patient said got in the way: {words}."
    if case.get("appointment_missed"):
        return "MISSED", "The appointment was missed."
    return "GENERIC", "No barrier on file; general follow-up message."


def draft_outreach(case: dict[str, Any], language: str, llm: LLMProvider,
                   check: Any) -> dict[str, Any]:
    """`check(text) -> {"ok": bool, "violations": [...]}` is case-core's policy endpoint."""
    key, why = choose_template(case)
    if key is None:
        return {"draft": None, "why": why}
    template = OUTREACH[key][language]
    text, source, model, rejected = template, "template", "approved-library", None
    out = llm.structured(DRAFT_SYSTEM, f"Language: {language}\nApproved message: {template}", Draft)
    if out is not None:
        verdict = check(out.text)
        if verdict.get("ok"):
            text, source, model = out.text.strip(), "llm", llm.name
        else:
            rejected = verdict.get("violations")
    final = check(text)
    if not final.get("ok"):  # a template that fails policy is a bug; never offer it
        return {"draft": None, "why": "No draft passed the message policy.", "violations": final.get("violations")}
    return {"draft": {"text": text, "language": language, "template": key}, "why": why,
            "provenance": "ai_suggestion" if source == "llm" else "template", "source": source, "model": model,
            "rejected_llm_output": rejected}


# ---- translation of patient replies for staff (LLM only) -----------------------------------------
class Translation(BaseModel):
    text: str = Field(max_length=4000)


def translate(text: str, target: str, llm: LLMProvider) -> dict[str, Any]:
    out = llm.structured("Translate the patient's message for their care team. Translate only; do not "
                         "summarise, interpret or add anything.", f"Target language: {target}\n\n{text}",
                         Translation)
    if out is None:
        return {"available": False, "why": "No translation model is configured; ask an interpreter."}
    return {"available": True, "text": out.text, "provenance": "ai_suggestion", "model": llm.name}
