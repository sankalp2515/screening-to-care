# Roadmap: from prototype to pilot

Tasleem was built in one challenge week. This page shows what is ready, what stands between it and a 90-day pilot, and what comes after. Each item has a test for "done".

## Where it stands (19 Nov 2026)

| Area | Ready today | Needed before a pilot |
|---|---|---|
| Safety rules R1–R6 | Enforced in one transaction, 241 tests, 64 of 67 hard cases | A signed clinical safety case; deadlines set by the programme's clinical lead |
| Integration | HL7 v2 (ORU, REF, SIU) and FHIR R4 ingest, with ACKs and idempotency | A Malaffi sandbox feed; code sets checked against the Malaffi catalogue |
| People and channels | One channel per person, quiet hours, fallbacks, receipts (gateways simulated) | Real Sahatna push, a UAE-hosted SMS gateway, an EMR inbox adapter |
| Identity | Demo personas via a header, for reviewers | UAE Pass for patients, Entra ID for staff; demo header off |
| Hosting | Azure (Sweden Central), managed PostgreSQL, Key Vault, HTTPS, uptime alerts | Azure UAE North, infrastructure as code, staging and production |
| AI | Suggest-only agent; brief and drafts validated; evaluated on 15 labelled replies | A 200-reply evaluation in Gulf Arabic and English, with drift monitoring |
| Quality | Backend, frontend and live smoke tests in CI | Browser end-to-end tests of every persona journey |

## Next: before the pilot (P0)

| ID | What | Why it matters | Done when |
|---|---|---|---|
| TSL-160 | **Cover and delegation** | An owner on leave must not leave cases unowned in practice (R1) | Each clinician has a named cover; open cases follow the cover during absence; a test proves no case waits on an absent owner |
| TSL-161 | **Unmatched-patient review queue** | A message that matches no patient is stored today but nobody reviews it | Coordinators see unmatched messages with "match" and "dismiss"; each decision is audited |
| TSL-162 | **Clinical safety case** | A hospital will ask who signed off each rule | Hazard log and safety case signed by a clinical safety officer; every deadline set in configuration by the clinical lead |
| TSL-166 | **Malaffi sandbox** | Real referral and result feeds are the product's input | REF and ORU from the Malaffi test environment flow end to end; LOINC and SNOMED codes verified |
| TSL-167 | **Real channels** | Simulated delivery proves the logic, not the reach | Sahatna push, SMS and EMR inbox send and return receipts in staging |
| TSL-168 | **Patient identity** | Matching must use the national identifier without storing it | Matching through the Malaffi patient index; Tasleem keeps pseudonymous ids only |
| TSL-169 | **Single sign-on** | Demo personas are for reviewers only | UAE Pass and Entra ID sign-in; the demo header is rejected in production |
| TSL-170 | **Least privilege inside the cluster** | Defence in depth for health data | One database role per service; mTLS between services; rate limits at the gateway |
| TSL-171 | **Penetration test and data-protection review** | DoH and ADHICS require it | External pen test passed; ADHICS controls mapped; DoH review complete |
| TSL-172 | **UAE hosting as code** | UAE health data must stay in the UAE | Bicep templates deploy staging and production in UAE North; images come from a registry; deploys are zero-downtime |
| TSL-173 | **Backups and audit anchoring** | Evidence must survive an incident | Restore drill meets a stated RPO and RTO; the audit chain head is anchored outside the database every day |
| TSL-176 | **Browser end-to-end tests** | Three demo-path bugs on 19 Nov were caught by hand, not by tests | Playwright runs the reviewer tour and every persona in CI |

## Then: during the pilot (P1)

| ID | What | Done when |
|---|---|---|
| TSL-163 | **Repeat-FIT guard** | A repeat stool test after a positive one warns the physician that a negative result does not cancel the colonoscopy (UAE CRC guideline 2022) |
| TSL-164 | **UAE public-holiday calendar** | Working-day deadlines and guideline measures skip public holidays |
| TSL-165 | **Female endoscopists in the GI directory** | A "prefer a female doctor" barrier comes with in-network centres and slots that offer one |
| TSL-174 | **Observability** | Traces across all five services; alerts on scheduler delay and outbox lag |
| TSL-175 | **High availability** | Two or more API replicas, managed Redis, scheduler leader election |
| TSL-177 | **Accessibility audit** | WCAG 2.1 AA in Arabic and English, checked with axe and a screen reader |
| TSL-180 | **Fresh offline demo** | The no-backend demo bundle is re-recorded from the current build, and CI checks it matches the API |
| TSL-181 | **Bigger AI evaluation** | 200 or more labelled replies, Gulf Arabic included; drift is monitored; a second reader checks distress |
| TSL-182 | **Programme reporting** | CSV export and a monthly report per clinic, with the guideline scorecard over time |
| TSL-186 | **Close the hard-case misses** | H42, H45 and H58 pass without new misses on a held-out set |

## Later: at scale (P2)

| ID | What |
|---|---|
| TSL-178 | Staff interface in Arabic; read-aloud on the patient screen for low literacy |
| TSL-179 | Smaller web bundle (code splitting) and a performance budget in CI |
| TSL-183 | Patient conveniences: add the appointment to a calendar; ask a family member to come along |
| TSL-184 | WhatsApp as a channel, once DoH rules on data residency for it |
| TSL-187 | Other IFHAS findings: hypertension, diabetes and obesity pathways, already configured in YAML |

## Done in the challenge week

The safety core and its six rules; HL7 and FHIR ingest; the scheduler, notifier, agent and connector services; the staff console, patient companion and landing page; the three-arm benchmark, 67 hard cases, an AI-persona simulation and a 5,000-patient load test; an Azure deployment with guest access; a national-guideline scorecard; and the "prefer a female doctor" barrier, drawn from Abu Dhabi evidence. The [test cases](evidence/TEST_CASES.md) list every one of them.
