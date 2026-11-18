"""AI-user simulation: personas with a job to be done drive the real Tasleem API.

The method follows multi-agent simulators such as MiroFish (personas with their own incentives, biases and
memory, interacting over rounds in one shared world), with one difference that matters for a clinical
product: the agents do not talk about the product, they *use* it. Every agent acts through the same HTTP
API the web app calls, as its own demo user, against one shared in-process instance with the synthetic seed.

    patients act -> staff act (they see what patients just did) -> the scheduler ticks -> next round

Two kinds of result, kept apart:
- **Deterministic checks** (the evidence): after the run, code checks each persona's job and the safety
  invariants R1-R6 against API state. An LLM never decides whether the product passed.
- **AI-user verdicts** (the colour): each persona says, in its own voice, whether the job got done and where
  it struggled. Useful for finding friction; never counted as proof.

Run (needs a free-tier key in backend/.env, e.g. GROQ_API_KEY; about 20 minutes on the free tier):
    cd backend && python -m tasleem.bench.personas --provider groq
Offline (scripted agents, no model): python -m tasleem.bench.personas --provider scripted
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
OUT_MD = ROOT / "docs" / "evidence" / "PERSONA_SIMULATION.md"
OUT_JSON = ROOT / "docs" / "evidence" / "data" / "persona_simulation.json"


# --------------------------------------------------------------------------------------------- personas
@dataclass(frozen=True)
class Persona:
    user: str            # demo user id the agent signs in as
    name: str
    role: str            # family_physician | navigator | clinic_lead | program_coordinator | gi_specialist | patient
    profile: str         # who they are, constraints, digital literacy, language
    incentives: str      # what they want and what they avoid
    jtbd: str            # When ..., I want to ..., so I can ...
    script: tuple[tuple[str, dict[str, Any]], ...] = ()  # offline fallback actions, used by --provider scripted


PERSONAS: tuple[Persona, ...] = (
    # Patients act first in every round.
    Persona("p-noura", "Noura A., 52", "patient",
            "Arabic only (Gulf dialect). Missed her colonoscopy. Afraid of sedation and nobody can drive her home. "
            "Uses Sahatna on her phone but types short messages.",
            "Wants help without being judged; avoids phone calls from unknown numbers.",
            "When I am scared and cannot get there, I want to tell someone in Arabic and get practical help, "
            "so I can still have the test.",
            (("tell_care_team", {"codes": ["NO_ESCORT"], "text": "ما عندي احد يوصلني، ممكن تساعدوني؟"}),)),
    Persona("p-sunita", "Sunita R., 53", "patient",
            "English. Colonoscopy booked next week. Since yesterday she has had bleeding and cramps and is worried.",
            "Wants a clinician to know today; does not want to wait for the appointment.",
            "When something feels wrong with my body, I want a clinician to know today, so I am safe.",
            (("tell_care_team", {"codes": ["OTHER"],
                                 "text": "I have been bleeding since yesterday and I feel dizzy."}),)),
    Persona("p-fatma", "Fatma N., 70", "patient",
            "Arabic. Low digital literacy; her daughter reads messages for her. Has not yet discussed her result.",
            "Wants someone to phone her; dislikes forms and apps.",
            "When the app asks me things, I want a person to call me instead, so I do not have to use the phone.",
            (("tell_care_team", {"codes": ["WANTS_CALLBACK"], "text": "اتصلوا علي من فضلكم"}),)),
    Persona("p-john", "John D., 59", "patient",
            "English. Had a colonoscopy at a hospital in Kochi, India, three weeks ago while visiting family; "
            "has the PDF report. Has no family physician in Abu Dhabi.",
            "Wants to say it once and stop being chased.",
            "When I have already had the test abroad, I want to tell them once and send the report, so they stop "
            "chasing me and my record is right.",
            (("tell_care_team", {"codes": ["DONE_ELSEWHERE"],
                                 "text": "I already had the colonoscopy in Kochi three weeks ago. "
                                         "I have the report."}),)),
    Persona("p-rajesh", "Rajesh K., 58", "patient",
            "English. Went to the GI centre; thinks everything is finished because the app thanked him.",
            "Wants plain words; does not want to read scary results by text.",
            "When I think I am done, I want to know whether anything is still needed, so nothing is missed.",
            (("finish", {}),)),
    Persona("p-yousef", "Yousef H., 47", "patient",
            "Arabic. Shift worker; colonoscopy booked on a weekday he is rostered. Cannot lose a day's pay.",
            "Wants a different date, ideally a weekend or evening.",
            "When the appointment clashes with my shift, I want to move it easily, so I do not lose pay or skip it.",
            (("tell_care_team", {"codes": ["TIME_OR_WORK"], "text": "عندي دوام يوم الموعد، ابي موعد ثاني"}),)),
    # Staff act after patients, so they see what patients just reported.
    Persona("nav-aisha", "Aisha, care navigator (org-ghaf)", "navigator",
            "Calls and supports about 40 patients a week across two clinics. Speaks Arabic, English and Urdu.",
            "Wants to know who to call first and what is in the way; hates hunting through case lists.",
            "When a patient misses an appointment or replies with a problem, I want to know who to call first "
            "and what is in the way, so I can rebook them this week.",
            (("open_my_first_item", {}),)),
    Persona("dr-fatima", "Dr. Fatima, family physician (org-ghaf)", "family_physician",
            "Sees about 35 patients a day, five minutes between them. Owns most positive-FIT cases in the clinic.",
            "Will not adopt another inbox unless it saves time; wants one clear action per case.",
            "When one of my positive-FIT patients is stuck, I want to see who, why, and the one thing I must do, "
            "so I can act between patients without chasing anyone.",
            (("open_my_first_item", {}),)),
    Persona("dr-salma", "Dr. Salma, family physician (org-samar)", "family_physician",
            "Owns Sunita's and Grace's cases. Wants urgent things on top.",
            "Never wants to miss a patient in danger; dislikes noise.",
            "When a patient reports something worrying, I want it on top of my list today, so I can call them.",
            (("open_my_first_item", {}),)),
    Persona("dr-hessa", "Dr. Hessa, clinic lead (org-ghaf)", "clinic_lead",
            "Receives escalations from the clinic. Covers when doctors are on leave.",
            "Wants to see what is truly stuck and reassign it; does not want to do the doctors' work.",
            "When cases escalate to me, I want to see which are truly stuck and reassign them safely, so nothing "
            "is lost when a doctor is away.",
            (("open_my_first_item", {}),)),
    Persona("coord-sara", "Sara, programme coordinator", "program_coordinator",
            "Reports screening follow-up to the public health authority every month. Not a clinician.",
            "Wants verified numbers and where people are lost; must not make clinical decisions.",
            "When I report to the programme, I want verified completion and where people are lost by clinic and "
            "language, so I can direct resources.",
            (("view_metrics", {}),)),
)

ROUND_ORDER = [p.user for p in PERSONAS]


# ---------------------------------------------------------------------------------------------- the world
class Client(Protocol):
    def request(self, method: str, url: str, **kw: Any) -> Any: ...


@dataclass
class Call:
    round: int
    user: str
    action: str
    method: str
    path: str
    status: int
    error: str | None = None


@dataclass
class World:
    client: Client
    calls: list[Call] = field(default_factory=list)
    round: int = 0

    def api(self, user: str, action: str, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        r = self.client.request(method, path, headers={"X-Demo-User": user}, json=body)
        try:
            data = r.json()
        except ValueError:
            data = r.text
        err = None
        if r.status_code >= 400:
            err = (data.get("error") or data.get("detail")) if isinstance(data, dict) else str(data)[:200]
            err = json.dumps(err, ensure_ascii=False)[:300] if not isinstance(err, str) else err[:300]
        self.calls.append(Call(self.round, user, action, method, path, r.status_code, err))
        return r.status_code, data

    def get(self, user: str, path: str) -> Any:
        status, data = self.api(user, "read", "GET", path)
        return data if status == 200 else {}


def _short_case(d: dict[str, Any]) -> dict[str, Any]:
    """The part of a case a person needs on screen (keeps prompts small for free-tier models)."""
    ns = d.get("next_step") or {}
    return {
        "case_id": d.get("id"), "patient": d.get("patient", {}).get("name"),
        "owner": d.get("owner", {}).get("id"), "status": d.get("status"),
        "verified_stage": (d.get("progress") or {}).get("verified", {}).get("stage"),
        "malaffi_status": (d.get("progress") or {}).get("reported", {}).get("admin_status"),
        "stalls": [s.get("label") for s in d.get("stalls", [])],
        "next_step": {"who": ns.get("who"), "person": (ns.get("person") or {}).get("id"), "text": ns.get("text")}
        if ns else None,
        "barriers": [{"id": b["id"], "codes": b.get("reported_codes"), "suggested": b.get("suggested_code"),
                      "status": b.get("status"), "assigned_to_role": b.get("assignee_role"),
                      "text": (b.get("text") or "")[:160]} for b in d.get("barriers", [])],
        "distress": [{"id": x["id"], "routed_to": x.get("routed_to"), "resolved": x.get("resolved")}
                     for x in d.get("distress", [])],
        "consults": [{"id": k.get("id"), "to": k.get("to_id") or k.get("to"), "answered": bool(k.get("answer"))}
                     for k in d.get("consults", [])],
        "pending_handoff": d.get("pending_handoff"),
        "outcome": d.get("outcome"),
    }


def screen(world: World, p: Persona, focus: list[str]) -> dict[str, Any]:
    """What this person sees right now in the product."""
    if p.role == "patient":
        items = world.get(p.user, "/v1/me/cases").get("items", [])
        return {"my_cases": [{"case_id": i["case_id"], "status": i["status"], "message": i["message"],
                              "appointment_at": i.get("appointment_at"), "consent_given": i.get("consent_given"),
                              "can_report": [b["code"] for b in i.get("barrier_options", [])],
                              "open_requests": i.get("open_requests")} for i in items]}
    work = world.get(p.user, "/v1/me/work")
    sections = [{"kind": s["kind"], "label": s["label"], "count": s["count"],
                 "items": [{"case_id": i["id"], "patient": i["patient"]["name"],
                            "stalls": [x["label"] for x in i.get("stalls", [])],
                            "open_barriers": i.get("open_barriers"), "distress_open": i.get("distress_open")}
                           for i in s["items"][:6]]}
                for s in work.get("sections", []) if s["count"]]
    ids = list(dict.fromkeys(focus + [i["case_id"] for s in sections for i in s["items"]]))[:3]
    view: dict[str, Any] = {"my_work": sections or "Your work list is empty.",
                            "open_cases": [_short_case(world.get(p.user, f"/v1/cases/{c}")) for c in ids]}
    if p.role in ("program_coordinator", "clinic_lead"):
        m = world.get(p.user, "/v1/program/metrics")
        keys = ("cases", "verified_complete", "referral_status_says_completed", "false_done",
                "median_days_result_to_procedure", "open_stalls_by_reason", "barriers_by_code", "open_distress",
                "open_cases_without_owner")
        view["programme_metrics"] = {k: m.get(k) for k in keys}
        # The Programme page's filters: the same measures by clinic and by language.
        view["programme_metrics_by_filter"] = {
            f: {k: world.get(p.user, f"/v1/program/metrics?{f}").get(k)
                for k in ("cases", "verified_complete", "false_done", "open_stalls_by_reason")}
            for f in ("org=org-ghaf", "org=org-samar", "language=ar", "language=en")}
    return view


# --------------------------------------------------------------------------------------------- actions
Handler = Callable[[World, Persona, dict[str, Any]], tuple[int, str]]


def _post(path: str, keys: tuple[str, ...] = (), extra: Callable[[dict[str, Any]], dict[str, Any]] | None = None
          ) -> Handler:
    def h(w: World, p: Persona, a: dict[str, Any]) -> tuple[int, str]:
        args = a.get("args") or {}
        body = extra(args) if extra else {k: args.get(k) for k in keys}
        url = path.format(case_id=a.get("case_id") or "-", **{k: args.get(k, "-") for k in
                                                              ("barrier_id", "distress_id", "consult_id")})
        status, data = w.api(p.user, a["action"], "POST", url, body)
        return status, (json.dumps(data, ensure_ascii=False)[:300] if status >= 400 else "ok")
    return h


STAFF_ACTIONS: dict[str, tuple[str, Handler | None]] = {
    "view_case": ("Open a case to see it in full. args: {}", None),
    "log_contact": ("Record a call or message attempt. args: {channel: phone|sms|sahatna|whatsapp|in_person|email, "
                    "result: reached|no_answer|wrong_number|left_message|declined}",
                    _post("/v1/cases/{case_id}/contact-attempts", ("channel", "result"))),
    "confirm_barrier": ("Confirm what is in the way, from the AI suggestion or your own judgement. "
                        "args: {barrier_id, code: FEAR|PREP_UNCLEAR|NO_ESCORT|TRANSPORT|COST_OR_INSURANCE|"
                        "TIME_OR_WORK|LANGUAGE|WANTS_CALLBACK|DONE_ELSEWHERE|OTHER}",
                        _post("/v1/cases/{case_id}/barriers/{barrier_id}/confirm", ("code",))),
    "resolve_barrier": ("Mark a confirmed barrier as handled. args: {barrier_id, note}",
                        _post("/v1/cases/{case_id}/barriers/{barrier_id}/resolve", ("note",))),
    "resolve_distress": ("Clinicians only: record that you dealt with a worrying patient message. "
                         "args: {distress_id, note}",
                         _post("/v1/cases/{case_id}/distress/{distress_id}/resolve", ("note",))),
    "message_patient": ("Send the patient a short message in their language (never results). "
                        "args: {text, language: en|ar}",
                        _post("/v1/cases/{case_id}/patient-messages", ("text", "language"))),
    "offer_handoff": ("Offer the case to another named person; you stay owner until they accept. args: {to, reason}",
                      _post("/v1/cases/{case_id}/handoff", ("to", "reason"))),
    "accept_handoff": ("Accept a case offered to you. args: {}", _post("/v1/cases/{case_id}/handoff/accept")),
    "reject_handoff": ("Decline a case offered to you. args: {reason_code}",
                       _post("/v1/cases/{case_id}/handoff/reject", ("reason_code",))),
    "request_consult": ("Ask a specialist a question. args: {to, question}",
                        _post("/v1/cases/{case_id}/consults", ("to", "question"))),
    "answer_consult": ("Answer a question asked of you. args: {consult_id, answer}",
                       _post("/v1/cases/{case_id}/consults/{consult_id}/answer", ("answer",))),
    "close_case": ("Close a case. args: {outcome: COMPLETED_WITH_REPORT|COMPLETED_ELSEWHERE|PLAN_CHANGED|"
                   "INFORMED_REFUSAL|UNREACHABLE, evidence_ref (document id, if any), reason}",
                   _post("/v1/cases/{case_id}/close", ("outcome", "evidence_ref", "reason"))),
    "finish": ("Stop for now.", None),
}
PATIENT_ACTIONS: dict[str, tuple[str, Handler | None]] = {
    "tell_care_team": ("Tell your care team what is happening or what is in the way. "
                       "args: {codes: list of the 'can_report' codes on your screen, text: your own words}",
                       _post("/v1/cases/{case_id}/barriers", ("codes", "text"))),
    "give_consent": ("Agree to the follow-up. args: {}", _post("/v1/me/cases/{case_id}/consent")),
    "finish": ("Stop for now.", None),
}
STAFF_DIRECTORY = ("dr-fatima, dr-salma (family physicians); nav-aisha (navigator); dr-omar, dr-lina "
                   "(gastroenterologists); dr-hessa (clinic lead); coord-sara (programme coordinator)")


class Step(BaseModel):
    thought: str = Field(description="One short sentence, in your own voice, about what you see and want.")
    action: str
    case_id: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)


class Verdict(BaseModel):
    job_done: bool
    score: int = Field(ge=1, le=5, description="1 = the product failed me, 5 = it did the job well")
    what_worked: list[str] = Field(default_factory=list)
    friction: list[str] = Field(default_factory=list, description="Where it was confusing, slow or missing")
    quote: str = Field(description="One sentence you would say to a colleague or friend about it")


class Brain(Protocol):
    name: str

    def step(self, p: Persona, view: dict[str, Any], memory: list[str], menu: dict[str, str]) -> Step | None: ...
    def verdict(self, p: Persona, memory: list[str], final_view: dict[str, Any]) -> Verdict | None: ...


def _system(p: Persona) -> str:
    return (f"You are {p.name}, a {p.role.replace('_', ' ')} in Abu Dhabi, using the Tasleem app (synthetic test). "
            f"Profile: {p.profile} Incentives: {p.incentives} Your job to be done: {p.jtbd} "
            "Behave like this real person would, with their limits and impatience. Use only what is on screen. "
            "Pick one action from the menu per turn; choose 'finish' when you have done what you can for now.")


class LLMBrain:
    def __init__(self, provider: Any) -> None:
        self.provider = provider
        self.name = getattr(provider, "name", "llm")

    def step(self, p: Persona, view: dict[str, Any], memory: list[str], menu: dict[str, str]) -> Step | None:
        user = (f"MENU (action: description): {json.dumps(menu, ensure_ascii=False)}\n"
                + (f"STAFF YOU CAN NAME: {STAFF_DIRECTORY}\n" if p.role != "patient" else "")
                + f"WHAT YOU DID SO FAR: {json.dumps(memory[-8:], ensure_ascii=False)}\n"
                f"YOUR SCREEN NOW: {json.dumps(view, ensure_ascii=False, default=str)[:5000]}")
        return self.provider.structured(_system(p), user, Step)

    def verdict(self, p: Persona, memory: list[str], final_view: dict[str, Any]) -> Verdict | None:
        user = ("The session is over. Judge honestly, as this person, whether Tasleem did your job to be done. "
                f"WHAT YOU DID AND WHAT HAPPENED: {json.dumps(memory, ensure_ascii=False)}\n"
                f"YOUR SCREEN AT THE END: {json.dumps(final_view, ensure_ascii=False, default=str)[:4000]}")
        return self.provider.structured(_system(p), user, Verdict)


class ScriptedBrain:
    """Offline: each persona plays its scripted actions once, then finishes. For tests and CI."""
    name = "scripted"

    def __init__(self) -> None:
        self.pos: dict[str, int] = {}

    def step(self, p: Persona, view: dict[str, Any], memory: list[str], menu: dict[str, str]) -> Step | None:
        i = self.pos.get(p.user, 0)
        self.pos[p.user] = i + 1
        if i >= len(p.script):
            return Step(thought="Done for now.", action="finish")
        action, args = p.script[i]
        case_id = None
        if p.role == "patient":
            cases = view.get("my_cases") or []
            case_id = cases[0]["case_id"] if cases else None
        elif action == "open_my_first_item":
            items = [it for s in (view.get("my_work") if isinstance(view.get("my_work"), list) else [])
                     for it in s["items"]]
            return Step(thought="Look at the first thing in my list.", action="view_case" if items else "finish",
                        case_id=items[0]["case_id"] if items else None)
        elif action == "view_metrics":
            return Step(thought="Read the programme numbers.", action="finish")
        return Step(thought="Scripted.", action=action, case_id=case_id, args=args)

    def verdict(self, p: Persona, memory: list[str], final_view: dict[str, Any]) -> Verdict | None:
        return None


# -------------------------------------------------------------------------------------------- the run
def run(world: World, brain: Brain, rounds: int = 2, steps: int = 3,
        log: Callable[[str], None] = lambda s: None) -> dict[str, Any]:
    memory: dict[str, list[str]] = {p.user: [] for p in PERSONAS}
    focus: dict[str, list[str]] = {p.user: [] for p in PERSONAS}
    failed_turns = 0
    for r in range(1, rounds + 1):
        world.round = r
        for p in PERSONAS:
            actions = PATIENT_ACTIONS if p.role == "patient" else STAFF_ACTIONS
            menu = {k: v[0] for k, v in actions.items()}
            for _ in range(steps):
                view = screen(world, p, focus[p.user])
                st = brain.step(p, view, memory[p.user], menu)
                if st is None:
                    failed_turns += 1
                    memory[p.user].append(f"R{r}: (no decision: model unavailable)")
                    break
                if st.action == "finish" or st.action not in actions:
                    note = "finished" if st.action == "finish" else f"tried unknown action {st.action!r}"
                    memory[p.user].append(f"R{r}: {note}. {st.thought}")
                    break
                if st.action == "view_case":
                    if st.case_id:
                        focus[p.user] = [st.case_id] + [c for c in focus[p.user] if c != st.case_id]
                    memory[p.user].append(f"R{r}: opened case {st.case_id}. {st.thought}")
                    continue
                handler = actions[st.action][1]
                assert handler is not None
                if p.role == "patient":
                    own = [c["case_id"] for c in view.get("my_cases") or []]
                    if own and st.case_id not in own:
                        st.case_id = own[0]  # a patient taps a button on their own case; there is no id to type
                status, result = handler(world, p, {"action": st.action, "case_id": st.case_id, "args": st.args})
                memory[p.user].append(f"R{r}: {st.action} {st.case_id} {json.dumps(st.args, ensure_ascii=False)} "
                                      f"-> {status} {result}. {st.thought}")
                log(f"  R{r} {p.user:11} {st.action:16} {status}")
        # Time passes: the scheduler checks deadlines and escalates (R4).
        world.api("coord-sara", "tick", "POST", "/v1/system/tick",
                  {"now": (datetime.now(UTC) + timedelta(hours=26 * r)).isoformat()})
    verdicts: dict[str, Any] = {}
    for p in PERSONAS:
        v = brain.verdict(p, memory[p.user], screen(world, p, focus[p.user]))
        verdicts[p.user] = v.model_dump() if v else None
    return {"memory": memory, "verdicts": verdicts, "failed_turns": failed_turns}


# ------------------------------------------------------------------------------------------- checks
@dataclass
class Check:
    persona: str
    check: str
    passed: bool
    detail: str


def _all_cases(w: World) -> list[dict[str, Any]]:
    items = w.get("coord-sara", "/v1/cases").get("items", [])
    return [w.get("coord-sara", f"/v1/cases/{i['id']}") for i in items]


def _in_work(w: World, user: str, case_id: str, kinds: tuple[str, ...] | None = None) -> bool:
    for s in w.get(user, "/v1/me/work").get("sections", []):
        if kinds and s["kind"] not in kinds:
            continue
        if any(i["id"] == case_id for i in s["items"]):
            return True
    return False


def _case_of(cases: list[dict[str, Any]], patient: str) -> dict[str, Any] | None:
    return next((c for c in cases if c.get("patient", {}).get("id") == patient), None)


def _patient_barriers(case: dict[str, Any], patient: str) -> list[dict[str, Any]]:
    return [b for b in case.get("barriers", []) if b.get("reported_by") == patient]


def checks(w: World) -> list[Check]:
    """Deterministic: each persona's job and the safety invariants, read back from the API."""
    out: list[Check] = []
    cases = _all_cases(w)
    staff = {p["id"]: p for p in w.get("coord-sara", "/v1/directory/people").get("staff", [])}
    clinicians = {i for i, s in staff.items() if s["role"] in ("family_physician", "clinic_lead", "gi_specialist")}

    # Safety invariants on every case.
    for c in cases:
        if c.get("status") == "open":
            out.append(Check("all", f"R1 one named owner ({c['patient']['id']})", bool(c.get("owner", {}).get("id")),
                             c.get("owner", {}).get("id") or "no owner"))
        audit = w.get("coord-sara", f"/v1/cases/{c['id']}/audit")
        ok = (audit.get("verification") or {}).get("ok")
        out.append(Check("all", f"R6 audit chain intact ({c['patient']['id']})", ok is True,
                         f"{(audit.get('verification') or {}).get('checked')} events checked"))
        if c.get("status") == "closed":
            o = c.get("outcome") or {}
            has_basis = bool(o.get("evidence_ref") or o.get("reason") or o.get("decided_by"))
            out.append(Check("all", f"R3 closure has outcome and evidence or reason ({c['patient']['id']})",
                             bool(o.get("outcome") or o.get("code")) and has_basis, json.dumps(o)[:160]))
    server_errors = [c for c in w.calls if c.status >= 500]
    out.append(Check("all", "no server errors during the run", not server_errors,
                     "; ".join(f"{c.user} {c.method} {c.path} {c.status}" for c in server_errors[:5]) or "none"))

    # Whatever a patient reports must reach a named person who sees it in their work list.
    for pid in ("p-noura", "p-fatma", "p-john", "p-yousef"):
        c = _case_of(cases, pid)
        if not c:
            out.append(Check(pid, "patient has an open case", False, "no case"))
            continue
        open_bars = [b for b in _patient_barriers(c, pid) if b.get("status") in ("reported", "confirmed")]
        if not open_bars:
            out.append(Check(pid, "what the patient reported was acted on or is still visible", True,
                             "no open barrier left (handled or never reported)"))
            continue
        who = {c["owner"]["id"]}
        ns = c.get("next_step") or {}
        if (ns.get("person") or {}).get("id"):
            who.add(ns["person"]["id"])
        seen_by = sorted(u for u in who if _in_work(w, u, c["id"], ("task", "distress", "escalated", "handoff")))
        out.append(Check(pid, "an open patient report is in an action list of the person who must act",
                         bool(seen_by), f"must act: {sorted(who)}; sees it as an action: {seen_by or 'nobody'}"))

    # Navigator: a case whose next step is the navigator's must be in the navigator's work list.
    for c in cases:
        ns = c.get("next_step") or {}
        if c.get("status") == "open" and ns.get("who") == "navigator" and (ns.get("person") or {}).get("id"):
            nav = ns["person"]["id"]
            out.append(Check(nav, f"navigator step for {c['patient']['id']} is in the navigator's work list",
                             _in_work(w, nav, c["id"]), ns.get("text", "")[:120]))

    # Distress: every open distress flag goes to a clinician and is on top of their list.
    for c in cases:
        for d in c.get("distress", []):
            if d.get("resolved"):
                continue
            to = d.get("routed_to")
            out.append(Check("p-sunita" if c["patient"]["id"] == "p-sunita" else c["patient"]["id"],
                             f"distress ({c['patient']['id']}) routed to a clinician", to in clinicians, f"to={to}"))
            out.append(Check(to or "?", f"distress ({c['patient']['id']}) is in the clinician's distress section",
                             bool(to) and _in_work(w, to, c["id"], ("distress",)), f"to={to}"))

    # Done elsewhere: a non-clinician owner cannot accept the evidence, so a clinician must be asked.
    john = _case_of(cases, "p-john")
    if john and john.get("status") == "open" and any(
            "DONE_ELSEWHERE" in (b.get("reported_codes") or []) or b.get("confirmed_code") == "DONE_ELSEWHERE"
            for b in john.get("barriers", [])):
        owner = john["owner"]["id"]
        clin_sees = sorted(u for u in clinicians if _in_work(w, u, john["id"]))
        out.append(Check("p-john", "'done elsewhere' report reaches a clinician who can accept the evidence",
                         owner in clinicians or bool(clin_sees), f"owner={owner}; clinicians who see it: {clin_sees}"))

    # Rajesh: the companion must not let him believe he is done while the clinical loop is still open.
    raj = _case_of(cases, "p-rajesh")
    if raj and raj.get("status") == "open":
        msg = next((i["message"] for i in w.get("p-rajesh", "/v1/me/cases").get("items", [])
                    if i["case_id"] == raj["id"]), "")
        out.append(Check("p-rajesh", "companion says the follow-up is not finished while no report exists",
                         "not finished" in msg.lower() or "will contact you" in msg.lower(), msg[:160]))

    # A patient who told us something sees that it was received and who acts next, not the stage prompt again.
    for pid in ("p-noura", "p-fatma", "p-john", "p-yousef", "p-sunita"):
        c = _case_of(cases, pid)
        open_bars = [b for b in (c or {}).get("barriers", []) if b.get("status") != "resolved"]
        if not c or c.get("status") != "open" or not open_bars:
            continue
        msg = next((i["message"] for i in w.get(pid, "/v1/me/cases").get("items", []) if i["case_id"] == c["id"]), "")
        acked = msg.startswith(("Thank you", "شكراً")) and "book a visit" not in msg and "يرجى حجز" not in msg
        out.append(Check(pid, "companion acknowledges the open request and does not repeat the old prompt", acked,
                         msg[:160]))

    # Escalation must give the power to act: whoever a stall is escalated to can reassign the case (R2 two-step).
    for c in cases:
        if c.get("status") != "open" or c.get("pending_handoff"):
            continue  # a handoff already waiting must be accepted or declined first (R2)
        targets = {(s.get("escalated_to") or {}).get("id") for s in c.get("stalls", [])} - {None, c["owner"]["id"]}
        for u in targets:
            if staff.get(u, {}).get("role") != "clinic_lead":
                continue
            acts = w.get(u, f"/v1/cases/{c['id']}").get("actions") or {}
            ok = (acts.get("offer_handoff") or {}).get("allowed") is True
            out.append(Check(u, f"clinic lead can reassign the escalated case ({c['patient']['id']})", ok,
                             json.dumps(acts.get("offer_handoff"))[:160]))

    # Coordinator: verified completion and status-says-completed side by side; no case without an owner.
    m = w.get("coord-sara", "/v1/program/metrics")
    out.append(Check("coord-sara", "metrics show verified completion next to Malaffi 'completed'",
                     "verified_complete" in m and "referral_status_says_completed" in m,
                     f"verified={m.get('verified_complete')} malaffi={m.get('referral_status_says_completed')}"))
    out.append(Check("coord-sara", "no open case without an owner", m.get("open_cases_without_owner") in (0, None),
                     f"{m.get('open_cases_without_owner')}"))
    return out


