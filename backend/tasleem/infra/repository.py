from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from ..domain.audit import GENESIS, StoredEvent, event_hash
from ..domain.model import CaseState, Event, to_utc
from ..domain.pathways import Pathway
from .db import CaseAssignmentRow, CaseEventRow, CaseRow, OutboxRow


class ConcurrencyError(Exception):
    """The case changed since it was loaded (optimistic lock)."""


def _projection(state: CaseState, pathway: Pathway, next_check: datetime | None, last_hash: str) -> dict:
    far = pathway.furthest_stage(set(state.stages)) or "OPENED"
    return dict(
        patient_id=state.patient_id, pathway_id=state.pathway_id, pathway_version=state.pathway_version,
        status=state.status, owner_id=state.owner_id, verified_stage=far, admin_status=state.admin_status.value,
        priority=state.priority, open_stall_count=len(state.stalls), escalation_level=state.escalation_level,
        outcome=state.outcome.value if state.outcome else None, opened_at=state.opened_at,
        updated_at=state.updated_at, last_progress_at=state.last_progress_at, closed_at=state.closed_at,
        next_check_at=next_check, last_hash=last_hash, state_json=state.model_dump(mode="json"),
        version=state.version,
    )


class CaseRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    # ---- reads -----------------------------------------------------------------------------------
    def get(self, case_id: str, *, for_update: bool = False) -> CaseState | None:
        # populate_existing: projection rows are updated with Core UPDATEs, so never trust the identity map.
        q = select(CaseRow).where(CaseRow.id == case_id).execution_options(populate_existing=True)
        if for_update:
            q = q.with_for_update()
        row = self.s.execute(q).scalar_one_or_none()
        return None if row is None else CaseState.model_validate(row.state_json)

    def last_hash(self, case_id: str) -> str:
        v = self.s.execute(select(CaseRow.last_hash).where(CaseRow.id == case_id)).scalar_one_or_none()
        return v or GENESIS

    def find_open_for_patient(self, patient_id: str) -> list[CaseState]:
        rows = self.s.execute(
            select(CaseRow).where(CaseRow.patient_id == patient_id, CaseRow.status == "open")
            .order_by(CaseRow.opened_at, CaseRow.id).execution_options(populate_existing=True)
        ).scalars()
        return [CaseState.model_validate(r.state_json) for r in rows]

    def list(
        self, *, owner_id: str | None = None, status: str | None = None, stalled: bool | None = None,
        pathway_id: str | None = None, patient_id: str | None = None, limit: int = 100, offset: int = 0,
        visible_to: tuple[list[str], str] | None = None,
    ) -> list[CaseRow]:
        q = select(CaseRow)
        if visible_to is not None:
            org_members, person_id = visible_to
            q = q.where(CaseRow.owner_id.in_(org_members) | CaseRow.id.in_(self.visible_case_ids(person_id)))
        if owner_id:
            q = q.where(CaseRow.owner_id == owner_id)
        if status:
            q = q.where(CaseRow.status == status)
        if stalled is True:
            q = q.where(CaseRow.open_stall_count > 0)
        elif stalled is False:
            q = q.where(CaseRow.open_stall_count == 0)
        if pathway_id:
            q = q.where(CaseRow.pathway_id == pathway_id)
        if patient_id:
            q = q.where(CaseRow.patient_id == patient_id)
        # Risk ordering: most stalls, highest escalation, longest without progress.
        q = q.order_by(CaseRow.open_stall_count.desc(), CaseRow.escalation_level.desc(),
                       CaseRow.last_progress_at.asc(), CaseRow.id).limit(limit).offset(offset)
        return list(self.s.execute(q.execution_options(populate_existing=True)).scalars())

    def all_rows(self) -> list[CaseRow]:
        return list(self.s.execute(select(CaseRow).execution_options(populate_existing=True)).scalars())

    def iter_states(self, batch: int = 1000) -> Iterator[dict]:
        """Stream case state documents in batches (server-side cursor on Postgres): constant memory."""
        q = select(CaseRow.state_json).execution_options(yield_per=batch)
        for (doc,) in self.s.execute(q):
            yield doc

    def due_case_ids(self, now: datetime, limit: int) -> list[str]:
        q = (select(CaseRow.id)
             .where(CaseRow.status == "open", CaseRow.next_check_at.is_not(None), CaseRow.next_check_at <= now)
             .order_by(CaseRow.next_check_at).limit(limit))
        if self.s.bind is not None and self.s.bind.dialect.name == "postgresql":
            q = q.with_for_update(skip_locked=True)
        return list(self.s.execute(q).scalars())

    def events(self, case_id: str) -> list[StoredEvent]:
        rows = self.s.execute(
            select(CaseEventRow).where(CaseEventRow.case_id == case_id).order_by(CaseEventRow.seq)
        ).scalars()
        return [StoredEvent(case_id=r.case_id, seq=r.seq, type=r.type, actor_id=r.actor_id,
                            actor_type=r.actor_type, occurred_at=to_utc(r.occurred_at), payload=r.payload,
                            prev_hash=r.prev_hash, hash=r.hash) for r in rows]

    def visible_case_ids(self, person_id: str):  # type: ignore[no-untyped-def]
        """Subquery of case ids a person is assigned to in any way (owner, escalation, handoff, consult...)."""
        return select(CaseAssignmentRow.case_id).where(CaseAssignmentRow.person_id == person_id)

    def assignments_for(self, person_id: str) -> list[CaseAssignmentRow]:
        return list(self.s.execute(
            select(CaseAssignmentRow).where(CaseAssignmentRow.person_id == person_id)
            .order_by(CaseAssignmentRow.since)).scalars())

    def rows_by_ids(self, ids: Sequence[str]) -> list[CaseRow]:
        if not ids:
            return []
        q = (select(CaseRow).where(CaseRow.id.in_(list(ids)))
             .order_by(CaseRow.open_stall_count.desc(), CaseRow.escalation_level.desc(),
                       CaseRow.last_progress_at.asc(), CaseRow.id))
        return list(self.s.execute(q.execution_options(populate_existing=True)).scalars())

    def outbox(self, *, case_id: str | None = None, status: str | None = None, after_id: int = 0,
               limit: int = 100) -> list[OutboxRow]:
        q = select(OutboxRow).where(OutboxRow.id > after_id)
        if case_id:
            q = q.where(OutboxRow.case_id == case_id)
        if status:
            q = q.where(OutboxRow.status == status)
        return list(self.s.execute(q.order_by(OutboxRow.id).limit(limit)).scalars())

    def outbox_row(self, outbox_id: int) -> OutboxRow | None:
        return self.s.get(OutboxRow, outbox_id)

    def active_in_period(self, start: datetime, end: datetime) -> list[tuple[str, str, int]]:
        """(owner_id, pathway_id, cases) for cases open at any moment in [start, end). Metering for
        per-active-case pricing: a case counts once per month it was open, whatever happened to it."""
        q = (select(CaseRow.owner_id, CaseRow.pathway_id, func.count())
             .where(CaseRow.opened_at < end, or_(CaseRow.closed_at.is_(None), CaseRow.closed_at >= start))
             .group_by(CaseRow.owner_id, CaseRow.pathway_id))
        return [(o, p, int(n)) for o, p, n in self.s.execute(q)]

    def ack_outbox(self, ids: Sequence[int], now: datetime) -> int:
        res = self.s.execute(update(OutboxRow).where(OutboxRow.id.in_(list(ids)), OutboxRow.status == "pending")
                             .values(status="delivered", delivered_at=now))
        return res.rowcount or 0

    def write_side_effects(self, case_id: str, assignments: Sequence[tuple[str, str, str, datetime]],
                           messages: Sequence[dict[str, Any]]) -> None:
        """Same transaction as the events: rebuild the case's assignments, append outbox messages."""
        self.s.execute(delete(CaseAssignmentRow).where(CaseAssignmentRow.case_id == case_id))
        self.s.add_all([CaseAssignmentRow(case_id=case_id, person_id=p, kind=k, ref=r, since=to_utc(t))
                        for p, k, r, t in assignments])
        now = datetime.now(UTC)
        self.s.add_all([OutboxRow(case_id=case_id, created_at=now, status="pending", **m) for m in messages])
        self.s.flush()

    # ---- writes ----------------------------------------------------------------------------------
    def _append_events(self, case_id: str, start_seq: int, prev_hash: str, events: Sequence[Event]) -> str:
        now = datetime.now(UTC)
        h = prev_hash
        for i, e in enumerate(events):
            seq = start_seq + i
            payload = Event.model_validate(e).model_dump(mode="json")["payload"]
            new_h = event_hash(h, case_id, seq, e.type.value, e.actor_id, e.actor_type.value, e.occurred_at, payload)
            self.s.add(CaseEventRow(case_id=case_id, seq=seq, type=e.type.value, actor_id=e.actor_id,
                                    actor_type=e.actor_type.value, occurred_at=to_utc(e.occurred_at),
                                    recorded_at=now, payload=payload, prev_hash=h, hash=new_h))
            h = new_h
        return h

    def insert(self, state: CaseState, events: Sequence[Event], pathway: Pathway, next_check: datetime | None) -> None:
        """Create the case row first (events reference it), then the hash-chained events."""
        row = CaseRow(id=state.id, **_projection(state, pathway, next_check, GENESIS))
        self.s.add(row)
        self.s.flush()
        last = self._append_events(state.id, 1, GENESIS, events)
        row.last_hash = last
        self.s.flush()

    def save(
        self, state: CaseState, expected_version: int, events: Sequence[Event], pathway: Pathway,
        next_check: datetime | None,
    ) -> None:
        if not events:
            # nothing changed except perhaps next_check_at
            self.s.execute(update(CaseRow).where(CaseRow.id == state.id).values(next_check_at=next_check))
            return
        prev = self.last_hash(state.id)
        last = self._append_events(state.id, expected_version + 1, prev, events)
        res = self.s.execute(
            update(CaseRow)
            .where(CaseRow.id == state.id, CaseRow.version == expected_version)
            .values(**_projection(state, pathway, next_check, last))
        )
        if res.rowcount != 1:
            raise ConcurrencyError(state.id)
        self.s.flush()
