# Backlog — Tasleem MVP

Priority: **P0** = required for the 20 Nov submission; **P1** = strongly improves scoring; **P2** = after submission.
Estimate: S ≤ 2 h, M ≤ 4 h, L ≤ 1 day. Status: `todo`, `doing`, `done`.
Each item links to PRD requirements. Done means its acceptance criteria are covered by a passing test or a recorded demo check.
Rules for agents: [AGENTS.md](../../AGENTS.md) and [Additional.md](../../Additional.md).

## Milestones
| Milestone | Date (2026) | Items |
|---|---|---|
| M1 Core engine and API | 16 Nov | E1, E2, E3, E4, E5 core |
| M2 Benchmark and clinician UI | 17 Nov | E6, E7 |
| M3 Patient, consult, program, deploy | 18 Nov | E8, E9, E10, E11 |
| M4 Review checkpoint and evidence (feature freeze) | 19 Nov | E12 |
| M5 Submission | 20 Nov | E13 |

---

## E1 Foundations
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-001 | Repository layout, AGENTS.md, Additional.md, docs | — | P0 | S | done | Files exist; AGENTS.md points to Additional.md |
| TSL-002 | Backend project (FastAPI, SQLAlchemy, settings from env) | NFR | P0 | S | done | `uvicorn tasleem.api.app:app` serves `/healthz` |
| TSL-003 | Docker image and docker-compose (API, Postgres, Redis) | NFR | P0 | S | done | Verified 16 Nov: `docker compose up` + `python -m tasleem.smoke` 20/20 against Postgres 16 |
| TSL-004 | CI workflow: lint, audit, tests, benchmarks, Postgres migrations, Docker stack smoke | NFR | P1 | S | done | `.github/workflows/ci.yml` written and YAML-validated 17 Nov. Not yet run on GitHub: the folder is not a repository yet |

## E2 Domain engine (safety core)
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-010 | Pathway config loader (YAML, versioned) for FIT+ and HbA1c | 4 | P0 | M | done | Both pathways load and validate; invalid config fails fast |
| TSL-011 | Case opening with default owner = family physician; coordinator fallback with warning | FR-2 | P0 | S | done | Test: opens with FP; without FP opens with coordinator and warning |
| TSL-012 | Two-step handoff: offer, accept, reject with reason | FR-3 | P0 | M | done | Tests: owner unchanged until accept; only the target can accept |
| TSL-013 | Verified stages from evidence; admin status never advances a stage | FR-4.3 | P0 | M | done | Test: REF "completed" leaves verified stage unchanged |
| TSL-014 | Stall checks (8 types) on events and on tick | FR-4 | P0 | L | done | One test per stall type; stalls clear on resolving evidence |
| TSL-015 | Escalation ladder to named humans; re-escalation | FR-5 | P0 | M | done | Test: missed deadline → ESCALATED to a named id; next level after N days |
| TSL-016 | Closure rules for 6 outcomes; AI/system/patient cannot close | FR-6 | P0 | M | done | Tests for each outcome's requirement and each forbidden actor |
| TSL-017 | Barrier reporting, AI suggestion, human confirmation, playbook assignment | FR-7 | P0 | M | done | Test: free text → suggestion event (actor ai) → confirm → assignee role set |
| TSL-018 | Distress and red-flag detection escalates to clinician; blocks closure | FR-5.3, FR-6.1 | P0 | S | done | Test: "blood" or "terrified" reply escalates to a clinician; close blocked until a clinician resolves |
| TSL-019 | Randomized invariant test: R1, R3, R4, R5 hold across 2,000 random command sequences | Release 2 | P0 | M | done | 2,000 × 14 steps with a fixed seed; replay equals state |
| TSL-020 | Consult bridge events and CONSULT_UNANSWERED stall | FR-9 | P1 | S | done | Test: unanswered past deadline flags stall |

## E3 Audit
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-030 | Hash-chained per-case events | FR-12.1 | P0 | S | done | Each event stores prev_hash and hash |
| TSL-031 | Verify endpoint reports first broken link | FR-12.2 | P0 | S | done | Test: tampered payload detected at the right sequence |

