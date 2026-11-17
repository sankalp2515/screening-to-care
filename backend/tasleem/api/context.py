from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..domain.barriers import BarrierClassifier, KeywordBarrierClassifier
from ..domain.pathways import PathwayRegistry
from ..infra.cache import Cache, make_cache
from ..infra.db import create_schema, make_engine, make_sessionmaker
from ..infra.repository import CaseRepository
from ..services.cases import CaseService
from ..services.directory import Directory
from ..services.ingest import IngestService
from ..services.views import MetricsService


@dataclass
class AppContext:
    """Process-wide singletons. Everything request-scoped is built from these per request."""

    settings: Settings
    engine: Engine
    sessions: sessionmaker
    registry: PathwayRegistry
    cache: Cache
    classifier: BarrierClassifier

    @classmethod
    def build(cls, settings: Settings) -> AppContext:
        engine = make_engine(settings.database_url, pool_size=settings.db_pool_size,
                             max_overflow=settings.db_max_overflow,
                             statement_timeout_ms=settings.db_statement_timeout_ms)
        if settings.auto_create_schema:
            create_schema(engine)  # SQLite and demo; Postgres deployments run `python -m tasleem.migrate`
        return cls(settings=settings, engine=engine, sessions=make_sessionmaker(engine),
                   registry=PathwayRegistry.from_dir(settings.pathways_dir), cache=make_cache(settings.redis_url),
                   classifier=KeywordBarrierClassifier())


@dataclass
class Services:
    session: Session
    directory: Directory
    cases: CaseService
    ingest: IngestService
    metrics: MetricsService

    @classmethod
    def build(cls, ctx: AppContext, session: Session) -> Services:
        directory = Directory(session, ctx.cache)
        cases = CaseService(session, ctx.registry, directory, ctx.cache, ctx.classifier)
        ingest = IngestService(session, ctx.registry, directory, cases)
        metrics = MetricsService(CaseRepository(session).iter_states, ctx.registry, ctx.cache,
                                 ctx.settings.metrics_ttl_seconds, ctx.settings.metrics_max_staleness_seconds,
                                 org_of=lambda pid: (p.org_id if (p := directory.person(pid)) else None),
                                 language_of=lambda pid: (x.preferred_language if (x := directory.patient(pid))
                                                          else None))
        return cls(session, directory, cases, ingest, metrics)
