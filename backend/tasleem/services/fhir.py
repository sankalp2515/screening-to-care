"""FHIR R4 → normalized Signal adapter (subset needed for screening follow-up).

Only fields the pathways use are read. Unknown resource types are ignored, not rejected, so a Malaffi
feed can send everything and Tasleem picks what matters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from ..domain.model import AdminStatus, Signal, SignalKind, to_utc

PURPOSE_INVITE = "result-invitation"
PURPOSE_OUTCOME = "outcome-notification"
REASON_RESULT_DISCUSSION = "result-discussion"


class IngestValidationError(Exception):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class Parsed(BaseModel):
    message_id: str
    resource_type: str
    signals: list[Signal]
    ignored_reason: str | None = None


def _ref_id(ref: str | None, prefix: str = "Patient/") -> str | None:
    if not ref or not ref.startswith(prefix):
        return None
    return ref[len(prefix):] or None


def _codes(cc: Any) -> list[str]:
    """Codes from a CodeableConcept or a list of them. Anything else is malformed and rejected (422),
    never silently read as 'no code', which would hide a positive result."""
    if cc is None:
        return []
    items = cc if isinstance(cc, list) else [cc]
    out: list[str] = []
    for c in items:
        if not isinstance(c, dict) or not isinstance(c.get("coding", []), list):
            raise TypeError(f"expected a CodeableConcept, got {type(c).__name__}")
        out += [str(x["code"]) for x in c.get("coding", []) if isinstance(x, dict) and x.get("code")]
    return out


def _patient(r: dict[str, Any]) -> str | None:
    for key in ("subject", "patient", "for"):
        pid = _ref_id((r.get(key) or {}).get("reference"))
        if pid:
            return pid
    for part in r.get("participant", []) or []:
        pid = _ref_id((part.get("actor") or {}).get("reference"))
        if pid:
            return pid
    for rec in r.get("recipient", []) or []:
        pid = _ref_id(rec.get("reference"))
        if pid:
            return pid
    return None


def _time(r: dict[str, Any], default: datetime) -> datetime:
    for key in ("effectiveDateTime", "issued", "performedDateTime", "sent", "authoredOn", "occurrenceDateTime"):
        if r.get(key):
            return to_utc(datetime.fromisoformat(str(r[key]).replace("Z", "+00:00")))
    for key in ("performedPeriod", "period", "executionPeriod", "effectivePeriod"):
        start = (r.get(key) or {}).get("start")
        if start:
            return to_utc(datetime.fromisoformat(str(start).replace("Z", "+00:00")))
    last = (r.get("meta") or {}).get("lastUpdated")
    if last:
        return to_utc(datetime.fromisoformat(str(last).replace("Z", "+00:00")))
    return default


def _dt(v: Any) -> datetime | None:
    return to_utc(datetime.fromisoformat(str(v).replace("Z", "+00:00"))) if v else None


def parse_resource(r: dict[str, Any], now: datetime, message_id: str | None = None) -> Parsed:
    rt = r.get("resourceType")
    if not rt:
        raise IngestValidationError("resourceType", "resourceType is required")
    if not r.get("id"):
        raise IngestValidationError("id", f"{rt}.id is required")
    version = (r.get("meta") or {}).get("versionId") or "1"
    mid = message_id or f"{rt}/{r['id']}/{version}"
    ref = f"{rt}/{r['id']}"
    status = r.get("status")

    def skip(reason: str) -> Parsed:
        return Parsed(message_id=mid, resource_type=rt, signals=[], ignored_reason=reason)

    handled = {"Observation", "DiagnosticReport", "ServiceRequest", "Task", "Appointment", "Procedure",
               "Communication", "Encounter", "CarePlan"}
    if rt not in handled:
        return skip(f"resource type {rt} not used by any pathway")
    pid = _patient(r)
    if not pid:
        raise IngestValidationError("subject", f"{rt} must reference a Patient")
    at = _time(r, now)

    def sig(kind: SignalKind, **kw: Any) -> Parsed:
        return Parsed(message_id=mid, resource_type=rt,
                      signals=[Signal(kind=kind, patient_id=pid, occurred_at=at, ref=ref, **kw)])

    final = status in ("final", "amended", "corrected")
    if rt == "Observation":
        if not final:
            return skip(f"observation status {status}")
        vq = r.get("valueQuantity") or {}
        return sig(SignalKind.LAB_RESULT, codes=_codes(r.get("code")), interpretation=_codes(r.get("interpretation")),
                   value=vq.get("value"), unit=vq.get("unit"))
    if rt == "DiagnosticReport":
        if not final:
            return skip(f"report status {status}")
        return sig(SignalKind.REPORT_FINAL, codes=_codes(r.get("code")))
    if rt == "ServiceRequest":
        if status != "active":
            return skip(f"service request status {status}")
        return sig(SignalKind.REFERRAL_SENT, codes=_codes(r.get("code")))
    if rt == "Task":
        if status in ("accepted", "in-progress"):
            return sig(SignalKind.REFERRAL_ACCEPTED)
        if status == "rejected":
            reason = (r.get("statusReason") or {}).get("text") or ",".join(_codes(r.get("statusReason"))) or None
            return sig(SignalKind.REFERRAL_REJECTED, reason=reason)
        return skip(f"task status {status}")
    if rt == "Appointment":
        start = _dt(r.get("start"))
        if status == "booked":
            if start is None:
                raise IngestValidationError("start", "a booked Appointment needs a start time")
            return sig(SignalKind.APPOINTMENT_BOOKED, appointment_at=start)
        if status in ("fulfilled", "arrived", "checked-in"):
            return sig(SignalKind.APPOINTMENT_ATTENDED)
        if status == "noshow":
            return sig(SignalKind.APPOINTMENT_NOSHOW)
        if status == "cancelled":
            return sig(SignalKind.APPOINTMENT_CANCELLED)
        return skip(f"appointment status {status}")
    if rt == "Procedure":
        if status != "completed":
            return skip(f"procedure status {status}")
        return sig(SignalKind.PROCEDURE_COMPLETED, codes=_codes(r.get("code")))
    if rt == "Communication":
        if status != "completed":
            return skip(f"communication status {status}")
        purposes = _codes(r.get("category"))
        if PURPOSE_INVITE in purposes:
            return sig(SignalKind.PATIENT_INVITED)
        if PURPOSE_OUTCOME in purposes:
            return sig(SignalKind.OUTCOME_COMMUNICATED)
        return skip("communication purpose not tracked")
    if rt == "Encounter":
        if status != "finished":
            return skip(f"encounter status {status}")
        if REASON_RESULT_DISCUSSION in _codes(r.get("reasonCode")) + _codes(r.get("type")):
            return sig(SignalKind.RESULT_DISCUSSED)
        return skip("encounter not a result discussion")
    if rt == "CarePlan":
        if status != "active":
            return skip(f"care plan status {status}")
        return sig(SignalKind.CARE_PLAN_ACTIVE)
    return skip("unhandled")  # pragma: no cover


def parse(payload: dict[str, Any], now: datetime, message_id: str | None = None) -> list[Parsed]:
    try:
        return _parse(payload, now, message_id)
    except IngestValidationError:
        raise
    except (ValueError, TypeError) as exc:  # bad dates, wrong JSON types: a 422 with a reason, never a 500
        raise IngestValidationError("resource", f"unreadable value: {str(exc).splitlines()[0][:200]}") from None


def _parse(payload: dict[str, Any], now: datetime, message_id: str | None = None) -> list[Parsed]:
    if not isinstance(payload, dict):
        raise IngestValidationError("resource", "body must be a JSON object")
    if payload.get("resourceType") == "Bundle":
        entries = payload.get("entry") or []
        if not entries:
            raise IngestValidationError("entry", "Bundle has no entries")
        return [parse_resource(e.get("resource") or {}, now) for e in entries]
    return [parse_resource(payload, now, message_id)]


class ReferralStatusMessage(BaseModel):
    """Simplified Malaffi REF status message (field names are an assumption until the spec is confirmed)."""

    message_id: str
    referral_id: str
    patient_id: str
    status: AdminStatus
    occurred_at: datetime
    service: str | None = None

    def to_signal(self) -> Signal:
        return Signal(kind=SignalKind.ADMIN_STATUS, patient_id=self.patient_id, occurred_at=to_utc(self.occurred_at),
                      ref=f"ServiceRequest/{self.referral_id}", admin_status=self.status, service=self.service)
