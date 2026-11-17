# Failure modes and recovery (production-incident view)

Each row is a failure we reasoned through, how the system behaves, and the test that proves it. "Never guess": where we have not tested something, the table says so.

## Cross-service hand-over

| Failure | What happens | Why it is safe | Proof |
|---|---|---|---|
| Notifier crashes after storing messages, before acking case-core | The same messages are pulled again | Stored by outbox id, so the duplicate is ignored | `test_handover_is_at_least_once_and_never_duplicates` |
| Notifier crashes before storing | Case-core still has them as `pending` | Nothing was acked, so nothing is lost | Same design: the ack follows the commit |
| Two notifier replicas pull the same page | Both try to insert | The primary key on outbox id makes one of them roll back. Provider sends carry the idempotency key `outbox:step:channel` | Unique constraints; tested for one replica, reasoned for two |
| SMS or Sahatna gateway down (5xx or timeout) | Up to 5 retries with exponential backoff on the same step, then the next channel | Clinical writes are untouched; delivery has its own clock | `test_webhook_provider_..._retries_on_5xx`, state machine |
| A patient is unreachable on every channel | `exhausted`, then case-core opens a navigator call task | The patient reaches a person, not another message. Retried until case-core accepts; never duplicated | `test_unreachable_patient_comes_back_as_a_navigator_task_once` |
| Case-core is down when the connector receives HL7 | ACK `AE` with HTTP 503, after the client's bounded retries | The sending interface engine queues and resends. The resend is idempotent on MSH-10 | `test_core_outage_returns_ae_503_so_the_sender_retries`, `test_positive_fit_over_hl7_opens_a_case_once` |
| A lab resends the same HL7 message | AA again; one case and one event | Resource ids are derived from MSH-10 plus the OBX set id | Same test |
| Case-core is down when the agent is asked | 503 `CORE_UNAVAILABLE` | Nothing is drafted from stale data | `core_get` in the agent |
| The LLM is down, slow, refuses, or returns invalid or unsafe text | Template or extractive output, with the rejection recorded in `rejected_llm_output` | The agent never blocks care and never shows unvalidated text | `test_hallucinated_brief...`, `test_unsafe_llm_draft...` |

## Inside case-core

| Failure | What happens | Proof |
|---|---|---|
| Two people write the same case at once | Optimistic version check: one commits, the other retries up to 3 times, then gets 409 | `test_robustness`, smoke "8 concurrent writes" on Postgres |
| Two scheduler replicas | `SKIP LOCKED` on due cases; any overlap is a counted conflict, never a double escalation | Scale run: 4,395 cases drained, 0 conflicts ([SCALE_POSTGRES.md](../evidence/SCALE_POSTGRES.md)) |
| Evidence arrives before its trigger | Stored, then replayed when the case opens | Hard case H15 |
| Unknown patient | Stored as unmatched, never dropped | Hard case H09, `test_unknown_patient_is_accepted_and_held_for_review` |
| Audit tampering | `GET /cases/{id}/audit` names the first broken link | `test_barriers_audit` |
| A database built by an older version | `python -m tasleem.migrate` stamps the v0.1 baseline, then applies newer migrations (found and fixed 17 Nov: stamping at head would have hidden a missing column) | `test_migrate_upgrades_a_v01_database_missing_new_columns`; verified on the live Docker volume (`alembic_version` = 0002) |
| A patient writes in distress at night | Distress alerts are urgent and skip quiet hours: EMR task and SMS page at once | `test_distress_pages_the_clinician_on_every_urgent_channel` |
| A routine patient message at 02:00 | Held until 08:00 Gulf time | `test_quiet_hours_hold_routine_patient_messages_only` (also surfaced by a night-time test run) |

## Data-corruption risks reviewed
- **Assignments and outbox drifting from case state:** they are written in the same transaction as the events. A rollback removes all of them.
- **A delivery alert left open after a human already called:** any `CONTACT_ATTEMPTED` resolves open delivery alerts (`test_patient_unreached...` checks it clears).
- **Clock skew between services:** timers that matter clinically (stalls, escalations) run only in case-core, on one clock. The notifier's clock only affects message timing.

## Not tested (stated plainly)
- Network partitions between replicas of the same service.
- Postgres failover mid-transaction (managed-service behaviour; covered by retries but not exercised).
- Sustained gateway outages longer than the retry window. Messages stay `sending`, and an operations alert on the backlog is in [OPERATIONS.md](OPERATIONS.md).
