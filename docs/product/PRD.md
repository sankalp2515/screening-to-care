# PRD — Tasleem: verified screening-to-care follow-through

| | |
|---|---|
| Status | Approved for build, 16 Nov 2026 |
| Challenge | Future Health Digital Innovation Challenge 2026 · Population Health · Challenge 05 |
| Release | MVP for submission, 20 Nov 2026 11:59 PM IST |
| Constraints | [Additional.md](../../Additional.md) (overrides this PRD on conflict) |
| Background | [00-PRODUCT-LIFECYCLE.md](00-PRODUCT-LIFECYCLE.md) |

## 1. Summary
Malaffi now tells you a referral exists. **Tasleem tells you whether the care actually happened, why not, and who is fixing it.**

Tasleem is a verification and recovery layer beside Malaffi and Sahatna. It reads referral and result events, opens a case for every actionable screening result, keeps one accountable owner, compares reported progress against clinical evidence, detects stalls with deterministic rules, captures the patient's barrier and routes it to the right person, escalates every missed deadline to a named human, and closes a case only on evidence or a signed clinician decision.

## 2. Goals and non-goals

**Goals (MVP)**
- G1. Every actionable result in a configured pathway becomes a case with a named owner within one ingest cycle.
- G2. The system distinguishes reported (administrative) progress from verified (clinical evidence) progress and flags the gap.
- G3. Stalled cases are surfaced with a reason and an assigned human, not just a status.
- G4. Closure is impossible without the evidence or signature the outcome requires.
- G5. Program leads see where results are lost, by stage, reason, provider and language.
- G6. A reproducible benchmark demonstrates G2–G4 against two baselines.

**Non-goals:** risk or no-show prediction; medical-advice chatbot; EHR or referral exchange; result disclosure by text; real patient data; native mobile apps; billing.

## 3. Users
Primary: family physician (default owner). Also: care navigator, specialist (GI), ADPHC screening lead (buyer), patient. Details in the lifecycle doc, section 3.

## 4. Core concepts

| Term | Definition |
|---|---|
| Pathway | Versioned configuration (YAML) describing trigger, stages, deadlines, checks, escalation ladder and barrier playbooks. Clinician-approved; no code change to add one. |
| Case | One actionable result for one patient in one pathway, from opening to closure. |
| Stage | A verified step, reached only from clinical evidence (FHIR resource or signed staff action). |
| Admin status | What the referral system says (Malaffi REF: sent, accepted, scheduled, completed, cancelled). Never advances a stage by itself. |
| Stall | A rule-detected condition where care isn't progressing (see FR-4). |
| Barrier | The reason a patient isn't progressing, reported by the patient or staff, confirmed by a human. |
| Outcome | One of six closure types (FR-6). |

## 5. Functional requirements

### FR-1 Ingest (Malaffi-compatible)
- FR-1.1 Accept FHIR R4 resources: Observation, DiagnosticReport, ServiceRequest, Task, Appointment, Procedure, Communication, Encounter.
- FR-1.2 Accept simplified Malaffi referral status messages (REF) mapping to admin status.
- FR-1.3 Ingest is idempotent per (source, message id). A duplicate returns the original result.
- FR-1.4 Unknown or unmatched resources are stored and reported, never silently dropped.
- FR-1.5 Missing required fields (patient id, code) are rejected with a field-level error; non-blocking gaps are flagged as warnings on the case.

### FR-2 Case opening and ownership (R1)
- FR-2.1 A trigger result (e.g., FIT positive, HbA1c ≥ 6.5%) opens one case per patient per pathway; a repeat trigger on an open case is attached, not duplicated.
- FR-2.2 Default owner is the patient's family physician. If none is registered, the program coordinator owns it and a warning is shown.
- FR-2.3 Priority comes from the pathway rule, never from AI.
- FR-2.4 An open case always has exactly one owner.

### FR-3 Handoff (R2)
- FR-3.1 Owner (or coordinator) offers a handoff to a named person with a reason.
- FR-3.2 Ownership transfers only when the receiver accepts. The receiver can reject with a reason code.
- FR-3.3 An unanswered offer past its deadline creates a stall and escalates.

### FR-4 Verification and stall detection (core differentiator)
Deterministic checks, evaluated on each event and on the scheduler tick:

| Check | Rule |
|---|---|
| STEP_OVERDUE | Next expected stage not reached within its deadline since the last verified progress |
| BOOKED_NOT_ATTENDED | Appointment time + grace passed with no attendance evidence, or a no-show event |
| CONSULT_NO_PROCEDURE | Attended, but no procedure within the configured days |
| CLOSED_WITHOUT_EVIDENCE | Admin status is "completed" but there is no report evidence (the false-done detector) |
| REPORT_NOT_COMMUNICATED | Report received, outcome not communicated to patient and referrer within N days |
| HANDOFF_NOT_ACCEPTED | Handoff offer older than its deadline |
| REFERRAL_REJECTED | Receiver rejected the referral |
| CONSULT_UNANSWERED | E-consult question unanswered past its deadline |

- FR-4.1 Each new stall is recorded with reason, stage and detail, and escalates (FR-5).
- FR-4.2 A stall clears automatically when the evidence that resolves it arrives.
- FR-4.3 The case view shows **reported progress** and **verified progress** side by side.

### FR-5 Escalation (R4)
- FR-5.1 Escalation ladder from the pathway: level 1 owner, level 2 clinic lead, level 3 program coordinator. Each level resolves to a named person.
- FR-5.2 An open stall re-escalates to the next level after the configured days.
- FR-5.3 Distress or red-flag replies escalate immediately to a clinician (owner) regardless of level.

