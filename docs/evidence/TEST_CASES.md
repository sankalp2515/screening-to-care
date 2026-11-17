# Test cases and results

Every case below is an automated test in `backend/tests`. Run: `cd backend && python -m pytest -q`.
Last run: **17 Nov 2026 — 198 passed, 0 failed** (Python 3.12, SQLite in memory; also passes on the pinned production versions in `constraints.txt`). Full stack on Docker + PostgreSQL 16 + Redis, 7 containers: **32 of 32 checks passed** (`python -m tasleem.smoke --stack`). Hard cases: **64 of 67** ([HARD_CASES.md](HARD_CASES.md)).

What this proves: the software enforces its safety rules and detects the defined failures on synthetic data.
What it does not prove: any effect on real patients' follow-up rates. That needs a clinical pilot.

The three-arm benchmark (reminders only vs Malaffi status only vs Tasleem) is in [benchmark.md](benchmark.md); the 67 labelled hard cases are in [HARD_CASES.md](HARD_CASES.md).

## Safety rules (R1–R6)

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| S1 | Open case without owner | trigger, owner "" | refused `R1_OWNER_REQUIRED` | pass | engine.open_case |
| S2 | Patient with no family physician | FIT+ for p-john | owner = program coordinator, warning shown | pass | directory.default_owner |
| S3 | Handoff before acceptance | offer to dr-fp2 | owner unchanged until accept | pass | engine handoff |
| S4 | Wrong person accepts handoff | navigator accepts | refused `R2_NOT_HANDOFF_TARGET` | pass | engine.accept_handoff |
| S5 | Second offer while pending | offer twice | refused `R2_HANDOFF_PENDING` | pass | engine.offer_handoff |
| S6 | Non-owner offers handoff | navigator offers | refused `R2_NOT_OWNER`; coordinator allowed | pass | engine.offer_handoff |
| S7 | Close as completed without report | booked only | refused, lists missing stages | pass | engine.close_case |
| S8 | Navigator signs completion | complete case | refused `R3_SIGNATURE_REQUIRED` | pass | engine.close_case |
| S9–S13 | Outcome requirements | elsewhere / refusal / plan change / unreachable without evidence, reason or attempts | refused with the matching R3 code | pass | engine.close_case |
| S14 | Unreachable after 3 attempts + escalation | contact log ×3 | closes as UNREACHABLE | pass | engine.close_case |
| S15–S18 | AI, system, integration, patient try to close | complete case | refused `R5_HUMAN_REQUIRED` / `FORBIDDEN_ROLE` | pass | engine.close_case |
| S19 | AI confirms a barrier | AI actor | refused | pass | engine.confirm_barrier |
| S20 | Commands on a closed case | contact log | refused `CASE_CLOSED`; no further deadlines | pass | engine |
| S21 | Missed deadline escalates to a named person, then up the ladder, capped | no invite for 30 days | level 1 owner → 2 clinic lead → 3 coordinator; no level 4 | pass | engine.reconcile_stalls |
| S22 | Tampered audit payload | edit event 2 | verification fails at seq 2 | pass | audit.verify |
| S23 | Deleted / reordered audit events | drop or swap events | verification fails | pass | audit.verify |
| S24 | Tamper in the database | SQL update of event 3 | API audit reports broken at seq 3 | pass | API audit |
| S25 | Randomized sequences | 2,000 sequences × 14 random commands by random actors (incl. AI, system, wrong people) | R1, R3, R4, R5 hold after every accepted step; replay equals state | pass | test_invariants |

## Stall detection (apparent progress vs real progress)

