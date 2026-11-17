"""Channel policy loaded from channels.yaml and validated at start-up (bad config fails fast)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

DEFAULT_POLICY = Path(__file__).with_name("channels.yaml")


class ChannelDef(BaseModel):
    success_on: Literal["sent", "delivered", "read"]
    audience: Literal["patient", "staff"]
    carries_content: bool


class Step(BaseModel):
    channel: str
    wait_hours: float = 0


class Route(BaseModel):
    steps: list[Step] = Field(min_length=1)
    urgent_steps: list[Step] = Field(default_factory=list)
    quiet_hours: bool = False
    on_exhausted: Literal["report_patient_unreached"] | None = None


class QuietHours(BaseModel):
    start: int = Field(ge=0, le=23)
    end: int = Field(ge=0, le=23)


class Policy(BaseModel):
    timezone_offset_hours: float = 4
    quiet_hours: QuietHours = QuietHours(start=21, end=8)
    digest_hour: int = Field(default=7, ge=0, le=23)
    channels: dict[str, ChannelDef]
    recipients: dict[str, Route]

    @model_validator(mode="after")
    def _known_channels(self) -> Policy:
        if "default" not in self.recipients:
            raise ValueError("channel policy needs a 'default' recipient route")
        for role, r in self.recipients.items():
            for s in r.steps + r.urgent_steps:
                if s.channel not in self.channels:
                    raise ValueError(f"{role}: unknown channel {s.channel}")
                if role == "patient" and self.channels[s.channel].audience != "patient":
                    raise ValueError(f"patient route uses staff channel {s.channel}")
        return self

    @classmethod
    def load(cls, path: Path | None = None) -> Policy:
        return cls.model_validate(yaml.safe_load((path or DEFAULT_POLICY).read_text(encoding="utf-8")))

    # ---- decisions (pure) -----------------------------------------------------------------------
    def route(self, role: str) -> Route:
        return self.recipients.get(role) or self.recipients["default"]

    def steps_for(self, role: str, urgent: bool) -> tuple[list[Step], bool]:
        """(steps, parallel). Urgent messages go out on every urgent channel at once."""
        r = self.route(role)
        if urgent and r.urgent_steps:
            return r.urgent_steps, True
        return r.steps, False

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(hours=self.timezone_offset_hours))

    def quiet_until(self, role: str, urgent: bool, now: datetime) -> datetime | None:
        """If a message must wait for the end of quiet hours, when it may go out. None = send now."""
        if urgent or not self.route(role).quiet_hours:
            return None
        local = now.astimezone(self.tz)
        start, end = self.quiet_hours.start, self.quiet_hours.end
        h = local.hour
        in_quiet = (h >= start or h < end) if start > end else (start <= h < end)
        if not in_quiet:
            return None
        release = local.replace(hour=end, minute=0, second=0, microsecond=0)
        if release <= local:
            release += timedelta(days=1)
        return release.astimezone(now.tzinfo)

    def digest_due(self, now: datetime) -> bool:
        return now.astimezone(self.tz).hour >= self.digest_hour

    def local_day(self, now: datetime) -> str:
        return now.astimezone(self.tz).date().isoformat()

    def matrix(self) -> list[dict[str, object]]:
        """Human-readable table: who gets what, on which channel (for the UI and the docs)."""
        out = []
        for role, r in self.recipients.items():
            out.append({"recipient": role,
                        "routine": [s.model_dump() for s in r.steps],
                        "urgent": [s.model_dump() for s in r.urgent_steps] or None,
                        "quiet_hours": r.quiet_hours, "when_all_fail": r.on_exhausted})
        return out
