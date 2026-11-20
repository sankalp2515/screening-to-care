from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def to_utc(dt: datetime) -> datetime:
    """Normalize to timezone-aware UTC (SQLite returns naive datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# --------------------------------------------------------------------------------------------------
# Actors
# --------------------------------------------------------------------------------------------------
class ActorType(StrEnum):
    CLINICIAN = "clinician"
    NAVIGATOR = "navigator"
    COORDINATOR = "coordinator"
    PATIENT = "patient"
    SYSTEM = "system"
    AI = "ai"
    INTEGRATION = "integration"


STAFF_TYPES = frozenset({ActorType.CLINICIAN, ActorType.NAVIGATOR, ActorType.COORDINATOR})
# Actor types that can never take a human decision (R5).
NON_HUMAN_TYPES = frozenset({ActorType.SYSTEM, ActorType.AI, ActorType.INTEGRATION})


class Actor(BaseModel, frozen=True):
    id: str
    type: ActorType


SYSTEM_ACTOR = Actor(id="system", type=ActorType.SYSTEM)


# --------------------------------------------------------------------------------------------------
# Vocabularies
# --------------------------------------------------------------------------------------------------
class AdminStatus(StrEnum):
    """What the referral system (Malaffi REF) reports. Never advances a verified stage by itself."""

    NONE = "NONE"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SignalKind(StrEnum):
    """Normalized clinical/administrative signals produced by ingest adapters."""

    LAB_RESULT = "LAB_RESULT"
    PATIENT_INVITED = "PATIENT_INVITED"
    RESULT_DISCUSSED = "RESULT_DISCUSSED"
    REFERRAL_SENT = "REFERRAL_SENT"
    REFERRAL_ACCEPTED = "REFERRAL_ACCEPTED"
    REFERRAL_REJECTED = "REFERRAL_REJECTED"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    APPOINTMENT_ATTENDED = "APPOINTMENT_ATTENDED"
    APPOINTMENT_NOSHOW = "APPOINTMENT_NOSHOW"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    PROCEDURE_COMPLETED = "PROCEDURE_COMPLETED"
    REPORT_FINAL = "REPORT_FINAL"
    OUTCOME_COMMUNICATED = "OUTCOME_COMMUNICATED"
    CARE_PLAN_ACTIVE = "CARE_PLAN_ACTIVE"
    ADMIN_STATUS = "ADMIN_STATUS"


class StallReason(StrEnum):
    STEP_OVERDUE = "STEP_OVERDUE"
    BOOKED_NOT_ATTENDED = "BOOKED_NOT_ATTENDED"
    CONSULT_NO_PROCEDURE = "CONSULT_NO_PROCEDURE"
    CLOSED_WITHOUT_EVIDENCE = "CLOSED_WITHOUT_EVIDENCE"
    REPORT_NOT_COMMUNICATED = "REPORT_NOT_COMMUNICATED"
    HANDOFF_NOT_ACCEPTED = "HANDOFF_NOT_ACCEPTED"
    REFERRAL_REJECTED = "REFERRAL_REJECTED"
    CONSULT_UNANSWERED = "CONSULT_UNANSWERED"
    # Evidence Reader: a report arrived, but what it says has not been confirmed, or it says the loop is not closed.
    REPORT_NOT_REVIEWED = "REPORT_NOT_REVIEWED"
    PROCEDURE_INCOMPLETE = "PROCEDURE_INCOMPLETE"
    PATHOLOGY_OUTSTANDING = "PATHOLOGY_OUTSTANDING"


class Outcome(StrEnum):
    COMPLETED_WITH_REPORT = "COMPLETED_WITH_REPORT"
    COMPLETED_ELSEWHERE = "COMPLETED_ELSEWHERE"
    PLAN_CHANGED = "PLAN_CHANGED"
    INFORMED_REFUSAL = "INFORMED_REFUSAL"
    UNREACHABLE = "UNREACHABLE"


# Outcomes that represent the diagnostic step actually happening. Everything else is reported separately.
CARE_COMPLETED_OUTCOMES = frozenset({Outcome.COMPLETED_WITH_REPORT, Outcome.COMPLETED_ELSEWHERE})


class BarrierCode(StrEnum):
    FEAR = "FEAR"
    PREP_UNCLEAR = "PREP_UNCLEAR"
    NO_ESCORT = "NO_ESCORT"
    TRANSPORT = "TRANSPORT"
    COST_OR_INSURANCE = "COST_OR_INSURANCE"
    TIME_OR_WORK = "TIME_OR_WORK"
    LANGUAGE = "LANGUAGE"
    # Abu Dhabi evidence: embarrassment, above all a male endoscopist for a female patient (BMC Cancer 2021).
    FEMALE_CLINICIAN = "FEMALE_CLINICIAN"
    WANTS_CALLBACK = "WANTS_CALLBACK"
    DONE_ELSEWHERE = "DONE_ELSEWHERE"
    OTHER = "OTHER"


class EventType(StrEnum):
    CASE_OPENED = "CASE_OPENED"
    WARNING_ADDED = "WARNING_ADDED"
    TRIGGER_REPEATED = "TRIGGER_REPEATED"
    STAGE_REACHED = "STAGE_REACHED"
    APPOINTMENT_MISSED = "APPOINTMENT_MISSED"
    ADMIN_STATUS_CHANGED = "ADMIN_STATUS_CHANGED"
    REFERRAL_REJECTED = "REFERRAL_REJECTED"
    HANDOFF_OFFERED = "HANDOFF_OFFERED"
    HANDOFF_ACCEPTED = "HANDOFF_ACCEPTED"
    HANDOFF_REJECTED = "HANDOFF_REJECTED"
    STALL_FLAGGED = "STALL_FLAGGED"
    STALL_CLEARED = "STALL_CLEARED"
    ESCALATED = "ESCALATED"
    BARRIER_REPORTED = "BARRIER_REPORTED"
    BARRIER_SUGGESTED = "BARRIER_SUGGESTED"
    BARRIER_CONFIRMED = "BARRIER_CONFIRMED"
    BARRIER_RESOLVED = "BARRIER_RESOLVED"
    DISTRESS_FLAGGED = "DISTRESS_FLAGGED"
    DISTRESS_RESOLVED = "DISTRESS_RESOLVED"
    CONTACT_ATTEMPTED = "CONTACT_ATTEMPTED"
    CONSULT_REQUESTED = "CONSULT_REQUESTED"
    CONSULT_ANSWERED = "CONSULT_ANSWERED"
    CONSENT_RECORDED = "CONSENT_RECORDED"
    PATIENT_MESSAGE_SENT = "PATIENT_MESSAGE_SENT"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    REPORT_TEXT_RECEIVED = "REPORT_TEXT_RECEIVED"
    REPORT_REVIEWED = "REPORT_REVIEWED"
    CASE_CLOSED = "CASE_CLOSED"


# --------------------------------------------------------------------------------------------------
# Events and signals
# --------------------------------------------------------------------------------------------------
class Event(BaseModel):
    """A fact about a case. Sequence numbers and hashes are added by the repository on append."""

    type: EventType
    actor_id: str
    actor_type: ActorType
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class Signal(BaseModel):
    """Normalized output of an ingest adapter (FHIR resource or Malaffi REF message)."""

    kind: SignalKind
    patient_id: str
    occurred_at: datetime
    ref: str  # e.g. "Appointment/apt-1"
    codes: list[str] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    value: float | None = None
    unit: str | None = None
    appointment_at: datetime | None = None
    admin_status: AdminStatus | None = None
    service: str | None = None
    reason: str | None = None
    text: str | None = None  # free text of a report (DiagnosticReport.conclusion), read by the Evidence Reader


# --------------------------------------------------------------------------------------------------
# Case aggregate state (projection of the event stream)
# --------------------------------------------------------------------------------------------------
class StageEvidence(BaseModel):
    reached_at: datetime
    ref: str
    signal: str
    by: str


class Handoff(BaseModel):
    to_id: str
    reason: str
    offered_by: str
    offered_at: datetime


class Stall(BaseModel):
    reason: StallReason
    stage: str | None = None
    detail: str = ""
    flagged_at: datetime
    level: int = 1
    last_escalated_at: datetime
    escalated_to: str


class Barrier(BaseModel):
    id: str
    reported_codes: list[BarrierCode] = Field(default_factory=list)
    text: str | None = None
    reported_by: str
    reported_at: datetime
    suggested_code: BarrierCode | None = None
    suggested_confidence: float | None = None
    suggested_model: str | None = None
    confirmed_code: BarrierCode | None = None
    confirmed_by: str | None = None
    assignee_role: str | None = None
    action: str | None = None
    due_at: datetime | None = None
    status: str = "reported"  # reported | confirmed | resolved
    resolution_note: str | None = None


class DistressFlag(BaseModel):
    id: str
    barrier_id: str | None
    matched: list[str]
    flagged_at: datetime
    routed_to: str
    resolved: bool = False
    resolved_by: str | None = None
    note: str | None = None


class Consult(BaseModel):
    id: str
    to_id: str
    asked_by: str
    question: str
    asked_at: datetime
    due_at: datetime
    answer: str | None = None
    answered_at: datetime | None = None


class ReportReview(BaseModel):
    """A free-text report and, once a clinician has checked it, the findings they confirmed (Evidence Reader)."""

    id: str  # "rpt-<n>"
    ref: str
    text: str
    received_at: datetime
    findings: dict[str, Any] | None = None  # confirmed values only; None until reviewed
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    suggested_by: str | None = None  # reader that proposed the values (model id or keyword reader)
    corrected: list[str] = Field(default_factory=list)  # fields the clinician changed from the suggestion

    @property
    def reviewed(self) -> bool:
        return self.findings is not None


class DeliveryAlert(BaseModel):
    """A patient message that no channel could deliver. A human must take over (navigator call)."""

    id: str  # "out-<outbox id>"
    channels: list[str]
    flagged_at: datetime
    resolved: bool = False
    resolved_by: str | None = None


class CaseState(BaseModel):
    id: str
    patient_id: str
    pathway_id: str
    pathway_version: int
    status: str = "open"  # open | closed
    owner_id: str
    priority: str
    trigger_ref: str
    opened_at: datetime
    updated_at: datetime
    last_progress_at: datetime
    stages: dict[str, StageEvidence] = Field(default_factory=dict)
    admin_status: AdminStatus = AdminStatus.NONE
    admin_status_at: datetime | None = None
    appointment_at: datetime | None = None
    appointment_missed: str | None = None  # "noshow" | "cancelled" | None
    referral_rejected_at: datetime | None = None
    referral_rejected_reason: str | None = None
    pending_handoff: Handoff | None = None
    stalls: dict[str, Stall] = Field(default_factory=dict)
    barriers: dict[str, Barrier] = Field(default_factory=dict)
    distress: dict[str, DistressFlag] = Field(default_factory=dict)
    consults: dict[str, Consult] = Field(default_factory=dict)
    contact_attempts: int = 0
    messages_sent: int = 0
    delivery_alerts: dict[str, DeliveryAlert] = Field(default_factory=dict)
    escalation_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    reports: dict[str, ReportReview] = Field(default_factory=dict)
    consent_at: datetime | None = None
    outcome: Outcome | None = None
    outcome_evidence_ref: str | None = None
    outcome_reason: str | None = None
    closed_at: datetime | None = None
    closed_by: str | None = None
    version: int = 0  # number of events applied

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    @property
    def escalation_level(self) -> int:
        return max((s.level for s in self.stalls.values()), default=0)

    @property
    def open_distress(self) -> list[DistressFlag]:
        return [d for d in self.distress.values() if not d.resolved]

    @property
    def open_delivery_alerts(self) -> list[DeliveryAlert]:
        return [a for a in self.delivery_alerts.values() if not a.resolved]

    def reached(self, stage: str) -> bool:
        return stage in self.stages

    @property
    def unreviewed_reports(self) -> list[ReportReview]:
        return [r for r in self.reports.values() if not r.reviewed]

    @property
    def confirmed_findings(self) -> dict[str, Any]:
        """Findings confirmed across every reviewed report; a later report overrides what it states (for example a
        pathology report clearing "pathology pending"), and leaves alone what it does not mention."""
        out: dict[str, Any] = {}
        for r in sorted((r for r in self.reports.values() if r.reviewed), key=lambda r: r.received_at):
            for k, v in (r.findings or {}).items():
                if v is not None:
                    out[k] = v
        return out
