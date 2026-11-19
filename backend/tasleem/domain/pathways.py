from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from .model import AdminStatus, BarrierCode, Signal, SignalKind


class Trigger(BaseModel):
    signal: SignalKind = SignalKind.LAB_RESULT
    codes: list[str]
    positive_interpretations: list[str] = Field(default_factory=list)
    value_gte: float | None = None

    def matches(self, s: Signal) -> bool:
        if s.kind != self.signal or not set(s.codes) & set(self.codes):
            return False
        if self.positive_interpretations and set(s.interpretation) & set(self.positive_interpretations):
            return True
        if self.value_gte is not None and s.value is not None and s.value >= self.value_gte:
            return True
        return False


class StageDef(BaseModel):
    id: str
    label: str
    signals: list[SignalKind]  # ("on" would parse as a YAML boolean)
    codes: list[str] = Field(default_factory=list)  # optional code filter
    sla_days: float | None = None  # deadline from last verified progress; None = handled by a specific check
    note: str | None = None

    def matches(self, s: Signal) -> bool:
        if s.kind not in self.signals:
            return False
        return not self.codes or bool(set(s.codes) & set(self.codes))


class Checks(BaseModel):
    booked_stage: str | None = None
    attended_stage: str | None = None
    attended_grace_hours: float = 24
    procedure_stage: str | None = None
    consult_no_procedure_days: float = 21
    evidence_stage: str | None = None  # what proves the referral really completed
    admin_completed_grace_days: float = 3
    report_stage: str | None = None
    communicated_stage: str | None = None
    report_not_communicated_days: float = 7
    handoff_accept_days: float = 2
    consult_answer_days: float = 2
    reescalate_after_days: float = 3


class Playbook(BaseModel):
    assignee_role: str
    action: str
    due_days: float = 2


class PrepOption(BaseModel):
    id: str
    text: dict[str, str]


class PrepQuestion(BaseModel):
    """One teach-back question. A wrong answer becomes a barrier the care team must act on."""

    id: str
    text: dict[str, str]
    options: list[PrepOption]
    correct: str
    barrier_on_wrong: BarrierCode = BarrierCode.PREP_UNCLEAR

    @model_validator(mode="after")
    def _correct_is_an_option(self) -> PrepQuestion:
        if self.correct not in {o.id for o in self.options}:
            raise ValueError(f"prep question {self.id}: correct answer {self.correct} is not an option")
        return self


class Closure(BaseModel):
    completion_stages: list[str]
    min_contact_attempts_for_unreachable: int = 3


class GuidelineTarget(BaseModel):
    """One national quality indicator, measured on verified clinical evidence, never on referral status.
    Without `from_stage` it is the share of cases that reached `stage`; with it, the share that reached
    `stage` within `working_days` of `from_stage` (cases still inside the window are counted as pending)."""

    id: str
    label: str
    stage: str
    from_stage: str | None = None
    working_days: int | None = None
    acceptable: float = Field(ge=0, le=1)
    desirable: float = Field(ge=0, le=1)


class Guideline(BaseModel):
    source: str
    targets: list[GuidelineTarget]


class Pathway(BaseModel):
    id: str
    version: int
    name: str
    priority: str  # set by clinician-approved config, never by AI (R5)
    referral_service: str | None = None
    trigger: Trigger
    stages: list[StageDef]
    admin_status_map: dict[AdminStatus, str] = Field(default_factory=dict)
    checks: Checks = Field(default_factory=Checks)
    escalation_ladder: list[str] = Field(default_factory=lambda: ["owner", "clinic_lead", "program_coordinator"])
    playbooks: dict[BarrierCode, Playbook] = Field(default_factory=dict)
    closure: Closure
    patient_messages: dict[str, dict[str, str]] = Field(default_factory=dict)
    prep_check: list[PrepQuestion] = Field(default_factory=list)
    guideline: Guideline | None = None

    @model_validator(mode="after")
    def _validate(self) -> Pathway:
        ids = [s.id for s in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: duplicate stage ids")
        known = set(ids)
        c = self.checks
        for name in ("booked_stage", "attended_stage", "procedure_stage", "evidence_stage",
                     "report_stage", "communicated_stage"):
            v = getattr(c, name)
            if v is not None and v not in known:
                raise ValueError(f"{self.id}: checks.{name}={v} is not a stage")
        for st in self.closure.completion_stages:
            if st not in known:
                raise ValueError(f"{self.id}: closure stage {st} is not a stage")
        for st in self.admin_status_map.values():
            if st not in known:
                raise ValueError(f"{self.id}: admin_status_map stage {st} is not a stage")
        for t in self.guideline.targets if self.guideline else []:
            for st in (t.stage, t.from_stage):
                if st is not None and st not in known:
                    raise ValueError(f"{self.id}: guideline target {t.id} stage {st} is not a stage")
            if (t.from_stage is None) != (t.working_days is None):
                raise ValueError(f"{self.id}: guideline target {t.id} needs both from_stage and working_days")
        if not self.escalation_ladder or self.escalation_ladder[0] != "owner":
            raise ValueError(f"{self.id}: escalation ladder must start with 'owner'")
        if BarrierCode.OTHER not in self.playbooks:
            raise ValueError(f"{self.id}: a playbook for OTHER is required")
        return self

    @property
    def stage_ids(self) -> list[str]:
        return [s.id for s in self.stages]

    def stage_index(self, stage_id: str) -> int:
        return self.stage_ids.index(stage_id)

    def stage(self, stage_id: str) -> StageDef:
        return self.stages[self.stage_index(stage_id)]

    def stages_for(self, s: Signal) -> list[StageDef]:
        return [st for st in self.stages if st.matches(s)]

    def furthest_stage(self, reached: set[str]) -> str | None:
        idx = [self.stage_index(s) for s in reached if s in self.stage_ids]
        return self.stage_ids[max(idx)] if idx else None

    def next_stage(self, reached: set[str]) -> StageDef | None:
        far = self.furthest_stage(reached)
        start = 0 if far is None else self.stage_index(far) + 1
        return self.stages[start] if start < len(self.stages) else None


class PathwayRegistry:
    """Loads clinician-approved pathway files. Immutable per (id, version), so safe to cache in memory."""

    def __init__(self, pathways: list[Pathway]) -> None:
        self._by_id = {p.id: p for p in pathways}

    @classmethod
    def from_dir(cls, directory: Path) -> PathwayRegistry:
        files = sorted(Path(directory).glob("*.yaml"))
        if not files:
            raise FileNotFoundError(f"no pathway files in {directory}")
        return cls([Pathway.model_validate(yaml.safe_load(f.read_text(encoding="utf-8"))) for f in files])

    def get(self, pathway_id: str) -> Pathway:
        return self._by_id[pathway_id]

    def all(self) -> list[Pathway]:
        return list(self._by_id.values())
