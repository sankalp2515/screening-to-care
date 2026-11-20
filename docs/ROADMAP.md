# Roadmap: from prototype to pilot

Tasleem was built in one challenge week. This page shows what is ready, what stands between it and a 90-day pilot, and what comes after. Every item has a test for "done", and every test is listed in [TEST_CASES.md](evidence/TEST_CASES.md).

## Where it stands (20 Nov 2026)

| Area | Ready today | Needed before a pilot |
|---|---|---|
| Safety rules R1–R6 | Enforced in one transaction; 279 backend tests; 72 of 75 hard cases | A signed clinical safety case; deadlines set by the programme's clinical lead |
| People away | Named cover while an owner is away; ownership never moves | Cover rotas imported from the clinic's roster |
| Integration | HL7 v2 and FHIR R4 ingest with ACKs; unmatched messages queued for a person, never dropped | A Malaffi sandbox feed; code sets checked against the Malaffi catalogue |
| People and channels | One channel per person, quiet hours, fallbacks, receipts (gateways simulated); WhatsApp shown as a vision | Real Sahatna push, a UAE-hosted SMS gateway, an EMR inbox adapter |
| Identity | Demo personas via a header, for reviewers | UAE Pass for patients, Entra ID for staff; demo header off |
| Hosting | Azure (Sweden Central), managed PostgreSQL, Key Vault, HTTPS, uptime alerts, daily audit anchor | Azure UAE North, infrastructure as code, staging and production |
| AI | Suggest-only agent: Evidence Reader (28 labelled reports), reply reader, policy-checked drafts; acceptance monitored | 200 real de-identified reports and replies under a DoH data agreement; drift alerts |
| Quality | Backend, web, 25 browser end-to-end tests and WCAG 2.1 AA checks, all in CI | Load and failover tests on the pilot environment |

## Done during the challenge (19–20 Nov)

| ID | What | Proof |
|---|---|---|
| TSL-160 | **Cover while away.** A clinician names a cover; their work list and new escalations go to the cover until they are back. The owner never changes (R1). | Z18 |
| TSL-161 | **Unmatched-patient queue.** A message for a record nobody knows waits for the coordinator to match or dismiss it; each decision is recorded. | Z19 |
| TSL-163 | **Repeat-FIT guard.** A negative repeat FIT never cancels the colonoscopy; the physician sees a warning citing the UAE guideline. | Z20 |
| TSL-164 | **UAE public holidays** in working-day measures (Islamic dates expected until announced). | Z22 |
| TSL-165 | **Female endoscopists in the GI directory**, listed first once a patient asks for a female doctor. | Z24 |
| TSL-173 | **Daily audit anchor** published outside the database (systemd timer to the server journal). *Backups and a restore drill remain, below.* | Z26 |
| TSL-176 | **Browser end-to-end tests** of the reviewer tour and every persona, in CI. | Z15 |
| TSL-177 | **Accessibility checks** (axe, WCAG 2.1 A/AA) on six screens, in CI. *A screen-reader pass by a person remains.* | Z16 |
| TSL-178 | **Read-aloud** on the patient screen. *An Arabic staff interface remains, below.* | Z17 area |
| TSL-179 | **Smaller web bundle:** the chart library loads lazily; no chunk over 500 kB. | Z27 |
| TSL-180 | **Fresh offline demo bundle**, with a test that fails if the API shape drifts. | Z28 |
| TSL-182 | **Programme CSV export**, pseudonymous ids only. | Z26 |
| TSL-183 | **Patient conveniences:** add the appointment to a calendar; ask a family member to come along. | web unit + browser tests |
| TSL-184 | **WhatsApp, as a vision:** a simulated, content-free nudge whose reply runs through the real rules. Not live until a DoH data-residency ruling. | Z17 |
| TSL-186 | **Hard-case misses closed** (H42, H45, H58), with 8 new held-out cases kept honest. | Z23 |
| TSL-187 | **Obesity pathway**, from one YAML file. | Z25 |
| TSL-190 | **Evidence Reader.** AI reads free-text colonoscopy reports (complete? prep? polyps? pathology pending? next step? interval?), quoting each sentence; a physician confirms; rules keep incomplete or pathology-pending cases open. | Z29–Z32 |
| TSL-191 | **AI at work.** Acceptance and correction rates of every AI suggestion, from the audit log. | Z34 |
| TSL-192 | **Judge-agent fixes**: Usage tab, cover answers e-consults, symptoms never confirmed as barriers, no patient draft for GI-side gaps, decision bar on the case page, deduplicated work list. | Z33 |

## Next: before the pilot (P0, needs a partner)

These need someone outside the team, so they were not faked.

| ID | What | Needs | Done when |
|---|---|---|---|
| TSL-162 | **Clinical safety case** | A clinical safety officer | Hazard log and safety case signed; every deadline set by the clinical lead |
| TSL-166 | **Malaffi sandbox** | DoH / Malaffi access | REF and ORU from the Malaffi test environment flow end to end; codes verified |
| TSL-167 | **Real channels** | Sahatna team, an SMS provider, an EMR vendor | Sends and receipts in staging |
| TSL-168 | **Patient identity** | Malaffi patient index | Matching through Malaffi; Tasleem keeps pseudonymous ids only |
| TSL-169 | **Single sign-on** | UAE Pass onboarding; an Entra ID tenant | Production rejects the demo header |
| TSL-170 | **Least privilege inside the cluster** | The pilot environment | One database role per service; mTLS; gateway rate limits |
| TSL-171 | **Penetration test and data-protection review** | An accredited tester; DoH | Reports filed; ADHICS controls mapped |
| TSL-172 | **UAE North hosting as code** | A subscription with UAE North capacity | Bicep deploys staging and production; registry images; zero-downtime deploys |
| TSL-173b | **Backups and restore drill** | The pilot database | A drill meets a stated RPO and RTO |

## Then: during the pilot (P1)

| ID | What | Done when |
|---|---|---|
| TSL-174 | **Observability** | Traces across all five services; alerts on scheduler delay and outbox lag |
| TSL-175 | **High availability** | Two or more API replicas, managed Redis, scheduler leader election |
| TSL-181 | **Bigger AI evaluation** | 200 or more labelled replies, Gulf Arabic included; drift monitored; a second reader checks distress |
| TSL-188 | **Barrier phrasing** | The held-out barrier misses (H49, H50, H52) pass, measured on a new held-out set |

## Later: at scale (P2)

| ID | What |
|---|---|
| TSL-178b | Staff interface in Arabic |
| TSL-184b | WhatsApp live, once DoH rules on data residency for it |
| TSL-189 | Other IFHAS findings beyond the four pathways already configured |
