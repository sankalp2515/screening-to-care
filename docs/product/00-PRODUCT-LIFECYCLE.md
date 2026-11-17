# Tasleem — Product lifecycle record (0 → 1)

Owner: Product. Status: **Idea locked 16 Nov 2026; backend built 17 Nov** (see section 10). Build window: 16–20 Nov 2026.

This file records each lifecycle stage a senior PM runs before handing a PRD to engineering, with the decision taken at each gate. Facts are separated from our assumptions. Constraints that override everything: [Additional.md](../../Additional.md).

| Stage | Output | Gate decision |
|---|---|---|
| 1. Opportunity framing | Problem, who suffers, why now | GO: Challenge 05 |
| 2. Discovery and evidence | Evidence table, stakeholder needs | Problem is real and local |
| 3. Users and jobs | Personas, jobs to be done, journey | 5 personas, 1 primary buyer |
| 4. Market and competition | Competitor map, positioning | Abu Dhabi-native verification layer |
| 5. Solution definition | Concept, scope, non-goals | Merged idea locked |
| 6. Success metrics | North star, guardrails, benchmark | Three-arm benchmark |
| 7. Risk review | Clinical, privacy, AI, commercial | Safety rules R1–R6 |
| 8. Go-to-market and pilot path | Buyer, pricing hypothesis, pilot | Pilot with one ADPHC pathway |
| 9. Delivery plan | PRD, backlog, milestones | Hand-off to engineering |

---

## 1. Opportunity framing

**Problem statement (patient language).** A positive cancer-screening result can start a referral without ever leading to the care the patient needs.

**Problem statement (system language).** After an actionable screening result, referrals and appointments get recorded as completed administrative steps, but nobody reliably confirms that the diagnostic follow-up happened. When it didn't, nobody knows why, or who should fix it.

**Who suffers.**
- Patients whose cancer or chronic disease is found late.
- Family physicians who stay legally and ethically responsible but can't see what happened at other providers.
- ADPHC, which can't measure whether the screening program converts results into care.

**Why now (facts).**
- ADPHC reported cancer screenings up more than 280% in 2025 versus 2024: more positives to follow up.
- The new IFHAS adult screening program (launched September 2026) covers more than 50 tests for adults 18 to 75.
- **DoH Circular 210/2026 (27 Oct 2026)** requires every licensed facility to send every referral to Malaffi (HL7 REF) and receive referrals through the Malaffi Referral API within 3 months. For the first time, referral events across providers will exist in one place. Nobody yet reconciles them against clinical evidence.

## 2. Discovery and evidence

| Evidence | Source | What it tells us |
|---|---|---|
| Only 30.5% of positive stool tests had a follow-up colonoscopy; 36.3% of the 933 non-completers had been referred and did not attend | BMC Cancer 2021, Abu Dhabi data 2015–16 | Local, documented failure **after** referral. Historical, not a current rate. |
| eConsult raised scheduling from 66.5% to 82.3%, but completed specialist visits within 90 days stayed 38.4% vs 37.9% | JAMA Health Forum 2021, New York safety-net system | Administrative progress is not care. |
| Interventions raise follow-up colonoscopy from 47.8% to 69.1%; navigation 72.5%; automatic GI referral RR 1.68 | JAMA Internal Medicine, Oct 2026 meta-analysis | Navigation plus system changes work; reminders alone are weaker. |
| Barriers: fear, unclear communication, scheduling delays, weak coordination, transport, cost | 2026 review of 38 studies (AACR journals; verify citation before using on a slide) | The reason for a stall varies, so one reminder doesn't fit all. |
| Head of screening's desired journey and "clinical teams remain central" | ADPHC, explainer session 29 Oct 2026 | Exact workflow the buyer wants. |
| Abnormal results discussed in person (IFHAS clause 4.9.2.3); tracked via Malaffi, tagged in Sahatna | DoH IFHAS standard | Hard product constraint. |

**Discovery limits.** We could not interview Abu Dhabi clinicians in the build window. Stakeholder needs come from the official session recordings and published standards. Validation interviews are the first pilot activity.

## 3. Users and jobs to be done

| Persona | Role in the loop | Job to be done | Current pain |
|---|---|---|---|
| **Dr. Fatima, family physician** (primary user, default owner) | Gets the FIT result, refers, stays accountable | "When one of my patients has a positive result, tell me only about the ones that are stuck, and why, so I can act without chasing five systems." | Can't see whether the GI centre booked or did the colonoscopy. |
| **Aisha, care navigator** | Works the barrier queue | "Give me a list of people who are stuck for reasons I can fix, with the reason and the script." | Calls everyone the same way; no reason data. |
| **Dr. Omar, gastroenterologist** | Accepts referrals, does colonoscopy, returns report | "Accept or reject referrals with a reason and answer quick questions asynchronously." | Incomplete referrals; phone tag. |
| **Ms. Houra, ADPHC screening lead** (economic buyer) | Runs the program | "Show me where results are being lost, by provider and reason, and prove the program closes the loop." | Can count screenings, not completed care. |
| **Noura, 52, patient** | Has the positive result | "Help me understand what happens next, and help me with what stops me going." | Fear, prep confusion, no escort; misses the appointment. |

