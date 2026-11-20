from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..domain.actions import available_actions, next_step, viewer_step
from ..domain.audit import verify
from ..domain.errors import DomainError, NotFound
from ..domain.messaging import check_patient_text
from ..domain.model import Actor, ActorType, BarrierCode, CaseState, to_utc
from ..services.fhir import ReferralStatusMessage
from ..services.scheduler import tick
from ..services.views import case_detail, patient_view, worklist_item
from .context import AppContext, Services
from .deps import (
    current_actor,
    get_ctx,
    get_services,
    require_demo,
    require_integration,
    require_outbox,
    require_patient,
    require_staff,
    utcnow,
)
from .schemas import (
    AckIn,
    AnswerIn,
    BarrierIn,
    CloseIn,
    ConfirmBarrierIn,
    ConsultIn,
    ContactIn,
    DeliveryFailureIn,
    HandoffIn,
    NoteIn,
    PatientMessageIn,
    PrepAnswersIn,
    RejectIn,
    ReportReviewIn,
    TextIn,
    TickIn,
)

health = APIRouter(tags=["system"])
ingest = APIRouter(prefix="/v1/ingest", tags=["ingest"])
cases = APIRouter(prefix="/v1/cases", tags=["cases"])
me = APIRouter(prefix="/v1/me", tags=["patient"])
program = APIRouter(prefix="/v1/program", tags=["program"])
system = APIRouter(prefix="/v1", tags=["system"])
policy = APIRouter(prefix="/v1/policy", tags=["policy"])
integration = APIRouter(prefix="/v1/integration", tags=["integration"])
demo = APIRouter(prefix="/v1/demo", tags=["demo"])

INBOX_ORDER = ["distress", "escalated", "handoff", "consult", "task", "owner"]
INBOX_LABELS = {
    "distress": "Patient messages that need a clinician",
    "escalated": "Stalled cases you own or that were escalated to you",
    "handoff": "Cases offered to you",
    "consult": "E-consult questions for you",
    "task": "Tasks assigned to you: patient replies to confirm, calls and rebooking",
    "owner": "All open cases you own",
}


def _notification(m: Any) -> dict[str, Any]:
    return {"id": m.id, "case_id": m.case_id, "event_seq": m.event_seq, "channel": m.channel,
            "recipient": m.recipient_id, "recipient_role": m.recipient_role or None,
            "template": m.template, "urgent": m.urgent, "status": m.status,
            "created_at": m.created_at, "delivered_at": m.delivered_at, "payload": m.payload}


def _detail(svc: Services, ctx: AppContext, case_id: str, viewer: Actor | None = None) -> dict[str, Any]:
    st = svc.cases.get(case_id)
    now = utcnow()
    out = case_detail(st, svc.cases.repo.events(case_id), ctx.registry, svc.directory, now)
    p = ctx.registry.get(st.pathway_id)
    step = next_step(st, p)
    if step and step["who"] in ("owner", "navigator", "clinician"):
        who = step["who"]
        if who == "owner":
            pid = st.owner_id
        elif who == "clinician":
            pid = svc.directory.resolver(st, "clinician")
        else:
            pid = svc.directory.person_for_role(st, who)
        person = svc.directory.person(pid)
        step["person"] = {"id": pid, "name": person.name if person else pid}
    if viewer is not None:
        mine = viewer_step(st, viewer.id, svc.cases.covers(viewer, now), lambda pid: _short(svc, pid))
        if mine is not None:
            mine["person"] = {"id": viewer.id, "name": _short(svc, viewer.id)}
            step = mine
    out["next_step"] = step
    out["actions"] = (available_actions(st, p, viewer, now, svc.cases.covers(viewer, now))
                      if viewer is not None else None)
    out["notifications"] = [_notification(m) for m in svc.cases.repo.outbox(case_id=case_id, limit=200)]
    return out


