"""Read models for the API: worklist rows, case detail, patient companion and program metrics."""

from __future__ import annotations

import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import datetime
from statistics import median
from typing import Any

from ..domain.audit import StoredEvent
from ..domain.model import CARE_COMPLETED_OUTCOMES, AdminStatus, BarrierCode, CaseState, StallReason, to_utc
from ..domain.pathways import Pathway, PathwayRegistry
from ..infra.cache import WRITE_VERSION_KEY, Cache
from ..infra.db import CaseRow
from .directory import Directory

# Label every timeline item so humans can tell facts from computed results and AI output (Additional.md).
PROVENANCE = {"integration": "fact", "system": "computed", "ai": "ai_suggestion"}

STALL_LABELS = {
    StallReason.STEP_OVERDUE: "Next step overdue",
    StallReason.BOOKED_NOT_ATTENDED: "Booked but not attended",
    StallReason.CONSULT_NO_PROCEDURE: "Seen but no procedure",
    StallReason.CLOSED_WITHOUT_EVIDENCE: "Marked completed without a report",
    StallReason.REPORT_NOT_COMMUNICATED: "Report not communicated",
    StallReason.HANDOFF_NOT_ACCEPTED: "Handoff not accepted",
    StallReason.REFERRAL_REJECTED: "Referral rejected",
    StallReason.CONSULT_UNANSWERED: "E-consult unanswered",
}

BARRIER_LABELS: dict[BarrierCode, dict[str, str]] = {
    BarrierCode.FEAR: {"en": "I feel scared or worried", "ar": "أشعر بالخوف أو القلق"},
    BarrierCode.PREP_UNCLEAR: {"en": "I don't understand the preparation", "ar": "لم أفهم تعليمات التحضير"},
    BarrierCode.NO_ESCORT: {"en": "No one can take me home", "ar": "لا يوجد من يرافقني أو يوصلني"},
    BarrierCode.TRANSPORT: {"en": "Getting there is hard", "ar": "صعوبة في المواصلات"},
    BarrierCode.COST_OR_INSURANCE: {"en": "Cost or insurance", "ar": "التكلفة أو التأمين"},
    BarrierCode.TIME_OR_WORK: {"en": "Work or no time", "ar": "العمل أو ضيق الوقت"},
    BarrierCode.LANGUAGE: {"en": "I need an interpreter", "ar": "أحتاج إلى مترجم"},
    BarrierCode.WANTS_CALLBACK: {"en": "Please call me", "ar": "أريد أن يتصل بي أحد"},
    BarrierCode.DONE_ELSEWHERE: {"en": "I had the test somewhere else", "ar": "أجريت الفحص في مكان آخر"},
    BarrierCode.OTHER: {"en": "Something else", "ar": "سبب آخر"},
}

MISSED_MESSAGE = {
    "en": "We noticed you could not attend. Tell us what got in the way and we will help you rebook.",
    "ar": "لاحظنا أنك لم تتمكن من الحضور. أخبرنا بما منعك وسنساعدك في إعادة الحجز.",
}


def implied_admin_stage(state: CaseState, p: Pathway) -> str | None:
    """What a 'Malaffi referral status only' view would believe the furthest step is."""
    if state.admin_status in (AdminStatus.NONE, AdminStatus.CANCELLED):
        return None
    return p.admin_status_map.get(state.admin_status)


def progress(state: CaseState, p: Pathway) -> dict[str, Any]:
    verified = p.furthest_stage(set(state.stages))
    reported = implied_admin_stage(state, p)
    v_idx = p.stage_index(verified) + 1 if verified else 0
    r_idx = p.stage_index(reported) + 1 if reported else 0
    return {
        "verified": {"stage": verified, "step": v_idx, "of": len(p.stages)},
        "reported": {"admin_status": state.admin_status.value, "implied_stage": reported, "step": r_idx,
                     "of": len(p.stages)},
        "gap": r_idx > v_idx,
    }


def _days_since(dt: datetime, now: datetime) -> float:
    return round((now - to_utc(dt)).total_seconds() / 86400, 1)


def _name(directory: Directory, pid: str) -> dict[str, Any]:
    p = directory.person(pid)
    return {"id": pid, "name": p.name if p else pid, "role": p.role if p else None}


def worklist_item(row: CaseRow, registry: PathwayRegistry, directory: Directory, now: datetime) -> dict[str, Any]:
    st = CaseState.model_validate(row.state_json)
    p = registry.get(st.pathway_id)
    pat = directory.patient(st.patient_id)
    return {
        "id": st.id,
        "patient": {"id": st.patient_id, "name": pat.display_name if pat else st.patient_id,
                    "language": pat.preferred_language if pat else None},
        "pathway": {"id": p.id, "name": p.name},
        "status": st.status,
        "priority": st.priority,
        "owner": _name(directory, st.owner_id),
        "progress": progress(st, p),
        "stalls": [{"reason": s.reason.value, "label": STALL_LABELS[s.reason], "level": s.level}
                   for s in st.stalls.values()],
        "escalation_level": st.escalation_level,
        "days_since_progress": _days_since(st.last_progress_at, now),
        "open_barriers": sum(1 for b in st.barriers.values() if b.status != "resolved"),
        "distress_open": len(st.open_distress),
        "outcome": st.outcome.value if st.outcome else None,
    }


