"""Delivery state machine. Every decision is a pure function of the policy, the message and the clock.

Hand-over from case-core is at-least-once: pull pending outbox messages, store them (keyed by outbox
id), commit, then acknowledge. A crash between commit and ack means the same messages are pulled again
and ignored. A crash before commit means nothing was stored and core still has them as pending.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from tasleem_common.http import ServiceClient, ServiceError

from .adapters import Outgoing, Provider, render
from .policy import Policy, Step
from .store import DeliveryRow, DigestRunRow, NotificationRow

log = logging.getLogger("tasleem.notifier")
RANK = {"queued": 0, "sent": 1, "delivered": 2, "read": 3}
MAX_PROVIDER_RETRIES = 5


def _satisfied(status: str, success_on: str) -> bool:
    return status != "failed" and RANK.get(status, 0) >= RANK[success_on]


def message_key(m: dict[str, Any]) -> str:
    """Natural key of a case-core outbox message (see NotificationRow)."""
    return f"{m['case_id']}/{m['event_seq']}/{m['channel']}/{m['recipient']}/{m['template']}"


def _language(m: dict[str, Any]) -> str:
    lang = (m.get("payload") or {}).get("language")
    return lang if lang in ("en", "ar") else "en"


class Notifier:
    def __init__(self, sessions: sessionmaker, policy: Policy, provider: Provider,
                 core: ServiceClient | None, page_size: int = 200) -> None:
        self.sessions = sessions
        self.policy = policy
        self.provider = provider
        self.core = core
        self.page_size = page_size

    # ---- 1. hand-over from case-core ------------------------------------------------------------
    def pull(self, now: datetime) -> int:
        if self.core is None:
            return 0
        stored = 0
        for _ in range(50):  # bounded: at most 50 pages per run
            page = self.core.json("GET", "/v1/integration/outbox",
                                  params={"status": "pending", "after_id": 0, "limit": self.page_size})
            items = page.get("items", [])
            if not items:
                break
            with self.sessions() as s:
                keys = {message_key(m): m for m in items}
                known = set(s.execute(select(NotificationRow.message_key).where(
                    NotificationRow.message_key.in_(list(keys)))).scalars())
                for key, m in keys.items():
                    if key in known:
                        continue
                    s.add(NotificationRow(
                        message_key=key, outbox_id=m["id"], case_id=m["case_id"], recipient_id=m["recipient"],
                        recipient_role=m.get("recipient_role") or ("patient" if m["channel"] == "sahatna"
                                                                   else "default"),
                        template=m["template"], urgent=bool(m["urgent"]), language=_language(m),
                        payload=m["payload"], status="pending", next_at=now, received_at=now, updated_at=now))
                    stored += 1
                try:
                    s.commit()
                except IntegrityError:  # another notifier replica stored them first
                    s.rollback()
            self.core.json("POST", "/v1/integration/outbox/ack", json={"ids": [m["id"] for m in items]})
            if len(items) < self.page_size:
                break
        return stored

    # ---- 2. dispatch ------------------------------------------------------------------------------
    def dispatch(self, now: datetime, limit: int = 500) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        with self.sessions() as s:
            due = s.execute(select(NotificationRow).where(
                NotificationRow.status.in_(["pending", "sending", "waiting"]),
                or_(NotificationRow.next_at.is_(None), NotificationRow.next_at <= now))
                .order_by(NotificationRow.urgent.desc(), NotificationRow.id).limit(limit)).scalars().all()
            for n in due:
                self._advance(s, n, now)
                n.updated_at = now
                counts[n.status] += 1
            s.commit()
        return dict(counts)

    def _send(self, s: Session, n: NotificationRow, step_no: int, step: Step, now: datetime) -> str:
        ch = self.policy.channels[step.channel]
        msg = Outgoing(channel=step.channel, recipient_id=n.recipient_id,
                       idempotency_key=f"{n.message_key}:{step_no}:{step.channel}",
                       body=render(step.channel, n, ch.carries_content))
        result = self.provider.send(msg)
        d = self._delivery(s, n, step_no, step.channel)
        status = "failed" if result.status == "retry" else result.status
        if d is None:
            d = DeliveryRow(notification_id=n.id, step=step_no, channel=step.channel, created_at=now)
            s.add(d)
        d.status, d.provider_ref, d.detail, d.updated_at = status, result.provider_ref, result.detail[:300], now
        s.flush()
        return result.status

    def _advance(self, s: Session, n: NotificationRow, now: datetime) -> None:
        steps, parallel = self.policy.steps_for(n.recipient_role, n.urgent)
        if n.status == "pending":
            release = self.policy.quiet_until(n.recipient_role, n.urgent, now)
            if release is not None:
                n.next_at = release
                return
        if parallel:
            results = [self._send(s, n, i, st, now) for i, st in enumerate(steps)]
            n.status = "done" if any(r in ("sent", "delivered", "read") for r in results) else "exhausted"
            n.next_at = None
            return
        while True:
            if n.step >= len(steps):
                self._exhaust(n)
                return
            step = steps[n.step]
            success_on = self.policy.channels[step.channel].success_on
            if n.status == "waiting":
                d = self._delivery(s, n, n.step, step.channel)
                if d is not None and _satisfied(d.status, success_on):
                    n.status, n.next_at = "done", None
                    return
                n.step, n.attempts, n.status = n.step + 1, 0, "sending"  # timed out or failed: next channel
                continue
            if step.channel == "email_digest":
                if self._delivery(s, n, n.step, step.channel) is None:
                    s.add(DeliveryRow(notification_id=n.id, step=n.step, channel=step.channel, status="queued",
                                      created_at=now, updated_at=now))
                n.status, n.next_at = "digest", None
                return
            result = self._send(s, n, n.step, step, now)
            if result == "retry":
                n.attempts += 1
                if n.attempts <= MAX_PROVIDER_RETRIES:
                    n.status, n.next_at = "sending", now + timedelta(minutes=2 ** n.attempts)
                    return
                result = "failed"
            if result == "failed":
                n.step, n.attempts, n.status = n.step + 1, 0, "sending"
                continue
            if _satisfied(result, success_on):
                n.status, n.next_at = "done", None
                return
            n.status, n.next_at = "waiting", now + timedelta(hours=step.wait_hours)
            return

    def _delivery(self, s: Session, n: NotificationRow, step_no: int, channel: str) -> DeliveryRow | None:
        return s.execute(select(DeliveryRow).where(DeliveryRow.notification_id == n.id, DeliveryRow.step == step_no,
                                                   DeliveryRow.channel == channel)).scalar_one_or_none()

    def _exhaust(self, n: NotificationRow) -> None:
        n.status, n.next_at = "exhausted", None
        if self.policy.route(n.recipient_role).on_exhausted == "report_patient_unreached":
            n.report_pending = True

    # ---- 3. provider receipts ---------------------------------------------------------------------
    def receipt(self, delivery_id: int, status: str, now: datetime) -> dict[str, Any] | None:
        with self.sessions() as s:
            d = s.get(DeliveryRow, delivery_id)
            if d is None:
                return None
            if status == "failed" or RANK.get(status, 0) > RANK.get(d.status, 0):
                d.status, d.updated_at = status, now
            n = s.get(NotificationRow, d.notification_id)
            if n is not None and n.status == "waiting" and n.step == d.step:
                success_on = self.policy.channels[d.channel].success_on
                if _satisfied(d.status, success_on):
                    n.status, n.next_at = "done", None
                elif d.status == "failed":
                    n.next_at = now  # move to the next channel on the next dispatch
                n.updated_at = now
            s.commit()
            return {"delivery_id": d.id, "status": d.status, "notification_status": n.status if n else None}

    # ---- 4. daily digest --------------------------------------------------------------------------
    def run_digest(self, now: datetime, force: bool = False) -> int:
        if not (force or self.policy.digest_due(now)):
            return 0
        day = self.policy.local_day(now)
        sent = 0
        with self.sessions() as s:
            queued = s.execute(select(NotificationRow).where(NotificationRow.status == "digest")).scalars().all()
            by_recipient: dict[str, list[NotificationRow]] = defaultdict(list)
            for n in queued:
                by_recipient[n.recipient_id].append(n)
            for rid, items in by_recipient.items():
                if s.get(DigestRunRow, (rid, day)) is not None:
                    continue  # today's digest already went; these wait for tomorrow
                lines = [render("email_digest", n, True) for n in items]
                result = self.provider.send(Outgoing(channel="email_digest", recipient_id=rid,
                                                     idempotency_key=f"digest:{rid}:{day}",
                                                     body={"subject": f"Tasleem daily summary ({len(items)})",
                                                           "items": lines}))
                if result.status in ("retry", "failed"):
                    continue
                s.add(DigestRunRow(recipient_id=rid, day=day, items=len(items), sent_at=now))
                for n in items:
                    d = self._delivery(s, n, n.step, "email_digest")
                    if d is not None:
                        d.status, d.provider_ref, d.updated_at = "sent", result.provider_ref, now
                    n.status, n.updated_at = "done", now
                sent += 1
            s.commit()
        return sent

    # ---- 5. tell case-core about patients no channel reached --------------------------------------
    def report_unreached(self, now: datetime) -> int:
        if self.core is None:
            return 0
        reported = 0
        with self.sessions() as s:
            pending = s.execute(select(NotificationRow).where(NotificationRow.report_pending.is_(True))
                                .limit(200)).scalars().all()
            for n in pending:
                channels = [d.channel for d in s.execute(select(DeliveryRow).where(
                    DeliveryRow.notification_id == n.id).order_by(DeliveryRow.step)).scalars()]
                try:
                    self.core.json("POST", "/v1/integration/delivery-failures",
                                   json={"outbox_id": n.outbox_id, "channels": channels or ["none"]})
                except ServiceError as exc:
                    if exc.status is not None and 400 <= exc.status < 500 and exc.status not in (408, 429):
                        log.warning("core refused unreached report %s: %s", n.outbox_id, exc.body)
                        n.report_pending = False  # e.g. case closed meanwhile; do not retry forever
                    continue
                n.report_pending, n.updated_at = False, now
                reported += 1
            s.commit()
        return reported

    def run_once(self, now: datetime) -> dict[str, Any]:
        return {"pulled": self.pull(now), "dispatched": self.dispatch(now), "digests": self.run_digest(now),
                "reported_unreached": self.report_unreached(now)}
