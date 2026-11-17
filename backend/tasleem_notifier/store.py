"""The notifier's own database (never the case-core database): notifications and delivery attempts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class NotificationRow(Base):
    """A copy of one case-core outbox message plus its delivery progress.

    De-duplicated on `message_key` (case, event number, channel, recipient, template), a natural key that
    stays unique even if case-core's numeric outbox ids restart (a demo reset or a restored backup), so
    pulling the same message twice stores it once and a new message is never mistaken for an old one."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_key: Mapped[str] = mapped_column(String(200), unique=True)
    outbox_id: Mapped[int] = mapped_column(Integer, index=True)  # case-core id, for reports back to it
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    recipient_id: Mapped[str] = mapped_column(String(64), index=True)
    recipient_role: Mapped[str] = mapped_column(String(40))
    template: Mapped[str] = mapped_column(String(40))
    urgent: Mapped[bool] = mapped_column(default=False)
    language: Mapped[str] = mapped_column(String(8), default="en")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    # pending -> sending -> waiting (for a receipt) -> done | exhausted ; digest = queued for the digest
    status: Mapped[str] = mapped_column(String(16), default="pending")
    step: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # provider retries on the current step
    next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_pending: Mapped[bool] = mapped_column(default=False)  # unreached report not yet accepted by core
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_notif_due", "status", "next_at"),)


class DeliveryRow(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16))  # queued | sent | delivered | read | failed
    provider_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("notification_id", "step", "channel", name="ux_delivery_step"),)


class DigestRunRow(Base):
    """One digest per recipient per local day, even if several workers run at digest time."""

    __tablename__ = "digest_runs"
    recipient_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    items: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def make_store(url: str) -> tuple[Engine, sessionmaker]:
    kwargs: dict[str, Any] = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)  # small, additive schema owned by this service
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
