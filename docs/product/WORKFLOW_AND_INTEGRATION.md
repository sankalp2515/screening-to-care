# Tasleem: real users, real workflow, real integration, real scale

Everything here is backed by running code. Each claim names the endpoint, file or test that proves it. All people and records are synthetic. For the short version (one problem, one user, each person's flow and channel) read [USER_JOURNEYS.md](USER_JOURNEYS.md).

---

## 1. The real problem, for one real user

**Dr. Fatima, family physician, Ghaf Family Health Centre (Abu Dhabi).**

She refers a positive-FIT patient for colonoscopy. From then on, her only window is the referral status in Malaffi: SENT, ACCEPTED, SCHEDULED, COMPLETED. Malaffi tells her a referral exists. It doesn't tell her whether the colonoscopy happened, or why not, or who is fixing it.

**The moment that matters:** on a Tuesday, Malaffi shows Rajesh's referral as COMPLETED. Nobody ever sent a colonoscopy report. Everyone believes the loop is closed. Two years later, Rajesh is diagnosed late.

**Root cause (five whys).** Follow-up runs on administrative status, not on clinical evidence. Nobody is named as responsible after the referral leaves the clinic.

**How might we** give every family physician a named, verified next step for every positive screening result, using the events Malaffi already carries, so that no result is lost between services?

**One sentence.** For family physicians whose positive-FIT patients stall silently after referral, Tasleem watches Malaffi events and clinical evidence, gives every case a named owner and escalates stalls, so that every stalled journey reaches a named person within days.

**Proof on synthetic data.** 98.5% of stalled journeys reach a named person, against 70.1% for status-only monitoring. The median time to alert is 4 days instead of 14.4. Zero journeys are counted as done when they weren't, against 125 for status-only. Source: [benchmark.md](../evidence/benchmark.md).

---

## 2. The workflow, today versus with Tasleem

| Step | Today | With Tasleem | Mechanism (built) |
|---|---|---|---|
| Positive FIT resulted | Lab result sits in the EMR | A case opens with a **named owner**: the family physician, or the programme coordinator with a visible warning if there is none | `POST /v1/ingest/fhir` (Observation); rule R1 |
| Patient invited | Generic SMS | Plain-language Sahatna message in Arabic or English, **with no result value in it** | Outbox `sahatna` `patient_update` (FHIR Communication) |
| Referred | Referral sent; status in Malaffi | Referral recorded as evidence. The status is shown next to it but **never advances a verified step** | REF adapter `POST /v1/ingest/referral-status` |
| Booked, then missed | Nobody notices | Within 24 hours the case flags "Booked but not attended" and escalates to a named person. The patient is asked what got in the way | Scheduler; stall checks |
| Patient replies "I'm scared, no one can drive me" | The reply is lost, or never sent | An AI suggestion of FEAR, which **a human confirms**. Then a navigator task with the playbook action and a due date | `POST /cases/{id}/barriers`; confirm; outbox `barrier_task` |
| Patient writes "there was blood again" | Read days later, if ever | Routed to a clinician **at once**. An urgent EMR task is raised and the case can't close until a clinician acts | Distress detector; rule R3; outbox `distress_alert` |
| Malaffi says COMPLETED, no report | Counted as done | Flagged "Marked completed without a report" and escalated: owner, then clinic lead, then programme coordinator | False-done check; rule R4 ladder |
| Report arrives | Filed | The stall clears on **evidence**. Next step: "Tell the patient" | `DiagnosticReport` ingest |
| Closure | Implicit | Only a human, only with the evidence or signature the outcome needs, and recorded in the tamper-evident audit | Rules R3, R5, R6; `GET /cases/{id}/audit` |

---

## 3. A day for each person who uses it

| Person | What they open | What they see first | What they do |
|---|---|---|---|
| **Dr. Fatima**, family physician | "My work" (`GET /v1/me/work`) | Stalled cases she owns or that were escalated to her, worst first, each with the reason and a one-line next step | Opens a case, sees reported versus verified progress, logs a call, requests an e-consult, closes on evidence |
| **Aisha**, care navigator | "My work": barrier tasks | "Noura: FEAR + NO_ESCORT. Call to explain sedation; arrange an escort. Due tomorrow" | Calls, rebooks, resolves the barrier with a note |
| **Dr. Hessa**, clinic lead | "My work": escalations at level 2 | Cases her physicians haven't moved after the deadline | Reassigns by handoff, which the receiver must accept (R2), or chases the owner |
| **Sara**, programme coordinator | Programme view (`GET /v1/program/metrics`), with access to every case | The funnel, stalls by reason, false-done count, open distress, and how many cases have no owner (always 0) | Clears level-3 escalations and owns patients with no family physician |
| **Dr. Omar**, GI specialist | His EMR inbox, with no new app | "E-consult question from Dr. Fatima" | Answers through Tasleem, or later through his EMR adapter |
| **Noura**, patient | Sahatna (`GET /v1/me/cases`) | "We noticed you could not attend. Tell us what got in the way" (Arabic, right to left) | Taps "I feel scared" and "No one can take me home", or types a message |

**What each person can see.** Each clinic sees its own patients. People see other clinics' cases only when they are pulled in by an escalation, a handoff or an e-consult. The programme coordinator sees everything. Anything outside your view returns 404, so even the case's existence isn't revealed. Proof: `test_org_scoping_hides_other_clinics_patients` and hard cases H32 and H33.

**What each person can do.** Every case view includes the list of allowed actions for the person viewing. Each entry is computed by dry-running the real engine, so a button is greyed out with the exact rule ("R3_EVIDENCE_REQUIRED: Required clinical evidence has not been received") before anyone clicks. File: `tasleem/domain/actions.py`. Proof: `test_actions_mirror_the_engine`.

---

## 4. How it fits into the real Abu Dhabi workflow

Tasleem doesn't replace Malaffi, Sahatna or any EMR. It is a thin layer that **listens** to events already flowing and **tells** the right person through the channels they already use.

```
 Lab / Facility EMRs ──FHIR R4──┐                         ┌──> Sahatna (patient)    FHIR Communication
 Malaffi HL7 REF (Circular 210) ├──> Tasleem ingest ──> engine ──> Outbox ──┼──> EMR / Malaffi worklist FHIR Task
 Sahatna replies (patient) ─────┘   (idempotent)    (rules)  (same txn)    └──> SMS gateway (fallback)
```

**Inbound (built).**
- **FHIR R4:** Observation, DiagnosticReport, ServiceRequest, Task, Appointment, Procedure, Communication, Encounter and CarePlan.
- **Malaffi referral status:** SENT, ACCEPTED, SCHEDULED, COMPLETED, CANCELLED.
- **Duplicates:** messages are idempotent on (source, message_id).
- **Out-of-order messages:** evidence that arrives before its trigger is replayed when the case opens.
- **Unknown patients:** stored for review, never dropped.

**Outbound (built, this release).**
- **Transactional outbox:** every notification is written in the same database transaction as the case events, so a message is never sent for a change that rolled back, and never lost for one that committed.
- **Notifier service (built 17 Nov):** pulls `GET /v1/integration/outbox`, stores each message, acknowledges it, then delivers it on the channel that fits the person ([channels.yaml](../../backend/tasleem_notifier/channels.yaml)):
  - patients: Sahatna, then a content-free SMS nudge, then a navigator call task;
  - clinicians: EMR inbox task, plus an SMS page when urgent;
  - navigators: the worklist;
  - coordinators: a daily digest.

  Quiet hours, retries, signed receipts and a per-message idempotency key are built in. Real gateways plug in through the signed webhook provider.
- **HL7 v2 connector (built 17 Nov):** facilities and Malaffi send ORU (results), REF (referrals, Circular 210) and SIU (scheduling). The connector maps them to FHIR or referral status and answers with HL7 ACKs. Resends are idempotent on MSH-10.
- **Message formats:**
  - EMR messages are FHIR `Task` resources: owner, priority, a plain description of the next step, and a link to the case.
  - Patient messages are FHIR `Communication` resources in the patient's language. They contain no result values, codes or diagnoses (IFHAS 4.9.2.3), and a test checks this.
- **No new app for most staff:** clinicians receive the task in the inbox they already use. The Tasleem screen is there when they want the full picture.

**Identity.**
- **Demo:** guest personas through `X-Demo-User`, so judges can test hands-on.
- **Production design:** UAE Pass for patients and the DoH identity provider (OIDC) for staff, validated at the gateway. This is not configured in this build, and the API refuses to run without it when demo mode is off.

**What it never does.**
- It never closes a case on its own.
- It never sets priority with AI.
- It never sends a result to a patient by text.
- It never becomes a second referral exchange.

---

## 5. How it scales to a bigger audience

| Dimension | How | Proof |
|---|---|---|
| **More screening findings** | Each finding is a YAML pathway file, with no code change. Three ship today: positive FIT to colonoscopy; HbA1c in the diabetes range; raised blood pressure, added in this release by configuration only | `backend/pathways/*.yaml`; scenario `raised-blood-pressure`; seeded case for Khalfan |
| **More clinics and providers** | Org-scoped visibility plus an indexed `case_assignments` table. A person's inbox is one indexed query, not a scan of every case | `GET /v1/me/work`; `ix_assign_person` |
| **More patients and messages** | Stateless API behind a load balancer. Postgres row locks with optimistic versions. The scheduler only touches cases that are due (`next_check_at`), with `SKIP LOCKED` so several workers can share the work. Metrics are cached with bounded staleness | [SCALE.md](../evidence/SCALE.md) (SQLite, ~235 msg/s) and [SCALE_POSTGRES.md](../evidence/SCALE_POSTGRES.md) (Postgres 16 in Docker, 51.8 msg/s with the workflow layer on, 0 broken audit chains, 0 unowned cases). Expected Abu Dhabi load is ~0.05 msg/s on average, so one replica has ~1,000× headroom |
| **More channels** | New delivery workers read the same outbox. Nothing changes in the engine | `GET /v1/integration/outbox` |
| **Real infrastructure** | Five services in one image plus Postgres 16 (a database per service) plus Redis, verified end to end on 17 Nov 2026: 32 of 32 smoke checks, including HL7 in, channel fallback, AI draft sent by a person, concurrent writes and audit verification | `python -m tasleem.smoke --stack` |

**Rollout path (each step uses the same code).**
1. **Pilot (90 days):** one pathway (positive FIT), 3 to 5 primary-care centres plus one GI centre, read-only Malaffi feed, navigators supplied by the provider. Measure verified colonoscopy completion, days from result to procedure, false-done cases found, and the share of stalls with a named owner.
2. **Network:** all centres in one provider group; add the HbA1c and hypertension pathways; switch on EMR task delivery.
3. **Emirate:** every resident's family physician; the programme office uses the programme view; Sahatna delivery for every case.

---

## 6. Limits, stated plainly

- **Synthetic data only.** The benchmark shows that the logic catches the failures it was designed to catch. It doesn't show the effect on patient outcomes.
- **Placeholder deadlines.** Every deadline in the pathway files must be set by the screening programme's clinical lead.
- **Simple classifiers.** The barrier and distress classifiers use keywords. 3 of 67 hard cases are known misses and stay published in [HARD_CASES.md](../evidence/HARD_CASES.md).
- **Not built yet:**
  - production OIDC;
  - provider-specific bridges to the real Sahatna, EMR and SMS gateways (the notifier's signed webhook is the contract they implement);
  - MLLP over TCP (interface engines relay to HTTPS);
  - the clinician and patient user interfaces, which are being built separately in Lovable against this API.

## 7. Check it yourself

```bash
cd backend && python -m pytest -q                      # 177 tests
python -m tasleem.bench.hardcases                       # 67 labelled hard cases
python -m tasleem.bench --n 1000 --seeds 2026,2027,2028 # three-arm benchmark
docker compose up -d --build --wait && python -m tasleem.smoke --stack   # every service, Postgres
```
