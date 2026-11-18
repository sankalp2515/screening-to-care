Design the complete UI/UX for **Tasleem**, a clinical software product for Abu Dhabi primary care, as a set of high-fidelity screens. This is a design pass only: we want the look, layout, components and interaction states, using the exact sample data below. A developer will build the working app from your designs afterwards, so make every screen precise, consistent and buildable with React, Tailwind and shadcn/ui.

## What Tasleem is
When a screening result is positive (for example a positive stool test, "FIT", that needs a colonoscopy), the patient is referred. Malaffi, Abu Dhabi's health information exchange, carries the referral and its status. But a status is not care: a referral can say COMPLETED while no colonoscopy report exists. Tasleem watches referral events and clinical evidence, gives every case one named owner, flags stalled care and escalates it to a named person, captures why the patient is stuck (Arabic or English), and lets a case close only on clinical evidence or a signed clinician decision. An AI assistant drafts briefs and patient messages; a person always decides and sends.

Pitch: "Malaffi tells you a referral exists. Tasleem tells you whether the care actually happened, why not, and who is fixing it."

## Design direction
- Calm, credible clinical SaaS at the level of Linear, Stripe or Vercel. Generous whitespace on marketing pages; dense but readable on staff screens.
- No stock photos of people, no cartoons, no real logos (Malaffi, Sahatna, DoH named in text only), no gradients on data.
- Colours: primary deep teal #0F5C6E; ink #101828; muted #475467; surfaces white and #F9FAFB; borders #EAECF0; amber attention #B7791F; red only for distress and safety #B42318; green verified #1E7A4C; AI purple #7A5AF8.
- Type: Inter for Latin; IBM Plex Sans Arabic for Arabic, right-to-left. Large tight headings, 16–18 px body.
- 8 px grid, radius 10–14 px, hairline borders, visible focus rings, WCAG AA contrast.
- Provenance is a core visual language. Every piece of information carries one of five badges:
  - "Fact" (green outline);
  - "Computed by rule" (blue outline);
  - "AI suggestion · needs a person to confirm" (purple dashed outline plus a sparkle icon);
  - "Recorded by {name}" (grey);
  - "From the approved library" (grey outline).
  AI output must never look like a fact or a decision.
- Disabled actions show why: a tooltip with the reason and a small monospace rule chip such as "R3".
- Every screen shows "Synthetic data" somewhere quiet. Landing and sign-in footers say "Demo with synthetic data. No real patients."

## Screens to design (in this order of importance)

### 1. Case view (desktop 1440 px), the signature screen
Patient: **Rajesh K. (58)**, English. Pathway: Positive FIT to colonoscopy. Priority: high ("Computed by rule"). Owner: **Dr. Fatima (family physician)**.
- Two columns: main (about 65%) and a sticky right panel with tabs Assistant, Timeline, Messages, Audit.
- Header with name, language tag "EN", pathway, owner, priority.
- Next-step banner (amber): "Malaffi says completed but no colonoscopy report exists. Ask the GI centre for the report or rebook." Who acts: Dr. Fatima. Reason chip: "Marked completed without a report".
- **Reported versus verified**, the hero component; make it beautiful. Two bars on a 9-step scale:
  - "Reported by referral status: COMPLETED", grey and hatched, 9 of 9;
  - "Verified by clinical evidence: Attended", green, 6 of 9;
  - amber shading over the gap, with the callout "Malaffi says COMPLETED. Clinical evidence stops at 'Attended'."
  - Below, a vertical stepper of the 9 stages: Patient invited, Referral created, Referred, Referral accepted, Booked, Attended, Report received, Outcome reviewed, Outcome communicated. The first six have green checks, a time and a monospace evidence reference with a "Fact" badge. The rest are hollow; "Report received" shows the stall detail inline.