# ---- health -------------------------------------------------------------------------------------
@health.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up. Never touches the database, so a DB blip does not restart pods."""
    return {"status": "ok"}


@health.get("/readyz")
def readyz(svc: Services = Depends(get_services)) -> dict[str, str]:
    """Readiness: the database answers. Load balancers stop routing here when it does not."""
    svc.session.execute(text("SELECT 1"))
    return {"status": "ready"}


# ---- ingest -------------------------------------------------------------------------------------
@ingest.post("/fhir")
def ingest_fhir(payload: dict[str, Any] = Body(...), source: str = Depends(require_integration),
                x_message_id: str | None = Header(default=None),
                svc: Services = Depends(get_services)) -> dict[str, Any]:
    return {"results": svc.ingest.ingest_fhir(payload, source, utcnow(), x_message_id)}


@ingest.post("/referral-status")
def ingest_referral_status(msg: ReferralStatusMessage, source: str = Depends(require_integration),
                           svc: Services = Depends(get_services)) -> dict[str, Any]:
    return svc.ingest.ingest_referral_status(msg, source, utcnow())


# ---- cases (care team) --------------------------------------------------------------------------
@cases.get("")
def list_cases(owner: str | None = None, status: str | None = Query(default="open", pattern="^(open|closed|all)$"),
               stalled: bool | None = None, pathway: str | None = None, limit: int = Query(100, ge=1, le=500),
               offset: int = Query(0, ge=0, le=100_000),
               actor: Actor = Depends(require_staff), ctx: AppContext = Depends(get_ctx),
               svc: Services = Depends(get_services)) -> dict[str, Any]:
    rows = svc.cases.repo.list(owner_id=owner, status=None if status == "all" else status, stalled=stalled,
                               pathway_id=pathway, limit=limit + 1, offset=offset,
                               visible_to=svc.cases.scope(actor))
    now = utcnow()
    more = len(rows) > limit
    return {"items": [worklist_item(r, ctx.registry, svc.directory, now) for r in rows[:limit]],
            "next_offset": offset + limit if more else None}


@cases.get("/{case_id}")
def get_case(case_id: str, actor: Actor = Depends(require_staff), ctx: AppContext = Depends(get_ctx),
             svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    return _detail(svc, ctx, case_id, actor)


@cases.get("/{case_id}/notifications")
def case_notifications(case_id: str, actor: Actor = Depends(require_staff),
                       svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    return {"items": [_notification(m) for m in svc.cases.repo.outbox(case_id=case_id, limit=500)]}


@cases.post("/{case_id}/handoff")
def handoff(case_id: str, body: HandoffIn, actor: Actor = Depends(require_staff),
            ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.offer_handoff(case_id, actor, body.to, body.reason, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/handoff/accept")
def handoff_accept(case_id: str, actor: Actor = Depends(require_staff), ctx: AppContext = Depends(get_ctx),
                   svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.accept_handoff(case_id, actor, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/handoff/reject")
def handoff_reject(case_id: str, body: RejectIn, actor: Actor = Depends(require_staff),
                   ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.reject_handoff(case_id, actor, body.reason_code, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/barriers")
def report_barrier(case_id: str, body: BarrierIn, actor: Actor = Depends(current_actor),
                   svc: Services = Depends(get_services)) -> dict[str, Any]:
    if actor.type != ActorType.PATIENT:
        svc.cases.require_visible(case_id, actor)
    st, bid = svc.cases.report_barrier(case_id, actor, body.codes, body.text, utcnow())
    b = st.barriers[bid]
    return {"barrier": b.model_dump(mode="json"), "routed_to_human": True,
            "distress_flagged": any(d.barrier_id == bid for d in st.open_distress)}


@cases.post("/{case_id}/barriers/{barrier_id}/confirm")
def confirm_barrier(case_id: str, barrier_id: str, body: ConfirmBarrierIn, actor: Actor = Depends(require_staff),
                    ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.confirm_barrier(case_id, actor, barrier_id, body.code, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/barriers/{barrier_id}/resolve")
def resolve_barrier(case_id: str, barrier_id: str, body: NoteIn, actor: Actor = Depends(require_staff),
                    ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.resolve_barrier(case_id, actor, barrier_id, body.note, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/distress/{distress_id}/resolve")
def resolve_distress(case_id: str, distress_id: str, body: NoteIn, actor: Actor = Depends(require_staff),
                     ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.resolve_distress(case_id, actor, distress_id, body.note, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/contact-attempts")
def contact(case_id: str, body: ContactIn, actor: Actor = Depends(require_staff),
            ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.log_contact(case_id, actor, body.channel, body.result, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/consults")
def consult(case_id: str, body: ConsultIn, actor: Actor = Depends(require_staff),
            ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    _, cid = svc.cases.request_consult(case_id, actor, body.to, body.question, utcnow())
    return {"consult_id": cid, "case": _detail(svc, ctx, case_id, actor)}


@cases.post("/{case_id}/consults/{consult_id}/answer")
def answer(case_id: str, consult_id: str, body: AnswerIn, actor: Actor = Depends(require_staff),
           ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.answer_consult(case_id, actor, consult_id, body.answer, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/reports/{report_id}/review")
def review_report(case_id: str, report_id: str, body: ReportReviewIn, actor: Actor = Depends(require_staff),
                  ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    """Evidence Reader: a clinician confirms or corrects what a free-text report says. Rules act only on this."""
    svc.cases.require_visible(case_id, actor)
    svc.cases.review_report(case_id, actor, report_id, dict(body.findings), utcnow(),
                            suggested_by=body.suggested_by,
                            suggestion=dict(body.suggestion) if body.suggestion is not None else None)
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/patient-messages")
def message_patient(case_id: str, body: PatientMessageIn, actor: Actor = Depends(require_staff),
                    ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    """A person sends a plain-language message to the patient's Sahatna inbox (optionally an approved AI
    draft). Refused with IFHAS_MESSAGE_POLICY if it would disclose a result or give advice."""
    svc.cases.require_visible(case_id, actor)
    svc.cases.send_patient_message(case_id, actor, body.text, body.language, utcnow(), body.ai_draft_id)
    return _detail(svc, ctx, case_id, actor)


@cases.post("/{case_id}/close")
def close(case_id: str, body: CloseIn, actor: Actor = Depends(require_staff), ctx: AppContext = Depends(get_ctx),
          svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    svc.cases.close(case_id, actor, body.outcome, body.evidence_ref, body.reason, utcnow())
    return _detail(svc, ctx, case_id, actor)


@cases.get("/{case_id}/referral-options")
def referral_options(case_id: str, actor: Actor = Depends(require_staff), ctx: AppContext = Depends(get_ctx),
                     svc: Services = Depends(get_services)) -> dict[str, Any]:
    st = svc.cases.require_visible(case_id, actor)
    p = ctx.registry.get(st.pathway_id)
    prefer_female = any(BarrierCode.FEMALE_CLINICIAN in (b.reported_codes or []) or
                        BarrierCode.FEMALE_CLINICIAN in (b.confirmed_code, b.suggested_code)
                        for b in st.barriers.values())
    return {"service": p.referral_service, "prefer_female": prefer_female,
            "options": svc.directory.referral_options(st.patient_id, p.referral_service, prefer_female)}


@cases.get("/{case_id}/audit")
def audit(case_id: str, actor: Actor = Depends(require_staff), svc: Services = Depends(get_services)) -> dict[str, Any]:
    svc.cases.require_visible(case_id, actor)
    events = svc.cases.repo.events(case_id)
    v = verify(events)
    return {"verification": {"ok": v.ok, "checked": v.checked, "broken_at_seq": v.broken_at_seq,
                             "problem": v.problem},
            "events": [{"seq": e.seq, "type": e.type, "actor_id": e.actor_id, "actor_type": e.actor_type,
                        "occurred_at": e.occurred_at, "prev_hash": e.prev_hash, "hash": e.hash} for e in events]}


# ---- me: identity and personal inbox ------------------------------------------------------------
@me.get("")
def whoami(actor: Actor = Depends(current_actor), svc: Services = Depends(get_services)) -> dict[str, Any]:
    p = svc.directory.person(actor.id)
    if p is not None:
        return {"id": p.id, "name": p.name, "role": p.role, "actor_type": actor.type.value, "org_id": p.org_id,
                "sees_all_cases": svc.cases.scope(actor) is None}
    pat = svc.directory.patient(actor.id)
    return {"id": actor.id, "name": pat.display_name if pat else actor.id, "role": "patient",
            "actor_type": actor.type.value, "language": pat.preferred_language if pat else "en"}


def _short(svc: Services, pid: str) -> str:
    """A person's display name without the role suffix ("Dr. Fatima"), never a raw id when the directory knows them."""
    p = svc.directory.person(pid)
    return p.name.split(" (")[0] if p else pid


