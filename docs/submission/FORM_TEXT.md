# Submission form text (draft for TSL-132; edit freely before 20 Nov)

Character counts are checked by `python docs/submission/count.py`. Numbers come from [benchmark.md](../evidence/benchmark.md), [HARD_CASES.md](../evidence/HARD_CASES.md) and the tests. Re-run them before submitting if anything changes.

## Solution summary (limit 2,000 characters)

<!-- summary:start -->
Malaffi now tells a family physician that a referral exists. It does not tell her whether the colonoscopy happened, why not, or who is fixing it. In Abu Dhabi only 30.5% of positive stool tests had a follow-up colonoscopy, and a referral marked "completed" can have no report behind it.

Tasleem is a verification and recovery layer beside Malaffi and Sahatna. For family physicians whose positive-FIT patients stall silently after referral, it watches Malaffi events and clinical evidence, gives every case a named owner and escalates stalls, so that every stalled journey reaches a named person within days.

Health impact and clinical relevance: progress counts only on clinical evidence, never on administrative status. Patients are invited in Sahatna in Arabic or English without result values (IFHAS 4.9.2.3), say what stops them, and reach a navigator with a playbook. Distress reaches a clinician the same minute.

Responsible AI, safety and data governance: decisions, deadlines and priorities are deterministic, clinician-approved rules. The AI agent only drafts cited briefs and patient messages; it has no write access, and a named person sends. Cases close only with the evidence or signature the outcome requires. Every change is in a hash-chained audit log.

Technical depth and scalability: five services (rules core, scheduler, HL7 v2 connector, channel notifier, AI agent) on PostgreSQL, with org-scoped visibility, scoped service keys and migrations. 177 automated tests; 32 of 32 end-to-end checks pass on Docker. On 5,000 synthetic patients one API replica handles about 1,000 times the expected load.

Measured on a synthetic cohort: 98.5% of stalled journeys reach a named person versus 70.1% for status-only monitoring, with zero journeys wrongly counted as done versus 125. These are software results, not patient outcomes.

Path to pilot: 90 days, FIT-positive pathway, 3 to 5 primary-care centres and one GI centre, read-only Malaffi feed.
<!-- summary:end -->

## What was built during the challenge (limit 1,500 characters)

<!-- built:start -->
Everything was built during the challenge window (16 to 20 Nov 2026) on synthetic data.

Built: the rules engine enforcing six safety rules (named owner, two-step handoff, evidence-based closure, escalation to named people, no AI decisions, hash-chained audit); FHIR R4 and Malaffi referral-status ingest; an HL7 v2 connector (ORU results, REF referrals, SIU scheduling) with ACKs and idempotency; a notifier that reaches each person on their own channel (Sahatna, content-free SMS, EMR inbox task, worklist, daily digest) with quiet hours and fallback to a navigator call; a suggest-only AI agent with cited briefs and policy-checked drafts; a patient-message policy that blocks result disclosure; personal inboxes and org-scoped visibility; three pathways from configuration (FIT, HbA1c, blood pressure); a three-arm benchmark, 67 labelled hard cases (64 match), 177 tests, a Docker stack with PostgreSQL and CI.

Pre-existing: none. The UI is built with Lovable against this API.
<!-- built:end -->

## Data sources
- **Synthetic only.** Generated patients, directory, feeds and cohort (seeded generator, Synthea-compatible ids). No real patient data was used.
- **Published evidence cited:** BMC Cancer 2021 (Abu Dhabi FIT follow-up), JAMA Health Forum 2021 (eConsult), JAMA Internal Medicine 2026 meta-analysis, DoH IFHAS standard, DoH Circular 210/2026, ADPHC explainer session.
- **Codes:** LOINC and SNOMED CT codes as reference identifiers. Check them against the Malaffi code sets before a pilot.

## IP and licences
- Code written by the team during the challenge. Third-party libraries under permissive licences (FastAPI, SQLAlchemy, Pydantic, Alembic, httpx: MIT or BSD). The optional LLM provider is used through its API terms. No model is trained, and no user data is used for training.
- Note the challenge's 6-month right of first refusal. We will ask for written clarification of the terms ([00-PRODUCT-LIFECYCLE.md](../product/00-PRODUCT-LIFECYCLE.md) section 7).

## Conflicts of interest
- None declared. Edit if any team member has a relationship with a provider, DoH, ADPHC or a co-creator.