| # | Case | Expected | Actual |
|---|---|---|---|
| D1 | Malaffi REF says COMPLETED, no report | no flag within 3-day grace; `CLOSED_WITHOUT_EVIDENCE` after; clears when report arrives | pass |
| D2 | Referral status never advances a verified stage | stages empty after admin COMPLETED | pass |
| D3 | No-show | `BOOKED_NOT_ATTENDED`; clears on rebooking | pass |
| D4 | Appointment time passed, no attendance record | flag only after 24 h grace | pass |
| D5 | Attended, no procedure for 21 days | `CONSULT_NO_PROCEDURE` | pass |
| D6 | Report received, outcome not communicated for 7 days | `REPORT_NOT_COMMUNICATED` | pass |
| D7 | Referral rejected by GI centre | `REFERRAL_REJECTED`; clears on a new referral | pass |
| D8 | Handoff unanswered 2 days | `HANDOFF_NOT_ACCEPTED` | pass |
| D9 | E-consult unanswered past deadline | `CONSULT_UNANSWERED` | pass |
| D10 | Next step overdue | `STEP_OVERDUE` on the expected stage | pass |
| D11 | Scheduler only touches due cases | tick in the future flags the on-track case once its appointment passes | pass |

## Patient messages, barriers and distress

| # | Input | Expected | Actual |
|---|---|---|---|
| B1–B11 | English and Arabic messages (fear, prep, escort, cost, work, interpreter, call back, done elsewhere) | correct barrier suggestion | pass (11/11) |
| B12 | "ok thanks" | no suggestion (abstain) | pass |
| B13–B18 | "I saw blood", "black stool", "terrified", "فيه نزيف", "شفت الدم", "can't cope" | distress flagged → clinician | pass (6/6) |
| B19–B21 | "Spain", "عدم" (contains دم), "bloodwork" | no false distress match | pass (3/3) |
| B22 | Distress when owner is a navigator | routed to the patient's family physician; closure blocked; navigator cannot clear it | pass |
| B23 | Patient reports on someone else's case | 403 | pass |
| B24 | Patient view | Arabic RTL; no codes, values or "positive" wording | pass |

Limits of this set: the barrier and distress lexicons were written by the team; the labelled hard-case benchmark with independent labels (≥ 40 cases, TSL-063) is still to do.

## Ingest

| # | Input | Expected | Actual |
|---|---|---|---|
| I1 | Same FHIR resource twice | second returns `duplicate: true`, no new events | pass |
| I2 | Unknown patient | stored, status `unmatched` | pass |
| I3 | Observation without subject | 422, field `subject` | pass |
| I4 | Unused resource type | stored, status `ignored` | pass |
| I5 | Stale version write | `ConcurrencyError` (409) | pass |

## Robustness and scale

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| R1 | Duplicate message races another worker | same FIT message, duplicate check blinded once | unique key trips, rollback, retry returns `duplicate: true`; event count unchanged; one inbound row | pass | ingest._process |
| R2 | Scheduler backlog | 12 overdue cases, batch size 4 | drained in ≥ 3 batches in one run; second run finds nothing | pass | scheduler.drain |
| R3 | Metrics under write load | write after a cached read, staleness 60 s / 0 s | stale result flagged within bound; exact recompute at 0 s | pass | MetricsService |
| R4 | Oversized request | 300 KB body, limit 200 KB | 413 `PAYLOAD_TOO_LARGE` | pass | app middleware |
| R5 | Worklist paging | pages of 3 | same ids, same order as one full page; no gaps or repeats | pass | GET /v1/cases |
| R6 | Liveness vs readiness | GET /healthz, /readyz | both OK; liveness never touches the DB | pass | routes |
| R8 | Evidence delivered before its trigger | invite arrives before the FIT it follows | replayed onto the new case; no false 'invite overdue' | pass (bug found by the benchmark, fixed) | ingest._replay_early_evidence |
| R7 | Scale run | 5,000 synthetic patients, 29,099 messages | no broken audit chains, every open case owned, flat latency | pass, see [SCALE.md](SCALE.md) (SQLite) and [SCALE_POSTGRES.md](SCALE_POSTGRES.md) (Postgres 16) | tasleem.loadtest |