## E4 Ingest
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-040 | FHIR R4 adapter (Observation, DiagnosticReport, ServiceRequest, Task, Appointment, Procedure, Communication, Encounter) | FR-1.1 | P0 | L | done | Tests map each resource to the right signal |
| TSL-041 | Malaffi REF status adapter | FR-1.2 | P0 | S | done | Test: statuses map to admin status |
| TSL-042 | Idempotency by (source, message id) | FR-1.3 | P0 | S | done | Test: duplicate returns same result, no new events |
| TSL-043 | Unmatched resources stored and reported | FR-1.4 | P0 | S | done | Test: unknown patient returns `unmatched` and is stored |
| TSL-044 | Field-level validation errors | FR-1.5 | P0 | S | done | Test: missing patient → 422 with field |
| TSL-045 | Queue-based ingest (Azure Service Bus) for production | NFR | P2 | M | done (design) | ADR-001: outbox plus pull and ack now; a broker is the documented next step, with the same consumers. The HL7 connector already retries and is idempotent |

## E5 API and persistence
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-050 | Database schema, repositories, optimistic locking | NFR | P0 | M | done | Concurrent write on stale version → 409 |
| TSL-051 | Worklist API with filters (owner, status, stalled, pathway) | FR-11.2 | P0 | S | done | Test: filters return expected cases |
| TSL-052 | Case detail API: reported vs verified progress, stalls, barriers, timeline | FR-4.3 | P0 | S | done | Test: response includes both progress fields |
| TSL-053 | Command APIs: handoff, barrier, confirm, contact attempt, consult, close | FR-3,6,7,9 | P0 | M | done | Tests: rule violations → 409 with rule id |
| TSL-054 | Scheduler tick endpoint and worker loop using `next_check_at` | FR-4, FR-5 | P0 | M | done | Test: tick flags overdue cases only |
| TSL-055 | Program metrics API with cache | FR-11.1 | P0 | S | done | Test: metrics correct; cache invalidated on write |
| TSL-056 | Referral options by insurance network | FR-10 | P1 | S | done | Test: only in-network providers returned |
| TSL-057 | Demo identity (guest) auth; OIDC design for production | NFR | P0 | S | done | Header identity in demo mode; disabled when `TASLEEM_DEMO_MODE=false` |
| TSL-058 | Seed synthetic directory and scenario cases covering every stall and outcome | Release 4 | P0 | M | done | `python -m tasleem.seed` loads data; demo cases visible |
| TSL-059 | Alembic migrations | NFR | P1 | S | done | `python -m tasleem.migrate`: baseline 0001 plus 0002; drift test; a v0.1 database is upgraded (tested; live Docker volume at 0002) |

## E6 Benchmark harness (headline evidence)
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-060 | Synthetic cohort generator with failure injection (seeded, Synthea-compatible IDs) | FR-13.1 | P0 | L | done | Same seed → same cohort; injection rates configurable |
| TSL-061 | Arm A: reminders only; Arm B: Malaffi status only; Arm C: Tasleem | FR-13.2 | P0 | L | done | Same cohort through all three arms |
| TSL-062 | Metrics and per-case CSV; markdown report | FR-13.3 | P0 | M | done | `python -m tasleem.bench` writes `docs/evidence/benchmark.md` |
| TSL-063 | Hard-case set: missing fields, wrong codes, out-of-order, duplicates, Arabic and English distress replies | Additional.md | P0 | M | done | ≥ 40 labelled cases in `docs/evidence/TEST_CASES.md` with results |
| TSL-064 | Scale and robustness: ingest race retry, scheduler drain, bounded-staleness metrics, paging, request limits, readiness; 5,000-patient load run | NFR | P0 | M | done | `python -m tasleem.loadtest` writes `docs/evidence/SCALE.md`; robustness tests R1–R7 pass |
| TSL-065 | Personal inbox `GET /v1/me/work` from an indexed `case_assignments` projection | FR-11.2 | P0 | M | done | Owner, escalation target, handoff receiver, consultee and barrier assignee each see the case under the right reason (W1) |
| TSL-066 | Org-scoped visibility (clinic sees own patients; pulled-in people see that case; coordinator sees all) | NFR privacy | P0 | M | done | Other clinic gets 404 on read and command (W2, H32–H33) |
| TSL-067 | Action hints and deterministic next step in case detail (dry-run of the real engine) | Additional.md | P0 | S | done | Blocked actions carry the rule code before the click (W3–W4) |
| TSL-068 | Transactional outbox: FHIR Task to EMR inbox, FHIR Communication to Sahatna; pull + ack API | Integration | P0 | M | done | Distress → urgent task to named clinician; patient messages never carry values (W5–W6) |
| TSL-069 | Live demo scenarios (Malaffi feed simulator) through the real ingest path | Release 4 | P0 | S | done | false-done, report-arrives, new FIT, missed, distress, blood pressure (W7–W8) |
| TSL-102 | Pathway C: raised screening blood pressure (configuration only) | Scale | P1 | S | done | `pathways/hypertension.yaml`; seeded case; scenario |
| TSL-123 | End-to-end smoke test against a deployment (`python -m tasleem.smoke`) | Release 4 | P0 | S | done | 20/20 on Docker + Postgres (W9) |
| TSL-075 | Lovable UI brief, OpenAPI export and real response fixtures | Release 4 | P0 | S | done | `docs/lovable/` |