@me.get("/work")
def my_work(actor: Actor = Depends(require_staff), ctx: AppContext = Depends(get_ctx),
            svc: Services = Depends(get_services)) -> dict[str, Any]:
    """Everything waiting on this person, grouped by why. One indexed query on case_assignments."""
    rows = svc.cases.inbox_for(actor.id)
    by_kind: dict[str, list[Any]] = {}
    for a in rows:
        by_kind.setdefault(a.kind, []).append(a)
    cases_by_id = {r.id: r for r in svc.cases.repo.rows_by_ids(list({a.case_id for a in rows}))}
    now = utcnow()
    covers = svc.cases.covers(actor, now)
    sections = []
    for kind in INBOX_ORDER:
        grouped: dict[str, list[Any]] = {}
        for a in by_kind.get(kind, []):
            grouped.setdefault(a.case_id, []).append(a)
        items = []
        for case_id, rows_for_case in grouped.items():
            row = cases_by_id.get(case_id)
            if row is None or row.status != "open":
                continue
            item = worklist_item(row, ctx.registry, svc.directory, now)
            mine = viewer_step(CaseState.model_validate(row.state_json), actor.id, covers,
                               lambda pid: _short(svc, pid))
            if mine is not None:
                item["next_action"] = {"reason": mine["reason"], "who": "you", "text": mine["text"]}
            items.append({**item,
                          "why": {"kind": kind, "refs": [a.ref for a in rows_for_case],
                                  "since": min(a.since for a in rows_for_case)}})
        items.sort(key=lambda i: (-len(i["stalls"]), -i["escalation_level"], -i["days_since_progress"]))
        sections.append({"kind": kind, "label": INBOX_LABELS[kind], "count": len(items), "items": items})
    needs_action = sum(sec["count"] for sec in sections if sec["kind"] != "owner")
    covering = [{"id": p.id, "name": p.name, "until": p.away_until} for p in svc.directory.covering_for(actor.id)]
    return {"person": actor.id, "needs_action": needs_action, "sections": sections, "covering": covering}


