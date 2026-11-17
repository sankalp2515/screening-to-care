# Testing strategy

Rule from the organisers (V2): write the test cases before the code, record input, expected, actual and component, and publish the misses. Every layer below runs in CI ([ci.yml](../../.github/workflows/ci.yml)).

| Layer | What it proves | Where | Count (17 Nov) | Command |
|---|---|---|---|---|
| Unit: domain engine | R1–R6, stall checks, closure rules, fold and replay | `tests/test_engine.py`, `test_barriers_audit.py` | part of 177 | `pytest tests/test_engine.py` |
| Property / invariant | R1, R3, R4, R5 hold across 2,000 random command sequences; replay equals state | `tests/test_invariants.py` | 1 (2,000 × 14 steps) | `pytest tests/test_invariants.py` |
| API | Every route's rules, 404 scoping, validation, error codes | `tests/test_api.py`, `test_workflow.py`, `test_core_v2.py` | part of 177 | `pytest tests/test_api.py` |
| Security | Secure defaults, scoped keys, rate limit, headers, existence hiding, message policy, signed receipts, HTTPS-only webhooks, HL7 limits, agent cannot write | `test_core_v2.py`, `test_notifier.py`, `test_agent.py`, `test_connector.py` | 30+ | `pytest -k "policy or key or rate or scop or signed"` |
| Contract (service to service) | Satellites call the **real** case-core app over HTTP (TestClient as transport): outbox pull, ack, failure report, policy check, ingest | `test_notifier.py`, `test_agent.py`, `test_connector.py` | 54 | `pytest tests/test_notifier.py` |
| Architecture fitness | No service imports another's internals | `test_core_v2.py::test_service_boundaries_hold` | 1 | — |
| Migrations | Alembic head equals the models (no drift); an old database is upgraded, not hidden | `test_core_v2.py` | 3 | `python -m tasleem.migrate` |
| End-to-end (in-process) | One patient across every service: HL7 → rules → channels → AI draft → person sends → evidence → closure → audit | `test_e2e_services.py` | 1 | `pytest tests/test_e2e_services.py` |
| End-to-end (real stack) | The same story over the network on Docker + Postgres 16 + Redis, 7 containers | `tasleem/smoke.py --stack` | 32 checks | `python -m tasleem.smoke --stack` |
| Hard cases (labelled, written first) | Messy inputs, Arabic and English barrier and distress text, safety attacks | `tasleem/bench/hardcases.py` | 64 of 67 match | `python -m tasleem.bench.hardcases` |
| Benchmark | Three arms on the same synthetic cohort | `tasleem/bench` | 3 seeds | `python -m tasleem.bench` |
| Performance | Ingest, scheduler drain, read latencies at 5,000 patients | `tasleem/loadtest.py` | 1 run each on SQLite and Postgres | `python -m tasleem.loadtest` |
| LLM evaluation | An LLM classifier must match the keyword baseline or stay off | `tasleem/bench/llm_barriers.py` | run 17 Nov on Groq free tier (`openai/gpt-oss-120b`): LLM 14/15, keywords 13/15, 0 failures; too few cases to claim better ([LLM_BARRIER_EVAL.md](../evidence/LLM_BARRIER_EVAL.md)) | `python -m tasleem.bench.llm_barriers --provider groq` |
| Dependencies | No known vulnerabilities in the pinned set | `constraints.txt` | clean | `pip-audit -r constraints.txt --no-deps` |

## Edge cases and failure scenarios covered
- Duplicates, out-of-order evidence, unknown patients, naive timestamps, wrong JSON types, oversize bodies.
- Quiet hours, urgent bypass, read receipts, provider 5xx, unreachable patients, case-core restarting its ids.
- Concurrent writes, multiple schedulers, a stale version returning 409.
- Prompt injection and hallucination: fake LLMs that return unsafe drafts or invented numbers.
- HL7: MLLP framing, escapes, missing PID, unsupported types, preliminary results, resent messages.

## What the tests found (and the code now prevents)
| When | Found by | Problem | Fix |
|---|---|---|---|
| 16 Nov | Hard case H05 | A malformed code was silently read as "no code", so a positive result could hide | 422 with a field |
| 17 Nov | Night-time test run | Routine patient messages are held in quiet hours, which the tests assumed away | Tests pin a daytime clock; smoke uses demo time travel |
| 17 Nov | Docker smoke after a demo reset | The notifier keyed on case-core's numeric outbox id, which restarts; new messages were acked as duplicates | Natural message key; regression test |
| 17 Nov | Live Docker volume from v0.1 | Stamping an old database at the newest migration would hide a missing column | Baseline 0001 plus 0002; upgrade test |
| 17 Nov | Hard case H56 | "The pain is unbearable" was not flagged as distress | Pain-severity rule, checked on 7 held-out cases written before the rule |
| 17 Nov | pip-audit | starlette 0.41.3 advisories | Version floors, `constraints.txt`, CI audit |