## E7 Clinician web app (single page, desktop and tablet)
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-070 | Frontend scaffold (React + Vite + TypeScript), API client, guest login screen | NFR | P0 | M | todo | "Continue as Guest" picks a demo persona |
| TSL-071 | Worklist: stalled first, reason chips, owner, days since progress | FR-11.2 | P0 | M | todo | Seeded stalled cases appear at top |
| TSL-072 | Case view: reported vs verified progress bars, stalls, barriers, timeline with Fact / Computed / AI labels | FR-4.3 | P0 | L | todo | Labels visible on every timeline item |
| TSL-073 | Actions: handoff, confirm barrier, log contact, close with outcome form | FR-3,6,7 | P0 | M | todo | Blocked closure shows the rule and what's missing |
| TSL-074 | Audit panel with "verify chain" | FR-12 | P1 | S | todo | Shows OK or the broken link |

## E8 Patient companion (mobile web, Sahatna-embeddable)
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-080 | Patient API: plain-language status without result values | FR-8.1 | P0 | S | done | Test: response contains no observation values |
| TSL-081 | Mobile screens: status, next step, "I can't make it", call me back | FR-8.2 | P0 | M | todo | Works at 375 px width |
| TSL-082 | Arabic RTL and English | FR-8.3 | P0 | M | todo | Language toggle; RTL layout correct |
| TSL-083 | Bowel-prep teach-back (3 questions) creating PREP_UNCLEAR | FR-8.4 | P1 | S | API done; screen todo (Lovable) | `GET/POST /v1/me/cases/{id}/prep-check`; a wrong answer opens a barrier; answers never sent to the client (`test_prep_teach_back_*`) |
| TSL-084 | Consent screen recorded as event | NFR | P0 | S | API done; screen todo (Lovable) | `POST /v1/me/cases/{id}/consent` records CONSENT_RECORDED (`test_barrier_flow_and_consent`) |

## E9 Consult bridge UI
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-090 | Specialist inbox: accept or reject referral with reason; answer e-consult | FR-3, FR-9 | P1 | M | API done; screen todo (Lovable) | E-consult arrives as an EMR task and is answered by API; a referral rejection with its reason arrives over HL7 REF and flags REFERRAL_REJECTED (`test_ref_status_is_admin_only_and_rejection_flags_a_stall`) |

## E10 Program view
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-100 | Funnel, stalls by reason, barriers, outcomes, false-done count | FR-11.1 | P0 | M | todo | Numbers match metrics API |
| TSL-101 | Filters by provider and language | FR-11.1 | P1 | S | API done; screen todo (Lovable) | `GET /v1/program/metrics?org=&language=` (`test_metrics_filter_by_provider_and_language`) |

## E11 AI helpers (optional, behind flag)
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-110 | LLM barrier classifier adapter (Claude or any OpenAI-compatible host: Groq, Gemini, NVIDIA, OpenRouter) | §7 | P1 | M | done; evaluated | `tasleem_agent/providers.py`, `classify.py`. 17 Nov on Groq free tier (`openai/gpt-oss-120b`): LLM 14/15 vs keywords 13/15, so the PRD rule allows switching it on as a suggestion a navigator confirms. Sample of 15 is too small to claim better; grow the labelled set. Demo default stays `offline` |
| TSL-111 | Plain-language message drafting and translation, human-approved | §7 | P2 | M | done | Agent drafts from the approved library (an LLM is optional); case-core policy check; a person sends with `ai_draft_id` (`test_outreach_draft_then_a_person_sends_it`) |

