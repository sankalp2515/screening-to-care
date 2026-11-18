Build the complete frontend for **Tasleem** in this one pass: a launch-quality marketing site and the product itself. Follow the project knowledge rules at all times. Read this whole brief before writing code; it is the full specification, and there will be no follow-up prompts, so finish every section.

# 0. What Tasleem is
Abu Dhabi screens adults (IFHAS programme). When a screening result is positive, for example a positive stool test (FIT) that needs a colonoscopy, the patient is referred. Malaffi, the health information exchange, now carries every referral and its status. But a status is not care: a referral can say COMPLETED while no colonoscopy was ever done. Tasleem watches the referral events and the clinical evidence and:
- gives every case one named owner;
- detects when care has stalled and escalates to a named person;
- captures why the patient is stuck, in Arabic or English;
- lets a case close only on clinical evidence or a signed clinician decision.

An AI assistant drafts briefs and patient messages; a person always decides and sends.

**One-line pitch:** "Malaffi tells you a referral exists. Tasleem tells you whether the care actually happened, why not, and who is fixing it."

**Users:**
- family physicians (case owners);
- care navigators;
- clinic leads;
- a screening-programme coordinator;
- GI specialists (e-consults);
- patients (a mobile companion designed to live inside the national Sahatna app).

# 1. Tech and structure
- **Stack:** use this project's default stack and its router (TypeScript, Tailwind, shadcn/ui), plus TanStack Query, Recharts and lucide-react. Everything runs in the browser: no server functions, no Supabase, no Lovable Cloud, no database, no auth provider. The backend already exists elsewhere. Environment variables are read with `import.meta.env`.
- **Routes:**
  - `/` landing page;
  - `/how-it-works` (optional anchor on the landing page instead: your choice; keep it one scroll if you can);
  - `/demo` guest sign-in (persona picker);
  - `/app/work` My work (staff home);
  - `/app/cases` All cases;
  - `/app/cases/:id` Case view;
  - `/app/programme` Programme (tabs: Measures, Channels, Usage, Benchmark);
  - `/app/simulator` Live feed simulator;
  - `/patient` patient companion (mobile frame on desktop, full screen on phones).
- **Persona** is stored in localStorage (`tasleem.persona`). `/app/*` without a staff persona redirects to `/demo`; `/patient` without a patient persona redirects to `/demo`.
- **A persistent "Reviewer tour" panel** (section 7) is available on every `/app` and `/patient` screen.

# 2. Data layer (build this first)
Create `src/lib/api/` with `client.ts` (one `request(service, method, path, body?)` function), `demo.ts` (the demo replayer), `types.ts` and hooks per resource. Services: `core`, `agent`, `notifier`, `connector`.

**Mode:**
- Use `live` when `VITE_API_BASE_URL` is set and `VITE_DEMO_MODE !== "true"`. Live mode sends real HTTP requests to the four base URLs with the header `X-Demo-User: {persona}`. Notifier trail calls also send `X-Ops-Key: import.meta.env.VITE_NOTIFIER_OPS_KEY`.
- Otherwise use `demo` mode.
- Show a small pill in the top bar: "Demo data" or "Live API".

**Demo mode** loads this file once, with a polished loading state ("Loading the synthetic demo…"):
`https://raw.githubusercontent.com/sankalp2515/screening-to-care/c7c35c46786b07b854bbcc357ae1b936854a00b2/docs/lovable/demo/demo-bundle.json`

It is about 1.1 MB of real responses recorded from the Tasleem services. Put it in a mutable in-memory store (deep-clone it). Add a "Reset demo" action that restores the original.

Bundle shape (top level):
```
meta: { generated_at, note }
directory: { staff: [{id,name,role,org_id}], patients: [{id,name,role,language}] }
me: { [personaId]: { id, name, role, actor_type, org_id?, sees_all_cases?, language? } }
work: { [staffId]: { needs_action, sections: [{ kind, label, count, items: CaseRow[] }] } }
case_lists: { [staffId]: { items: CaseRow[], next_offset } }
cases: { [caseId]: { detail_by_persona: { [staffId]: Case }, audit, referral_options, trail, assist_by_persona: { [staffId]: Assist } } }
patient_cases: { [patientId]: { en: { items: PatientCase[] }, ar: { items: PatientCase[] } } }
prep_checks: { [caseId]: { persona, response: PrepCheck } }
programme: { metrics, metrics_by_filter: { "org=org-ghaf", "org=org-samar", "language=ar", "language=en" }, usage, channels }
scenarios: { list: { items: [{ id, title, why }] }, runs: { [scenarioId]: ScenarioRun } }
commands: [{ label, service, method, path, persona, case_id, body, status, response }]
```

