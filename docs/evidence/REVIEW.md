# Review checkpoint (TSL-122) and final engineering review

Backend checked on 17 Nov 2026. The **UI** column is filled on 19 Nov, when every path is clicked through the Lovable app. After that, features are frozen (Additional.md: no features after 19 Nov unless they fix a broken demo path).

## 1. Demo paths

| # | Path | Backend proof | Backend | UI (19 Nov) |
|---|---|---|---|---|
| 1 | Malaffi says COMPLETED, no report → flagged, owner named, EMR task | smoke "false-done", `test_workflow` | pass | |
| 2 | Report arrives → stall clears on evidence → close enabled | smoke, `test_workflow` | pass | |
| 3 | Closure blocked with the rule shown before the click | smoke "UI hint", `test_actions_mirror_the_engine` | pass | |
| 4 | Another clinic cannot see the case (404) | smoke, H32 | pass | |
| 5 | Missed colonoscopy → patient says why → navigator confirms → playbook task | `test_e2e_services` | pass | |
| 6 | AI draft → navigator sends → reaches Sahatna; the event records the person and the draft | smoke, `test_e2e_services` | pass | |
| 7 | Message that discloses a result is refused | smoke, `test_message_policy_*` | pass | |
| 8 | Distress → clinician the same minute (EMR task and SMS page) → closure blocked | smoke, `test_distress_pages_*` | pass | |
| 9 | Patient unreachable on Sahatna and SMS → navigator call task | smoke, `test_unreachable_*` | pass | |
| 10 | HL7 from the lab opens a case; a resend does not duplicate | smoke, `test_positive_fit_over_hl7_*` | pass | |
| 11 | Raised blood pressure on a pathway added by configuration | smoke | pass | |
| 12 | Teach-back wrong answer → barrier | `test_prep_teach_back_*` | pass | |
| 13 | Programme view: funnel, false done, 0 cases without an owner; filters | smoke, `test_metrics_filter_*` | pass | |
| 14 | Audit chain verifies on every touched case | smoke | pass | |
| 15 | Reset demo restores the seeded state, and delivery still works afterwards | `test_new_messages_after_a_core_reset_*`, smoke after reset | pass | |

## 2. Final engineering review (Phase 16)

| Question | Answer | Where |
|---|---|---|
| Requirements satisfied? | All backend backlog items except deploy (TSL-120, on hold by request) and the submission files (drafted) | [BACKLOG.md](../product/BACKLOG.md) |
| Safety rules R1–R6 intact? | Yes. Enforced in one pure engine; invariant test over 2,000 random sequences; the AI has no write path | `test_invariants`, `test_agent_cannot_write_to_cases` |
| Architecture scalable? | Stateless services. Index-backed reads. Scheduler and notifier are safe with several replicas. About 1,000× headroom over expected load on one replica | [SCALE_POSTGRES.md](SCALE_POSTGRES.md), [ADR-001](../architecture/ADR-001-service-boundaries.md) |
| Security? | 16 findings, 15 fixed with tests, 1 accepted for demo only; dependencies audited clean | [SECURITY_AUDIT.md](../engineering/SECURITY_AUDIT.md) |
| Performance? | The worklist slowest-5% latency is 220 ms under concurrent ingest on Postgres in Docker. Acceptable for the pilot; the first thing to tune (EXPLAIN on the worklist index) if usage grows | [SCALE_POSTGRES.md](SCALE_POSTGRES.md) |
| Maintainable? | Service boundaries checked by a test. Shared library instead of copies. Ruff clean. Each module states its purpose | `test_service_boundaries_hold` |
| APIs consistent? | One error shape `{error: {code, message, details}}`; versioned under `/v1`; idempotency keys on every cross-service write | [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) §0.4, §4 |
| Database efficient? | Projections and indexes for every read path; migrations with a drift test; a database per service | ARCHITECTURE §0.3, §5 |
| Deployment-ready? | Container stack and CI ready; cloud deploy not done (on hold); OIDC not wired | [OPERATIONS.md](../engineering/OPERATIONS.md) |
| UI accessible? | Not built here. The Lovable brief sets WCAG AA, RTL, 375 px and keyboard rules | [LOVABLE_BRIEF.md](../lovable/LOVABLE_BRIEF.md) |
| Documentation complete? | README, setup, architecture, ADR, API, operations, security, failure modes, testing, contribution, journeys | [README.md](../../README.md) |

## 3. Code review notes (Phase 9), resolved before this checkpoint
- **Duplicated rate limiter:** moved to `tasleem_common.ratelimit`, now shared by case-core and the agent.
- **Duplicated message policy:** the agent calls case-core's `/v1/policy/patient-message-check` rather than keeping a copy; the engine checks again on send.
- **Delivery deduplication on a counter** that can restart: replaced by a natural key.
- **Import-time app construction** broke secure defaults: the app is now built lazily (`__getattr__`), so `uvicorn module:app` still works.
- **Known debt:** the notifier and agent create their small schemas with `create_all` (no Alembic yet); `views.worklist_item` revalidates the full state JSON per row; there is no OpenTelemetry tracing yet.