### FR-6 Closure (R3, R5)
| Outcome | Requires | Who may sign |
|---|---|---|
| COMPLETED_WITH_REPORT | Report received **and** outcome communicated | Clinician or coordinator |
| COMPLETED_ELSEWHERE | Evidence reference (document from another provider) | Clinician |
| PLAN_CHANGED | Written clinical reason | Clinician |
| INFORMED_REFUSAL | Documented discussion reference | Clinician |
| UNREACHABLE | ≥ N contact attempts and at least one escalation | Clinician |
| (none) | AI, system, integration and patient actors can never close | — |
- FR-6.1 Closure is blocked while a distress flag is unresolved.
- FR-6.2 Reports count INFORMED_REFUSAL, PLAN_CHANGED and UNREACHABLE separately and never as completed procedures.

### FR-7 Barriers and recovery
- FR-7.1 Patient selects one or more barrier codes (FEAR, PREP_UNCLEAR, NO_ESCORT, TRANSPORT, COST_OR_INSURANCE, TIME_OR_WORK, LANGUAGE, WANTS_CALLBACK, DONE_ELSEWHERE, OTHER) or writes free text in Arabic or English.
- FR-7.2 Free text gets an AI suggestion (code + confidence), labelled as AI. A navigator or clinician confirms or changes it.
- FR-7.3 Confirmed barriers map to the pathway playbook: assignee role, action script, deadline.
- FR-7.4 Every free-text reply appears in a human queue, whether or not the AI is confident.

### FR-8 Patient companion (mobile web, Sahatna-embeddable)
- FR-8.1 Plain-language status with no result values or diagnosis ("Your doctor would like to see you to talk about your result").
- FR-8.2 Next step, appointment details, "I can't make it / here's why", "Call me back", consent screen.
- FR-8.3 Arabic (RTL) and English; one expatriate language as stretch.
- FR-8.4 Teach-back check on bowel prep with 3 questions; a wrong answer creates a PREP_UNCLEAR barrier.

### FR-9 Consult bridge
- FR-9.1 Owner sends an e-consult question to a specialist; specialist answers asynchronously.
- FR-9.2 Unanswered past deadline → CONSULT_UNANSWERED stall.

### FR-10 Referral options
- FR-10.1 For a case, list providers offering the needed service that are in the patient's insurance network.

### FR-11 Program view
- FR-11.1 Funnel by stage (verified), open stalls by reason, barriers by code, outcomes by type, false-done count, median days to procedure; filterable by provider and language.
- FR-11.2 At-risk list ranked by explainable rules (open stall count, escalation level, days since progress), each with its reason.

### FR-12 Audit (R6)
- FR-12.1 Every state change is an append-only event with actor, actor type, time and payload.
- FR-12.2 Events are hash-chained per case; an endpoint verifies the chain and reports the first broken link.

### FR-13 Benchmark harness
- FR-13.1 Generate a synthetic cohort with configurable failure injection (no-shows, admin-completed without report, rejected referrals, lost reports, late consults, distress replies, out-of-order and duplicate events).
- FR-13.2 Run the same cohort through three arms: reminders only, Malaffi status only, Tasleem.
- FR-13.3 Output metrics (lifecycle doc, section 6) and a per-case results file; documented in `docs/evidence/`.

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Availability | Demo: single region; production target 99.9% |
| Performance | p95 < 300 ms for worklist and case reads at 10k open cases; ingest ≥ 200 events/s per pod (production target) |
| Scalability | Stateless API; horizontal scaling; per-case event streams; scheduler with row locking |
| Security | TLS; OIDC in production (Entra ID for staff, UAE Pass for patients); role-based access; demo guest identities only in demo mode |
| Privacy | Pseudonymous patient IDs; minimum data; consent recorded; no PII in logs; UAE data residency in production |
| Auditability | Hash-chained events; verify endpoint |
| Interoperability | FHIR R4, LOINC, SNOMED CT, HL7 REF mapping |
| Accessibility | Patient UI WCAG 2.1 AA; RTL support |
| Observability | Structured logs, request IDs, health endpoint; OpenTelemetry-ready |

## 7. AI policy
- Allowed: barrier suggestion from free text; drafting plain-language messages; translation; summarizing a case timeline for the owner. Each output is labelled "AI suggestion" and stored as an event with actor type `ai`.
- Not allowed: closing, prioritizing, changing a plan, advising the patient, disclosing results.
- Default build ships a deterministic keyword classifier (offline, testable). An LLM adapter (Azure OpenAI or Claude) is optional behind a flag and must pass the same benchmark.

## 8. Release criteria (20 Nov)
1. All P0 backlog items done and their acceptance tests pass.
2. Engine invariant tests (R1–R6) pass, including the randomized command-sequence test.
3. Benchmark run documented with real measured numbers.
4. Live demo link with guest access; seeded cases cover every stall type and every outcome.
5. Video under 3 minutes; deck on the 16-slide template as a PDF ≤ 5 MB.

## 9. Open questions
- Exact FIT LOINC codes and the Malaffi REF field list. Confirm against Malaffi specifications; current mapping is an assumption.
- Whether IFHAS allows phone discussion of abnormal stool results (public guidance mentions phone or in person; the standard says in person). Default to in person.
- Team status (Atrium invite) and Azure credit availability.
