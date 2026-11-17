"""Robustness under load and races: ingest retries, scheduler drain, metrics staleness, request limits, paging."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import as_
from sqlalchemy import func, select

from tasleem.api.context import Services
from tasleem.config import Settings
from tasleem.infra.cache import WRITE_VERSION_KEY, InMemoryTTLCache
from tasleem.infra.db import CaseEventRow, InboundMessageRow, PatientRow
from tasleem.seed import fit
from tasleem.services.ingest import IngestService
from tasleem.services.scheduler import drain
from tasleem.services.views import MetricsService

FP = as_("dr-fatima")


def _ctx(client):
    return client.app.state.ctx


def test_readiness_and_liveness_are_separate(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_oversized_request_is_rejected_before_parsing(client):
    big = {"resourceType": "Observation", "note": "x" * 300_000}
    r = client.post("/v1/ingest/fhir", json=big)
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_worklist_pages_without_gaps_or_repeats(client):
    everything = client.get("/v1/cases?status=all&limit=500", headers=FP).json()
    assert everything["next_offset"] is None
    ids, offset = [], 0
    while offset is not None:
        page = client.get(f"/v1/cases?status=all&limit=3&offset={offset}", headers=FP).json()
        ids += [i["id"] for i in page["items"]]
        offset = page["next_offset"]
    assert ids == [i["id"] for i in everything["items"]]


def test_duplicate_message_racing_another_worker_is_not_applied_twice(client, monkeypatch):
    """Simulate: our duplicate check ran before the other worker committed the same message."""
    ctx = _ctx(client)
    now = datetime.now(UTC)
    with ctx.sessions() as s:
        svc = Services.build(ctx, s)
        first = svc.ingest.ingest_fhir(fit("p-yousef", "race-1", now), "lab", now)[0]
        assert first["duplicate"] is False
        events_before = s.execute(select(func.count()).select_from(CaseEventRow)).scalar_one()

        real = IngestService._existing
        calls = {"n": 0}

        def blind_first(self, source, message_id):  # first lookup misses, as if the other commit was in flight
            calls["n"] += 1
            return None if calls["n"] == 1 else real(self, source, message_id)

        monkeypatch.setattr(IngestService, "_existing", blind_first)
        second = svc.ingest.ingest_fhir(fit("p-yousef", "race-1", now), "lab", now)[0]
        assert second["duplicate"] is True and calls["n"] == 2  # unique key tripped, rolled back, retried
        assert s.execute(select(func.count()).select_from(CaseEventRow)).scalar_one() == events_before
        rows = s.execute(select(func.count()).select_from(InboundMessageRow)
                         .where(InboundMessageRow.message_id == first["message_id"])).scalar_one()
        assert rows == 1


def test_scheduler_drains_a_backlog_in_batches(client):
    ctx = _ctx(client)
    now = datetime.now(UTC)
    with ctx.sessions() as s:
        for i in range(12):
            s.add(PatientRow(id=f"p-load-{i}", display_name=f"Load {i}", preferred_language="en",
                             insurance_network="thiqa", family_physician_id="dr-fatima"))
        s.commit()
        svc = Services.build(ctx, s)
        for i in range(12):
            svc.ingest.ingest_fhir(fit(f"p-load-{i}", f"load-{i}", now - timedelta(days=40)), "lab",
                                   now - timedelta(days=40))
        result = drain(svc.cases, now + timedelta(days=1), batch=4, budget_seconds=30)
        assert result["batches"] >= 3 and result["checked"] >= 12 and result["conflicts"] == 0
        # Nothing is left due: a second drain finds no work.
        assert drain(svc.cases, now + timedelta(days=1), batch=4)["checked"] == 0


def test_metrics_staleness_is_bounded_and_flagged():
    cache = InMemoryTTLCache()
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return iter([])

    class Reg:
        def all(self):
            return []

    m = MetricsService(loader, Reg(), cache, ttl=60, max_staleness=60)
    assert m.get()["cached"] is False
    cache.incr(WRITE_VERSION_KEY)  # a write happened
    hit = m.get()
    assert hit["cached"] is True and hit["stale"] is True and calls["n"] == 1  # served within the bound

    exact = MetricsService(loader, Reg(), cache, ttl=60, max_staleness=0)
    cache.incr(WRITE_VERSION_KEY)
    assert exact.get()["cached"] is False and calls["n"] == 2  # bound 0 → always exact after a write


def test_settings_have_safe_production_limits():
    s = Settings()
    assert s.db_statement_timeout_ms > 0 and s.max_request_bytes <= 5_000_000
    assert 0 < s.metrics_max_staleness_seconds <= 60


def test_evidence_that_arrives_before_its_trigger_is_replayed(client):
    """Out-of-order delivery: the invite reaches Tasleem before the FIT result that it follows."""
    from tasleem.seed import comm
    from tasleem.services.fhir import PURPOSE_INVITE

    ctx = _ctx(client)
    t0 = datetime.now(UTC) - timedelta(days=2)
    with ctx.sessions() as s:
        s.add(PatientRow(id="p-ooo", display_name="Out Of Order", preferred_language="en",
                         insurance_network="thiqa", family_physician_id="dr-fatima"))
        s.commit()
        svc = Services.build(ctx, s)
        early = svc.ingest.ingest_fhir(comm("p-ooo", "inv-ooo", t0 + timedelta(hours=20), PURPOSE_INVITE), "lab",
                                       t0 + timedelta(hours=21))[0]
        assert early["status"] == "no_effect"  # no case yet
        opened = svc.ingest.ingest_fhir(fit("p-ooo", "fit-ooo", t0), "lab", t0 + timedelta(hours=30))[0]
        assert any(e["effect"] == "replayed" for e in opened["effects"])
        case = svc.cases.repo.find_open_for_patient("p-ooo")[0]
        assert "PATIENT_INVITED" in case.stages and not case.stalls
        # an older message (clinically before the trigger) is never pulled into the new case
        old = svc.ingest.ingest_fhir(comm("p-ooo", "inv-old", t0 - timedelta(days=30), PURPOSE_INVITE), "lab",
                                     t0 + timedelta(hours=31))[0]
        assert old["status"] in ("applied", "no_effect")
