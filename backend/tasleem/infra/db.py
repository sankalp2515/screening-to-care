from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

JSONType = JSON().with_variant(JSONB(), "postgresql")
# SQLite only auto-increments INTEGER PRIMARY KEY; Postgres gets BIGSERIAL.
BigId = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


class OrganizationRow(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))
    services: Mapped[list[str]] = mapped_column(JSONType, default=list)
    insurance_networks: Mapped[list[str]] = mapped_column(JSONType, default=list)


class PractitionerRow(Base):
    __tablename__ = "practitioners"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("practitioners.id"), nullable=True)
    # Cover while away (TSL-160): until `away_until`, this person's work list and new escalations go to `cover_id`.
    # Ownership does not move (R1 names the owner); the cover acts on their behalf.
    away_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cover_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PatientRow(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    insurance_network: Mapped[str | None] = mapped_column(String(64), nullable=True)
    family_physician_id: Mapped[str | None] = mapped_column(ForeignKey("practitioners.id"), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseRow(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    pathway_id: Mapped[str] = mapped_column(String(80))
    pathway_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    owner_id: Mapped[str] = mapped_column(String(64))
    verified_stage: Mapped[str] = mapped_column(String(64))
    admin_status: Mapped[str] = mapped_column(String(16))
    priority: Mapped[str] = mapped_column(String(16))
    open_stall_count: Mapped[int] = mapped_column(Integer, default=0)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_progress_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_hash: Mapped[str] = mapped_column(String(64))
    state_json: Mapped[dict[str, Any]] = mapped_column(JSONType)
    version: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_cases_owner_status", "owner_id", "status"),
        Index("ix_cases_status_stalled", "status", "open_stall_count"),
        # Worklist risk ordering: status filter, then most stalls, highest escalation, oldest progress.
        Index("ix_cases_worklist", "status", "open_stall_count", "escalation_level", "last_progress_at"),
        Index("ix_cases_patient_status", "patient_id", "status"),
        Index("ix_cases_due", "next_check_at", postgresql_where=text("status = 'open'"),
              sqlite_where=text("status = 'open'")),
        # At most one open case per patient per pathway.
        Index("ux_cases_open_per_pathway", "patient_id", "pathway_id", unique=True,
              postgresql_where=text("status = 'open'"), sqlite_where=text("status = 'open'")),
    )


class CaseEventRow(Base):
    __tablename__ = "case_events"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("case_id", "seq", name="ux_case_events_seq"),)


class InboundMessageRow(Base):
    __tablename__ = "inbound_messages"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64))
    message_id: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Kept so evidence that arrived before its trigger can be replayed when the case opens.
    patient_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)
    __table_args__ = (UniqueConstraint("source", "message_id", name="ux_inbound_source_msg"),
                      Index("ix_inbound_patient_status", "patient_id", "status"))


class CaseAssignmentRow(Base):
    """Who has to act on which open case, and why. A projection rebuilt on every case write.

    Lets a person's inbox ("owned by me", "escalated to me", "handoff offered to me", "consult for me")
    be one indexed query instead of a scan of every case, and drives org-scoped visibility.
    """

    __tablename__ = "case_assignments"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    person_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    ref: Mapped[str] = mapped_column(String(64), primary_key=True)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_assign_person", "person_id", "kind"),)


class OutboxRow(Base):
    """Transactional outbox: notifications for Sahatna, the EMR inbox or SMS, written in the same
    transaction as the case events. An integration worker pulls, delivers and acknowledges them."""

    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    event_seq: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(24))
    recipient_id: Mapped[str] = mapped_column(String(64))
    recipient_role: Mapped[str] = mapped_column(String(40), default="")
    template: Mapped[str] = mapped_column(String(40))
    urgent: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_outbox_status_id", "status", "id"),)


def make_engine(url: str, *, pool_size: int = 10, max_overflow: int = 20,
                statement_timeout_ms: int = 5000) -> Engine:
    if url.startswith("sqlite"):
        memory = url in ("sqlite://", "sqlite:///:memory:")
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if memory:
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)
        if not memory:
            @event.listens_for(engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _):  # type: ignore[no-untyped-def]
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")  # readers do not block the writer
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()
        return engine
    connect_args: dict[str, Any] = {}
    if url.startswith("postgresql") and statement_timeout_ms > 0:
        connect_args["options"] = f"-c statement_timeout={statement_timeout_ms}"
    return create_engine(url, pool_pre_ping=True, pool_size=pool_size, max_overflow=max_overflow,
                         pool_recycle=1800, connect_args=connect_args)


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def drop_schema(engine: Engine) -> None:
    Base.metadata.drop_all(engine)