class AbsenceIn(BaseModel):
    until: datetime | None = None  # None ends the absence
    cover_id: str | None = Field(default=None, max_length=64)


@me.put("/absence")
def set_my_absence(body: AbsenceIn, actor: Actor = Depends(require_staff),
                   svc: Services = Depends(get_services)) -> dict[str, Any]:
    """TSL-160: name a cover while away. Ownership stays with you (R1); your work list and new escalations go
    to the cover until you are back (R4 still reaches a named person)."""
    if body.until is not None:
        if body.until <= utcnow():
            raise DomainError("VALIDATION", "The end of the absence must be in the future.")
        cover = svc.directory.person(body.cover_id or "")
        if cover is None or cover.id == actor.id:
            raise DomainError("VALIDATION", "Name a colleague in the directory as your cover.")
        if cover.away():
            raise DomainError("VALIDATION", f"{cover.name} is away too. Choose someone who is in.")
    p = svc.directory.set_absence(actor.id, body.until, body.cover_id)
    svc.cases.bump_write_version()
    return {"id": p.id, "away_until": p.away_until, "cover_id": p.cover_id}


# ---- patient companion --------------------------------------------------------------------------
@me.get("/cases")
def my_cases(lang: str | None = None, actor: Actor = Depends(require_patient), ctx: AppContext = Depends(get_ctx),
             svc: Services = Depends(get_services)) -> dict[str, Any]:
    pat = svc.directory.patient(actor.id)
    language = lang or (pat.preferred_language if pat else "en")
    states = svc.cases.repo.find_open_for_patient(actor.id)
    return {"items": [patient_view(s, ctx.registry, language) for s in states]}