- Stall card: "Marked completed without a report", detail "referral marked completed, but no report has been received", flagged 8 Nov, escalation ladder 1 Owner → 2 Clinic lead → 3 Programme coordinator with level 3 highlighted, "Escalated to Sara (program coordinator)", "Computed by rule".
- Sticky action bar: Log contact, Message the patient, Hand off, E-consult, Referral options, Close case.
- Right panel, Assistant tab ("Assistant · suggestions only", purple dashed border): What happened (facts with citation chips "#4", "#7"), What the rules say (with "The assistant cannot change this."), a short brief, and a draft patient message with a "From the approved library" badge. Footer: "Hands off to Dr. Fatima. Nothing is sent or changed until a person acts."

### 2. Close case dialog (over the case view)
Outcomes as radio cards:
- "Completed, report received": disabled, chip "R3", message "Required clinical evidence has not been received."
- "Completed elsewhere": allowed, needs "Evidence reference" (monospace field).
- "Plan changed": allowed, needs "Clinical reason".
- "Informed refusal": allowed, needs evidence reference and reason.
- "Unreachable": disabled, chip "R3", message "UNREACHABLE needs at least 3 contact attempts and one escalation."

### 3. My work (staff home, desktop)
Persona Dr. Fatima. Headline: "You have **5** cases that need action." Sections in order (distress first and red-accented when present; hide empty ones): "Stalled cases you own or that were escalated to you" (5). Rows:
- Rajesh K. (58), EN: mini dual progress bar with amber gap, chip "Marked completed without a report" (level 3, red), "Escalated to you".
- Ahmed S. (64), AR: chips "Referral rejected" (level 3), "Next step overdue" (level 2), 10 days since progress.
- Fatma N. (70), AR: chips "Handoff not accepted" (level 2), "Next step overdue" (level 1), 9 days since progress.
App shell: collapsible left sidebar (My work with badge 5, All cases, Programme, Live simulator, divider, Patient view, Back to site); top bar with persona avatar and switcher, a "Demo data" pill, "Synthetic data" text and a "Tour" button; a ⌘K command palette.

### 4. Barrier and AI-suggestion moment (case view section, navigator persona)
Persona Aisha (care navigator), patient **Noura**, Arabic. Next step (amber): "Reach the patient, record what got in the way, and rebook." Progress: booked, 5 of 9, no gap.
- Quote block, right-to-left in IBM Plex Sans Arabic: "انا خايفة من التخدير وما في احد يوصلني البيت". The patient tapped: "I feel scared or worried" (FEAR) and "No one can take me home" (NO_ESCORT).
- Purple dashed box: "AI suggestion · needs a person to confirm: FEAR (50%)", model "keyword-v1".
- Actions: "Confirm as…" select and "Mark resolved". Show the after state too: a task card with action, assigned role and due date.
- Patient-message composer with a live policy check: typed text "your result is positive" shows red violations under the box and a disabled Send button. Helper: "Patients never receive results or advice by message. Invite them to talk instead."

### 5. Distress state (case view, top-pinned red panel)
Patient Sunita: "Urgent: patient message mentions blood". "Routed to Dr. Salma". Button "Record what was done". Show it enabled for a clinician and disabled with a "R3" chip for a non-clinician.

