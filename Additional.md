# Additional.md — Organizer guidance that every build decision must respect

Source of truth for what the Future Health Digital Innovation Challenge 2026 organizers, ADPHC experts and Inception mentors told participants, plus the submission rules. Read this before starting any task. If a backlog item conflicts with this file, this file wins; raise the conflict instead of building around it.

Challenge: **Population Health · Challenge 05 "Closing the Screening-to-Care Loop"**.
Deadline: **20 Nov 2026, 11:59 PM IST** (aim to submit by the afternoon of 20 Nov IST).

Sources:
- V1: "From Prototype to Production: Agentic AI Lab for Protecting Brain Health Earlier" (Dr. Nance Elena, Inception 42, 4 Nov 2026).
- V2: "From Idea to Pilot: Building and Benchmarking Healthcare AI" (Nabeel Akhtar Sayed, Inception 42, with Hadeel from DoH, 3 Nov 2026).
- V3: "Challenge Explainer: Population Health" (ADPHC experts, 29 Oct 2026).
- V4: "From Idea to Impact: Designing, Building and Pitching a Winning AI Agent Use Case" (Stephan Geyer, AI Lead, Microsoft Innovation Hub Dubai, with the Hack2skill host, 16 Nov 2026). See section 6.
- Rules, FAQ and the submission form on Hack2skill.

---

## 1. What the problem owner asked for (V3, Ms. Houra Hassan, head of screening, ADPHC)

The journey she described. Our product must visibly follow it:

1. Record the screening result and **link it to the personal health record**.
2. **Prioritize higher-risk findings.** She named hypertension, obesity, diabetes and cancer.
3. **Refer to the appropriate service, taking the person's insurance coverage and network into account.**
4. **Automated reminders and care navigation** so the person attends and completes the next step.
5. **Track the outcome**: did they receive the service, how quickly, was treatment completed, who is at risk of being lost to follow-up.

Her goal, in her words: no actionable result should be left without a clear next step, a responsible team and a documented outcome. AI helps identify delays and prioritize follow-up **"while clinical teams remain central to decisions and care."**

Abu Dhabi context she gave:
- "We are not starting from zero": **Malaffi** (unified health information exchange) and **Sahatna** (patient app) already exist. Build on them, don't replace them.
- Everyone is insured, but through different schemes and networks.

## 2. DO

### Product
- **DO** build on Malaffi and Sahatna. Read referral and result events from Malaffi (DoH Circular 210/2026 requires every facility to send all referrals to Malaffi as HL7 REF messages). **Never build a competing referral exchange or EHR.**
- **DO** make the patient side **mobile-first**, designed so it could be adopted inside Sahatna (V3: "From our side, it's a mobile application").
- **DO** default the case owner to the patient's **family physician** (V3: every resident is to have one; flagged cases should link back to them).
- **DO** make solutions "easy to replicate and integrate within any health platform" (V3). Use FHIR R4, SNOMED CT and LOINC at the edges.
- **DO** cover adults **18 to 75** (V3 Q&A: the age range for this challenge).
- **DO** support Arabic and English at minimum. Regional language consideration is welcome (V2).
- **DO** reduce clinic load. DoH supports moving non-urgent work to remote or asynchronous consults (V2). That is our consult bridge.
- **DO** prefer empowerment over penalties. ADPHC currently threatens to block insurance cards after 3 months of SMS reminders and says it does not want to rely on that (V3).