How the demo replayer answers each request. `P` = current persona. Unknown routes return 404 `{error:{code:"NOT_FOUND",message:"Not found"}}`.

| Request | Demo answer |
|---|---|
| core GET `/v1/directory/people` | `directory` |
| core GET `/v1/me` | `me[P]` |
| core GET `/v1/me/work` | `work[P]` |
| core GET `/v1/cases?status&stalled&pathway&owner` | `case_lists[P].items`, filtered client-side: `status` (open, closed, all; default open), `stalled=true` (has stalls), `pathway` (= `pathway.id`), `owner` (= `owner.id`). Keep the given order |
| core GET `/v1/cases/:id` | `cases[id].detail_by_persona[P]`; if missing → 404 `NOT_FOUND` ("Not found, or outside your clinic") |
| core GET `/v1/cases/:id/audit` | `cases[id].audit` |
| core GET `/v1/cases/:id/referral-options` | `cases[id].referral_options` |
| agent GET `/v1/cases/:id/assist` | `assist_by_persona[P]`, else the first available entry, else 404 |
| notifier GET `/v1/notifications?case_id=` | `cases[id].trail` |
| notifier GET `/v1/policy` | `programme.channels` |
| core GET `/v1/me/cases?lang=` | `patient_cases[P][lang]` |
| core GET `/v1/me/cases/:id/prep-check` | `prep_checks[id].response` when `prep_checks[id].persona === P`, else 404 |
| core GET `/v1/program/metrics?org=&language=` | `metrics_by_filter["org=…"]` or `["language=…"]` when exactly one filter is set, else `metrics` |
| core GET `/v1/program/usage` | `programme.usage` |
| core GET `/v1/demo/scenarios` | `scenarios.list` |
| core POST `/v1/demo/scenarios/:sid` | see "Scenario side effects" below |
| notifier POST `/v1/run-once` | see "Scenario side effects" below |
| connector POST `/v1/hl7` | if the text contains `MSH|` and `ORU^R01`: return `runs["new-positive-fit"].hl7_ack` and apply the new-positive-fit side effects. Otherwise return `runs["new-positive-fit"].hl7_ack_garbage`. Both are plain text |
| core POST `/v1/policy/patient-message-check` | run the local message policy below and return `{ ok, violations: [{ code, detail }] }` |
| any other POST | find the first entry in `commands` with the same `method`, `path` and `persona === P`; if none, the same method and path for any persona. Found: return its `status` and `response` |
| any other POST, not found | return status 501 with `{error:{code:"DEMO_NOT_RECORDED", message:"This action isn't part of the recorded demo. In the live product it calls " + method + " " + path + "."}}`. Show it as a neutral info toast |

**Applying a command result:**
- When a POST returns 200 and the response looks like a case (it has `id`, `timeline` and `actions`), store it as `cases[id].detail_by_persona[P]`.
- Also store it for every other persona that already had that case.
- Update the matching row in every `case_lists[*].items` (status, stalls, owner, `progress`, `days_since_progress`).
- A response of the form `{ consult_id, case }` is applied as `case`.

**Scenario side effects:** `run = scenarios.runs[sid]`, response = `run.response`.
- **Every scenario:**
  - set `cases[run.response.case_id] ??= { detail_by_persona: {}, audit: {verification:{ok:true,checked:0},events:[]}, referral_options: {options:[]}, trail: {items:[]}, assist_by_persona: {} }`;
  - store `run.case_as_owner` under the owner id, and under `coord-sara`;
  - store `run.assist_as_owner` for the owner;
  - prepend a CaseRow built from the case to `case_lists[owner]` and `case_lists["coord-sara"]` (remove any older row with the same id);
  - set `work[owner] = run.owner_work_after`.
- **`report-arrives`:** only enabled after `false-done` has been run in this session. It replaces the false-done case with `run.case_as_owner`, whose stall is cleared on evidence.
- **`unreachable-patient`:** after it runs, enable "Run the notifier now". That button returns `run.notifier_run_once` and then:
  - replaces the case for `nav-aisha` and the owner with `run.case_after_notifier`;
  - sets `cases[id].trail = run.trail_after_notifier`;
  - sets `work["nav-aisha"] = run.navigator_work_after`.

  Before the scenario has run, "Run the notifier now" returns `{ pulled: 0 }` and shows "Nothing waiting to send".

