"""Idempotent ingest: signals → open/attach cases → record evidence. One transaction per message."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.model import Actor, ActorType, CaseState, Signal, SignalKind
from ..domain.pathways import PathwayRegistry
from ..infra.db import InboundMessageRow
from ..infra.repository import CaseRepository, ConcurrencyError
from .cases import CaseService
from .directory import Directory
from .fhir import Parsed, ReferralStatusMessage, parse

# Evidence that arrives before its trigger (out-of-order delivery) is replayed onto the new case if its
# clinical time is on or after the trigger and within this window.
LATE_TRIGGER_LOOKBACK = timedelta(days=60)


class IngestService:
    def __init__(self, session: Session, registry: PathwayRegistry, directory: Directory, cases: CaseService) -> None:
        self.s = session
        self.registry = registry
        self.directory = directory
        self.cases = cases
        self.repo = CaseRepository(session)

    def _existing(self, source: str, message_id: str) -> InboundMessageRow | None:
        return self.s.execute(
            select(InboundMessageRow).where(InboundMessageRow.source == source,
                                            InboundMessageRow.message_id == message_id)
        ).scalar_one_or_none()

    def ingest_fhir(self, payload: dict[str, Any], source: str, now: datetime,
                    message_id: str | None = None) -> list[dict[str, Any]]:
        parsed = parse(payload, now, message_id)  # raises IngestValidationError before anything is written
        return [self._process(source, p, payload if len(parsed) == 1 else {"bundle_entry": p.resource_type}, now)
                for p in parsed]

    def ingest_referral_status(self, msg: ReferralStatusMessage, source: str, now: datetime) -> dict[str, Any]:
        p = Parsed(message_id=msg.message_id, resource_type="REF", signals=[msg.to_signal()])
        return self._process(source, p, msg.model_dump(mode="json"), now)

    def _process(self, source: str, p: Parsed, raw: dict[str, Any], now: datetime,
                 attempts: int = 4) -> dict[str, Any]:
        """One atomic transaction per message, retried on races.

        Races this absorbs: the same message delivered twice at once (unique (source, message_id)),
        two triggers opening the same pathway for one patient (unique open case), and a staff command
        or scheduler tick changing a case mid-ingest (optimistic version). On retry, a message that
        another worker already stored comes back as a duplicate, so evidence is never applied twice.
        """
        for attempt in range(attempts):
            try:
                return self._process_once(source, p, raw, now)
            except (IntegrityError, ConcurrencyError):
                self.s.rollback()
                if attempt == attempts - 1:
                    raise ConcurrencyError(f"ingest {source}/{p.message_id}") from None
        raise AssertionError("unreachable")  # pragma: no cover

    def _process_once(self, source: str, p: Parsed, raw: dict[str, Any], now: datetime) -> dict[str, Any]:
        prior = self._existing(source, p.message_id)
        if prior is not None:
            return {**(prior.result or {}), "duplicate": True}

        actor = Actor(id=source, type=ActorType.INTEGRATION)
        results: list[dict[str, Any]] = []
        status = "ignored" if p.ignored_reason else "no_effect"
        for s in p.signals:
            outcome = self._apply_signal(s, actor, now)
            results.extend(outcome)
        if any(r["effect"] == "unmatched" for r in results):
            status = "unmatched"
        elif any(r["effect"] in ("opened", "updated", "attached", "replayed") for r in results):
            status = "applied"
        result = {"message_id": p.message_id, "resource_type": p.resource_type, "status": status,
                  "ignored_reason": p.ignored_reason, "effects": results}
        self.s.add(InboundMessageRow(source=source, message_id=p.message_id, kind=p.resource_type, payload=raw,
                                     result=result, status=status, received_at=now,
                                     patient_id=p.signals[0].patient_id if p.signals else None,
                                     signals=[s.model_dump(mode="json") for s in p.signals] or None))
        self.s.flush()  # unique (source, message_id) fails here, before commit, if another worker won
        self.s.commit()
        if status == "applied":
            self.cases.bump_write_version()
        return {**result, "duplicate": False}

    def _apply_signal(self, s: Signal, actor: Actor, now: datetime) -> list[dict[str, Any]]:
        patient = self.directory.patient(s.patient_id)
        if patient is None:
            return [{"effect": "unmatched", "patient_id": s.patient_id,
                     "detail": "patient not in Tasleem directory; stored for review"}]
        effects: list[dict[str, Any]] = []
        opened: set[str] = set()
        open_cases = self.repo.find_open_for_patient(patient.id)

        # 1. Triggers: open a case, or attach a repeat trigger to the open one.
        for pathway in self.registry.all():
            if not pathway.trigger.matches(s):
                continue
            existing = [c for c in open_cases if c.pathway_id == pathway.id]
            if existing:
                self.cases.trigger_repeated(existing[0].id, s, actor, now)
                effects.append({"effect": "attached", "case_id": existing[0].id, "pathway_id": pathway.id})
            else:
                st = self.cases.open_case(patient, pathway, s, actor, now)
                opened.add(st.id)
                effects.append({"effect": "opened", "case_id": st.id, "pathway_id": pathway.id,
                                "owner_id": st.owner_id})

        # 2. Evidence for every other open case of this patient.
        for case in self.repo.find_open_for_patient(patient.id):
            if case.id in opened or not self._relevant(case, s):
                continue
            _, n = self.cases.apply_signal(case.id, s, actor, now)
            if n:
                effects.append({"effect": "updated", "case_id": case.id, "events": n})

        # 3. Out-of-order delivery: evidence stored earlier with no effect, but clinically after this trigger.
        if opened:
            effects += self._replay_early_evidence(patient.id, s, opened, actor, now)
        return effects

    def _relevant(self, case: CaseState, s: Signal) -> bool:
        pathway = self.registry.get(case.pathway_id)
        return not (s.kind == SignalKind.ADMIN_STATUS and (
            pathway.referral_service is None or (s.service and s.service != pathway.referral_service)))

    def _replay_early_evidence(self, patient_id: str, trigger: Signal, opened: set[str], actor: Actor,
                               now: datetime) -> list[dict[str, Any]]:
        rows = self.s.execute(
            select(InboundMessageRow)
            .where(InboundMessageRow.patient_id == patient_id, InboundMessageRow.status == "no_effect")
            .order_by(InboundMessageRow.received_at, InboundMessageRow.id)
        ).scalars().all()
        effects: list[dict[str, Any]] = []
        for row in rows:
            applied = 0
            for raw in row.signals or []:
                sig = Signal.model_validate(raw)
                if not (trigger.occurred_at <= sig.occurred_at <= trigger.occurred_at + LATE_TRIGGER_LOOKBACK):
                    continue
                for case in self.repo.find_open_for_patient(patient_id):
                    if case.id in opened and self._relevant(case, sig):
                        _, n = self.cases.apply_signal(case.id, sig, actor, now)
                        applied += n
            if applied:
                row.status = "applied_late"
                effects.append({"effect": "replayed", "message_id": row.message_id, "events": applied})
        return effects
