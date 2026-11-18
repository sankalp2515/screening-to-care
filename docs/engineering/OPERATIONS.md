# Operations: deploy, configure, observe, recover

**Status:** the full stack runs locally in Docker and passes 32 of 32 end-to-end checks. Nothing is deployed to a cloud yet. Everything below is the production design. Items marked *built* exist in the code.

## 1. Environments
| Environment | Purpose | Data | Demo mode |
|---|---|---|---|
| local | Development, tests | SQLite in memory or Docker Postgres | on |
| demo | Reviewers and the web app | Synthetic seed, reset on demand | on (guest personas) |
| pilot | One provider network | Real data under a DoH agreement | **off**: OIDC, keys and migrations required |

Every service refuses to start in an unsafe state outside demo mode (*built*):
- **case-core:** wildcard CORS, no integration keys, or SQLite;
- **notifier:** no operations key;
- **connector:** no inbound key.

## 2. Deployment target (UAE data residency)
Hosting: Azure UAE North (or any UAE-hosted Kubernetes). To avoid platform lock-in, the design needs only containers, Postgres and Redis.

| Component | Production form | Scaling |
|---|---|---|
| case-core API | Container App or Deployment, ≥ 2 replicas behind the API gateway (WAF, OIDC validation, distributed rate limit) | Horizontal on CPU and requests; stateless |
| scheduler | 1–3 replicas, or a CronJob running `--once` every 5 minutes | `SKIP LOCKED` makes replicas safe (*built*) |
| migrations | A release job before new API replicas start | One-shot; idempotent (*built*) |
| notifier | 1–2 replicas, poll every 15 s | Unique message key makes replicas safe (*built*) |
| agent | 1+ replicas; scale to zero allowed | LLM is optional; templates when it is off (*built*) |
| HL7 connector | 2 replicas behind the interface engine (MLLP to HTTPS) | Stateless (*built*) |
| PostgreSQL | Azure Database for PostgreSQL Flexible Server: separate databases `tasleem`, `notifier`, `agent`, each with its own role. Zone-redundant HA, read replica for the programme view | Vertical first |
| Redis | Azure Cache for Redis (cache only; losing it is safe) | — |
| Secrets | Key Vault into env vars: integration keys, ops key, webhook secret, the LLM key (`ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `NVIDIA_API_KEY` or `AGENT_LLM_API_KEY`) | Rotate keys by adding the new key, then removing the old |

## 3. Configuration (environment variables)
All settings, with defaults, are in [backend/.env.example](../../backend/.env.example). Each service reads its own prefix: `TASLEEM_`, `NOTIFIER_`, `AGENT_`, `CONNECTOR_`. The ones you must set for a pilot:
- `TASLEEM_INTEGRATION_KEYS`, `TASLEEM_CORS_ORIGINS`, `TASLEEM_DATABASE_URL`, `TASLEEM_AUTO_CREATE_SCHEMA=false`.
- `NOTIFIER_CORE_INTEGRATION_KEY`, `NOTIFIER_OPS_KEY`, `NOTIFIER_PROVIDER=webhook`, `NOTIFIER_WEBHOOKS`, `NOTIFIER_WEBHOOK_SECRET`.
- `CONNECTOR_CORE_INTEGRATION_KEY`, `CONNECTOR_INBOUND_KEY`.
- `AGENT_LLM_PROVIDER` (`offline` until the LLM evaluation passes): `offline`, `claude`, `groq`, `gemini`, `nvidia`, `openrouter` or `openai_compat` (with `AGENT_LLM_BASE_URL`). Keys are read from the shell, else from `backend/.env`; Docker passes `backend/.env` to the agent container only. `AGENT_LLM_MODEL` empty means the provider's default; check the provider console, as model ids change.
- Free tiers are for the synthetic demo and the evaluation only. Some free tiers (for example Google AI Studio's) may use what is sent to improve their products, so never point a free tier at real patient data. A production deployment needs a paid, contracted model host in a UAE region.
- Run the evaluation: `python -m tasleem.bench.llm_barriers --provider groq` (paced at 2.5 s per call; writes `docs/evidence/LLM_BARRIER_EVAL.md`). First run `--list-models` (free) to pick a current model id with `--model`; the run stops at the first 400/401/403/404/422 and writes nothing.

## 4. Health, metrics, logs, alerts
| Signal | Source | Alert when |
|---|---|---|
| Liveness | `/healthz` on every service (no DB call) (*built*) | Restart the container |
| Readiness | `/readyz` on core, notifier and agent (DB `SELECT 1`) (*built*) | Remove from the load balancer |
| Request id | `x-request-id` on every response, propagated between services (*built*) | Used to trace one request across logs |
| Outbox backlog | `GET /v1/integration/outbox?status=pending` count | > 500 pending for 10 minutes (notifier down) |
| Delivery health | Notifier `exhausted` and `sending` counts (`GET /v1/notifications`) | Exhausted staff alerts > 0; `sending` older than 1 h |
| Safety invariants | `GET /v1/program/metrics`: `open_cases_without_owner` | ≠ 0 (pages the on-call engineer and the programme lead) |
| Audit integrity | Nightly job verifies a sample of chains | Any broken chain |
| Scheduler | Log line `drain {...}` every interval | No drain for 15 minutes |
| Rate limiting | 429 count per caller | A spike (abuse or a broken client) |

Logs are structured to stdout: request ids and counts, never payloads or names. The next step is OpenTelemetry traces across the five services; not built.

## 5. Backups and disaster recovery
- **Postgres:** point-in-time restore, 7–35 days, in a paired UAE region. **RPO** ≤ 5 minutes, **RTO** ≤ 1 hour (managed-service targets; not yet exercised).
- **Rebuilding derived data:** the case-core event log is the source of truth. Projections, assignments and the cache are rebuilt from events, and the notifier database holds only derived delivery state. After a restore, the notifier re-pulls pending outbox messages, and the natural message key prevents double sends (*built*, tested).
- **Restore drill:** restore to a staging database, run `python -m tasleem.migrate`, then `python -m tasleem.smoke --stack`.

## 6. Release and rollback
1. CI must be green: lint, tests, audit, hard cases, benchmark, migrations on Postgres, stack smoke.
2. Run the migration job. Migrations are additive and backward-compatible for one release (expand, then contract). For example, 0002 adds a column with a default, so the old code keeps working.
3. Roll out the API, then the workers and satellites, as rolling or blue-green revisions.
4. **Rollback:** route traffic back to the previous revision. Leave the schema in place, because old code ignores new columns. Use `alembic downgrade` only for a migration that was never released.

## 7. Troubleshooting
| Symptom | Likely cause | Check |
|---|---|---|
| API exits at start with "Unsafe production configuration" | Demo mode is off and keys, CORS or the database URL are missing | The message lists exactly what to set |
| 401 `INTEGRATION_KEY` / 403 `INTEGRATION_SCOPE` | Wrong key, or the right key on the wrong endpoint | The connector key works only on ingest; the notifier key only on the outbox |
| Patient messages "stuck" at night | Quiet hours, 21:00–08:00 Gulf time | `next_at` in `GET notifier /v1/notifications` |
| Notifier delivers nothing | Core URL or key is wrong | Notifier logs; `GET core /v1/integration/outbox` with the notifier key |
| HL7 sender gets `AE` with 503 | case-core is down or restarting | The interface engine retries; the resend is idempotent |
| Docker on Windows: "all predefined address pools have been fully subnetted" | Too many Docker networks | Add an override file that sets `networks.default.ipam.config: [{subnet: 10.231.77.0/24}]` and pass it with `-f` |
| Git Bash mangles `docker exec` paths | MSYS path conversion | Prefix with `MSYS_NO_PATHCONV=1` |