**Fictional patient journey (demo story).** Noura's FIT is positive → her family physician is notified and invites her for an in-person result discussion → referral sent to a GI centre in her insurance network → colonoscopy booked → she misses it: fear, prep confusion, no escort → **today**: the clinic shows "referred", the hospital shows "booked", Malaffi may even show "completed" → **with Tasleem**: stall detected the next morning, Noura taps "I'm scared" and "No one to take me home" in Sahatna, navigator Aisha is assigned with the playbook, the colonoscopy is rebooked, the report is received, the outcome is communicated, and the case closes on evidence.

## 4. Market and competition

| Option | What it already does | Gap we target |
|---|---|---|
| Azra AI | US cancer screening follow-up, navigator worklists | US EHR ecosystem; no Malaffi, IFHAS or Sahatna fit |
| Luma Health | Referral scheduling, outreach, no-show recovery | Scheduling-centred; doesn't reconcile admin status against clinical evidence |
| Rad AI | Imaging follow-up tracking with audit trail | Radiology only |
| Epic, 360X | Cross-EHR closed-loop referral messaging | Messaging standard, not outcome verification or barrier recovery |
| Malaffi + Sahatna | Shared records, referrals (Circular 210), patient app | Infrastructure; no case ownership, stall detection or barrier playbooks |
| Spreadsheets and phone calls | What most programs do today | Invisible, unmeasured |

**Positioning.** For screening programs and provider networks in Abu Dhabi, Tasleem is the verification and recovery layer on top of Malaffi. Unlike referral and scheduling tools, it checks whether care actually happened, finds the reason when it didn't, and routes the fix to a named person, under clinician-governed rules.

**Honest assessment.** Category: adjacent competitors exist; we are not inventing a new category. Differentiation comes from native fit (Circular 210, IFHAS, Sahatna, insurance networks, Arabic) and from measured safety behavior.

## 5. Solution definition (locked)

**Concept.** Ingest Malaffi referral and result events → open a case for every actionable result → keep one accountable owner → compare reported progress against clinical evidence → detect stalls by rules → capture and route the barrier → escalate missed deadlines to named humans → close only on evidence or a signed decision → measure the program.

**In scope (MVP for 20 Nov).**
- Pathway A, built deep: positive FIT → colonoscopy → report → outcome communicated.
- Pathway B, configuration only: HbA1c in the diabetes range → confirmation → care plan.
- Clinician worklist, case timeline, patient companion (mobile web), consult bridge, program view.
- Benchmark harness with three arms and documented hard cases.

**Non-goals.** Disease or no-show prediction; a chatbot giving advice; an EHR or referral exchange; billing; real patient data; native mobile apps.

## 6. Success metrics

**North star (pilot).** Share of actionable results that reach a **verified outcome** within the pathway target time.

**Prototype metrics (measured in simulation; not patient outcomes).**

| Metric | Definition | Target |
|---|---|---|
| False-done rate | Cases shown as complete without clinical evidence | 0% in Tasleem vs measured baseline |
| Time to detect a stall | Hours from missed step to flag | ≤ 24 h simulated |
| Unsafe closures | Closures accepted without the required evidence or signature, across injected attempts | 0 |
| Distress routing | Distressed or urgent patient replies routed to a human | 100% of labelled set |
| Barrier routing accuracy | Confirmed barrier routed to the correct role | Report measured value |
| Owner coverage | Open cases without a named owner at any moment | 0 |

**Guardrails.** No AI-made decision events; audit chain verifies; no PII in logs.

## 7. Risk review

| Risk | Type | Mitigation |
|---|---|---|
| Disclosing abnormal results by text | Clinical / regulatory | Patient app only invites; no result text (IFHAS 4.9.2.3) |
| AI misclassifies a barrier or misses distress | AI safety | Suggestion only; every free-text reply goes to a human queue; distress keywords escalate to a clinician |
| False reassurance via wrong closure | Clinical | R3 evidence rules; refusal never counts as procedure |
| Alert fatigue for physicians | Adoption | Only stalled cases surface; navigator handles barriers first |
| PII exposure | Privacy | Pseudonymous IDs, minimum data, consent capture, synthetic data only |
| Incumbent adds the feature | Commercial | Win on local fit and measured safety; position as a layer Malaffi can embed |
| Challenge IP terms (6-month right of first refusal) | Legal | Declare pre-existing IP; ask for written clarification |

## 8. Go-to-market and pilot path (hypotheses, not validated)