### 6. Landing page (desktop 1440 and mobile 375)
Sections:
1. Nav: "Tasleem" wordmark with a check-in-circle mark; links How it works, Proof, Safety, For teams; "View on GitHub"; primary "Try the live demo".
2. Hero: eyebrow "For Abu Dhabi screening follow-up"; H1 "Know whether the care actually happened."; sub "Malaffi tells you a referral exists. Tasleem tells you whether the colonoscopy was done, why not, and who is fixing it, for every positive screening result."; buttons "Try the live demo" and "See how it works". The hero visual is a real product card: Rajesh's reported-versus-verified bars, the amber gap, the chip "Marked completed without a report", owner Dr. Fatima, "Escalated to Sara · level 3".
3. Problem: two columns, "Today" and "With Tasleem" (Rajesh's story), plus a sourced line: "In published programmes, 30–55% of people with an abnormal stool test complete a colonoscopy in safety-net settings, against 70–80% in organised programmes with tracking, a named owner and navigation." (BMJ Open, 2026).
4. How it works: four steps, Sense, Decide, Act, Hand off.
5. Proof: heading "Tested before it is trusted."; horizontal bars "Stalled journeys that reached a named person": Reminders only 0%, Malaffi status only 70.1%, Tasleem 98.5%. Tiles: "0 vs 125" journeys falsely counted as done; "4 vs 14.4 days" median time to alert; "198" automated tests passing; "64 of 67" labelled hard cases handled. Caption: "Synthetic cohort of 1,000 patients, three seeds. This tests the software, not patient outcomes; that needs a clinical pilot."
6. Safety: "Clinical teams stay in charge." Six small cards: one named owner; handoff counts only when accepted; closes only on evidence or a signed clinician decision; every missed deadline reaches a named person; AI suggests, never closes, sets priority or advises; tamper-evident audit log.
7. Built on what exists: text badges "Malaffi referral events (Circular 210/2026)", "Sahatna patient app", "HL7 v2 and FHIR R4", "SNOMED CT and LOINC", "Arabic and English".
8. For teams: family physicians, navigators, programme leads.
9. Pilot band (teal): Now / Next / Later, with buttons "Try the live demo" and "Talk to us about a pilot".
10. Footer.

### 7. Guest sign-in / persona picker (`/demo`)
"Try Tasleem", "Choose who you are. Everything here is synthetic." A large recommended card, "Start the guided tour as Dr. Fatima, family physician". Then grouped persona cards:
- Care team: Dr. Fatima, Dr. Salma, Aisha (navigator), Dr. Hessa (clinic lead), Sara (programme coordinator), Dr. Omar and Dr. Lina (GI specialists).
- Patients: Noura (Arabic), Rajesh (English).

### 8. Programme view (coordinator, desktop)
KPI tiles, with the hero pair "Malaffi says completed" vs "Verified complete", plus "False 'done' found" (amber), open distress, "Cases without an owner: 0" (green check) and median days to procedure. A funnel per pathway, a bar chart of open stalls by reason, a bar chart of barriers by code, and a donut of outcomes. A Benchmark tab with the three-arm table (Reminders only, Malaffi status only, Tasleem), including the honest line: staff alerts per 100 patients 38.5 vs 66.4, "more alerts, each naming one person and one action; they are the stalls status-only monitoring misses".

### 9. Live simulator
"Send real-world events and watch Tasleem react." Scenario cards (for example "Malaffi says completed, colonoscopy never happened" and "GI centre sends the report"), a feed of arriving messages with sources ("Malaffi (FHIR)", "Malaffi (HL7 REF)", "Lab (HL7 ORU)", "Sahatna (patient)"), and an HL7 card with a monospace message and an ACK where "MSA|AA" is highlighted green.

### 10. Patient companion (mobile 390 px, Arabic and English)
Styled as a page inside a national patient app: header "My care steps", soft surfaces, large touch targets, an EN/عربي toggle. Arabic version, right-to-left: message "تم إرسال التحويل. ستتواصل معك العيادة لحجز الموعد."; a consent card ("Allow your care team to follow up with you in this app"); "Something getting in the way?" with multi-select chips (أشعر بالخوف أو القلق، لا يوجد من يرافقني أو يوصلني، صعوبة في المواصلات …) and a free-text box; the after state "Your care team will contact you."; a "Before your test: three quick questions" card. Never any clinical values or results. Footer: "Sample screen. In production this would live inside the Sahatna app."

### 11. Reviewer tour panel
A compact, dockable panel at the bottom right: "Step 1 of 7", one instruction, "Take me there", Back and Next.

## Also deliver
A one-page design-system sheet: colour tokens, type scale, spacing, the five provenance badges, stall chips by level (1 amber, 2 orange, 3 red), rule chips, the dual progress bar in its three states (no gap, gap, closed), buttons (including disabled with a reason), and empty, loading and error states.

## Don't
- Don't invent numbers, customers, partners, testimonials or pricing beyond what is written here.
- Don't add screens beyond these.
- Don't show a Close button that skips the outcome dialog, or anything that sends to a patient without a person clicking Send.
