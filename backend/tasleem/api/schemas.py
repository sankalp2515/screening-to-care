from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..domain.model import BarrierCode, Outcome


class HandoffIn(BaseModel):
    to: str
    reason: str


class RejectIn(BaseModel):
    reason_code: str


class BarrierIn(BaseModel):
    codes: list[BarrierCode] = Field(default_factory=list)
    text: str | None = Field(default=None, max_length=2000)


class ConfirmBarrierIn(BaseModel):
    code: BarrierCode


class NoteIn(BaseModel):
    note: str = Field(max_length=2000)


class ContactIn(BaseModel):
    channel: str = Field(pattern="^(phone|sms|sahatna|whatsapp|in_person|email)$")
    result: str = Field(pattern="^(reached|no_answer|wrong_number|left_message|declined)$")


class ConsultIn(BaseModel):
    to: str
    question: str = Field(max_length=4000)


class ReportReviewIn(BaseModel):
    """What the clinician confirms a report says. `suggestion` is what the reader proposed, so corrections are
    measured (AI acceptance monitoring)."""

    findings: dict[str, bool | int | str | None]
    suggested_by: str | None = Field(default=None, max_length=80)
    suggestion: dict[str, bool | int | str | None] | None = None


class AnswerIn(BaseModel):
    answer: str = Field(max_length=4000)


class CloseIn(BaseModel):
    outcome: Outcome
    evidence_ref: str | None = None
    reason: str | None = Field(default=None, max_length=2000)


class TickIn(BaseModel):
    now: datetime | None = None
    limit: int = Field(default=500, ge=1, le=5000)


class AckIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=1000)


class PatientMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    language: str = Field(default="en", pattern="^(en|ar)$")
    # Set when the text started as an AI draft; recorded on the event (R5 provenance).
    ai_draft_id: str | None = Field(default=None, max_length=64, pattern="^[A-Za-z0-9_-]+$")


class TextIn(BaseModel):
    text: str = Field(max_length=4000)


class PrepAnswersIn(BaseModel):
    answers: dict[str, str] = Field(max_length=20)


class DeliveryFailureIn(BaseModel):
    outbox_id: int = Field(ge=1)
    channels: list[str] = Field(min_length=1, max_length=10)