def case_detail(st: CaseState, events: list[StoredEvent], registry: PathwayRegistry, directory: Directory,
                now: datetime) -> dict[str, Any]:
    p = registry.get(st.pathway_id)
    pat = directory.patient(st.patient_id)
    stages = []
    for sd in p.stages:
        ev = st.stages.get(sd.id)
        stages.append({"id": sd.id, "label": sd.label, "note": sd.note, "reached": ev is not None,
                       "reached_at": ev.reached_at if ev else None, "evidence_ref": ev.ref if ev else None,
                       "provenance": "fact" if ev else None})
    timeline = [{"seq": e.seq, "type": e.type, "at": e.occurred_at, "actor": e.actor_id,
                 "provenance": PROVENANCE.get(e.actor_type, "human"), "payload": e.payload} for e in events]
    return {
        "id": st.id,
        "status": st.status,
        "patient": {"id": st.patient_id, "name": pat.display_name if pat else st.patient_id,
                    "language": pat.preferred_language if pat else None,
                    "insurance_network": pat.insurance_network if pat else None,
                    "birth_year": pat.birth_year if pat else None},
        "pathway": {"id": p.id, "name": p.name, "version": p.version},
        "priority": {"value": st.priority, "provenance": "computed", "rule": f"pathway {p.id} v{p.version}"},
        "owner": _name(directory, st.owner_id),
        "pending_handoff": st.pending_handoff.model_dump(mode="json") if st.pending_handoff else None,
        "progress": progress(st, p),
        "stages": stages,
        "appointment_at": st.appointment_at,
        "appointment_missed": st.appointment_missed,
        "stalls": [{**s.model_dump(mode="json"), "label": STALL_LABELS[s.reason],
                    "escalated_to": _name(directory, s.escalated_to), "provenance": "computed"}
                   for s in st.stalls.values()],
        "barriers": [{**b.model_dump(mode="json"),
                      "suggestion_provenance": "ai_suggestion" if b.suggested_code else None}
                     for b in st.barriers.values()],
        "distress": [d.model_dump(mode="json") for d in st.distress.values()],
        "consults": [k.model_dump(mode="json") for k in st.consults.values()],
        "contact_attempts": st.contact_attempts,
        "warnings": st.warnings,
        "consent_at": st.consent_at,
        "outcome": ({"type": st.outcome.value, "evidence_ref": st.outcome_evidence_ref, "reason": st.outcome_reason,
                     "signed_by": st.closed_by, "closed_at": st.closed_at,
                     "care_completed": st.outcome in CARE_COMPLETED_OUTCOMES} if st.outcome else None),
        "days_since_progress": _days_since(st.last_progress_at, now),
        "timeline": timeline,
        "version": st.version,
    }


def patient_view(st: CaseState, registry: PathwayRegistry, lang: str) -> dict[str, Any]:
    """Plain language only. Never includes result values, codes or diagnoses (IFHAS 4.9.2.3)."""
    return patient_view_for(st, registry.get(st.pathway_id), lang)


def patient_view_for(st: CaseState, p: Pathway, lang: str) -> dict[str, Any]:
    lang = lang if lang in ("en", "ar") else "en"
    key = p.furthest_stage(set(st.stages)) or "OPENED"
    msgs = p.patient_messages.get(key) or p.patient_messages.get("OPENED") or {}
    message = msgs.get(lang) or msgs.get("en") or ""
    if StallReason.BOOKED_NOT_ATTENDED.value in st.stalls:
        message = MISSED_MESSAGE[lang]
    return {
        "case_id": st.id,
        "status": st.status,
        "language": lang,
        "direction": "rtl" if lang == "ar" else "ltr",
        "message": message,
        "appointment_at": st.appointment_at if st.appointment_at and not st.appointment_missed else None,
        "consent_given": st.consent_at is not None,
        "barrier_options": [{"code": c.value, "label": BARRIER_LABELS[c][lang]} for c in BarrierCode],
        "open_requests": sum(1 for b in st.barriers.values() if b.status != "resolved"),
    }