## Real workflow: inbox, scoping, action hints, outbound messages, live scenarios

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| W1 | Personal inbox | `GET /v1/me/work` as dr-fatima, dr-salma | false-done case under "escalated" for its owner; handoff and distress listed for the receiver; patients get 403 | pass | routes.my_work, case_assignments |
| W2 | Org scoping | dr-fatima lists cases; reads/acts on a Samar clinic case | own clinic only; other clinic's case 404 (existence not revealed); handoff receiver can see the offered case; coordinator sees all | pass | CaseService.scope / require_visible |
| W3 | Action hints match the engine | case view for owner and navigator on a false-done and a ready case | blocked closure shows `R3_EVIDENCE_REQUIRED` before the click; navigator cannot close; "allowed" closure then succeeds | pass | domain/actions.py (dry-runs engine) |
| W4 | Next step is deterministic | distress, false done, missed appointment, ready to close | one fixed rule-based next step with a named person | pass | actions.next_step |
| W5 | Outbound notifications | distress on Sunita's case; all patient messages | urgent FHIR Task to the named clinician; Sahatna messages contain no LOINC codes, values or "POS" | pass | routing.outbox, transactional outbox |
| W6 | Outbox delivery contract | pull, ack 5, pull again | acknowledged messages never redelivered | pass | /v1/integration/outbox |
| W7 | Live false-done scenario | Malaffi COMPLETED 4 days ago, no report | `CLOSED_WITHOUT_EVIDENCE`, owner = family physician; report arrives → stall clears | pass | demo.false_done, report_arrives |
| W8 | Scenarios cover the loop | new FIT with no family physician; missed colonoscopy; distress; raised blood pressure | coordinator owns with warning; TIME_OR_WORK suggested but unconfirmed (R5); distress next step; hypertension pathway opens by config only | pass | demo.py, pathways/hypertension.yaml |
| W9 | Postgres end-to-end, concurrent writes | 8 parallel contact logs on one case | every 200 is counted, conflicts return 409, none lost; audit chains verify | pass | tasleem.smoke on Docker |
| H32–H33 | Hard cases: another clinic reads a case; outsider accepts a handoff | — | 404 NOT_FOUND | pass | see [HARD_CASES.md](HARD_CASES.md) |


