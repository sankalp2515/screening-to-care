from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tasleem.api.app import create_app
from tasleem.config import Settings
from tasleem.domain import engine
from tasleem.domain.model import Actor, ActorType, CaseState, Event, Signal, SignalKind
from tasleem.domain.pathways import Pathway, PathwayRegistry

PATHWAYS = Path(__file__).resolve().parents[1] / "pathways"
T0 = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)

FP = Actor(id="dr-fp", type=ActorType.CLINICIAN)
FP2 = Actor(id="dr-fp2", type=ActorType.CLINICIAN)
NAV = Actor(id="nav", type=ActorType.NAVIGATOR)
COORD = Actor(id="coord", type=ActorType.COORDINATOR)
PATIENT = Actor(id="p1", type=ActorType.PATIENT)
AI = Actor(id="keyword-v1", type=ActorType.AI)
SYS = Actor(id="system", type=ActorType.SYSTEM)
INTEG = Actor(id="malaffi", type=ActorType.INTEGRATION)

TARGETS = {"owner": None, "clinic_lead": "lead", "program_coordinator": "coord", "clinician": "dr-fp"}


def resolver(state: CaseState, target: str) -> str:
    return state.owner_id if target == "owner" else TARGETS[target]


def sig(kind: SignalKind, t: datetime, **kw: object) -> Signal:
    return Signal(kind=kind, patient_id="p1", occurred_at=t, ref=f"X/{kind.value}/{t.isoformat()}", **kw)


@pytest.fixture(scope="session")
def registry() -> PathwayRegistry:
    return PathwayRegistry.from_dir(PATHWAYS)


@pytest.fixture
def fit(registry: PathwayRegistry) -> Pathway:
    return registry.get("fit-positive-colonoscopy")


class Case:
    """Test helper that drives the pure engine and keeps every event (for replay and audit checks)."""

    def __init__(self, pathway: Pathway, t: datetime = T0, owner: str = "dr-fp") -> None:
        self.p = pathway
        self.events: list[Event] = []
        trig = sig(SignalKind.LAB_RESULT, t, codes=list(pathway.trigger.codes[:1]), interpretation=["POS"], value=9.0)
        evs = engine.open_case(case_id="c1", patient_id="p1", pathway=pathway, trigger=trig, owner_id=owner,
                               actor=INTEG)
        self.state, out = engine.execute(None, evs, pathway, t, resolver)
        self.events += out

    def run(self, events: list[Event], now: datetime) -> CaseState:
        self.state, out = engine.execute(self.state, events, self.p, now, resolver)
        self.events += out
        return self.state

    def signal(self, kind: SignalKind, t: datetime, **kw: object) -> CaseState:
        return self.run(engine.record_signal(self.state, self.p, sig(kind, t, **kw), INTEG), t)

    def tick(self, now: datetime) -> CaseState:
        return self.run([], now)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(Settings(database_url="sqlite://", demo_mode=True, seed_on_start=True,
                              metrics_max_staleness_seconds=0, max_request_bytes=200_000,
                              rate_limit_per_second=0))
    with TestClient(app) as c:
        yield c


def as_(user: str) -> dict[str, str]:
    return {"X-Demo-User": user}