# ------------------------------------------------------------------------------------------- report
def report(res: dict[str, Any], chks: list[Check], calls: list[Call], brain_name: str, rounds: int) -> str:
    passed = sum(c.passed for c in chks)
    lines = [
        "# AI-user simulation: personas with a job to be done, using the real product",
        "",
        f"Run on {datetime.now(UTC):%d %b %Y}. Agents: `{brain_name}`. {len(PERSONAS)} personas, {rounds} rounds, "
        f"{len(calls)} API calls against one shared synthetic world. Reproduce: "
        "`cd backend && python -m tasleem.bench.personas --provider groq`.",
        "",
        "Method (after multi-agent simulators such as MiroFish): each AI user has a profile, incentives and a job "
        "to be done, keeps a memory of what it did, and acts only through the API the web app uses, signed in as "
        "its own demo user. Patients act first in each round, staff then see what patients reported, then the "
        "scheduler moves time on. **Pass/fail comes from deterministic checks on API state, never from the "
        "models' opinions.** The verdicts are each persona's own words and are kept for friction, not as proof.",
        "",
        f"## Deterministic checks: {passed} of {len(chks)} passed",
        "",
        "| Who | Check | Result | Detail |",
        "|---|---|---|---|",
    ]
    for c in sorted(chks, key=lambda c: (c.passed, c.persona)):
        lines.append(f"| {c.persona} | {c.check} | {'pass' if c.passed else '**FAIL**'} | "
                     f"{c.detail.replace('|', '/')[:200]} |")
    lines += ["", "## Each persona: job to be done and verdict", ""]
    for p in PERSONAS:
        v = res["verdicts"].get(p.user)
        lines += [f"### {p.name} ({p.role.replace('_', ' ')})", "", f"**Job to be done.** {p.jtbd}", ""]
        if v:
            lines += [f"**Verdict:** job done: {'yes' if v['job_done'] else 'no'}, score {v['score']}/5. "
                      f"\"{v['quote']}\"", ""]
            if v["what_worked"]:
                lines.append("- Worked: " + "; ".join(v["what_worked"]))
            if v["friction"]:
                lines.append("- Friction: " + "; ".join(v["friction"]))
            lines.append("")
        lines += ["What they did:", ""] + [f"- {m}" for m in res["memory"][p.user]] + [""]
    errors = [c for c in calls if c.status >= 400]
    lines += ["## Refused or failed calls", "",
              "Refusals are often correct (a rule protecting the patient). Each is listed so a human can judge.", ""]
    lines += [f"- R{c.round} `{c.user}` {c.action}: {c.method} {c.path} -> {c.status} {c.error or ''}"
              for c in errors] or ["- none"]
    lines += ["", f"Turns with no model decision (rate limit or invalid reply): {res['failed_turns']}.", ""]
    return "\n".join(lines)