## Services, channels and the AI agent (17 Nov, v0.2)

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| V1 | Channel per kind of person | policy for patient, physician (routine, urgent), navigator, coordinator, unknown role | Sahatna → SMS; EMR task; EMR + SMS page in parallel; worklist; e-mail digest; default route | pass | notifier policy |
| V2 | Quiet hours | routine patient message at 23:30 Gulf time; urgent; staff | held until 08:00; urgent and staff not held | pass | notifier policy |
| V3 | Fallback | push not opened in 24 h | SMS nudge, delivered, done; SMS body has no case content | pass | notifier state machine |
| V4 | Read receipt | push opened after 1 h | no SMS sent | pass | notifier receipts |
| V5 | Distress delivery | distress scenario | urgent EMR task + SMS page to the clinician; page has no symptom text | pass | notifier |
| V6 | Unreachable patient | no app, no phone | both channels fail → case-core DELIVERY_FAILED → navigator task "call the patient"; reported once | pass | notifier + case-core |
| V7 | At-least-once hand-over | ack lost, message re-pulled | stored once | pass | notifier pull |
| V8 | Case-core reset | demo reset restarts outbox ids | new messages still delivered (found on Docker; fixed) | pass | notifier message key |
| V9 | Webhook provider | 200 / 503 / no endpoint / http URL | delivered / retry / failed / refused; HMAC signature verifies | pass | notifier adapters |
| V10 | Receipts must be signed | unsigned, then signed receipt | 401, then 200 | pass | notifier API |
| V11 | Message policy | value "9.2", "162/95", "positive", "polyp", Arabic "إيجابي", "nothing to worry about", a link, empty | each refused with its code; logistics such as "21 Nov at 9:30" allowed | pass | domain/messaging.py |
| V12 | Staff send to patient | approved text with ai_draft_id; text with a result; patient; other clinic | 200, event actor = person, ai_assisted; 409 IFHAS_MESSAGE_POLICY; 403; 404 | pass | case-core |
| V13 | Agent sense → decide → act → hand off | false-done case | facts cite real audit events; next step copied from the rules; hand-off to the named person | pass | agent |
| V14 | Hallucinated brief | fake LLM cites event 9999 and invents "day 99, normal" | rejected; extractive brief used; rejection recorded | pass | agent validators |
| V15 | Unsafe LLM draft | "Your result is positive… nothing to worry about" | rejected; approved template used | pass | agent + policy |
| V16 | No draft when a person must act | open distress | no message drafted; reason given | pass | agent |
| V17 | Agent scoping | other clinic asks the agent; no identity; another clinic's draft | 404; 401; 404 | pass | agent |
| V18 | Every approved template | 12 templates × EN/AR | all pass the message policy | pass | agent templates |
| V19 | HL7 ORU positive FIT, sent twice | MSH-10 LAB-0001 twice | ACK AA both; one case; one CASE_OPENED | pass | connector |
| V20 | HL7 negative / preliminary | OBX-8 N; OBX-11 P | AA; no case | pass | connector |
| V21 | HL7 REF | RF1-1 A, then R with reason | admin status ACCEPTED but verified stage unchanged; rejection flags REFERRAL_REJECTED | pass | connector mapping |
| V22 | HL7 SIU | S12 booking, S26 no-show | appointment set; appointment_missed = noshow | pass | connector mapping |
| V23 | HL7 errors | garbage; ADT^A01; ORU without PID; case-core down | AR 422; AR; AE 422 naming PID-3; AE 503 "retry" | pass | connector |
| V24 | Teach-back | wrong "how will you get home"; all correct; other patient; HbA1c case | NO_ESCORT barrier; no barrier; 404; 404 | pass | case-core |
| V25 | Metrics filters, usage | org, language; month; non-coordinator; bad month | filtered totals add up; usage by provider; 403; 422 | pass | case-core |
| V26 | Scoped keys | no key, wrong key, notifier key on ingest, connector key on outbox | 401, 401, 403, 403 | pass | deps.integration |
| V27 | Secure defaults | default settings; demo off with unsafe config | demo off; refuses to start | pass | config, app |
| V28 | Rate limit and headers | 5 quick requests at 1/s burst 3 | 429 with Retry-After; per caller; probes exempt; no-store, nosniff | pass | api/security.py |
| V29 | Migrations | fresh; create_all database; v0.1 database missing a column | upgraded with no drift; stamped; column added | pass | tasleem.migrate |
| V30 | Service boundaries | import graph of all packages | no satellite imports case-core or another satellite | pass | architecture fitness test |
| V31 | Whole loop, all services | HL7 FIT → invite → referral → SIU booking → no-show → barrier → AI draft sent → rebook → HL7 report → close | every step as expected; audit verifies; AI draft recorded on the person's event | pass | `test_e2e_services.py` |
| V32 | Severe pain (held-out, written before the rule) | 5 severe-pain phrases EN/AR, 2 mild or anticipatory | 5 flagged, 2 not | pass | domain/barriers.py |
| V33 | Free-tier LLM host (Groq, Gemini, NVIDIA; fake transport) | good JSON; fenced JSON; off-vocabulary code; confidence 7; prose; content filter; 429 then OK; 429 forever; JSON mode unsupported; 401/403/404/500; network down | valid replies accepted; every other case returns no suggestion (templates used); 429 waits capped at 20 s; JSON mode dropped once; key never in logs | pass | tasleem_agent/providers.py |
| V34 | LLM provider misconfigured | provider set, no key; openai_compat without base URL | agent starts on templates, logs why | pass | make_provider |
| V35 | Eval run with a wrong model id | host answers 404 | stops after 1 call, no result file; found when a real Groq run with an outdated default model failed 15 of 15 | pass | bench/llm_barriers.py |
| V36 | LLM barrier classifier vs keywords (live, Groq free tier, `openai/gpt-oss-120b`) | 15 labelled synthetic messages, EN and AR | LLM no worse than keywords | LLM 14/15, keywords 13/15, 0 failed calls; 1 false barrier; sample too small to claim better ([LLM_BARRIER_EVAL.md](LLM_BARRIER_EVAL.md)) | pass | bench/llm_barriers.py |
| H28 | Patient reports on another patient's case | — | changed from 403 to 404 (no existence leak) | pass | case-core |