@me.post("/cases/{case_id}/consent")
def my_consent(case_id: str, actor: Actor = Depends(require_patient), ctx: AppContext = Depends(get_ctx),
               svc: Services = Depends(get_services)) -> dict[str, Any]:
    st = svc.cases.record_consent(case_id, actor, utcnow())
    pat = svc.directory.patient(actor.id)
    return patient_view(st, ctx.registry, pat.preferred_language if pat else "en")


def _prep_pathway(ctx: AppContext, svc: Services, case_id: str, actor: Actor) -> Any:
    st = svc.cases.get(case_id)
    if st.patient_id != actor.id:
        raise NotFound("case", case_id)
    p = ctx.registry.get(st.pathway_id)
    if not p.prep_check:
        raise NotFound("prep check", case_id)
    return p


def _patient_lang(svc: Services, actor: Actor, lang: str | None = None) -> str:
    if lang in ("en", "ar"):
        return lang
    pat = svc.directory.patient(actor.id)
    return pat.preferred_language if pat and pat.preferred_language in ("en", "ar") else "en"


@me.get("/cases/{case_id}/prep-check")
def prep_check(case_id: str, lang: str | None = None, actor: Actor = Depends(require_patient),
               ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    """Teach-back questions in the patient's language. Correct answers are never sent to the client."""
    p = _prep_pathway(ctx, svc, case_id, actor)
    language = _patient_lang(svc, actor, lang)
    return {"case_id": case_id, "language": language, "direction": "rtl" if language == "ar" else "ltr",
            "questions": [{"id": q.id, "text": q.text.get(language, q.text["en"]),
                           "options": [{"id": o.id, "text": o.text.get(language, o.text["en"])} for o in q.options]}
                          for q in p.prep_check]}


PREP_REPLY = {
    True: {"en": "Thank you. A member of the care team will call you to go through the preparation together.",
           "ar": "شكراً لك. سيتصل بك أحد أعضاء فريق الرعاية لمراجعة التحضير معك."},
    False: {"en": "Thank you. You are ready for the preparation.", "ar": "شكراً لك. أنت جاهز للتحضير."},
}


@me.post("/cases/{case_id}/prep-check")
def prep_check_answer(case_id: str, body: PrepAnswersIn, lang: str | None = None,
                      actor: Actor = Depends(require_patient),
                      ctx: AppContext = Depends(get_ctx), svc: Services = Depends(get_services)) -> dict[str, Any]:
    """A wrong or missing answer opens a barrier (PREP_UNCLEAR, or the question's own code) so a navigator
    goes through it with the patient. The patient is never told they 'failed'."""
    p = _prep_pathway(ctx, svc, case_id, actor)
    wrong = [q for q in p.prep_check if body.answers.get(q.id) != q.correct]
    codes = sorted({q.barrier_on_wrong for q in wrong}, key=lambda c: c.value)
    barrier_id = None
    if codes:
        _, barrier_id = svc.cases.report_barrier(case_id, actor, codes, None, utcnow())
    return {"all_correct": not wrong, "follow_up_needed": bool(wrong), "barrier_id": barrier_id,
            "barrier_codes": [c.value for c in codes],
            "message": PREP_REPLY[bool(wrong)][_patient_lang(svc, actor, lang)]}


# ---- policy -------------------------------------------------------------------------------------
@policy.post("/patient-message-check")
def patient_message_check(body: TextIn, actor: Actor = Depends(require_staff)) -> dict[str, Any]:
    """The same deterministic check the engine runs before sending. The AI agent calls it on every draft."""
    v = check_patient_text(body.text)
    return {"ok": not v, "violations": [{"code": x.code, "detail": x.detail} for x in v]}


# ---- program ------------------------------------------------------------------------------------
@program.get("/metrics")
def metrics(pathway: str | None = None, org: str | None = Query(default=None, max_length=64),
            language: str | None = Query(default=None, pattern="^(en|ar)$"), actor: Actor = Depends(require_staff),
            svc: Services = Depends(get_services)) -> dict[str, Any]:
    return svc.metrics.get(pathway, org, language)


@program.get("/ai-oversight")
def ai_oversight_view(actor: Actor = Depends(require_staff), svc: Services = Depends(get_services)) -> dict[str, Any]:
    """A5: AI suggestions made, accepted and corrected by people, from the audit log (acceptance monitoring)."""
    from ..services.ai_oversight import ai_oversight
    return ai_oversight(svc.session)


@program.get("/usage")
def usage(month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), actor: Actor = Depends(require_staff),
          svc: Services = Depends(get_services)) -> dict[str, Any]:
    """Active cases per provider and pathway in a calendar month: the unit of the per-active-case
    pricing hypothesis. Programme coordinator only."""
    if actor.type != ActorType.COORDINATOR:
        raise DomainError("FORBIDDEN", "Programme coordinator only.")
    y, m = (int(x) for x in month.split("-"))
    start = datetime(y, m, 1, tzinfo=UTC)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)
    by_org: dict[str, dict[str, int]] = {}
    for owner_id, pathway_id, n in svc.cases.repo.active_in_period(start, end):
        person = svc.directory.person(owner_id)
        org_cases = by_org.setdefault(person.org_id if person else "unknown", {})
        org_cases[pathway_id] = org_cases.get(pathway_id, 0) + n
    items = [{"org_id": o, "pathways": v, "active_cases": sum(v.values())} for o, v in sorted(by_org.items())]
    return {"month": month, "active_cases": sum(i["active_cases"] for i in items), "by_org": items}


