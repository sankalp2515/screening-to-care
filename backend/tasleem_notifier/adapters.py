"""Channel adapters: render a message for one channel and hand it to a provider.

Two providers ship:
- SandboxProvider (demo and tests): records every send, never leaves the process, and can simulate a
  patient with no Sahatna app or an unreachable phone.
- WebhookProvider (pilot bridge): POSTs the rendered message as JSON to a configured HTTPS endpoint with
  an HMAC-SHA256 signature. The receiving bridge owns the real Sahatna / SMS gateway / EMR credentials,
  so this service never stores them.

Content rule: channels marked `carries_content: false` (SMS) send a fixed nudge in the person's language
and nothing about the case, because SMS is neither private nor under our control.
"""

from __future__ import annotations

import fnmatch
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

SMS_NUDGE = {
    "en": "You have a new message from your care team in the Sahatna app.",
    "ar": "لديك رسالة جديدة من فريق الرعاية في تطبيق صحتنا.",
}
SMS_PAGE = "Tasleem: an urgent task is waiting in your inbox."


@dataclass
class Outgoing:
    """What a provider receives. `recipient_id` is a pseudonymous id; the bridge resolves contacts."""

    channel: str
    recipient_id: str
    idempotency_key: str
    body: dict[str, Any]


@dataclass
class SendResult:
    status: str  # sent | delivered | failed | retry
    provider_ref: str | None = None
    detail: str = ""


class Provider(Protocol):
    def send(self, msg: Outgoing) -> SendResult: ...


def render(channel: str, n: Any, carries_content: bool) -> dict[str, Any]:
    """`n` is a stored notification (outbox copy). Pure function of its fields."""
    lang = n.language if n.language in ("en", "ar") else "en"
    if channel == "sms_nudge":
        return {"text": SMS_NUDGE[lang], "language": lang}
    if channel == "sms_page":
        return {"text": SMS_PAGE}
    if not carries_content:  # defensive: a future content-free channel never leaks the payload
        return {"text": SMS_PAGE}
    if channel in ("email", "email_digest"):
        task = n.payload or {}
        return {"subject": f"Tasleem: {(task.get('code') or {}).get('text') or n.template}",
                "text": task.get("description") or "", "case": n.case_id}
    if channel == "worklist":
        return {"case": n.case_id, "template": n.template, "where": "Tasleem > My work"}
    return n.payload  # sahatna_push: FHIR Communication; emr_task: FHIR Task


@dataclass
class SandboxProvider:
    """Deterministic stand-in for real gateways. Patterns use shell wildcards, e.g. 'p-demo-unreach-*'."""

    no_app: list[str] = field(default_factory=list)  # Sahatna push fails for these recipients
    no_phone: list[str] = field(default_factory=list)  # SMS fails for these recipients
    sent: list[Outgoing] = field(default_factory=list)

    def _match(self, rid: str, patterns: list[str]) -> bool:
        return any(fnmatch.fnmatch(rid, p) for p in patterns)

    def send(self, msg: Outgoing) -> SendResult:
        if msg.channel == "sahatna_push" and self._match(msg.recipient_id, self.no_app):
            return SendResult("failed", detail="no Sahatna app registered for this patient")
        if msg.channel in ("sms_nudge", "sms_page") and self._match(msg.recipient_id, self.no_phone):
            return SendResult("failed", detail="no reachable mobile number")
        self.sent.append(msg)
        # SMS gateways report handset delivery; the sandbox does so at once. Push 'read' needs a receipt.
        status = "delivered" if msg.channel.startswith("sms") else "sent"
        return SendResult(status, provider_ref=f"sbx-{uuid.uuid4().hex[:10]}")


@dataclass
class WebhookProvider:
    urls: dict[str, str]
    secret: str
    allow_insecure: bool = False
    timeout: float = 5.0
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        for ch, url in self.urls.items():
            if not url.startswith("https://") and not self.allow_insecure:
                raise ValueError(f"webhook for {ch} must use https")
        self._client = self.client or httpx.Client(timeout=self.timeout)

    def send(self, msg: Outgoing) -> SendResult:
        url = self.urls.get(msg.channel)
        if not url:
            return SendResult("failed", detail=f"no webhook configured for {msg.channel}")
        body = json.dumps({"channel": msg.channel, "recipient_id": msg.recipient_id, "body": msg.body},
                          separators=(",", ":"), sort_keys=True).encode()
        sig = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        try:
            r = self._client.post(url, content=body, headers={
                "content-type": "application/json", "idempotency-key": msg.idempotency_key,
                "x-tasleem-signature": f"sha256={sig}"})
        except httpx.TransportError as exc:
            return SendResult("retry", detail=f"transport error: {type(exc).__name__}")
        if r.status_code >= 500 or r.status_code == 429:
            return SendResult("retry", detail=f"provider {r.status_code}")
        if r.status_code >= 400:
            return SendResult("failed", detail=f"provider rejected ({r.status_code})")
        try:
            data = r.json()
        except ValueError:
            data = {}
        return SendResult(data.get("status", "sent") if data.get("status") in ("sent", "delivered") else "sent",
                          provider_ref=str(data.get("id")) if data.get("id") else None)


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    """For provider receipt callbacks: same HMAC scheme in the other direction."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])
