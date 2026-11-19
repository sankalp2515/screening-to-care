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

## Frontend (demo replayer and safety in the UI)

Automated in `frontend/src/test/demo.test.ts`. Run: `cd frontend && npm test`. Last run: **18 Nov 2026, 23 passed, 0 failed** (Vitest, Node 22, the recorded synthetic bundle `frontend/demo/demo-bundle.json`). Typecheck clean, production build passes. Checked by hand in the browser at 1440 px and 375 px the same day (rows F19–F22).

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| F1 | Message policy matches the server | recorded "policy check blocks a result" text | same `{ok, violations}` as the recorded server answer | pass | lib/demo.ts messagePolicy (port of domain/messaging.py) |
| F2 | Result word, Arabic result word, advice, link, empty | "Your result is positive"; "الفحص إيجابي"; "nothing to worry"; www link; blank | RESULT_DISCLOSURE; RESULT_DISCLOSURE; CLINICAL_ADVICE; LINK; EMPTY | pass | messagePolicy |
| F3 | Values vs logistics | "150/95"; "at 9:30 on 21 Nov" | RESULT_VALUE; allowed | pass | messagePolicy |
| F4 | R3 close without evidence | Rajesh, COMPLETED_WITH_REPORT, dr-fatima | 409 `R3_EVIDENCE_REQUIRED` | pass | demo close handler (reads server `actions.close`) |
| F5 | R3 allowed outcome, evidence missing | COMPLETED_ELSEWHERE, no evidence_ref | 422, not closed | pass | demo close handler |
| F6 | R3 unreachable too early | UNREACHABLE with too few contact attempts | 409 `R3_CONTACT_ATTEMPTS` | pass | demo close handler |
| F7 | R3 distress needs a clinician | resolve as coord-sara, then dr-salma | 409 `R3_SIGNATURE_REQUIRED`, then 200 and resolved | pass | recorded commands |
| F8 | Result in a patient message where a send was recorded | "Your result is positive" to Noura | 409 `IFHAS_MESSAGE_POLICY`; policy runs before any recorded reply | pass | demo patient-messages handler |
| F9 | Case outside the clinic | dr-lina opens Rajesh | 404 | pass | demo GET case |
| F10 | R1 in every list | all staff case lists | every open row has an owner | pass | bundle check |
| F11 | Stalled filter | coord-sara `?stalled=true` | only rows with stalls | pass | demo GET cases |
| F12 | Simulator order and evidence | report-arrives before false-done; then false-done; then report-arrives | 409; new row first in Dr. Fatima's list with CLOSED_WITHOUT_EVIDENCE; stall cleared | pass | runScenario |
| F13 | Channel fallback | run notifier before and after unreachable-patient | pulled 0; then 1, next step PATIENT_NOT_REACHED, trail exhausted | pass | runNotifier |
| F14 | HL7 | recorded ORU^R01; "not an hl7 message" | `MSA|AA`; `MSA|AR` | pass | connector replay |
| F15 | Prep check never says "wrong" | one wrong answer; all right | follow-up call message, no "wrong"; all_correct | pass | prep-check handler (answer key from pathways) |
| F16 | Patient isolation and status text | Noura reads Rajesh's prep check; every patient status message | 404; no result values or links | pass | demo GET prep-check; bundle check |
| F17 | Demo honesty | unrecorded handoff POST | 501 `DEMO_NOT_RECORDED`, shown as a neutral note | pass | demoRequest fallback |
| F18 | Reset | run false-done, then reset | lists and session back to recorded start | pass | resetDemo |
| F19 | Browser: R3 in the close dialog | Rajesh, choose COMPLETED_WITH_REPORT, try anyway | option shows rule code; server refusal shown in the dialog; Close button stays disabled | pass (manual, 1440 px) | CaseActions CloseDialog |
| F20 | Browser: AI suggestion confirmed by a person | Noura as nav-aisha, Confirm | HUMAN tag, task text, due in 1 day | pass (manual) | CaseView BarrierCard |
| F21 | Browser: composer blocks a result | append "your result is positive" to the draft | red violation shown; Send disabled (also while the check is pending) | pass (manual) | Composer |
| F22 | Browser: patient companion at 375 px | Noura (AR, RTL) barrier flow; Rajesh (EN) prep check, one wrong answer | one big button first; 5 choices + "other reasons"; instant reply; no horizontal scroll; one question at a time; reply asks for a call | pass (manual) | pages/Patient.tsx |