## E12 Deploy and review checkpoint
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-120 | Deploy API, DB and frontend (Azure Container Apps + Azure Database for PostgreSQL, or equivalent) | Release 4 | P0 | M | on hold (by request, 17 Nov) | Design in `docs/engineering/OPERATIONS.md`; the local stack passes 32 of 32 checks |
| TSL-121 | Reset-demo endpoint to restore seeded state | Release 4 | P0 | S | done | `POST /v1/admin/reset-demo` reseeds (demo mode only) |
| TSL-122 | Review checkpoint: run every demo path, fix, freeze features | Additional.md | P0 | M | backend done; UI pass 19 Nov | `docs/evidence/REVIEW.md` (15 paths pass on the backend) |

## E14 Services, channels and AI agent (17 Nov)
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-140 | Service architecture: safety core plus satellites; database per service; boundaries tested | NFR | P0 | M | done | ADR-001; `test_service_boundaries_hold`; 7-container compose stack |
| TSL-141 | Notifier: a channel per kind of person, quiet hours, fallback, digest, signed receipts, at-least-once hand-over | Challenge "patient communication" | P0 | L | done | `tests/test_notifier.py` (14); smoke "unreachable → navigator task" |
| TSL-142 | Delivery failure loop: patient unreached on every channel → navigator call task | FR-8 | P0 | S | done | `DELIVERY_FAILED` event; `test_patient_unreached_by_any_channel_becomes_navigator_task` |
| TSL-143 | AI agent service (suggest-only): sense → decide → act → hand off; cited brief; policy-checked drafts; no write path | §7 | P0 | L | done | `tests/test_agent.py` (35) |
| TSL-144 | Patient-message policy (IFHAS 4.9.2.3) and staff send endpoint | FR-8.1 | P0 | S | done | `test_message_policy_*`, `test_message_that_discloses_a_result_is_refused` |
| TSL-145 | HL7 v2 connector: ORU, REF (Circular 210), SIU to FHIR / status; ACK codes; idempotent | FR-1 | P0 | M | done | `tests/test_connector.py` (13) |
| TSL-146 | Standalone scheduler worker | FR-4 | P1 | S | done | `python -m tasleem.workers.scheduler`; compose service |
| TSL-147 | Security hardening: secure defaults, scoped keys, rate limits, headers, existence hiding | NFR | P0 | M | done | `docs/engineering/SECURITY_AUDIT.md` (S1–S16) |
| TSL-148 | Dependency audit, pinned constraints, CI audit | NFR | P0 | S | done | `pip-audit -r constraints.txt`: no known vulnerabilities |
| TSL-149 | Usage metering (active cases per provider per month) for SaaS pricing | Release 5 | P1 | S | done | `GET /v1/program/usage` (`test_usage_metering_is_coordinator_only`) |
| TSL-150 | Distress: severe-pain rule, checked on held-out cases | FR-5.3 | P0 | S | done | Hard cases 64 of 67 (was 56 of 60) |
| TSL-151 | End-to-end test across every service, in process and on Docker | Release 4 | P0 | M | done | `test_e2e_services.py`; `python -m tasleem.smoke --stack` 32 of 32 |

## E13 Submission
| ID | Story | PRD | Pri | Est | Status | Acceptance criteria |
|---|---|---|---|---|---|---|
| TSL-130 | 16-slide deck on mandatory template, PDF ≤ 5 MB | Release 5 | P0 | L | todo | Every heading answered |
| TSL-131 | Demo video ≤ 2:50 following the Noura story | Release 5 | P0 | M | script drafted | `docs/submission/VIDEO_SCRIPT.md`; recording needs the UI |
| TSL-132 | Form text: summary (2,000 chars), built-during-challenge (1,500 chars), data sources, IP, conflicts | Release 5 | P0 | S | drafted | `docs/submission/FORM_TEXT.md`; `count.py` checks the limits (1,966 and 982) |
