# Tasleem: who it is for, what goes wrong today, and each person's simple flow

All people below are fictional and all data is synthetic. Each step names the endpoint or test that makes it real.

---

## 1. One real problem, one real user, one moment

**User.** Dr. Fatima, family physician at a primary-care centre in Abu Dhabi. She is accountable for every patient she refers.

**The moment.** Rajesh, 58, had a positive stool test (FIT). Dr. Fatima referred him for colonoscopy. Three weeks later Malaffi shows the referral as **COMPLETED**. Nobody ever sent a colonoscopy report. Everyone believes the loop is closed. In two years Rajesh is diagnosed late.

**Why it happens (root cause).** Follow-up runs on *administrative status*, not on *clinical evidence*, and nobody is named as responsible once the referral leaves the clinic.

**The evidence that it is real.**
- In Abu Dhabi, only 30.5% of positive stool tests had a follow-up colonoscopy (BMC Cancer 2021, 2015–16 data).
- In a New York system, more referrals got scheduled while completed specialist visits did not change (JAMA Health Forum 2021).

Sources: BMC Cancer 2021 (Abu Dhabi data, 2015–16; 36.3% of the 933 non-completers had been referred and did not attend); JAMA Health Forum 2021 (New York safety-net system: eConsult raised scheduling from 66.5% to 82.3%, completed visits within 90 days stayed 38.4% vs 37.9%). More in [PRODUCT_FIT_ANALYSIS.md](PRODUCT_FIT_ANALYSIS.md).

**One sentence.** For family physicians whose positive-FIT patients stall silently after referral, Tasleem watches Malaffi events and clinical evidence, gives every case a named owner and escalates stalls, so that every stalled journey reaches a named person within days.

**Measured on synthetic data** ([benchmark.md](../evidence/benchmark.md)):

| Measure | Status-only monitoring | Tasleem |
|---|---|---|
| Stalled journeys that reach a named person | 70.1% | 98.5% |
| Journeys wrongly counted as done | 125 | 0 |

---

## 2. Noura's journey, twice

Noura, 52, speaks Arabic, has Thiqa insurance, and her family physician is Dr. Fatima.

| Step | Today | With Tasleem | Who is told, on which channel |
|---|---|---|---|
| 1. FIT positive | The result sits in the EMR | A case opens with Dr. Fatima as owner (R1) | Noura: Sahatna message in Arabic inviting her to see her doctor, **with no result in it** |
| 2. Seen, referred, booked | Malaffi shows "scheduled" | Evidence recorded; the referral status is shown but never counts as care | Noura: Sahatna "Your colonoscopy is booked. Tell us if anything could stop you" |
| 3. **Misses the appointment** | Nobody notices for weeks | Next morning: "Booked but not attended" stall, escalated to the owner (R4) | Dr. Fatima: task in her EMR inbox. Noura: Sahatna "Tell us what got in the way" |
| 4. Says why | Never asked | Noura taps "I feel scared" and "No one can take me home". A navigator confirms the barrier | Aisha (navigator): task in her Tasleem worklist, with the playbook action and due date |
| 5. Help | Generic reminder SMS | The agent drafts a message from the approved library. Aisha reads it and sends it; the event records her name and the draft (R5) | Noura: Sahatna message. If unread after 24 h, an SMS nudge with no content. If nothing gets through, a call task |
| 6. Rebooked, attended, report | "Completed" in Malaffi, with or without a report | The report arrives; the stall clears on **evidence** | Dr. Fatima: next step "Tell the patient" |
| 7. Closed | Implicit | Dr. Fatima closes with the outcome and its evidence (R3), and the audit chain verifies (R6) | Noura: "Your follow-up is complete" |

The same story runs as one automated test across every service: `backend/tests/test_e2e_services.py`.

---

## 3. A simple flow for each person

Each flow is the whole job, in at most five steps. Channel = where that person already works.

### Dr. Fatima, family physician (EMR inbox first, Tasleem when she wants the full picture)
1. A task lands in her **EMR inbox**: "Marked completed without a report (level 1)" and the next step.
2. She opens **My work** (`GET /v1/me/work`). Stalled cases come first, each with the reason.
3. She opens the case and sees **reported versus verified** progress side by side. The agent's cited brief explains the case in five lines (`GET agent /v1/cases/{id}/assist`).
4. She acts: asks the GI centre for the report, requests an e-consult, or hands the case off (the receiver must accept, R2).
5. When the evidence is in, **Close** is enabled. Until then the button already shows why it is blocked (`actions.close`).