Finding from F16: the backend status template "Your results are with your doctor, who will contact you." would itself fail the backend message policy (`your results are`). It carries no value, but the wording should be reviewed by a clinician before a pilot.

## Real-world fit (published failure mix, 18 Nov)

Run: `python -m tasleem.bench.reality` ([REAL_WORLD_FIT.md](REAL_WORLD_FIT.md)). Tests in `backend/tests/test_bench_reality.py` and `frontend/src/test/demo.test.ts`.

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| RW1 | Calibrated mix matches the literature | `CALIBRATED` weights | 1,000 per mix; 423 never get a colonoscopy (Martin 2017: 42.3%) | pass | bench/reality.py |
| RW2 | Weights override is safe | unknown scenario name; design weights passed explicitly | ValueError; identical cohort to the default | pass | bench/cohort.py |
| RW3 | A tighter status monitor is still blind to false done | 300 patients, 3 d / 7 d thresholds, repeating alerts | more alerts than the generous monitor; every FALSE_DONE still counted done | pass | bench/arms.py |
| RW4 | Tasleem invariants hold on the realistic mix | 80 patients | 0 false done, 0 open cases without an owner, 0% false alerts | pass | engine + scheduler |
| RW5 | **Distress from a patient with no family physician reaches a clinician** | 4 distress patients, none with a family physician | first DISTRESS alert goes to a named clinician (`dr-…`), within 24 h | **failed before the fix** (went to the programme coordinator, who cannot resolve it); pass after | services/directory.py `fallback_clinician_id` |
| RW6 | Full run, 3 seeds × 2,000 | published mix | never-colonoscopy flagged 100% vs 92.0% status only; median 1.9 vs 16.5 days; distress to a clinician in 24 h 10/11, 19/24, 15/18 (every miss is the deliberate no-cue message) | pass | whole pipeline |
| F23 | Tour finds case ids in live mode | `caseIdForPatient("p-rajesh")` | Rajesh's case id; unknown patient gives null | pass | lib/api.ts |
| F24 | Landing numbers are traceable | every value in `landing-facts.ts` | none blank; real-world values appear in REAL_WORLD_FIT.md | pass | lib/landing-facts.ts |
| F25 | Container gateway, live mode | `docker run` the web image on the stack network; GET `/api/core/v1/me`, `/api/{agent,notifier,connector}/healthz`, `/app/work` | 200 from every service through one origin; SPA route served | pass (manual) | frontend/Dockerfile, deploy/nginx.conf |


Finding from RW5: before the fix, 1 of 11 distress messages in seed 2026 went to a non-clinician. The design-mix benchmark never produced a patient with both no family physician and a distress message, so the gap only showed on a larger, realistic run.

Known flaky test (not changed): `test_workflow.py::test_outbox_notifies_named_people_and_never_leaks_results_to_patients` searches the whole payload JSON for "162" and "7.2", which a random id or timestamp can contain. It failed once in about five full runs.

## AI users with a job to be done (18 Nov)