### Architecture and AI (V1, V2)
- **DO** define the problem first, then split the workflow into steps, then decide where AI belongs. Sometimes plain automation is enough (V1).
- **DO** use **deterministic rules and scripted code for every decision, score and timer**. The LLM only drafts, translates, summarizes or suggests (V1: "don't leave the judgment to the AI").
- **DO** gate every step: consent, missing data, sudden or urgent change (escalate, don't continue the routine flow), clinician approval (V1).
- **DO** flag missing or wrong inputs instead of guessing. Distinguish blocking gaps from ones to request later (V2).
- **DO** visibly separate in the UI: **recorded facts**, **computed results** and **AI-generated text** (V1).
- **DO** keep a human in the loop for every clinical or exceptional decision (V1, V3).
- **DO** build privacy and consent in from the start. "It's not a side note. It's one of the things you'll be scored on" (V3 host).

### Evidence and testing (V2, the most important advice for winning)
- **DO** write the test cases **before** coding. For each: input, expected answer, actual answer, which component failed (V2).
- **DO** benchmark the **most safety-critical component** on hard cases (missing values, wrong values, out-of-order events), not only easy ones. V2's winning team showed 100% emergency detection. Our equivalents: **zero unsafe closures** and **every distressed patient reply routed to a human**.
- **DO** compare against **existing solutions** and against a **realistic baseline** ("Malaffi referral status only"), not a straw man (V2: judges will compare you to what exists).
- **DO** document every tested case in the repo and the submission. "If you do a lot of work that is their job to do, and you have mentioned it, it adds points for you" (V2).
- **DO** be transparent about data: say what is synthetic, how it was generated and why (V2). Synthetic data is acceptable (DoH, V2 and V1).
- **DO** state limits plainly: software behavior is proven by tests; patient outcomes are not proven.
- **DO** run a review checkpoint after each milestone before adding features (V2).
- **DO** simplify the code and documentation before submitting (V2).

### Framing (V2)
- **DO** answer in one sentence: *"We help WHO complete WHAT task using WHAT information."*
  Ours: **Tasleem helps family physicians, navigators and ADPHC screening teams turn every actionable IFHAS result into a verified outcome, using the referral and result events Malaffi now carries and the patient's Sahatna app.**
- **DO** lead with a recognizable patient failure (the fictional "Noura" story; renamed from Mariam on 16 Nov to avoid clashing with the workshop's "Dr. Mariam"), not with AI or architecture.

### Demo and submission
- **DO** ship a **live link** that reviewers can test hands-on with **"Continue as Guest"** or published demo credentials (V1 and V3: reviewers test software hands-on; template slide 11 requires guest access or credentials).
- **DO** pre-seed clickable synthetic cases so reviewers can see each failure and recovery path in under a minute.
- **DO** keep the demo video **under 3 minutes** (form limit). Our script targets 2:50.
- **DO** use the **mandatory 16-slide template**, exported as a PDF of 5 MB or less, and answer every heading explicitly.
- **DO** use the judging criteria's own words in the text fields. The form shows an automated "AI Evaluation Score".
- **DO** declare every data source and any pre-existing IP.
- **DO** keep every team member active on the event platform (inactivity can disqualify).

## 3. DON'T

- **DON'T** build a chatbot that gives medical advice or discloses abnormal results by text. IFHAS (clause 4.9.2.3) requires abnormal findings to be discussed with the person present; the app invites, it doesn't diagnose.
- **DON'T** let AI close a case, set urgency or priority, change a clinical plan, or declare anyone safe.
- **DON'T** build a disease-risk prediction or no-show prediction model. It needs clinical data we don't have and can't be validated from home.
- **DON'T** count administrative progress as care. A booked appointment is not an attended one; a closed referral is not a colonoscopy; an informed refusal is never a completed procedure.
- **DON'T** stop the whole flow for a missing field that isn't needed for the current decision (V2). Flag it and continue.
- **DON'T** build a 10-page UI. V2's winner was a single page; depth and benchmarks counted, not screens.
- **DON'T** claim real-world outcomes, ROI or deployment from a simulation.
- **DON'T** use models or datasets whose licence forbids commercial use without saying so (V1).
- **DON'T** pitch an emirate-wide operating system. Pitch a focused layer beside Malaffi and Sahatna.
- **DON'T** require platform lock-in. Azure is offered but optional (V3: "not specific to any one platform").
- **DON'T** add features after the review checkpoint on 19 Nov unless they fix a broken demo path.

## 4. Judging criteria (no weights published). Every feature should serve at least one

1. Health impact and clinical relevance
2. Technical depth and architecture
3. Working solution and demo quality
4. Responsible AI, safety and data governance
5. Scalability and deployment readiness
6. Commercial viability and path to pilot

Panel: one standard panel across challenges. DoH, co-creators (Future Health, Microsoft, Inception, MBZUAI), nominated providers and clinicians, covering clinical, commercial, regulatory, AI, scientific and academic views (V3).

## 5. Challenge 05 "should" items. Every release must show all six

1. Case visibility across providers
2. Ownership and service levels
3. Patient communication and reassurance
4. Cross-provider clinical consultation
5. Human-governed escalation and closure
6. Measures

## 6. V4 workshop (16 Nov 2026): what changes for us

Source: the recording (slides read frame by frame, speech transcribed locally, live chat downloaded). Speaker guidance is advice; host answers are organizer rules.

### Organizer answers (host, Hack2skill). These are rules
- **Deadline is 20 Nov.** Stated at 05:31 and 64:46, and re-checked on the audio at 55:23. Resubmitting before the deadline is allowed. Review runs 20 to 30 Nov; selected teams hear by email (said "after 26 Nov"); the award is at GITEX in December.
- **Prizes:** 50k / 35k / 20k USD, plus a readiness assessment and a possible route beyond the challenge.
- **The submission needs a detailed video showing the whole workflow.** That is what they evaluate first.
- **The prototype doesn't have to be fully functional.** It must solve the chosen problem and show a clear path for the rest.
- **Logins are fine** if credentials are provided. A click-through demo guide is fine if the form has somewhere to upload it, but always include the video in case they can't access the live app.
- **AI isn't mandatory.** A technology solution that solves the challenge qualifies.
- **The judging criteria are the six in section 4**, read out again in the same order.

### Stephan's method (Microsoft Innovation Hub). Use it in the deck and video
- **Winning teams show three things:** a real problem (a priority health need, not a technology looking for a use); a real user ("one person, one moment"); and proof you can see ("a working prototype, honest limits and a measurable outcome").
- **Steps:**
  1. Person.
  2. Five whys down to the root cause ("if your first sentence names a technology, back up").
  3. How-might-we.
  4. Agent loop: sense → predict → act → hand off to a clinician.
  5. Stress-test on desirability, feasibility and viability.
  6. Measurable outcome: how do you measure it, what is it now, what should it be, what is the difference worth.
  7. Bulls-eye scope: Now (the demo), Next (the pilot), Later (scale). "Not in the centre? Not in the demo."
  8. Story.
  9. One wow moment.
- **Story in four beats:** Problem → User → Solution → Outcome. "Poke the pain, sprinkle the magic." Tell the persona's story twice, once without the product and once with it, and stay in the pain before the fix.
- **One-sentence test:** "For [user] who [problem], our agent [does what], so that [measurable outcome]."
- **Lead with value, not features.** Pair each mechanism with what it means for the person. Example: "clinician review and audit trail" becomes "Dr. Mariam stays in charge of every clinical decision".
- **In 3 minutes,** spend most of the time showing rather than telling. End with a clear ask and a path to pilot, never with "hope you like it". Don't open with scale.
- **Demo checklist:**
  - Script the happy path: every click and every line, the same data every run, rehearsed three times with a timer.
  - Record a clean backup.
  - Cut features, not the story. Stop at the wow, then prove it.
  - Write down your assumptions and limits, know your data and safeguards, and have the pilot step ready.
- **Six questions to answer first, one per criterion:**
  1. Who exactly is this for?
  2. Why an agent and not a chatbot? Show what it senses, decides and does.
  3. Does it run end to end?
  4. What happens when it is wrong?
  5. What would it take to deploy: data, integration, and who operates it?
  6. What happens after you submit: one concrete next step with one partner?
- **Path to pilot:** judges want to see you've thought it through. Name the starting cohort and give your reasons for it. A letter of interest helps but isn't required.
- **Other answers from Stephan:**
  - Stick to one persona; pick the one with the biggest pain.
  - Don't rest a solution on training a model ("takes months") or on training with users' data (PII limits).
  - Behavioural outcomes still need KPIs.
  - For OCR, use document or form recognition, not plain OCR.

### Implications for Tasleem
- **His worked example is ours, one step earlier.** It covers a screening invite, a personal reason, one-tap booking, and a flagged result reaching "Dr. Mariam, family physician". Many teams will copy that template, which only covers the invitation. Our difference is everything after the referral, which his example never reaches. Say that in one line.
- **Rename the fictional patient in our story.** Judges have just seen "Dr. Mariam" as the clinician, and our patient is also "Mariam". Do it in the deck, video and seed data, keeping the synthetic-data labels.
- **One sentence:** "For family physicians whose positive-FIT patients stall silently after referral, Tasleem watches Malaffi events and clinical evidence, gives every case a named owner and escalates stalls, so that every stalled journey reaches a named person within days." Proof on the synthetic cohort: 98.5% of failures flagged versus 70% for status-only monitoring, median 4 days versus 14, and zero false "done".
- **Wow moment:** a referral marked COMPLETED in Malaffi, while Tasleem shows no colonoscopy was done, names the owner and escalates. Show it, then prove it with the benchmark chart.
- **Poke the pain first:** about 20 seconds of today's version ("Malaffi says completed; nobody notices; diagnosed later"), then replay the same journey with Tasleem.
- **Bulls-eye:**
  - Now: the FIT-positive colonoscopy loop.
  - Next: one Abu Dhabi family-medicine network plus one GI centre, measuring completed colonoscopies and days to procedure.
  - Later: the other IFHAS findings (hypertension, diabetes, obesity).
- **"Why not a chatbot":** it senses Malaffi and clinical events, decides with deterministic rules, and acts by assigning, escalating and messaging. A human closes every case.
- **The video must show the live app running,** not slides over a recording. Provide guest access or published credentials, plus a short click-through guide if the form allows it.

### Teams on the same challenge (from the live chat)
- A Nigerian team building a WhatsApp AI bot for the screening-to-care loop, in Hausa and English.
- A team building a three-surface clinical decision-support system on Microsoft Foundry in Azure UAE North (citizen app, clinician verification queue, ADPHC public-health command centre).
- Our edges against both: verified evidence instead of status, the benchmark, and the hard-case suite.