### Aisha, care navigator (Tasleem worklist)
1. **My work → Barrier tasks**: "Noura: FEAR + NO_ESCORT. Call to explain sedation; arrange an escort. Due tomorrow."
2. She confirms the AI's suggested barrier code. The suggestion is labelled; she decides.
3. She asks the agent for a message draft, edits it if she wants, and **sends** it (`POST /v1/cases/{id}/patient-messages`). Policy checks block result values, diagnosis words, advice and links.
4. She calls, rebooks and logs the contact. A "patient not reached" task clears itself when she logs a call.

### Noura, patient (Sahatna; SMS only as a nudge)
1. A Sahatna message in her language says what happens next, never her result.
2. If she can't go, she taps a reason or types a message (`POST /v1/cases/{id}/barriers`).
3. Before the test she answers three teach-back questions (`/v1/me/cases/{id}/prep-check`). A wrong answer quietly asks a nurse to call her.
4. If she writes about bleeding or severe pain, a clinician is alerted the same minute, by EMR task and SMS page.

### Dr. Hessa, clinic lead (EMR inbox)
1. A task arrives only when one of her physicians has not moved a stalled case after the deadline (escalation level 2).
2. She reassigns by handoff or chases the owner.

### Sara, programme coordinator (e-mail digest and programme view)
1. A **daily digest** at 07:00 lists her level-3 escalations and the patients with no family physician, whom she owns.
2. The **programme view** (`GET /v1/program/metrics?org=&language=`) shows the funnel, stalls by reason, false-done count, open distress, and cases without an owner (always 0).
3. **Usage** (`GET /v1/program/usage?month=`) shows active cases per provider.

### Dr. Omar, GI specialist (EMR inbox; no new app)
1. An e-consult question or a handoff arrives as a task in his **EMR inbox**.
2. He answers, and the answer appears on the case. Referral decisions come from his own system through Malaffi (HL7 REF), which the connector reads.

---

## 4. Channel matrix (why each person gets what they get)

| Person | Channel | Why this channel |
|---|---|---|
| Patient | **Sahatna** in-app message | The official patient app. Private, in Arabic or English, and already linked to Malaffi |
| Patient | **SMS nudge**, content-free | Reaches people without the app. SMS is not private, so it only says "you have a message in Sahatna" |
| Patient | **Phone call** by a navigator | When no message gets through. A person, not another message |
| Clinicians | **EMR inbox** (FHIR Task) | No new app to open. Tasleem is there when they want the full picture |
| Clinicians, urgent | **SMS page**, content-free | Distress cannot wait for an inbox check. The page says only "urgent task waiting" |
| Navigator | **Tasleem worklist** | Barrier work is their whole job; the worklist is their tool |
| Coordinator | **Daily e-mail digest** | Oversight, not interruption. Urgent items still page |

The policy is configuration ([channels.yaml](../../backend/tasleem_notifier/channels.yaml)), checked at start-up. The notifier never improvises a channel.

---

## 5. Where AI sits (and where it does not)

**Tasleem is an agent in the workshop's sense.**
- **It senses** Malaffi and clinical events.
- **It decides** with deterministic rules.
- **It acts** by assigning, escalating and messaging.
- **It hands off** to a named clinician.

The language model is one tool inside that loop, and it only drafts.

| Allowed (drafts a person reviews) | Never |
|---|---|
| A case brief where every sentence cites audit events. Numbers or citations the facts don't support are rejected | Close a case, set priority, change a plan, advise a patient |
| A patient message adapted from the approved library, re-checked by the message policy | Disclose a result. The policy blocks values and diagnosis words |
| A barrier code suggestion that a navigator confirms | Send anything. A person sends, and the event records who |
| Translating a patient reply for staff | Hold any credential that can write to a case |

Without a model (the default) the agent still works: it uses the extractive brief and the approved templates. Proof: `backend/tests/test_agent.py`.