**Local message policy** (demo only; the server is the authority in live mode). The checks, in order:
1. empty text → `EMPTY` "Write a message first.";
2. longer than 600 characters → `TOO_LONG`;
3. a number with a decimal or a unit (`\d+[.,]\d+` or `\d+\s?(mg|ng|µg|mmol|%)`) → `RESULT_VALUE` "Looks like a result value: '{match}'.";
4. words, case-insensitive: positive, negative, abnormal, result, cancer, tumour, tumor, polyp, malignant, diagnosis, نتيجة, إيجابي, سلبي, سرطان, ورم → `RESULT_DISCLOSURE` "Discloses or interprets a result: '{word}'.";
5. advice phrases: "you should take", "stop taking", "nothing to worry", "don't worry", "no need to" → `CLINICAL_ADVICE` "Gives clinical advice: '{phrase}'.";
6. `http`, `www.` or `.com` → `LINK` "Links are not allowed in patient messages."

`ok` is true only with no violations.

**Demo clock:** `now = new Date(meta.generated_at)` in demo mode; `new Date()` in live mode. Use it for every relative time.

Key types (the fields the UI uses):
```
CaseRow: { id, patient:{id,name,language}, pathway:{id,name}, status, priority, owner:{id,name,role},
  progress:{ verified:{stage,step,of}, reported:{admin_status,implied_stage,step,of}, gap },
  stalls:[{reason,label,level}], escalation_level, days_since_progress, open_barriers, distress_open, outcome,
  why?:{kind,refs,since} }
Case: { id, status, version, patient:{id,name,language,insurance_network,birth_year}, pathway:{id,name,version},
  priority:{value,provenance,rule}, owner:{id,name,role}, pending_handoff, progress (as above),
  stages:[{id,label,note,reached,reached_at,evidence_ref,provenance}], appointment_at, appointment_missed,
  stalls:[{reason,stage,detail,flagged_at,level,last_escalated_at,escalated_to:{id,name,role},label,provenance}],
  barriers:[{id,reported_codes,text,reported_by,reported_at,suggested_code,suggested_confidence,suggested_model,
    confirmed_code,confirmed_by,assignee_role,action,due_at,status,resolution_note,suggestion_provenance}],
  distress:[{id,barrier_id,matched,flagged_at,routed_to,resolved,resolved_by,note}],
  consults:[{id,to,question,answer,...}], contact_attempts, warnings, consent_at, outcome, days_since_progress,
  timeline:[{seq,type,at,actor,provenance,payload}],
  next_step:{reason,who,text,provenance,person:{id,name}},
  actions:{ offer_handoff, accept_handoff, reject_handoff, log_contact, request_consult, message_patient:
    {allowed,code?,message?}, close:[{outcome,requires:[],allowed,code?,message?}], barriers:{[id]:…}, distress:{[id]:…},
    consults:{[id]:…} },
  notifications:[{id,channel,recipient,recipient_role,template,urgent,status,created_at,payload}] }
Assist: { case_id, sense:[{id,text,cites:[seq]}], decide:{next_step,note},
  act:{ brief:{provenance,source,model,sentences:[{text,cites}],draft_id},
        patient_message:{draft:{text,language,template}|null, why, provenance, source, draft_id, requires_approval,
          send_with:{method,path,body:{text,language,ai_draft_id}}} },
  hand_off:{to:{id,name},note}, llm }
Trail: { items:[{outbox_id,recipient_id,recipient_role,template,urgent,status,next_at,
  deliveries:[{id,step,channel,status,detail,at}]}] }
Audit: { verification:{ok,checked,broken_at_seq,problem}, events:[{seq,type,actor_id,actor_type,occurred_at,prev_hash,hash}] }
PatientCase: { case_id,status,language,direction,message,appointment_at,consent_given,barrier_options:[{code,label}],open_requests }
PrepCheck: { case_id, language, direction, questions:[{id,text,options:[{id,text}]}] }
ScenarioRun.response: { patient_id, case_id, feed:[{at,source,message,status}], story, case }
Metrics: { cases:{total,open,closed}, by_pathway:{[id]:{name,cases,funnel:[{stage,label,count}]}},
  open_stalls_by_reason, barriers_by_code, outcomes, care_completed, referral_status_says_completed,
  verified_complete, false_done:{count,case_ids}, median_days_result_to_procedure, open_distress,
  open_cases_without_owner, filters, as_of }
Usage: { month, active_cases, by_org:[{org_id, pathways:{[id]:n}, active_cases}] }
Channels: { timezone_offset_hours, quiet_hours:{start,end}, digest_hour,
  channels:{[name]:{success_on,audience,carries_content}},
  recipients:[{recipient, routine:[{channel,wait_hours}], urgent, quiet_hours, when_all_fail}] }
```