- **Economic buyer:** ADPHC screening program; second buyer: provider networks.
- **Pricing hypothesis:** per active case per month or per program licence. No validated willingness to pay.
- **Pilot (90 days):** one pathway (FIT+), 3–5 primary care centres plus one GI centre, read-only Malaffi feed, navigator staffed by the provider. Success: stall detection precision reviewed by clinicians, false-done cases found, time to colonoscopy.
- **Integration path:** Malaffi REF and FHIR feeds → Tasleem service on UAE-hosted cloud (Azure UAE North) → Sahatna embed for the patient companion.

## 9. Delivery plan

- PRD: [PRD.md](PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)
- Architecture: [../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)

| Date (2026) | Milestone |
|---|---|
| 16 Nov | Docs locked; core engine and API with tests |
| 17 Nov | Benchmark simulator; clinician worklist and case view |
| 18 Nov | Patient companion, consult bridge, program view; deploy |
| 19 Nov | Review checkpoint, hard-case benchmark run, evidence doc; feature freeze |
| 20 Nov | Video, deck, form; submit by afternoon IST |

---

## 10. Where each stage stands (17 Nov 2026, honest status)

| # | Stage | Status | Evidence | What is still open |
|---|---|---|---|---|
| 1 | Opportunity framing | Done | Section 1 | — |
| 2 | Discovery and evidence | **Partly done** | Published studies, the ADPHC explainer, DoH standards | **No interviews with Abu Dhabi clinicians or patients yet.** This is the first pilot activity, and the biggest gap a judge can name |
| 3 | Users and jobs | Done | Section 3; simple flows per person in [USER_JOURNEYS.md](USER_JOURNEYS.md) | Validate the personas in interviews |
| 4 | Market and competition | Done | Section 4, plus two competitor teams from the workshop chat ([Additional.md](../../Additional.md) §6) | — |
| 5 | Solution definition | Done | Section 5; bulls-eye Now / Next / Later in Additional.md §6 | — |
| 6 | Success metrics | Done for the prototype | Three-arm benchmark, hard cases | Real-world baselines come from the pilot |
| 7 | Risk review | Done, updated | Section 7, [SECURITY_AUDIT.md](../engineering/SECURITY_AUDIT.md), [FAILURE_MODES.md](../engineering/FAILURE_MODES.md) | DoH data-protection review; penetration test |
| 8 | Go-to-market and pilot path | Hypotheses | Section 8; usage metering (`/v1/program/usage`) supports per-active-case pricing | Willingness to pay; a letter of interest would help |
| 9 | Delivery plan | Done | [BACKLOG.md](BACKLOG.md) | — |
| 10 | Build | **Backend done; UI in progress (Lovable)** | 5 services, 177 tests, 32 of 32 end-to-end checks on Docker + Postgres | Frontend (user, 18 Nov); cloud deploy (TSL-120) |
| 11 | Validate (review checkpoint) | Ready to run | [REVIEW.md](../evidence/REVIEW.md) checklist | Run every demo path through the UI on 19 Nov; freeze features |
| 12 | Launch (submission) | Not started | Drafts in [docs/submission](../submission/) | Deck, video, form by 20 Nov |
| 13 | Measure and iterate (pilot) | Planned | Section 8 pilot design | After the challenge |

So, have we followed the product lifecycle? Yes, for the stages that are possible before a pilot: 1 and 3 to 9 are done, and stage 2 is done from desk research only. What remains is inherent to a four-day build: talking to real users (stage 2) and measuring real outcomes (stage 13). We say so plainly in the deck rather than claim it.

## 11. Is this an AI agent? Is it a SaaS product?

**Agent: yes, in the sense the organisers use** (Stephan Geyer, V4: "sense → predict → act → hand off to a clinician").
- **Senses:** Malaffi and facility events over HL7 v2 and FHIR (connector, ingest).
- **Decides:** fixed, clinician-approved rules: stalls, deadlines, the next step, the escalation ladder. Deliberately not a model (V1: "don't leave the judgment to the AI").
- **Acts:** assigns a named owner, escalates, and messages each person on their own channel (notifier).
- **Hands off:** every closure, plan change and patient message is a named person's action, recorded in the audit chain.
- **The LLM is a tool inside the loop**, in its own service with no write access. It drafts cited briefs and patient messages from an approved library. Deterministic validators reject anything unsupported. It works fully offline.

**SaaS: yes, as a multi-provider service with single-tenant deployments.**
- **Unit of value:** active cases per month, per provider and pathway (`GET /v1/program/usage`). That supports the per-active-case pricing hypothesis.
- **Configuration, not code, per customer:** pathways (YAML), channel policy (YAML), escalation ladder, message library.
- **Tenancy:** a separate deployment and database per programme or emirate, in a UAE region. Health data residency and DoH governance make shared multi-tenant databases the wrong default. Inside a deployment, providers are isolated by org-scoped visibility (another clinic gets 404).
- **What a SaaS still needs** (after the challenge): self-service onboarding, billing, per-tenant admin UI, SLA monitoring. These are not built.