`backend/tasleem/bench/personas.py`: 11 personas (6 patients, 5 staff), each with a profile, incentives and a job to be done, act through the real API in a shared synthetic world; deterministic checks decide pass or fail. Write-up: [PERSONA_SIMULATION.md](PERSONA_SIMULATION.md). Automated in `tests/test_bench_personas.py`.

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| P1 | **Missed appointment reaches the navigator** | Noura (seeded): booked, not attended; next step says nav-aisha must rebook | case in nav-aisha's "Tasks" section | **failed before the fix** (Aisha's work list was empty); pass after | services/routing.py `assignments` (navigator next step) |
| P2 | **Patient reply waits for a person to confirm it** | Yousef: "I have a shift that day" (TIME_OR_WORK), then nav-aisha confirms | before confirming: in nav-aisha's Tasks; after: confirmed, assignee navigator, still in her Tasks | **failed before the fix** (unconfirmed replies were in nobody's work list); pass after | services/routing.py (reported barriers) |
| P3 | **"Done elsewhere" with no family physician reaches a clinician** | John (owner: programme coordinator) reports DONE_ELSEWHERE; coordinator confirms | a clinician sees it at once; the confirmed task goes to a clinician only | **failed before the fix** (report and task both sat with the coordinator, who cannot accept evidence under R3); pass after | services/directory.py `person_for_role("clinician")` |
| P4 | Whole simulation, scripted agents (offline) | 11 personas, 1 round | every job check and invariant passes (R1, R3, R6, distress to a clinician, no 5xx) | pass | bench/personas.py |
| P5 | **Attended, no report: the patient must not think he is done** | Rajesh (seeded: attended, Malaffi COMPLETED, no report) opens the companion | "not finished yet: we are waiting for the report"; no result words | **failed before the fix** (his AI user read "Your care team will follow up" as "I'm all set"); pass after | pathways/fit-positive.yaml ATTENDED |
| P6 | **The companion acknowledges what the patient reported** | John reports DONE_ELSEWHERE; Fatma asks for a call (EN and AR) | John: "A doctor will review the test you had elsewhere… no need to book"; Fatma: "will call you" / "شكراً…" | **failed before the fix** (John was still told to book a visit; Fatma was not told her request arrived); pass after | services/views.py `OPEN_REQUEST_MESSAGE` |
| P7 | **Escalation gives the power to reassign** | Dr. Hessa (clinic lead), a stall escalated to her; offers the case to dr-salma | allowed; owner unchanged until dr-salma accepts (R2); a clinician with no escalation is still refused | **failed before the fix** (R2_NOT_OWNER: the lead could see a stuck case but not move it); pass after | domain/engine.py `offer_handoff` |
| P8 | Next step offers only real actions | handoff waiting (HANDOFF_NOT_ACCEPTED) | text names accept or decline, not "withdraw" (no such command) | changed | domain/actions.py |
| P9 | Whole simulation, LLM agents (groq `openai/gpt-oss-120b`, free tier) | 11 personas × 2 rounds × up to 3 steps, shared world | every check passes | before the fixes: 31 of 36 (5 failures, P1–P3); after: **42 of 42**; 0 server errors; 0 lost turns | bench/personas.py |

## AI helper reply cache (18 Nov)
Why: the free Groq tier allows 8,000 tokens a minute and 200,000 a day, and every open of the Assistant tab asks for a brief and a patient draft (about 3,500 tokens each). Without a cache, roughly 25–30 views a day would use up the model. The cache changes cost only, never content: a cached reply passes the same validators as a fresh one.

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| C1 | Same case state viewed twice | the same prompt twice | one model call; the second reply is a copy the caller cannot alter | pass | tasleem_agent/providers.py `CachedProvider` |
| C2 | The case changed | a new fact (or another output type) | a new model call | pass | `CachedProvider._key` |
| C3 | Model failed | no reply, then a reply | the failure is not cached; the next view asks again | pass | `CachedProvider` |
| C4 | Rate limited (HTTP 429) | a 429, then another view within 60 s | templates at once with no model call and no wait; the model is used again after the cooldown | pass | `CachedProvider` cooldown |
| C5 | Memory bound | 3 prompts, limit 2 | 2 entries kept (oldest dropped) | pass | `CachedProvider` |
| C6 | No model or cache off | offline templates; `AGENT_LLM_CACHE_ENTRIES=0` | not wrapped | pass | `with_cache` |
| C7 | Assistant opened twice, then the patient reports a barrier | Yousef's case, `GET /assist` ×2, barrier, `GET /assist` | 1 brief call for the first two opens, still labelled AI; a 2nd brief call after the barrier; `/healthz` shows the hits | pass | tasleem_agent/app.py |

## Azure OpenAI and the live Azure deployment (19 Nov)
Why: the AI helper moves from the Groq free tier to Azure OpenAI (`gpt-5-mini`, a reasoning model) on the team's Azure credit. Reasoning models reject `temperature` and `max_tokens`, so without this change every call would fail and the helper would silently fall back to templates.

