"""Application service: load → decide (pure engine) → append events + projection → invalidate cache."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import checks, engine
from ..domain.barriers import BarrierClassifier
from ..domain.errors import NotFound
from ..domain.model import Actor, ActorType, BarrierCode, CaseState, Event, Outcome, Signal
from ..domain.pathways import Pathway, PathwayRegistry
from ..infra.cache import WRITE_VERSION_KEY, Cache
from ..infra.repository import CaseRepository, ConcurrencyError
from . import routing
from .directory import Directory, PatientInfo

Build = Callable[[CaseState, Pathway], Sequence[Event]]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class CaseService:
    def __init__(self, session: Session, registry: PathwayRegistry, directory: Directory, cache: Cache,
                 classifier: BarrierClassifier) -> None:
        self.s = session
        self.repo = CaseRepository(session)
        self.registry = registry
        self.directory = directory
        self.cache = cache
        self.classifier = classifier

    # ---- plumbing --------------------------------------------------------------------------------
    def bump_write_version(self) -> None:
        self.cache.incr(WRITE_VERSION_KEY)

    def get(self, case_id: str) -> CaseState:
        st = self.repo.get(case_id)
        if st is None:
            raise NotFound("case", case_id)
        return st

    def _run(self, case_id: str, build: Build, now: datetime, *, commit: bool = True,
             retries: int = 3) -> tuple[CaseState, int]:
        """Execute a command with optimistic locking. Returns (new state, number of events written)."""
        for attempt in range(retries):
            state = self.get(case_id)
            pathway = self.registry.get(state.pathway_id)
            events = list(build(state, pathway))
            new_state, all_events = engine.execute(state, events, pathway, now, self.directory.resolver)
            try:
                self.repo.save(new_state, state.version, all_events, pathway,
                               checks.next_check_at(new_state, pathway, now))
                if all_events:
                    self._side_effects(new_state, pathway, all_events, state.version + 1)
                if commit:
                    self.s.commit()
                    if all_events:
                        self.bump_write_version()
                return new_state, len(all_events)
            except (ConcurrencyError, IntegrityError) as exc:
                if not commit or attempt == retries - 1:
                    raise ConcurrencyError(case_id) from exc
                self.s.rollback()
        raise ConcurrencyError(case_id)  # pragma: no cover

    # ---- visibility ------------------------------------------------------------------------------
    def scope(self, actor: Actor) -> tuple[list[str], str] | None:
        """None = sees every case (program coordinator). Otherwise (owner ids in my organisation, me):
        a clinic sees its own patients plus any case it has been pulled into (escalation, handoff, consult)."""
        if actor.type == ActorType.COORDINATOR:
            return None
        me = self.directory.person(actor.id)
        return (self.directory.org_members(me.org_id) if me else [actor.id]), actor.id

    def inbox_for(self, person_id: str) -> list:
        """This person's assignments plus those of anyone they cover while away (TSL-160)."""
        rows = list(self.repo.assignments_for(person_id))
        for away in self.directory.covering_for(person_id):
            rows += self.repo.assignments_for(away.id)
        return rows

    def require_visible(self, case_id: str, actor: Actor) -> CaseState:
        st = self.get(case_id)
        scope = self.scope(actor)
        if scope is None or st.owner_id in scope[0]:
            return st
        if any(a.case_id == case_id for a in self.inbox_for(actor.id)):
            return st
        # Same answer as a missing case: do not reveal that the case exists.
        raise NotFound("case", case_id)

    # ---- lifecycle -------------------------------------------------------------------------------
    def open_case(self, patient: PatientInfo, pathway: Pathway, trigger: Signal, actor: Actor,
                  now: datetime) -> CaseState:
        """Called inside an ingest transaction; the caller commits."""
        owner, warnings = self.directory.default_owner(patient)
        events = engine.open_case(case_id=new_id("case"), patient_id=patient.id, pathway=pathway, trigger=trigger,
                                  owner_id=owner, actor=actor, warnings=warnings)
        state, all_events = engine.execute(None, events, pathway, now, self.directory.resolver)
        self.repo.insert(state, all_events, pathway, checks.next_check_at(state, pathway, now))
        self._side_effects(state, pathway, all_events, 1)
        return state

    def _side_effects(self, state: CaseState, pathway: Pathway, events: Sequence[Event], first_seq: int) -> None:
        self.repo.write_side_effects(state.id, routing.assignments(state, self.directory, pathway),
                                     routing.outbox(state, pathway, events, first_seq, self.directory))

    def apply_signal(self, case_id: str, s: Signal, actor: Actor, now: datetime) -> tuple[CaseState, int]:
        return self._run(case_id, lambda st, p: engine.record_signal(st, p, s, actor), now, commit=False)

    def trigger_repeated(self, case_id: str, s: Signal, actor: Actor, now: datetime) -> tuple[CaseState, int]:
        return self._run(case_id, lambda st, p: engine.trigger_repeated(st, s, actor), now, commit=False)

    def add_warning(self, case_id: str, text: str, actor: Actor, now: datetime) -> tuple[CaseState, int]:
        return self._run(case_id, lambda st, p: engine.add_warning(st, actor, now, text), now, commit=False)

    def evaluate(self, case_id: str, now: datetime) -> tuple[CaseState, int]:
        return self._run(case_id, lambda st, p: [], now)

    # ---- staff and patient commands ---------------------------------------------------------------
    def offer_handoff(self, case_id: str, actor: Actor, to_id: str, reason: str, now: datetime) -> CaseState:
        self.directory.require_person(to_id)
        return self._run(case_id, lambda st, p: engine.offer_handoff(st, actor, to_id, reason, now), now)[0]

    def accept_handoff(self, case_id: str, actor: Actor, now: datetime) -> CaseState:
        return self._run(case_id, lambda st, p: engine.accept_handoff(st, actor, now), now)[0]

    def reject_handoff(self, case_id: str, actor: Actor, reason_code: str, now: datetime) -> CaseState:
        return self._run(case_id, lambda st, p: engine.reject_handoff(st, actor, reason_code, now), now)[0]

    def report_barrier(self, case_id: str, actor: Actor, codes: Sequence[BarrierCode], text: str | None,
                       now: datetime) -> tuple[CaseState, str]:
        bid = new_id("bar")
        did = new_id("dis")

        def build(st: CaseState, p: Pathway) -> list[Event]:
            if actor.type == ActorType.PATIENT and st.patient_id != actor.id:
                raise NotFound("case", case_id)
            return engine.report_barrier(st, actor, barrier_id=bid, distress_id=did, codes=codes, text=text,
                                         now=now, classifier=self.classifier, resolver=self.directory.resolver)

        return self._run(case_id, build, now)[0], bid

    def confirm_barrier(self, case_id: str, actor: Actor, barrier_id: str, code: BarrierCode,
                        now: datetime) -> CaseState:
        return self._run(case_id, lambda st, p: engine.confirm_barrier(st, p, actor, barrier_id, code, now), now)[0]

    def resolve_barrier(self, case_id: str, actor: Actor, barrier_id: str, note: str, now: datetime) -> CaseState:
        return self._run(case_id, lambda st, p: engine.resolve_barrier(st, actor, barrier_id, note, now), now)[0]

    def resolve_distress(self, case_id: str, actor: Actor, distress_id: str, note: str,
                         now: datetime) -> CaseState:
        return self._run(case_id, lambda st, p: engine.resolve_distress(st, actor, distress_id, note, now), now)[0]

    def log_contact(self, case_id: str, actor: Actor, channel: str, result: str, now: datetime) -> CaseState:
        return self._run(case_id, lambda st, p: engine.log_contact(st, actor, channel, result, now), now)[0]

    def request_consult(self, case_id: str, actor: Actor, to_id: str, question: str,
                        now: datetime) -> tuple[CaseState, str]:
        self.directory.require_person(to_id)
        cid = new_id("con")
        st = self._run(case_id, lambda s, p: engine.request_consult(s, p, actor, cid, to_id, question, now), now)[0]
        return st, cid

    def covers(self, actor: Actor, now: datetime) -> tuple[str, ...]:
        """Ids of the people `actor` is covering for right now (they are away and named `actor`)."""
        return tuple(p.id for p in self.directory.covering_for(actor.id, now))

    def answer_consult(self, case_id: str, actor: Actor, consult_id: str, answer: str, now: datetime) -> CaseState:
        covers = self.covers(actor, now)
        return self._run(case_id, lambda st, p: engine.answer_consult(st, actor, consult_id, answer, now,
                                                                      covers=covers), now)[0]

    def review_report(self, case_id: str, actor: Actor, report_id: str, findings: dict, now: datetime, *,
                      suggested_by: str | None, suggestion: dict | None) -> CaseState:
        return self._run(case_id, lambda st, p: engine.review_report(st, actor, report_id, findings, now,
                                                                     suggested_by=suggested_by,
                                                                     suggestion=suggestion), now)[0]

    def record_consent(self, case_id: str, actor: Actor, now: datetime) -> CaseState:
        def build(st: CaseState, p: Pathway) -> list[Event]:
            if actor.type == ActorType.PATIENT and st.patient_id != actor.id:
                raise NotFound("case", case_id)
            return engine.record_consent(st, actor, now)

        return self._run(case_id, build, now)[0]

    def send_patient_message(self, case_id: str, actor: Actor, text: str, language: str, now: datetime,
                             ai_draft_id: str | None = None) -> CaseState:
        return self._run(case_id, lambda st, p: engine.send_patient_message(st, actor, text, language, now,
                                                                              ai_draft_id=ai_draft_id), now)[0]

    def record_delivery_failure(self, outbox_id: int, channels: Sequence[str], actor: Actor,
                                now: datetime) -> CaseState | None:
        """Only patient messages create a human task; staff alerts that fail are an operations problem
        reported by the notifier's own metrics, not a case event."""
        row = self.repo.outbox_row(outbox_id)
        if row is None:
            raise NotFound("outbox message", str(outbox_id))
        if row.channel != "sahatna":
            return None
        return self._run(row.case_id, lambda st, p: engine.record_delivery_failure(st, actor, outbox_id, channels,
                                                                                   now), now)[0]

    def close(self, case_id: str, actor: Actor, outcome: Outcome, evidence_ref: str | None, reason: str | None,
              now: datetime) -> CaseState:
        return self._run(case_id, lambda st, p: engine.close_case(st, p, actor, outcome, evidence_ref=evidence_ref,
                                                                    reason=reason, now=now), now)[0]