Human labels for codes:
- **Event types:** CASE_OPENED "Case opened", STAGE_REACHED "Step reached", ADMIN_STATUS_CHANGED "Referral status changed", STALL_FLAGGED "Stall detected", STALL_CLEARED "Stall cleared on evidence", ESCALATED "Escalated", HANDOFF_OFFERED "Handoff offered", HANDOFF_ACCEPTED "Handoff accepted", BARRIER_REPORTED "Patient reported a barrier", BARRIER_SUGGESTED "AI suggested a barrier code", BARRIER_CONFIRMED "Barrier confirmed", DISTRESS_FLAGGED "Distress flagged", DISTRESS_RESOLVED "Distress handled", CONTACT_ATTEMPTED "Contact attempt", CONSULT_REQUESTED "E-consult requested", CONSULT_ANSWERED "E-consult answered", APPOINTMENT_MISSED "Appointment missed", REFERRAL_REJECTED "Referral rejected", WARNING_ADDED "Data warning", PATIENT_MESSAGE_SENT "Message sent to patient", DELIVERY_FAILED "Message not delivered", CASE_CLOSED "Case closed". Fall back to title-casing the code.
- **Roles:** family_physician "Family physician", navigator "Care navigator", clinic_lead "Clinic lead", program_coordinator "Programme coordinator", gi_specialist "GI specialist", patient "Patient".
- **Outcomes:** COMPLETED_WITH_REPORT "Completed, report received", COMPLETED_ELSEWHERE "Completed elsewhere", PLAN_CHANGED "Clinical plan changed", INFORMED_REFUSAL "Informed refusal", UNREACHABLE "Patient unreachable". Only the first two count as care completed.

