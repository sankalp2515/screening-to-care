# ADR-001: A safety core plus satellite services

Status: **accepted, 17 Nov 2026**. Supersedes the "one deployable service" note in [ARCHITECTURE.md](ARCHITECTURE.md).

## Context
- **The request:** move to a microservice architecture.
- **The constraint** ([AGENTS.md](../../AGENTS.md)): rules R1 to R6 must never weaken.
- **The coupling:** R1 (one named owner), R3 (closure on evidence), R4 (escalation to a named human) and R6 (hash-chained audit) are enforced by writing four things in a single database transaction:
  1. the case events with their hash chain;
  2. the case projection;
  3. the assignments ("who must act");
  4. the outbox ("who must be told").

## Decision
Split along the lines where failure, scaling and trust really differ. Do not split the safety core.

| Service | Owns | Talks to | Why it is separate |
|---|---|---|---|
| **case-core API** (`tasleem`) | Cases, events, audit chain, assignments, outbox, pathways, directory (Postgres `tasleem`) | Postgres, Redis | The single writer of clinical state, so R1–R6 stay atomic and provable |
| **scheduler** (`tasleem.workers.scheduler`) | Nothing of its own: the same database as the core | Postgres | Deadlines keep running when the API scales to zero or restarts. Several replicas are safe: `SKIP LOCKED` plus optimistic versions |
| **notifier** (`tasleem_notifier`) | Notifications, delivery attempts, digests (Postgres `notifier`) | case-core over HTTP (outbox pull, ack, failure report); delivery bridges | An SMS or Sahatna outage must never block or roll back a clinical write. It has its own retry and fallback clock |
| **agent** (`tasleem_agent`) | Its own draft log (Postgres `agent`) | case-core over HTTP *as the caller*; an LLM, optionally | It has no credential that can write a case, so R5 holds by construction. LLM latency and cost are isolated. It can be switched off |
| **HL7 connector** (`tasleem_connector`) | Nothing | case-core ingest over HTTP | Parsing untrusted interface traffic stays outside the service that holds patient data. Each source's quirks live here |
| **shared library** (`tasleem_common`) | HTTP client with retries, rate limiter | — | Same behaviour everywhere, without copied code |

**Boundaries are enforced by a test.** `tests/test_core_v2.py::test_service_boundaries_hold` fails if:
- a satellite imports case-core code;
- a satellite imports another satellite;
- case-core imports a satellite.

The services share code only through `tasleem_common`, and data only through HTTP contracts.

## Alternatives rejected
- **Split the engine into case, task, escalation and audit services.** Each of R1, R3, R4 and R6 would then need a distributed transaction or a saga. An escalation could be lost, or an audit event written for a change that rolled back. That weakens the rules AGENTS.md forbids us to weaken. Rejected.
- **Stay a monolith.** Simpler, but channel outages, LLM cost and HL7 parsing would share a process and a blast radius with clinical writes. Rejected.
- **A message broker (Service Bus, Kafka) between services now.** The transactional outbox plus pull-and-ack already gives at-least-once hand-over with no extra infrastructure. Throughput needed is about 0.05 messages per second (see [SCALE_POSTGRES.md](../evidence/SCALE_POSTGRES.md)). A broker is the documented next step (TSL-045) when ingest bursts call for it, and the consumers would not change.

## Consequences
- **Five deployables from one image.** Every service runs identical library versions, but each scales, deploys and fails on its own. The trade-off: one image rebuild per change. Acceptable at this size; split the images when teams split.
- **Database per service** (three databases on one server locally; separate managed databases in production). No service reads another's tables.
- **Hand-over is at-least-once.** Every cross-service write is idempotent:
  - ingest is keyed by message id;
  - acks and failure reports are keyed by outbox id;
  - provider sends are keyed by outbox id, step and channel.
- **Local development stays simple.** Every service also runs in-process against SQLite. The tests wire the real apps together through HTTP test clients, so the contracts are exercised on every run.