class MetricsService:
    """Program metrics with bounded staleness and single-flight recompute.

    Cache key carries the global write version, so a write makes the next read recompute. To stop a busy
    ingest stream from forcing a full scan on every dashboard read, a result younger than
    ``max_staleness`` seconds is served even if writes happened since (flagged ``stale: true``). Only one
    recompute runs per process at a time; concurrent readers wait for it instead of scanning too.
    The scan streams state documents in batches and makes a single pass, so memory stays flat.
    """

    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, states_loader: Callable[[], Iterable[dict]], registry: PathwayRegistry, cache: Cache,
                 ttl: int, max_staleness: int = 0, *, org_of: Callable[[str], str | None] | None = None,
                 language_of: Callable[[str], str | None] | None = None) -> None:
        self._load = states_loader
        self._org_of = org_of or (lambda _: None)
        self._language_of = language_of or (lambda _: None)
        self.registry = registry
        self.cache = cache
        self.ttl = ttl
        self.max_staleness = max_staleness

    @classmethod
    def _lock(cls, key: str) -> threading.Lock:
        with cls._locks_guard:
            return cls._locks.setdefault(key, threading.Lock())

    def _fresh(self, hit: dict | None, version: int) -> dict[str, Any] | None:
        if hit is None:
            return None
        if hit["v"] == version:
            return {**hit["data"], "cached": True, "stale": False, "as_of": hit["at"]}
        age = time.time() - hit["at"]
        if age < self.max_staleness:
            return {**hit["data"], "cached": True, "stale": True, "as_of": hit["at"]}
        return None

    def get(self, pathway_id: str | None = None, org: str | None = None,
            language: str | None = None) -> dict[str, Any]:
        """Filters: pathway; provider (the owner's organisation); patient's preferred language."""
        key = f"metrics:{pathway_id or 'all'}:{org or 'all'}:{language or 'all'}"
        version = self.cache.get_int(WRITE_VERSION_KEY)
        served = self._fresh(self.cache.get(key), version)
        if served is not None:
            return served
        with self._lock(key):
            served = self._fresh(self.cache.get(key), version)  # another thread may have just computed it
            if served is not None:
                return served
            at = time.time()
            data = self.compute(pathway_id, org, language)
            data["filters"] = {"pathway": pathway_id, "org": org, "language": language}
            self.cache.set(key, {"v": version, "at": at, "data": data}, self.ttl)
        return {**data, "cached": False, "stale": False, "as_of": at}

    def compute(self, pathway_id: str | None, org: str | None = None,
                language: str | None = None) -> dict[str, Any]:
        pathways = {p.id: p for p in self.registry.all() if not pathway_id or p.id == pathway_id}
        completed_values = {o.value for o in CARE_COMPLETED_OUTCOMES}
        stalls: Counter[str] = Counter()
        outcomes: Counter[str] = Counter()
        barriers: Counter[str] = Counter()
        funnel: dict[str, Counter[str]] = {pid: Counter() for pid in pathways}
        cases_by_pathway: Counter[str] = Counter()
        false_done: list[str] = []
        total = open_ = admin_done = verified_done = distress = ownerless = 0
        days_to_procedure: list[float] = []

        for doc in self._load():
            s = CaseState.model_validate(doc)
            p = pathways.get(s.pathway_id)
            if p is None:
                continue
            if org and self._org_of(s.owner_id) != org:
                continue
            if language and self._language_of(s.patient_id) != language:
                continue
            total += 1
            cases_by_pathway[p.id] += 1
            if s.is_open:
                open_ += 1
                stalls.update(r.value if hasattr(r, "value") else r for r in s.stalls)
                if not s.owner_id:
                    ownerless += 1
            if s.outcome:
                outcomes[s.outcome.value] += 1
            for b in s.barriers.values():
                if b.confirmed_code:
                    barriers[b.confirmed_code.value] += 1
                elif b.reported_codes:
                    barriers.update(c.value for c in b.reported_codes)
                elif b.suggested_code:
                    barriers[b.suggested_code.value] += 1
            distress += len(s.open_distress)
            for stage_id in s.stages:
                funnel[p.id][stage_id] += 1
            if s.admin_status == AdminStatus.COMPLETED:
                admin_done += 1
                if p.checks.evidence_stage and p.checks.evidence_stage not in s.stages:
                    false_done.append(s.id)
            if all(st in s.stages for st in p.closure.completion_stages):
                verified_done += 1
            proc = p.checks.procedure_stage
            if proc and proc in s.stages:
                days_to_procedure.append((s.stages[proc].reached_at - s.opened_at).total_seconds() / 86400)

        by_pathway = {
            p.id: {"name": p.name, "cases": cases_by_pathway[p.id],
                   "funnel": [{"stage": sd.id, "label": sd.label, "count": funnel[p.id][sd.id]} for sd in p.stages]}
            for p in pathways.values()
        }
        false_done.sort()
        return {
            "cases": {"total": total, "open": open_, "closed": total - open_},
            "by_pathway": by_pathway,
            "open_stalls_by_reason": dict(stalls),
            "barriers_by_code": dict(barriers),
            "outcomes": dict(outcomes),
            "care_completed": sum(v for k, v in outcomes.items() if k in completed_values),
            "referral_status_says_completed": admin_done,
            "verified_complete": verified_done,
            # Ids are capped so the payload stays small at scale; the count is exact.
            "false_done": {"count": len(false_done), "case_ids": false_done[:100]},
            "median_days_result_to_procedure": round(median(days_to_procedure), 1) if days_to_procedure else None,
            "open_distress": distress,
            "open_cases_without_owner": ownerless,
        }