| # | Case | Input | Expected | Actual | Component |
|---|---|---|---|---|---|
| Z1 | Which models are reasoning models | `gpt-5-mini`, `GPT-5`, `openai/gpt-5-nano`, `o4-mini`, `o3` vs `gpt-4o-mini`, `openai/gpt-oss-120b`, Llama, Gemini, empty | first five yes, the rest no | pass (10 cases) | tasleem_agent/providers.py `is_reasoning_model` |
| Z2 | Request to a reasoning model | barrier text to `gpt-5-mini`, effort `minimal` | no `temperature` or `max_tokens`; `max_completion_tokens` and `reasoning_effort` sent; JSON mode kept; reply validated | pass | `OpenAICompatProvider.structured` |
| Z3 | Request to any other model | same text to a non-reasoning model | unchanged: `temperature` 0, `max_tokens` 2000, no reasoning fields | pass | `OpenAICompatProvider.structured` |
| Z4 | `azure_openai` preset | no key; key but no base URL; key and base URL | templates; templates; provider `azure_openai:gpt-5-mini` | pass | `make_provider` |
| Z5 | Settings | `AGENT_LLM_PROVIDER=azure_openai`, `AGENT_LLM_REASONING_EFFORT=minimal` | accepted | pass | tasleem_agent/app.py `AgentSettings` |
| Z6 | Live model, real prompts (manual) | Yousef's seeded case, `GET /assist`; Arabic barrier text | brief and patient draft from the model, both pass the validators and the message policy; barrier `NO_ESCORT` | pass: 3.2 s at effort `minimal`, 7.2 s at `low`; `NO_ESCORT` 0.92 | Azure OpenAI Sweden Central, `gpt-5-mini` |
| Z7 | Live Azure stack (manual) | `python -m tasleem.smoke --stack` against https://tasleem.swedencentral.cloudapp.azure.com/api/* | every check passes | **32 of 32** in 26 s; data then reset to the clean seed | deploy/azure |
| Z8 | Exposure (manual) | ports 8000, 8020, 8080, 5432 from the internet; plain HTTP | closed; HTTP redirects to HTTPS | closed ×4; 308 to HTTPS | NSG, Caddy, Postgres firewall |
| Z9 | Idle database connection (found live, 19 Nov) | Assistant tab on Rajesh's case after the stack sat idle; pooled Postgres connection dropped by the cloud network during the model call | brief shown; dead connection replaced, not used | before: HTTP 500 (`SSL error: unexpected eof` on the draft insert). After: agent and notifier pools pre-ping, recycle at 180 s (under Azure's 4-minute idle cut-off) and send TCP keepalives; 2 tests | tasleem_agent/app.py `make_engine`, tasleem_notifier/store.py `make_store` |
| Z10 | Live walkthrough: reviewer tour, last step (found live, 19 Nov) | tour step 7 "What Noura sees" → Take me there, from the programme view | Noura's Arabic patient screen | before: bounced to the role picker (`/demo`), because the staff-route guard saw the new patient role first. After: guards send a patient role to `/patient` and a staff role to `/app/work`; typecheck clean | frontend App.tsx `RequireStaff`, `RequirePatient` |
| Z11 | Live walkthrough: simulator order (found live, 19 Nov) | live API: run "Malaffi says completed, colonoscopy never happened", then "GI centre sends the report" | second scenario unlocks and clears the stall on evidence | before: stayed locked for ever (the unlock flag was set only in offline demo mode) and the request lacked the `case_id` the live API needs. After: the browser remembers the false-done case and sends its id; 1 test | frontend Simulator.tsx, lib/demo.ts `rememberFalseDone` |
| Z12 | Live walkthrough: Reset demo (found live, 19 Nov) | "Reset demo" on the live link after a reviewer changed cases | the shared synthetic data returns to the seed | before: only the browser cache cleared; the server kept the changes. After: in live mode the button calls `POST /v1/admin/reset-demo` and says the demo is shared | frontend DemoPicker.tsx |
| Z13 | Abu Dhabi barrier: female clinician (added 19 Nov) | patient taps "I would prefer a female doctor" (Arabic label "أفضّل أن تُجري الفحص طبيبة"); free text "embarrassed with a male doctor" | offered in both languages; keyword suggests FEMALE_CLINICIAN; navigator confirms; playbook task to rebook with a female endoscopist in network | pass; 1 API test + 3 classifier cases; hard cases unchanged at 64 of 67 | domain/model.py `BarrierCode`, barriers.py lexicon, fit-positive.yaml playbook, agent classify.py |
| Z14 | National guideline scorecard (added 19 Nov) | programme metrics on the seeded cohort | UAE CRC guideline 2022 targets: referred after a positive FIT (90% / 95%), colonoscopy within 31 working days of referral (90% / 95%); counted from clinical evidence; working days Monday to Friday | pass; 2 tests (UAE working week; scorecard matches the funnel; only the FIT pathway carries a guideline) | pathways.py `Guideline`, fit-positive.yaml, services/views.py `working_days_between` |