def make_world() -> tuple[World, Any]:
    from fastapi.testclient import TestClient

    from ..api.app import create_app
    from ..config import Settings

    app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True,
                              metrics_max_staleness_seconds=0, rate_limit_per_second=0))
    tc = TestClient(app)
    tc.__enter__()
    return World(tc), tc


def make_brain(kind: str) -> Brain:
    if kind == "scripted":
        return ScriptedBrain()
    from tasleem_agent.providers import make_openai_compat

    prov = make_openai_compat(kind, timeout=90)
    prov.max_retries, prov.max_wait = 8, 65  # free tiers rate-limit per minute: wait rather than give up
    return LLMBrain(prov)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--provider", default="groq", help="groq | nvidia | openrouter | gemini | scripted")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    world, tc = make_world()
    brain = make_brain(a.provider)
    try:
        res = run(world, brain, a.rounds, a.steps, log=print)
        chks = checks(world)
    finally:
        tc.__exit__(None, None, None)
    md = report(res, chks, world.calls, brain.name, a.rounds)
    print(f"\n{sum(c.passed for c in chks)} of {len(chks)} checks passed")
    for c in chks:
        if not c.passed:
            print(f"FAIL {c.persona}: {c.check} :: {c.detail}")
    if not a.no_write:
        OUT_MD.write_text(md, encoding="utf-8")
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps({"brain": brain.name, "rounds": a.rounds, "result": res,
                                        "checks": [c.__dict__ for c in chks],
                                        "calls": [c.__dict__ for c in world.calls]},
                                       ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
