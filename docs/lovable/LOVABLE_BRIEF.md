# Tasleem: UI brief for Lovable

How to use this file:
1. Paste **Part A** into Lovable as the first prompt.
2. Build one screen at a time with the prompts in **Part C**.
3. Attach the files in `docs/lovable/fixtures/` (real API responses) and `docs/lovable/openapi.json` so Lovable uses the exact data shapes.

Everything in the fixtures is synthetic.

---

## Part A. First prompt (paste as is)

> Build **Tasleem**, a web app for Abu Dhabi primary-care teams that makes sure every positive screening result turns into care that actually happened.
>
> **The idea in one line.** Malaffi (the health information exchange) tells you a referral exists. Tasleem tells you whether the care actually happened, why not, and who is fixing it.
>
> **Who uses it:**
> - Family physicians, care navigators, clinic leads and a screening-programme coordinator, on desktop.
> - Patients, in a mobile companion view styled like a page inside a national patient app. Arabic is right-to-left; English is also supported.
>
> **Tech:** React, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, React Router and Recharts.
>
> **API:** every call goes to `import.meta.env.VITE_API_BASE_URL`. Every request sends the header `X-Demo-User: <persona id>`, where the persona id is whoever the user picked on the guest login screen. (The assistant, channel and HL7 services have their own base URLs; see Part G, added after the main screens.)
>
> **Mock mode:** add a toggle (`VITE_USE_MOCKS=true`) that serves the attached JSON fixtures instead of the API, so the UI works before the backend is deployed.
>
> **Error format** from the API: `{ "error": { "code": "R3_EVIDENCE_REQUIRED", "message": "...", "details": {...} } }`. Show the message, and the code in small monospace text.
>
> **Look and feel:**
> - A calm, trustworthy clinical tool. No playful illustrations.
> - White and very light grey surfaces, one deep teal primary (#0F5C6E), amber for "needs attention" (#B7791F), red only for distress or safety (#B42318), green for verified evidence (#1E7A4C).
> - Fonts: Inter for Latin text, IBM Plex Sans Arabic for Arabic.
> - Dense but readable tables, 8 px spacing grid, generous whitespace around the key number on each screen.
> - Don't use any government or Malaffi logos. Tasleem has its own simple word mark.
>
> **Visual rules that matter more than anything else:**
> 1. **Reported versus Verified.** Every case shows two progress bars on the same scale. The top bar is "Reported by referral status" (grey, hatched). The bottom bar is "Verified by clinical evidence" (green). When reported is ahead of verified (`progress.gap = true`), shade the gap amber and label it "Status says more than the evidence shows".
> 2. **Where each item came from.** Every timeline item and value carries a small badge from its `provenance` field:
>    - `fact` → "Fact · from Malaffi/EMR" (green outline)
>    - `computed` → "Computed by rule" (blue outline)
>    - `ai_suggestion` → "AI suggestion: needs human confirmation" (purple dashed outline, with a sparkle icon)
>    - `human` → "Recorded by <name>" (grey)
>    AI text must never look like a fact or a decision.
> 3. **Next step banner.** At the top of each case, show `next_step.text`, who must act (`next_step.person.name`) and the reason. Red if the reason is `DISTRESS`, amber for stalls, teal otherwise.
> 4. **Rules shown before the click.** Each case response includes an `actions` object computed by the backend's rules engine. Never enable a button whose action has `allowed: false`. Disable it and show the backend's `message` in a tooltip, with the rule code (for example R3 or R2) as a small chip.
> 5. **Named people.** Never show "unassigned". Every case has an owner, and every stall shows who it was escalated to and at which level (1 owner, 2 clinic lead, 3 programme coordinator).
>
> Start with: a guest login screen, an app shell with left navigation (My work, All cases, Programme, Feed simulator, Patient view), and the "My work" screen. Details follow.

---

## Part B. Product and system context (reference for Lovable and for you)

**Problem owner.** Abu Dhabi Public Health Centre (ADPHC), head of screening: "no actionable result should be left without a clear next step, a responsible team and a documented outcome", "while clinical teams remain central to decisions and care".

**What already exists and must not be replaced.** Malaffi, the unified exchange, which carries referral status messages. Sahatna, the patient app. Facility EMRs. Tasleem sits beside them.

**The system behind the UI** (already built and tested: five services, 177 tests, a three-arm benchmark, 67 hard cases, 32 of 32 end-to-end checks on Docker and Postgres):
- **Ingest:** FHIR R4 and Malaffi referral-status messages, with duplicate and out-of-order handling.
- **Rules engine** with six safety rules:
  - R1: every open case has one named owner.
  - R2: handoff takes two steps; the sender stays owner until the receiver accepts.
  - R3: a case closes only with the required evidence or a signed reason.
  - R4: every missed deadline escalates to a named human.
  - R5: AI only suggests; it never decides.
  - R6: tamper-evident audit chain.
- **Stall detection** for 8 failure types, with an escalation ladder.
- **Barrier capture:** the patient says what got in the way, AI suggests a code, a human confirms, and a navigator gets a playbook task.
- **Distress detection:** a message about bleeding or fear goes to a clinician immediately.
- **Outbox:** messages to Sahatna (patient) and EMR inbox tasks (staff).
- **Org-scoped visibility:** each clinic sees its own patients.
- **Three screening pathways:** positive FIT to colonoscopy, HbA1c, and blood pressure.

**Personas for the guest login** (`GET /v1/directory/people`):

| id | Name | Role | Shows off |
|---|---|---|---|
| `dr-fatima` | Dr. Fatima | Family physician, Ghaf centre | Default. Owns most cases, including **Rajesh (false done)** and **Noura (missed, scared)** |
| `dr-salma` | Dr. Salma | Family physician, Samar clinic | **Sunita (distress)**, Fatma handoff waiting for her, Leila ready to close |
| `nav-aisha` | Aisha | Care navigator | Barrier tasks; can't close cases (shows R3/R5 blocks) |
| `dr-hessa` | Dr. Hessa | Clinic lead | Level-2 escalations |
| `coord-sara` | Sara | Programme coordinator | Sees every case and the programme view |
| `dr-omar` | Dr. Omar | GI specialist | E-consults |
| `p-noura` | Noura A. (52) | Patient, Arabic | Patient companion view |
| `p-rajesh` | Rajesh K. (58) | Patient, English | Patient companion view |

**The demo story for the video.** Use these labels exactly.
1. **Pain:** Rajesh's referral says COMPLETED in Malaffi. No colonoscopy report exists. Today nobody notices.
2. **Magic:** Tasleem shows the gap between reported and verified progress. It flagged "Marked completed without a report", escalated to Dr. Fatima and then her clinic lead, and blocks closure until evidence arrives (R3).
3. **Live:** in the Feed simulator, run "Malaffi says completed, colonoscopy never happened". A new case appears in My work in red or amber within a second. Then run "GI centre sends the report" and watch the stall clear on evidence.
4. **Human side:** Noura's Arabic message "I'm scared of the sedation and no one can drive me home". The AI suggestion is labelled, a navigator confirms it, and a task with a due date appears.
5. **Proof:** the programme view's false-done count, plus the benchmark chart (static image `benchmark.png`, 98.5% versus 70.1%).

---

## Part C. Screen prompts (one at a time)

### C1. Guest login
> Guest login screen. Title "Tasleem", subtitle "Verified screening-to-care follow-through". A note: "Demo with synthetic data only. No real patients."
>
> Load personas from `GET /v1/directory/people` (`staff[]` and `patients[]`, each with `id`, `name` and `role`). Show them as cards in two groups, "Care team" and "Patients", each with the role in plain words. Clicking a card stores the persona id (localStorage key `tasleem.persona`) and goes to My work for staff or Patient view for patients. Pre-select `dr-fatima` as "Recommended for the demo".
>
> Add a "Reset demo data" link that calls `POST /v1/admin/reset-demo` after a confirmation dialog.

### C2. App shell
> Left navigation:
> - My work (badge = `needs_action` from `/v1/me/work`)
> - All cases
> - Programme (only show for the role `program_coordinator`, or for everyone with a lock icon)
> - Feed simulator
> - Audit
>
> Top bar: the current persona (from `GET /v1/me`: name and role), a persona switcher dropdown, and a language toggle (EN/عربي) that flips `dir="rtl"` on the patient view only.
>
> Refetch every 15 s with TanStack Query and show "Updated 3 s ago".

### C3. My work (the home screen)
> Data: `GET /v1/me/work` → `{ needs_action, sections: [{ kind, label, count, items[] }] }`.
>
> Section order is fixed: `distress`, `escalated`, `handoff`, `consult`, `task`, `owner`. Show each section as a titled card with a count. Hide empty sections except `owner`.
>
> Each item is a row:
> - patient name and language flag;
> - pathway name;
> - the reported-versus-verified mini bar (`progress`);
> - stall chips (`stalls[].label`, coloured by `level`: 1 amber, 2 orange, 3 red);
> - owner name;
> - "days since progress" (`days_since_progress`);
> - small icons for open barriers (`open_barriers`) and distress (`distress_open`).
>
> The `why` object gives `kind`, `refs` and `since`: show "Escalated to you 2 days ago" and similar. Clicking a row opens the case view.
>
> At the top, one big sentence: "You have **5** cases that need action." Use `needs_action`.

### C4. All cases (worklist)
> Data: `GET /v1/cases?status=open|closed|all&stalled=true|false&pathway=<id>&owner=<id>&limit=50&offset=N` → `{ items[], next_offset }`.
>
> Use the same row design as My work. Add filters for status, stalled only, pathway (`fit-positive-colonoscopy`, `hba1c-diabetes-range`, `hypertension-screening`) and owner. Add "Load more" with `next_offset`.
>
> The backend already sorts most at-risk first, so don't re-sort. Each clinic only sees its own patients; that's expected, not an error.

### C5. Case view (the most important screen)
> Data: `GET /v1/cases/{id}`.
>
> Layout, from top to bottom:
> 1. **Header:** patient name, birth year, language, insurance network; pathway name and version; owner (with a pending handoff banner if `pending_handoff` is set); priority with the badge "Computed by rule".
> 2. **Next step banner** from `next_step`.
> 3. **Reported versus Verified:**
>    - Two bars from `progress`: reported shows `admin_status`, verified shows the furthest stage.
>    - Below them, a vertical **stage list** from `stages[]`: label, ✓ reached with time and evidence reference (badge "Fact"), or a hollow circle if not reached. The first unreached stage shows its deadline text from the matching stall `detail`.
>    - If `progress.gap`, an amber callout: "Malaffi says {reported.admin_status}. Clinical evidence stops at '{verified stage label}'."
> 4. **Stalls:** cards with the label, detail, "flagged {date}", level and escalated-to name (badge "Computed by rule").
> 5. **Patient said (barriers):**
>    - Each barrier shows the patient's own words (`text`, right-to-left if Arabic) and the codes they tapped (`reported_codes`).
>    - The AI suggestion (`suggested_code`, `suggested_confidence`) appears in a purple dashed box: "AI suggestion: needs human confirmation".
>    - Buttons: "Confirm as …" (a dropdown of codes, default = suggestion) → `POST /v1/cases/{id}/barriers/{barrier_id}/confirm {code}`. Then show the assigned playbook `action`, `assignee_role` and `due_at`.
>    - "Mark resolved" with a note → `/resolve {note}`.
> 6. **Distress:** a red panel per `distress[]` item where `resolved` is false: the matched words, "routed to {routed_to}", and a "Record what was done" form → `POST /v1/cases/{id}/distress/{distress_id}/resolve {note}`. Only clinicians can do this; the button state comes from `actions.distress[id]`.
> 7. **Actions bar** (sticky at the bottom). Every button's enabled state comes from `actions`:
>    - Log contact attempt: channel (phone, sms, sahatna, whatsapp, in_person, email) and result (reached, no_answer, wrong_number, left_message, declined) → `POST /v1/cases/{id}/contact-attempts`.
>    - Hand off → `POST /v1/cases/{id}/handoff {to, reason}`. The person picker comes from the directory. Show the note "Two-step: you stay owner until they accept (R2)".
>    - Accept or decline a handoff → `POST /v1/cases/{id}/handoff/accept`; `/handoff/reject {reason_code}`.
>    - E-consult → `POST /v1/cases/{id}/consults {to, question}`. Answer → `/consults/{consult_id}/answer {answer}`.
>    - In-network referral options → `GET /v1/cases/{id}/referral-options` (read-only list).
>    - **Close case** opens a dialog listing every outcome from `actions.close[]`. Disabled outcomes show the backend `message` and rule code. The form asks only for the fields in `requires` (`evidence_ref` = document reference, `reason` = clinical reason). Submit → `POST /v1/cases/{id}/close {outcome, evidence_ref?, reason?}`. On a 409, show the error and keep the dialog open.
> 8. **Timeline** (right column or a tab) from `timeline[]`: time, a human-readable event type, the actor, the provenance badge, and the key payload fields. Newest first.
> 9. **Messages sent** (tab) from `notifications[]`:
>    - channel icon (Sahatna phone, EMR inbox tray, SMS);
>    - recipient, template and "urgent" tag;
>    - for Sahatna, show `payload.payload[0].contentString` as a phone-style bubble;
>    - for EMR, show `payload.code.text` and `payload.description` as a task card.
>
> After any successful command, the API returns the updated case. Replace the cached case with it and show a toast.

### C6. Programme view (coordinator)
> Data: `GET /v1/program/metrics` (optional `?pathway=`).
>
> KPI tiles:
> - open cases (`cases.open`);
> - **"Malaffi says completed" (`referral_status_says_completed`) versus "Verified complete" (`verified_complete`)**, side by side;
> - **"False done found" (`false_done.count`)** in amber, with a link listing `false_done.case_ids`;
> - open distress (`open_distress`);
> - "Cases without an owner" (`open_cases_without_owner`), which should always read 0, with a green check;
> - median days from result to procedure.
>
> Charts:
> - funnel per pathway from `by_pathway[pathway].funnel[]` (stage label and count);
> - bar chart of `open_stalls_by_reason`;
> - bar chart of `barriers_by_code`;
> - donut of `outcomes`.
>
> Show `as_of`, and a "may lag up to 15 s" note when `stale` is true.
>
> Add a static card "Benchmark on 1,000 synthetic patients": 98.5% of stalled journeys flagged to a named person, against 70.1% with status-only monitoring; 0 versus 125 false "done"; median 4 versus 14.4 days. Include a link to the evidence.

### C7. Feed simulator (the live demo panel)
> Data: `GET /v1/demo/scenarios` → `items[{id, title, why}]`.
>
> Show each scenario as a card with a "Send to Tasleem" button → `POST /v1/demo/scenarios/{id}` (body `{}`). For `report-arrives`, the body is `{case_id}`; pre-fill it with the last false-done case run in this session.
>
> The response has `{patient_id, case_id, feed[], story, case}`:
> - Animate `feed[]` as messages arriving from "Malaffi (FHIR)", "Malaffi (HL7 REF)" or "Sahatna (patient)", each with a timestamp.
> - Then show `story` in a callout and a mini case card (stalls, next step, owner).
> - Add a button "Open case" and a button "See it in My work as {owner}", which switches persona to the owner.
>
> This panel is what the demo video records, so make it visually clear and calm.

### C8. Patient view (mobile, styled like a page inside Sahatna)
> 375 px wide phone frame, centred on desktop. Data: `GET /v1/me/cases?lang=ar|en` as a patient persona → `items[{case_id, message, direction, appointment_at, consent_given, barrier_options[], open_requests}]`.
>
> - Set `dir` from `direction`. Use IBM Plex Sans Arabic for `ar`.
> - Show `message` large, and the appointment if present.
> - If `consent_given` is false, show a consent card first: "Allow your care team to follow up with you through this app" → `POST /v1/me/cases/{case_id}/consent`.
> - A section "Something getting in the way?" with `barrier_options` as large tappable chips (multi-select), a free-text box and Send → `POST /v1/cases/{case_id}/barriers {codes:[...], text}`. Then show the confirmation "Your care team will contact you" from the response (`routed_to_human: true`).
> - **Never** show test values, codes or diagnoses here; the API doesn't send them.

### C9. Audit
> For a case, `GET /v1/cases/{id}/audit` → `{verification:{ok, checked, broken_at_seq, problem}, events[{seq, type, actor_id, actor_type, occurred_at, prev_hash, hash}]}`.
>
> Show a large green "Chain intact: {checked} events verified" (or red with `broken_at_seq`). Below it, a monospace table showing the hashes chained to each other (shortened to 10 characters).

---

## Part D. API contract (quick reference)

Base URL: `VITE_API_BASE_URL`. Every call except `/healthz`, `/readyz`, `/v1/directory/people`, `/v1/demo/*` and `/v1/admin/reset-demo` needs the header `X-Demo-User`. The full schema is in `openapi.json`.

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/v1/directory/people` | anyone (demo) | Personas for guest login |
| GET | `/v1/me` | any persona | Who am I: name, role, `sees_all_cases` |
| GET | `/v1/me/work` | staff | Personal inbox grouped by why |
| GET | `/v1/cases` | staff | Worklist (org-scoped, most at-risk first) |
| GET | `/v1/cases/{id}` | staff | Case detail including `next_step`, `actions` and `notifications` |
| POST | `/v1/cases/{id}/contact-attempts` | staff | `{channel, result}` |
| POST | `/v1/cases/{id}/handoff` | owner or coordinator | `{to, reason}` |
| POST | `/v1/cases/{id}/handoff/accept` | handoff target | — |
| POST | `/v1/cases/{id}/handoff/reject` | handoff target | `{reason_code}` |
| POST | `/v1/cases/{id}/barriers` | patient (own case) or staff | `{codes[], text}` |
| POST | `/v1/cases/{id}/barriers/{bid}/confirm` | staff | `{code}` |
| POST | `/v1/cases/{id}/barriers/{bid}/resolve` | staff | `{note}` |
| POST | `/v1/cases/{id}/distress/{did}/resolve` | clinician | `{note}` |
| POST | `/v1/cases/{id}/consults` | staff | `{to, question}` |
| POST | `/v1/cases/{id}/consults/{cid}/answer` | consulted specialist | `{answer}` |
| POST | `/v1/cases/{id}/close` | staff (rules decide) | `{outcome, evidence_ref?, reason?}` |
| GET | `/v1/cases/{id}/referral-options` | staff | In-network providers |
| GET | `/v1/cases/{id}/notifications` | staff | Messages sent for this case |
| GET | `/v1/cases/{id}/audit` | staff | Hash-chain verification |
| GET | `/v1/me/cases?lang=` | patient | Plain-language status |
| POST | `/v1/me/cases/{id}/consent` | patient | Record consent |
| GET | `/v1/program/metrics?pathway=` | staff | Programme KPIs |
| GET | `/v1/demo/scenarios` | demo | Simulator list |
| POST | `/v1/demo/scenarios/{id}` | demo | Run a scenario |
| POST | `/v1/admin/reset-demo` | demo | Reset the seeded data |
| POST | `/v1/system/tick` | staff | `{now?}`: run deadline checks (demo time travel) |

**Codes the UI will meet.**
- **Outcomes:** `COMPLETED_WITH_REPORT`, `COMPLETED_ELSEWHERE`, `PLAN_CHANGED`, `INFORMED_REFUSAL`, `UNREACHABLE`. Only the first two count as care completed.
- **Stall reasons:** `STEP_OVERDUE`, `BOOKED_NOT_ATTENDED`, `CONSULT_NO_PROCEDURE`, `CLOSED_WITHOUT_EVIDENCE`, `REPORT_NOT_COMMUNICATED`, `HANDOFF_NOT_ACCEPTED`, `REFERRAL_REJECTED`, `CONSULT_UNANSWERED`. The API sends the human label as `label`.
- **Barrier codes:** `FEAR`, `PREP_UNCLEAR`, `NO_ESCORT`, `TRANSPORT`, `COST_OR_INSURANCE`, `TIME_OR_WORK`, `LANGUAGE`, `WANTS_CALLBACK`, `DONE_ELSEWHERE`, `OTHER`.
- **Rule errors:** `R1_*`, `R2_*` (handoff), `R3_*` (evidence, signature, distress open), `R5_HUMAN_REQUIRED`, `CONCURRENT_UPDATE` (409: reload and retry), `NOT_FOUND` (also what you get for cases outside your clinic).

---

## Part G. v0.2 additions (17 Nov): the assistant, channels, teach-back and the HL7 feed

Paste these after the C-screens are built. Every response shape is in the matching fixture (`fixtures/`) and in `openapi-agent.json`, `openapi-notifier.json` and `openapi-connector.json`.

### G0. Environment
> Add three more base URLs:
> - `VITE_AGENT_BASE_URL` (default `http://localhost:8020`): the AI assistant;
> - `VITE_NOTIFIER_BASE_URL` (default `http://localhost:8010`): channels and delivery;
> - `VITE_CONNECTOR_BASE_URL` (default `http://localhost:8030`): the HL7 feed.
>
> The agent takes the same `X-Demo-User` header as the core API. Notifier delivery-trail calls send `X-Ops-Key: import.meta.env.VITE_NOTIFIER_OPS_KEY` (demo value `local-ops-key`; demo only, never in production). In mock mode, serve the new fixtures listed below.

### G1. Assistant panel in the case view (C5)
> Add a right-side panel titled **"Assistant: suggestions only"**, with a purple dashed border and a sparkle icon. Data: `GET {AGENT}/v1/cases/{id}/assist` (fixture `agent_assist_rajesh_dr-fatima.json`). Show four short blocks, in this order and with these labels:
> 1. **What happened (sense):** `sense[]`. Each fact's text, followed by small chips for `cites[]` ("#12"). Clicking a chip scrolls the timeline to that event `seq`.
> 2. **What the rules say to do (decide):** `decide.next_step.text`, with the "Computed by rule" badge and the note "The assistant cannot change this".
> 3. **Brief:** `act.brief.sentences[]`, each with its citation chips. Badge from `act.brief.provenance`: `computed` → "Computed by rule"; `ai_suggestion` → "AI suggestion".
> 4. **Message to the patient:** `act.patient_message`.
>    - If `draft` is null, show `why` in an amber note, for example "Open distress flag: a clinician must call the patient". Show no textarea.
>    - Otherwise, an editable textarea pre-filled with `draft.text` (right-to-left when `draft.language` is `ar`), the source badge ("From the approved library" for `template`, "AI suggestion" for `llm`), and `why` in small text.
>    - As the user types (debounce 400 ms), call `POST {API}/v1/policy/patient-message-check {text}` (fixtures `policy_check_ok.json`, `policy_check_violation.json`). Show each `violations[].detail` in red under the box. Disable **Send** while `ok` is false.
>    - **Send to patient** → `POST {API}` + `send_with.path`, with body `send_with.body` and `text` replaced by the edited text (keep `ai_draft_id`). On success the API returns the updated case. Toast: "Sent to Sahatna by {your name}".
>    - On a 409 `IFHAS_MESSAGE_POLICY` (fixture `patient_message_refused_409.json`), show the message and keep the text.
>
> Also give staff a plain **"Message the patient"** button in the actions bar, enabled from `actions.message_patient`. It opens the same composer without a draft.

### G2. Delivery trail (C5, "Messages sent" tab)
> For each message, fetch `GET {NOTIFIER}/v1/notifications?case_id={id}` (fixtures `notifier_trail_rajesh.json`, `notifier_trail_unreachable.json`). Show each item as a horizontal chain of its `deliveries[]`:
> - channel icon: Sahatna phone, SMS bubble, EMR tray, worklist, e-mail;
> - status chip: queued grey, sent teal, delivered teal, read green, failed red.
>
> The notification `status` is shown at the end of the chain: done ✓, waiting (show `next_at` as "next try …"), exhausted (red: "Not reached; a navigator was asked to call").
>
> Label SMS chips "nudge only (no case content)".

### G3. "Patient not reached" (C3 My work and C5)
> `next_step.reason == "PATIENT_NOT_REACHED"` → amber banner: "Messages in Sahatna and by SMS were not delivered. Call the patient", naming `next_step.person`. In My work these items appear under "Barrier tasks" with `why.refs` starting `out-`. Logging any contact attempt clears it (fixture `case_unreachable_after_notifier.json`, `me_work_nav-aisha.json`).

### G4. Who is reached how (new small screen under Programme, "Channels")
> `GET {NOTIFIER}/v1/policy` (fixture `notifier_policy.json`). Show a table with one row per `recipients[].recipient`: routine channel steps with their waits, urgent channels, quiet hours and "when all fail". Add a header note: "Patients never receive clinical content by SMS. Clinicians get tasks in the EMR inbox they already use."

### G5. Programme view (C6) additions
> - Filters above the KPIs: provider (`org`: `org-ghaf`, `org-samar`) and patient language (`ar`, `en`) → `GET /v1/program/metrics?org=&language=` (fixtures `program_metrics_org_ghaf.json`, `program_metrics_language_ar.json`). Echo the `filters` object as chips.
> - A **Usage** card, coordinator only: `GET /v1/program/usage?month=YYYY-MM` (fixture `program_usage.json`). Show active cases per provider and pathway, with the note "Billing unit: active case per month (hypothesis)".

### G6. Feed simulator (C7) additions
> - The scenario list now includes `unreachable-patient` (fixture `demo_run_unreachable_patient.json`).
> - Add a button **"Run the notifier now"** → `POST {NOTIFIER}/v1/run-once {now}`, where `now` is the next 10:00 in Abu Dhabi (06:00 UTC), with the note "Routine patient messages wait for 08:00 Gulf time (quiet hours)". Then refetch the case. Fixture: `notifier_run_once.json`.
> - Add an **"HL7 from the lab"** card:
>   - a monospace textarea pre-filled with `fixtures/hl7_sample_oru_fit.hl7`; put the `patient_id` from the last new-positive-fit run in PID-3, and join lines with `\r`;
>   - **Send** → `POST {CONNECTOR}/v1/hl7` with `Content-Type: application/hl7-v2` and the raw text as the body;
>   - show the ACK text (fixtures `hl7_ack_aa.hl7`, `hl7_ack_ar_garbage.hl7`), highlighting `MSA|AA` green and `AR`/`AE` red.

### G7. Patient view (C8) addition: preparation check
> When the case has an appointment, add a card "Before your test: three quick questions". Data: `GET /v1/me/cases/{id}/prep-check` (fixture `patient_prep_check_yousef_ar.json`), shown as radio groups in the patient's language and direction.
>
> Submit → `POST /v1/me/cases/{id}/prep-check {answers: {question_id: option_id}}` and show `message` only (fixture `patient_prep_check_answer_followup.json`). **Never** tell the patient an answer was wrong; the API already asked a nurse to call.
>
> A 404 means this pathway has no preparation: hide the card.

### G8. API additions (quick reference)
| Service | Method | Path | Who | Purpose |
|---|---|---|---|---|
| core | POST | `/v1/cases/{id}/patient-messages` | staff | `{text, language, ai_draft_id?}`; 409 `IFHAS_MESSAGE_POLICY` |
| core | POST | `/v1/policy/patient-message-check` | staff | `{text}` → `{ok, violations[]}` |
| core | GET/POST | `/v1/me/cases/{id}/prep-check` | patient | Teach-back questions and answers |
| core | GET | `/v1/program/metrics?pathway&org&language` | staff | Filtered KPIs |
| core | GET | `/v1/program/usage?month=` | coordinator | Active cases per provider |
| agent | GET | `/v1/cases/{id}/assist` | staff | Sense, decide, act, hand off |
| agent | POST | `/v1/cases/{id}/brief` | staff | Cited brief only |
| agent | POST | `/v1/cases/{id}/outreach-draft` | staff | `{language?}` → draft plus `send_with` |
| agent | GET | `/v1/drafts/{id}` | staff | What the assistant drafted (audit) |
| notifier | GET | `/v1/policy` | anyone | Channel matrix |
| notifier | GET | `/v1/notifications?case_id=` | ops key | Delivery trail |
| notifier | POST | `/v1/run-once` | ops key | `{now?}`: one delivery cycle (demo time travel) |
| connector | POST | `/v1/hl7` | demo | Raw HL7 v2 → ACK text |

New codes: `IFHAS_MESSAGE_POLICY`, `RATE_LIMITED` (429: wait `Retry-After` seconds), next step `PATIENT_NOT_REACHED`, and event types `PATIENT_MESSAGE_SENT` and `DELIVERY_FAILED`.

### G9. Extra acceptance checks
11. The assistant panel's facts link to timeline events. Its next step matches the case banner exactly.
12. The patient-message composer blocks "your result is positive" before the click, and Send stays disabled.
13. Sending an approved draft shows the sender's name on the new timeline event, with an "AI-assisted" tag.
14. The unreachable-patient scenario plus "Run the notifier now" shows a red delivery chain and the "Call the patient" banner for Aisha.
15. The HL7 card returns `MSA|AA`, and the new case appears in Dr. Fatima's My work.

---

## Part E. Acceptance checklist for the UI

1. From guest login to seeing the false-done case highlighted takes under 3 clicks.
2. Rajesh's case shows reported ahead of verified, with the amber gap and the "Marked completed without a report" stall.
3. "Close as COMPLETED_WITH_REPORT" is disabled on Rajesh's case, with R3 in the tooltip.
4. Noura's Arabic message renders right-to-left. The AI suggestion is visibly different from facts. Confirming it creates a navigator task.
5. Sunita's distress panel is red and at the top. Aisha (navigator) can't clear it; Dr. Salma can.
6. Feed simulator: false-done → the new case appears in Dr. Fatima's My work after a refetch. Report arrives → the stall clears.
7. The patient view at 375 px works in Arabic and English and shows no clinical values.
8. The programme view shows the false-done count and "0 cases without an owner".
9. Every API error shows the human message plus the rule code; nothing fails silently.
10. Mock mode works with the backend switched off.

## Part F. Things not to do

- Don't invent numbers. Every figure on screen comes from the API or the benchmark card.
- Don't call AI output a "diagnosis", "decision" or "recommendation". It is a suggestion that a human confirms.
- Don't show a free "Close" button that skips the outcome dialog.
- Don't add screens beyond those listed. Depth beats breadth.
- Don't use real logos, real patient names or real facility names.
- Don't let anything reach a patient without a person clicking **Send**; never auto-send an assistant draft.
- Don't show SMS as if it carried the message; SMS is a content-free nudge.