# ---- system and demo ----------------------------------------------------------------------------
@system.post("/system/tick")
def system_tick(body: TickIn | None = None, ctx: AppContext = Depends(get_ctx),
                actor: Actor = Depends(require_staff), svc: Services = Depends(get_services)) -> dict[str, Any]:
    body = body or TickIn()
    if body.now is not None and not ctx.settings.demo_mode:
        raise DomainError("FORBIDDEN", "Time travel is only available in demo mode.")
    now = to_utc(body.now) if body.now else utcnow()
    return tick(svc.cases, now, body.limit)


@system.get("/directory/people", dependencies=[Depends(require_demo)])
def people(svc: Services = Depends(get_services)) -> dict[str, Any]:
    staff = [{"id": p.id, "name": p.name, "role": p.role, "org_id": p.org_id,
              "away_until": p.away_until if p.away() else None, "cover_id": p.cover_id if p.away() else None}
             for p in svc.directory.people()]
    patients = [{"id": p.id, "name": p.display_name, "role": "patient", "language": p.preferred_language}
                for p in svc.directory.patients()]
    return {"staff": staff, "patients": patients}


@system.post("/admin/reset-demo", dependencies=[Depends(require_demo)])
def reset_demo(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    from ..seed import reset_and_seed

    return reset_and_seed(ctx)


# ---- integration: outbound notifications (transactional outbox) ---------------------------------
@integration.get("/outbox")
def pull_outbox(after_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                status: str = Query(default="pending", pattern="^(pending|delivered)$"),
                _: str = Depends(require_outbox), svc: Services = Depends(get_services)) -> dict[str, Any]:
    """Delivery workers (Sahatna push, EMR inbox, SMS gateway) pull pending messages in id order."""
    items = svc.cases.repo.outbox(status=status, after_id=after_id, limit=limit)
    return {"items": [_notification(m) for m in items], "next_after_id": items[-1].id if items else after_id}


@integration.post("/outbox/ack")
def ack_outbox(body: AckIn, _: str = Depends(require_outbox),
               svc: Services = Depends(get_services)) -> dict[str, Any]:
    n = svc.cases.repo.ack_outbox(body.ids, utcnow())
    svc.session.commit()
    return {"acknowledged": n}


@integration.post("/delivery-failures")
def delivery_failure(body: DeliveryFailureIn, caller: str = Depends(require_outbox),
                     svc: Services = Depends(get_services)) -> dict[str, Any]:
    """The notifier reports a message that no channel delivered. For a patient message this creates a
    navigator call task on the case; repeated reports for the same message are ignored."""
    actor = Actor(id=caller, type=ActorType.INTEGRATION)
    st = svc.cases.record_delivery_failure(body.outbox_id, body.channels, actor, utcnow())
    return {"recorded": st is not None, "case_id": st.id if st else None,
            "navigator_task": bool(st and st.open_delivery_alerts)}


# ---- demo: Malaffi feed simulator ---------------------------------------------------------------
@demo.get("/scenarios", dependencies=[Depends(require_demo)])
def demo_scenarios() -> dict[str, Any]:
    from ..demo import list_scenarios

    return {"items": list_scenarios()}


@demo.post("/scenarios/{scenario}", dependencies=[Depends(require_demo)])
def demo_run(scenario: str, body: dict[str, Any] | None = Body(default=None), ctx: AppContext = Depends(get_ctx),
             svc: Services = Depends(get_services)) -> dict[str, Any]:
    from ..demo import run

    out = run(svc, scenario, utcnow(), body)
    out["case"] = _detail(svc, ctx, out["case_id"])
    return out


# ---- unmatched-patient review queue (TSL-161) -------------------------------------------------------------
class UnmatchedResolveIn(BaseModel):
    action: str = Field(pattern="^(match|dismiss)$")
    patient_id: str | None = Field(default=None, max_length=64)


def _coordinator(actor: Actor) -> Actor:
    if actor.type != ActorType.COORDINATOR:
        raise DomainError("FORBIDDEN", "Programme coordinator only.")
    return actor


@integration.get("/unmatched")
def unmatched(actor: Actor = Depends(require_staff), svc: Services = Depends(get_services)) -> dict[str, Any]:
    """Messages for a patient Tasleem does not know. None is dropped: each waits here for a person."""
    _coordinator(actor)
    items = svc.ingest.unmatched()
    return {"items": items, "count": len(items)}


@integration.post("/unmatched/{row_id}/resolve")
def resolve_unmatched(row_id: int, body: UnmatchedResolveIn, actor: Actor = Depends(require_staff),
                      svc: Services = Depends(get_services)) -> dict[str, Any]:
    _coordinator(actor)
    return svc.ingest.resolve_unmatched(row_id, body.action, body.patient_id, actor, utcnow())


# ---- programme export (TSL-182) ----------------------------------------------------------------------------
@program.get("/export.csv")
def export_csv(actor: Actor = Depends(require_staff), ctx: AppContext = Depends(get_ctx),
               svc: Services = Depends(get_services)) -> Response:
    """One row per case for the programme's own reporting. Pseudonymous ids only: no names, no results."""
    import csv
    import io

    from ..domain.model import AdminStatus, CaseState

    _coordinator(actor)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["case_id", "patient_ref", "pathway", "clinic", "owner", "opened_at", "status",
                "malaffi_status", "verified_step", "of_steps", "false_done", "open_stalls", "escalation_level",
                "outcome", "days_to_procedure"])
    for doc in svc.cases.repo.iter_states():
        st = CaseState.model_validate(doc)
        p = ctx.registry.get(st.pathway_id)
        owner = svc.directory.person(st.owner_id)
        reached = [s.id for s in p.stages if s.id in st.stages]
        proc = p.checks.procedure_stage
        days = (round((st.stages[proc].reached_at - st.opened_at).total_seconds() / 86400, 1)
                if proc and proc in st.stages else "")
        false_done = bool(st.admin_status == AdminStatus.COMPLETED and p.checks.evidence_stage
                          and p.checks.evidence_stage not in st.stages)
        w.writerow([st.id, st.patient_id, p.id, owner.org_id if owner else "", st.owner_id,
                    st.opened_at.date().isoformat(), "open" if st.is_open else "closed",
                    st.admin_status.value if st.admin_status else "", len(reached), len(p.stages),
                    "yes" if false_done else "no", ";".join(sorted(str(getattr(r, "value", r)) for r in st.stalls)),
                    max((s.level for s in st.stalls.values()), default=0),
                    st.outcome.value if st.outcome else "", days])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="tasleem-programme.csv"'})


@program.get("/audit-anchor")
def audit_anchor(as_of: datetime | None = None, actor: Actor = Depends(require_staff),
                 svc: Services = Depends(get_services)) -> dict[str, Any]:
    """TSL-173: the root over every case's audit chain as of a moment. Compare it with a root published earlier
    outside the database: any rewritten history changes it."""
    from ..audit_anchor import anchor

    _coordinator(actor)
    return anchor(svc.session, to_utc(as_of) if as_of else None)