# 3. Landing page (`/`)
A single scroll, written for two readers: an Abu Dhabi health-system buyer and a competition judge. Use exactly this copy (you may tighten it, but don't add claims). The design should hold its own beside the best SaaS sites:
- generous whitespace;
- one strong product visual;
- crisp type (large tight headings, 18 px body);
- restrained colour;
- subtle motion only: fade-up on scroll, respecting `prefers-reduced-motion`.

1. **Nav:**
   - left: the "Tasleem" word mark with a small check-in-a-circle mark;
   - links: How it works, Proof, Safety, For teams;
   - right: "View on GitHub" (https://github.com/sankalp2515/screening-to-care) and a primary button "Try the live demo" → `/demo`.
2. **Hero:**
   - Eyebrow: "For Abu Dhabi screening follow-up"
   - H1: "Know whether the care actually happened."
   - Sub: "Malaffi tells you a referral exists. Tasleem tells you whether the colonoscopy was done, why not, and who is fixing it, for every positive screening result."
   - Buttons: "Try the live demo" (primary) and "See how it works" (ghost, scrolls).
   - **Hero visual:** a real, live-rendered product card built from the bundle (Rajesh's case: find the case whose `patient.id` is `p-rajesh`, using the `dr-fatima` detail). It shows:
     - the two progress bars, "Reported by referral status: COMPLETED" (grey, hatched, full) and "Verified by clinical evidence: Attended" (green, partial);
     - the amber gap label;
     - the stall chip "Marked completed without a report";
     - the owner, Dr. Fatima, and "Escalated to Sara · level 3".

     While the bundle loads, show a skeleton.
3. **The problem.** A short story in two columns, "Today" and "With Tasleem".
   - **Today:** "Rajesh, 58, has a positive stool test. He is referred for a colonoscopy. Weeks later the referral shows COMPLETED. No colonoscopy was done and no report exists. Nobody notices until he is diagnosed later."
   - **With Tasleem:** "The same referral says COMPLETED, but there is no procedure and no report. Tasleem flags it, names Dr. Fatima as owner, escalates when she is busy, and will not let the case close until the report arrives."
   - Under it, one line with a source: "In published programmes, 30–55% of people with an abnormal stool test complete a colonoscopy in safety-net settings, against 70–80% in organised programmes with tracking, a named owner and navigation." (BMJ Open, 2026). Link: https://bmjopen.bmj.com/content/16/10/e115052
4. **How it works** (id `how-it-works`). Four steps in a horizontal row, each with an icon and two lines:
   1. **Sense:** "Reads referral, booking and result events from Malaffi and labs (HL7 v2, FHIR R4)."
   2. **Decide:** "Fixed, tested rules spot stalls: booked but not attended, completed without a report, referral rejected, no reply."
   3. **Act:** "Assigns one owner, escalates on missed deadlines, and reaches each person on their own channel: Sahatna for patients, the EMR inbox for clinicians."
   4. **Hand off:** "A clinician closes every case, on evidence. The AI assistant drafts; a person always decides."
5. **Proof** (id `proof`). Heading: "Tested before it is trusted." A Recharts horizontal bar chart, "Stalled journeys that reached a named person": Reminders only 0%, Malaffi status only 70.1%, Tasleem 98.5%. Next to it, four stat tiles:
   - "0 vs 125": journeys falsely counted as done (Tasleem vs status only);
   - "4 vs 14.4 days": median time from care stopping to an alert;
   - "198": automated tests passing;
   - "64 of 67": labelled hard cases handled.

   Caption: "Synthetic cohort of 1,000 patients, three seeds. This tests the software, not patient outcomes; that needs a clinical pilot." Link: "Read the evidence" → https://github.com/sankalp2515/screening-to-care/blob/main/docs/evidence/benchmark.md
6. **Safety** (id `safety`). Heading: "Clinical teams stay in charge." Six small cards, plain words:
   - "Every open case has one named owner."
   - "A handoff counts only when the receiver accepts."
   - "A case closes only on evidence or a signed clinician decision."
   - "Every missed deadline reaches a named person."
   - "AI suggests. It never closes a case, sets priority or advises a patient."
   - "Every change is written to a tamper-evident audit log."

   Below: "Patient messages never contain results. Abnormal findings are discussed in person, as the IFHAS standard requires."
7. **Built on what exists.** A row of plain-text badges (no logos): "Malaffi referral events (Circular 210/2026)", "Sahatna patient app", "HL7 v2 and FHIR R4", "SNOMED CT and LOINC", "Arabic and English". Line: "Tasleem is a layer beside Malaffi and Sahatna. It doesn't replace them."
8. **For teams** (id `for-teams`). Three columns:
   - **Family physicians:** "One list of the cases that need you, and why."
   - **Navigators:** "The patient's own words, a suggested barrier and a task with a due date."
   - **Programme leads:** "Verified completion, false 'done' and time to colonoscopy, by clinic and language."
9. **Pilot call to action.** A teal band with three rows:
   - **Now:** "the positive-FIT-to-colonoscopy loop";
   - **Next:** "a 90-day pilot with one family-medicine network and one GI centre, measured on completed colonoscopies and days to procedure";
   - **Later:** "blood pressure, diabetes and other IFHAS findings".

   Buttons: "Try the live demo" and "Talk to us about a pilot" (mailto: link with subject "Tasleem pilot"; leave the address as a constant `CONTACT_EMAIL = "pilot@tasleem.example"` at the top of the file for the team to change).
10. **Footer:** "Tasleem · Future Health Digital Innovation Challenge 2026 · Challenge 05". "Demo with synthetic data. No real patients." GitHub link.

# 4. Guest sign-in (`/demo`)
- **Header:** title "Try Tasleem", sub "Choose who you are. Everything here is synthetic."
- **Recommended path:** a large highlighted card, "Start the guided tour as Dr. Fatima, family physician", which sets `dr-fatima`, opens the tour panel at step 1 and goes to `/app/work`.
- **Persona cards** from `directory`:
  - Grouped "Care team" (staff) and "Patients" (patients).
  - Each card shows the name, the role in plain words and one line about what you will see:
    - dr-fatima "Owns Rajesh's false 'completed' and Noura's missed appointment";
    - dr-salma "Sunita's urgent message; a handoff waiting for her";
    - nav-aisha "Barrier tasks; can't close cases";
    - dr-hessa "Clinic lead: level-2 escalations";
    - coord-sara "Programme view across all clinics";
    - dr-omar and dr-lina "GI specialists: e-consults";
    - p-noura "Patient view in Arabic";
    - p-rajesh "Patient view in English".

    Other patients: no line.
  - Staff cards go to `/app/work`; patient cards go to `/patient`.
- **Footer links:** "Reset demo" (with a confirmation dialog) and "Back to site".

# 5. App shell (`/app/*`)
- **Left sidebar** (collapsible):
  - "My work" with the badge `work[P].needs_action`;
  - "All cases";
  - "Programme";
  - "Live simulator";
  - a divider, then "Patient view" (opens `/patient` as `p-noura`) and "Back to site".
- **Top bar:**
  - persona avatar (initials), name and role, with a switcher dropdown listing all staff;
  - the "Demo data" / "Live API" pill;
  - "Synthetic data" text;
  - a "Tour" button that toggles the tour panel.
- **Global:** a ⌘K command palette to jump to a case by patient name, and toasts for every command.
- **Empty and loading states:** skeletons for loading; friendly empty states ("Nothing needs you right now"); clear error states with the code.

## 5.1 My work (`/app/work`), the staff home
- **Headline:** "You have **{needs_action}** cases that need action." with a sub-line of the persona's role.
- **Sections** from `work[P].sections`:
  - Fixed order: distress, escalated, handoff, consult, task, owner. Show each as a titled card with its count. Hide empty sections except `owner`.
  - The distress section is red-accented and always first.
- **Each row:**
  - patient name with a language tag (AR/EN);
  - pathway;
  - a mini dual progress bar (reported grey hatched on top, verified green below, amber where `gap`);
  - stall chips coloured by level (1 amber, 2 orange, 3 red);
  - owner;
  - "{days} days since progress";
  - icons for open barriers and distress;
  - the `why` line ("Escalated to you", "Waiting for you to accept", "Answer requested", "Task due") with a relative time.
- Clicking a row opens the case.

## 5.2 All cases (`/app/cases`)
- A dense table with the same columns as My work, plus priority.
- Filters: status (open, closed, all), "Stalled only", pathway, owner.
- Search by patient name.
- Keep the backend order ("most at-risk first"; say so in a small note).
- Note under the table: "Each clinic sees only its own patients."

## 5.3 Case view (`/app/cases/:id`), the most important screen
Two columns on desktop: main content on the left (about 65%), and on the right a sticky panel with tabs "Assistant", "Timeline", "Messages" and "Audit".

**Main column, top to bottom:**
1. **Header:**
   - patient name, birth year, language tag and insurance network;
   - pathway name and version;
   - owner (with a "Handoff pending to {name}: two-step, the sender stays owner until accepted (R2)" banner when `pending_handoff` is set);
   - priority with a "Computed by rule" badge.
2. **Next step banner** from `next_step`: the text, "Who acts: {person.name}" and the reason chip. Red for DISTRESS, amber for any stall reason or PATIENT_NOT_REACHED, teal otherwise. For PATIENT_NOT_REACHED the text reads "Messages in Sahatna and by SMS were not delivered. Call the patient."
3. **Reported versus verified** (the signature component; make it beautiful):
   - Two bars on the same 9-step scale: "Reported by referral status: {admin_status}" (grey, hatched) and "Verified by clinical evidence: {stage label}" (green).
   - When `progress.gap`: amber shading between them and the callout "Malaffi says {admin_status}. Clinical evidence stops at '{verified stage label}'."
   - Below, a vertical stepper from `stages[]`:
     - reached steps show a green check, the time and the `evidence_ref` in monospace with a "Fact" badge;
     - unreached steps show a hollow circle;
     - the first unreached step shows the matching stall detail.
4. **Stalls:** a card for each, showing the label, detail, "Flagged {relative}", the level ladder (1 Owner → 2 Clinic lead → 3 Programme coordinator, with the current level highlighted), "Escalated to {name}" and a "Computed by rule" badge.
5. **What the patient said (barriers):**
   - The patient's own words in a quote block (right-to-left for Arabic, with the font switched), the codes they tapped, and the time.
   - The suggestion in a purple dashed box: "AI suggestion · needs a person to confirm: {suggested_code} ({confidence as %})", model name in small text.
   - Actions:
     - "Confirm as…": a select defaulting to the suggestion, then POST `/v1/cases/{id}/barriers/{bid}/confirm {code}`;
     - "Mark resolved": a note, then `/resolve {note}`.
   - After confirmation, show the playbook task: `action`, assigned role and due date.
6. **Distress** (only unresolved items; red panel, pinned above everything else when present): "Urgent: patient message mentions {matched}", "Routed to {routed_to}", and "Record what was done" (a note, then POST `/v1/cases/{id}/distress/{did}/resolve {note}`). The button state comes from `actions.distress[did]`; a non-clinician sees it disabled with the R3 or R5 chip.
7. **E-consults:** a list of questions and answers. If the persona is the consulted specialist and there's no answer yet, show an answer box (POST `/consults/{cid}/answer {answer}`).
8. **Sticky actions bar** at the bottom of the main column. Every button reads `actions`:
   - **Log contact:** channel (phone, sms, sahatna, whatsapp, in_person, email) and result (reached, no_answer, wrong_number, left_message, declined), then POST `/contact-attempts`.
   - **Message the patient:** opens the composer (section 5.4) with no draft.
   - **Hand off:** person picker from the directory (staff only), with a reason, then POST `/handoff {to, reason}`; note "You stay owner until they accept (R2)". When P is the pending target: Accept (POST `/handoff/accept`) and Decline (with a reason code, POST `/handoff/reject`).
   - **E-consult:** pick a GI specialist and write a question, then POST `/consults {to, question}`.
   - **Referral options:** a sheet listing `referral_options.options` with an in-network badge and accepted networks.
   - **Close case:** a dialog listing every `actions.close[]` outcome as a radio card.
     - Disabled outcomes show their `message` and rule chip (for example "R3 · Required clinical evidence has not been received").
     - Selecting an allowed outcome asks only for the fields in `requires`: `evidence_ref` ("Evidence reference", monospace) and/or `reason` ("Clinical reason").
     - Submit: POST `/close {outcome, evidence_ref?, reason?}`. On a 409, keep the dialog open and show the error.

**Right panel tabs:**
- **Assistant** (default tab): titled "Assistant · suggestions only", with a purple dashed border and a sparkle icon. Four blocks:
  1. **What happened:** `sense[]` facts, each with citation chips "#{seq}". Clicking a chip switches to the Timeline tab and highlights that event.
  2. **What the rules say:** `decide.next_step.text`, with "Computed by rule" and "The assistant cannot change this."
  3. **Brief:** `act.brief.sentences[]` with citation chips, and a badge from `act.brief.provenance`.
  4. **Message to the patient:**
     - If `draft` is null, an amber note with `why` and no composer.
     - Otherwise, the composer (5.4) pre-filled with `draft.text`, a source badge ("From the approved library" for `template`, "AI suggestion" for `llm`) and `why` in small text.

  Footer: "Hands off to {hand_off.to.name}. Nothing is sent or changed until a person acts."
- **Timeline:** `timeline[]` newest first, with the time (relative plus exact on hover), event label, actor, provenance badge and two or three key payload fields in small text. Payloads with `ai_draft_id` get an "AI-assisted" tag.
- **Messages:** the delivery trail from the notifier (`Trail`). For each item:
  - a horizontal chain of `deliveries[]`, with a channel icon (Sahatna phone, SMS bubble, EMR tray, worklist list, e-mail) and a status chip (queued grey, sent teal, delivered teal, read green, failed red);
  - the end state: done ✓, "next try {time}" or "Not reached; a navigator was asked to call" (red).

  SMS chips say "nudge only (no case content)". Below the trail, list `notifications[]` from the case: Sahatna messages as a phone-style bubble (`payload.payload[0].contentString` when present), EMR tasks as a task card.
- **Audit:** a big status line, "Chain intact: {checked} events verified" (green shield) or red "Broken at #{broken_at_seq}". Below it, a monospace table of seq, type, actor, time and `prev_hash` → `hash` (first 10 characters), visually linked.

## 5.4 Patient-message composer (shared)
- A textarea, right-to-left when the language is Arabic, with an EN/AR selector.
- As the user types (debounced 400 ms), POST `/v1/policy/patient-message-check {text}`. Show each violation's `detail` in red under the box; Send is disabled while `ok` is false.
- Helper text: "Patients never receive results or advice by message. Invite them to talk instead."
- **Send to patient:**
  - from an assistant draft: POST `send_with.path` with `send_with.body`, the text replaced by the edited text and `ai_draft_id` kept;
  - otherwise: POST `/v1/cases/{id}/patient-messages {text, language}`.

  Success toast: "Sent to Sahatna by {your name}". On a 409 `IFHAS_MESSAGE_POLICY`, show the message and keep the text.

## 5.5 Programme (`/app/programme`)
Tabs:
- **Measures:**
  - Filter chips for provider (org-ghaf "Ghaf health centre", org-samar "Samar clinic") and language (Arabic, English). Only one filter at a time in demo mode.
  - KPI tiles:
    - open cases;
    - a hero pair, "Malaffi says completed: {referral_status_says_completed}" vs "Verified complete: {verified_complete}";
    - "False 'done' found: {false_done.count}" in amber, linking to those cases;
    - open distress;
    - "Cases without an owner: {open_cases_without_owner}" with a green check when 0;
    - median days from result to procedure.
  - Charts: a funnel per pathway (`by_pathway[*].funnel`), a bar chart of `open_stalls_by_reason` (with human labels), a bar chart of `barriers_by_code` and a donut of `outcomes`.
  - "As of {time}".
- **Channels:** "Who is reached how". A table from `Channels.recipients`: routine steps with waits, urgent channels, quiet hours (show "21:00–08:00 Gulf time") and "when all fail". Header note: "Patients never receive clinical content by SMS. Clinicians get tasks in the EMR inbox they already use."
- **Usage:** active cases per provider and pathway for `usage.month`, with the note "Billing unit: active case per month (pricing hypothesis)". Visible to `program_coordinator`; others see a lock message.
- **Benchmark:** the same chart and tiles as the landing Proof section, plus a three-arm table:
  - Reminders only: 0% flagged;
  - Malaffi status only: 70.1% flagged, 14.4 median days, 125 false done;
  - Tasleem: 98.5%, 4.0 days, 0 false done;
  - clean journeys falsely alerted 0.0%;
  - staff alerts per 100 patients: 38.5 for status only vs 66.4 for Tasleem, with the note "more alerts, each naming one person and one action; they are the stalls status-only monitoring misses".

  Link to the evidence.

## 5.6 Live simulator (`/app/simulator`)
- **Header:** "Send real-world events and watch Tasleem react."
- **Scenario cards** from `scenarios.list.items`: title, `why` and a "Send to Tasleem" button.
- **After a run:**
  - animate `run.response.feed[]` as messages arriving one by one (about 250 ms apart) from "Malaffi (FHIR)", "Malaffi (HL7 REF)", "Lab (HL7 ORU)" or "Sahatna (patient)", each with a time and a status chip;
  - then show `story` in a callout and a mini case card (next step, owner, stalls, the dual progress bar);
  - buttons: "Open case" and "See it in {owner}'s My work" (switches persona and navigates).
- **Run the notifier now:** the button and its note "Routine patient messages wait for 08:00 Gulf time (quiet hours)".
- **HL7 from the lab card:**
  - a monospace textarea pre-filled with `runs["new-positive-fit"].hl7_message`;
  - "Send" posts it to the connector;
  - show the ACK text with `MSA|AA` highlighted green, and `AR` or `AE` red;
  - a second button, "Send a broken message", sends "not an hl7 message" to show the rejection.

## 6. Patient companion (`/patient`)
- **Frame:** a 390 px phone frame centred on desktop (full screen on a phone), styled as a page inside a national patient app: simple header "My care steps", soft surfaces, large touch targets.
- **Language:** an EN/عربي toggle that refetches `/v1/me/cases?lang=` and sets `dir` from `direction`; Arabic uses IBM Plex Sans Arabic.
- **For each item:**
  - `message` in large text, and the appointment date if present;
  - if `consent_given` is false, a consent card first: "Allow your care team to follow up with you in this app" (POST `/v1/me/cases/{case_id}/consent`);
  - "Something getting in the way?": the `barrier_options` as multi-select chips plus a free-text box, then POST `/v1/cases/{case_id}/barriers {codes, text}`. Then show "Your care team will contact you." (and, if `distress_flagged`, "A clinician has been told and will call you today.");
  - if a preparation check exists (GET prep-check returns 200), a card "Before your test: three quick questions", rendered as radio groups. Submit: POST with `{answers:{questionId: optionId}}`, then show `message` only. Never say an answer was wrong.
- A small footer: "Sample screen. In production this would live inside the Sahatna app."
- The persona switcher in the frame header lists patient personas; a "Back to care team view" link is also there.

## 7. Reviewer tour (floating panel)
A compact, draggable or dockable panel, bottom-right, open by default after "Start the guided tour". It shows step N of 7, a short instruction, "Take me there" (switches persona and navigates) and Next/Back. Resolve case ids at runtime by patient id from `cases` (`detail_by_persona` entries whose `patient.id` matches).
1. "Rajesh's referral says COMPLETED. The evidence stops at Attended." Persona dr-fatima, Rajesh's case.
2. "Try to close it as 'Completed, report received'. The rules block it (R3)." Same case; open the Close dialog.
3. "Send a real event: run 'Malaffi says completed, colonoscopy never happened', then 'GI centre sends the report'." Simulator.
4. "Noura wrote in Arabic. Confirm the AI suggestion, then let the assistant draft a message and try adding 'your result is positive'." Persona nav-aisha, Noura's case.
5. "Sunita mentions blood. It goes to a clinician. Only a clinician can record the response." Persona dr-salma, Sunita's case.
6. "The programme view: verified completion against what Malaffi says." Persona coord-sara, Programme.
7. "What Noura sees: no results, just her next step, in Arabic." Persona p-noura, `/patient`.

The panel remembers its step in localStorage and can be closed and reopened from the top bar "Tour" button.

# 8. Quality bar (check each before finishing)
1. From `/` to seeing Rajesh's reported-versus-verified gap takes three clicks or fewer.
2. Closing Rajesh's case as COMPLETED_WITH_REPORT is disabled, with R3 and the backend message visible.
3. Noura's Arabic text renders right-to-left in the IBM Plex Sans Arabic font. The AI suggestion is visibly different from facts. Confirming it shows a task with a due date.
4. Typing "your result is positive" in the composer shows the red violations and disables Send.
5. Sunita's distress panel is red and on top. As coord-sara the resolve button is disabled, or returns the R3 message; as dr-salma it works.
6. Simulator: false-done adds a case to Dr. Fatima's My work; report-arrives clears the stall; unreachable-patient plus "Run the notifier now" shows a red delivery chain and the "Call the patient" banner for Aisha.
7. The HL7 card shows `MSA|AA` in green; the broken message shows a red rejection.
8. The patient view at 390 px works in Arabic and English and shows no clinical values.
9. Every API error shows a human message plus its code; no silent failures; no console errors.
10. The landing page scores well on mobile (375 px) and desktop, with no layout shift from the hero card loading.
11. Lighthouse accessibility 95 or above; every interactive element is keyboard reachable.

# 9. Don't
- Don't add screens beyond these. Depth beats breadth.
- Don't use real logos, real patient or facility names, or stock photos of people.
- Don't invent numbers, customers, partners, testimonials or pricing.
- Don't show a "Close" button that skips the outcome dialog.
- Don't let anything reach a patient without a person clicking Send.
- Don't add Supabase, authentication providers or a database.
