# AI-user simulation: personas with a job to be done, using the real product

Run on 18 Nov 2026. Agents: `groq:openai/gpt-oss-120b`. 11 personas, 2 rounds, 217 API calls against one shared synthetic world. Reproduce: `cd backend && python -m tasleem.bench.personas --provider groq`.

Method (after multi-agent simulators such as MiroFish): each AI user has a profile, incentives and a job to be done, keeps a memory of what it did, and acts only through the API the web app uses, signed in as its own demo user. Patients act first in each round, staff then see what patients reported, then the scheduler moves time on. **Pass/fail comes from deterministic checks on API state, never from the models' opinions.** The verdicts are each persona's own words and are kept for friction, not as proof.

## Deterministic checks: 31 of 36 passed

| Who | Check | Result | Detail |
|---|---|---|---|
| nav-aisha | navigator step for p-noura is in the navigator's work list | **FAIL** | Reach the patient, record what got in the way, and rebook. |
| nav-aisha | navigator step for p-yousef is in the navigator's work list | **FAIL** | The patient told us what got in the way. Review the suggestion and confirm it. |
| p-john | an open patient report is in an action list of the person who must act | **FAIL** | must act: ['coord-sara']; sees it as an action: nobody |
| p-john | 'done elsewhere' report reaches a clinician who can accept the evidence | **FAIL** | owner=coord-sara; clinicians who see it: [] |
| p-yousef | an open patient report is in an action list of the person who must act | **FAIL** | must act: ['dr-fatima', 'nav-aisha']; sees it as an action: nobody |
| all | R1 one named owner (p-ahmed) | pass | dr-fatima |
| all | R6 audit chain intact (p-ahmed) | pass | 18 events checked |
| all | R1 one named owner (p-fatma) | pass | dr-fatima |
| all | R6 audit chain intact (p-fatma) | pass | 11 events checked |
| all | R1 one named owner (p-grace) | pass | dr-salma |
| all | R6 audit chain intact (p-grace) | pass | 17 events checked |
| all | R1 one named owner (p-noura) | pass | dr-fatima |
| all | R6 audit chain intact (p-noura) | pass | 19 events checked |
| all | R1 one named owner (p-hamad) | pass | dr-fatima |
| all | R6 audit chain intact (p-hamad) | pass | 6 events checked |
| all | R1 one named owner (p-rajesh) | pass | dr-fatima |
| all | R6 audit chain intact (p-rajesh) | pass | 16 events checked |
| all | R1 one named owner (p-khalfan) | pass | dr-salma |
| all | R6 audit chain intact (p-khalfan) | pass | 5 events checked |
| all | R1 one named owner (p-sunita) | pass | dr-salma |
| all | R6 audit chain intact (p-sunita) | pass | 23 events checked |
| all | R1 one named owner (p-leila) | pass | dr-salma |
| all | R6 audit chain intact (p-leila) | pass | 14 events checked |
| all | R1 one named owner (p-yousef) | pass | dr-fatima |
| all | R6 audit chain intact (p-yousef) | pass | 11 events checked |
| all | R1 one named owner (p-john) | pass | coord-sara |
| all | R6 audit chain intact (p-john) | pass | 4 events checked |
| all | no server errors during the run | pass | none |
| coord-sara | navigator step for p-john is in the navigator's work list | pass | The patient told us what got in the way. Review the suggestion and confirm it. |
| coord-sara | metrics show verified completion next to Malaffi 'completed' | pass | verified=2 malaffi=4 |
| coord-sara | no open case without an owner | pass | 0 |
| dr-salma | distress (p-sunita) is in the clinician's distress section | pass | to=dr-salma |
| p-fatma | an open patient report is in an action list of the person who must act | pass | must act: ['dr-fatima']; sees it as an action: ['dr-fatima'] |
| p-noura | an open patient report is in an action list of the person who must act | pass | must act: ['dr-fatima', 'nav-aisha']; sees it as an action: ['dr-fatima'] |
| p-rajesh | companion message tells him what happens next while the case is open | pass | Thank you for attending. Your care team will follow up. |
| p-sunita | distress (p-sunita) routed to a clinician | pass | to=dr-salma |

## Each persona: job to be done and verdict

### Noura A., 52 (patient)

**Job to be done.** When I am scared and cannot get there, I want to tell someone in Arabic and get practical help, so I can still have the test.

**Verdict:** job done: no, score 3/5. "التطبيق سمح لي أبلغ مخاوفي وأعطي موافقتي، لكن لسه ما وصلني حل عملي."

- Worked: تمكنت من إبلاغ الفريق بخوفي من التخدير; أعطيت الموافقة لتسهيل إعادة الحجز
- Friction: ما زال الانتظار دون رد واضح; لم يتم توفير وسيلة نقل أو بديل فوري

What they did:

- R1: tell_care_team case_da6348dd15c5 {"codes": ["FEAR", "NO_ESCORT", "TRANSPORT"], "text": "أنا خايفة من التخدير وما عندي أحد يوصّلني للمنزل بعد الفحص. أحتاج مساعدة لإعادة الحجز أو بديل."} -> 200 ok. أحتاج أبلغ الفريق بخوفي من التخدير وما عندي أحد يوصّلني للمنزل بعد الفحص.
- R1: give_consent None {} -> 404 {"error": {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}}. أعطي موافقتي حتى يقدروا يساعدوني في إعادة الحجز أو بديل
- R1: give_consent case_da6348dd15c5 {} -> 200 ok. أعطي موافقتي لتسهيل إعادة الحجز أو بديل
- R2: finished. قمت بالإبلاغ عن مخاوفي ومنحت الموافقة، الآن أنتظر رد الفريق

### Sunita R., 53 (patient)

**Job to be done.** When something feels wrong with my body, I want a clinician to know today, so I am safe.

**Verdict:** job done: yes, score 4/5. "I was able to alert the care team and give consent quickly, but the first consent attempt was confusing."

- Worked: tell_care_team request succeeded; give_consent succeeded
- Friction: initial give_consent call returned 404 causing a brief delay

What they did:

- R1: tell_care_team case_e867ec7ffba2 {"codes": ["OTHER"], "text": "I have started bleeding and severe cramps since yesterday, I'm worried and need help before my colonoscopy."} -> 200 ok. I need to alert the care team about my bleeding and cramps urgently.
- R1: give_consent None {} -> 404 {"error": {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}}. I need to give consent so the care team can act quickly on my bleeding and cramps
- R1: give_consent case_e867ec7ffba2 {} -> 200 ok. I need to give consent so the care team can act on my bleeding and cramps urgently.
- R2: finished. I have alerted the care team and given consent, now I will finish.

### Fatma N., 70 (patient)

**Job to be done.** When the app asks me things, I want a person to call me instead, so I do not have to use the phone.

**Verdict:** job done: no, score 2/5. "I asked for a call and now I’m just waiting, not sure when I’ll hear back"

- Worked: Able to submit a callback request
- Friction: No immediate phone call, still waiting for contact; App suggests booking an appointment instead of callback

What they did:

- R1: tell_care_team case_d5918d8b08bd {"codes": ["WANTS_CALLBACK"], "text": "Please call me to discuss the result, I cannot use the app."} -> 200 ok. I need a person to call me about my result
- R1: finished. I have already asked for a callback, now I will wait for someone to call me
- R2: finished. I have asked for a callback and will wait for the call

### John D., 59 (patient)

**Job to be done.** When I have already had the test abroad, I want to tell them once and send the report, so they stop chasing me and my record is right.

**Verdict:** job done: no, score 2/5. "I told them I already had the colonoscopy, but they still keep asking me to book a visit."

- Worked: Able to send DONE_ELSEWHERE request and receive 200 OK
- Friction: Case remains open and still prompts to book a visit; No closure after reporting test done elsewhere

What they did:

- R1: tell_care_team case_d4fa0450ff0b {"codes": ["DONE_ELSEWHERE"], "text": "I had a colonoscopy three weeks ago in Kochi, India while visiting family. I have the PDF report and can upload it. Please update my record and stop the follow‑up requests."} -> 200 ok. I need to tell them I already had the colonoscopy abroad and send the report so they stop chasing me.
- R1: finished. I've already told them I had the colonoscopy abroad and offered the report, so I just want to stop now.
- R2: finished. I already told them about the colonoscopy abroad, so I just want to stop now.

### Rajesh K., 58 (patient)

**Job to be done.** When I think I am done, I want to know whether anything is still needed, so nothing is missed.

**Verdict:** job done: yes, score 4/5. "It let me know I'm all set and nothing else is needed."

- Worked: Clear thank-you message; Shows no open requests; Consent recorded automatically
- Friction: Case still listed as 'open' which could be confusing

What they did:

- R1: give_consent None {} -> 404 {"error": {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}}. I think I’m done, but need to confirm if anything else is required.
- R1: give_consent case_4c835eafba8a {} -> 200 ok. I should give consent so the care team can follow up.
- R1: finished. Looks like everything's done, no open requests.
- R2: finished. Looks like everything's done, no open requests.

### Yousef H., 47 (patient)

**Job to be done.** When the appointment clashes with my shift, I want to move it easily, so I do not lose pay or skip it.

**Verdict:** job done: no, score 2/5. "I told them I can't make the weekday slot, but I'm still stuck waiting for a new appointment."

- Worked: Able to send a message to the care team about shift conflict
- Friction: No immediate alternative date offered; Must wait for care team response

What they did:

- R1: tell_care_team case_4bce321955c1 {"codes": ["TIME_OR_WORK"], "text": "أنا لا أستطيع الحضور في هذا الموعد لأنه يتعارض مع دوامي ولا يمكنني فقدان أجر اليوم. أحتاج إلى موعد في عطلة نهاية الأسبوع أو في المساء إذا أمكن."} -> 200 ok. I need to tell the care team that my shift prevents me from attending the weekday colonoscopy and I want a weekend or evening slot.
- R1: finished. I have already informed the care team about my shift conflict, so I’ll stop for now.
- R2: finished. I’ve already told the care team about my shift conflict, so I’ll stop and wait for their response.

### Aisha, care navigator (org-ghaf) (navigator)

**Job to be done.** When a patient misses an appointment or replies with a problem, I want to know who to call first and what is in the way, so I can rebook them this week.

**Verdict:** job done: yes, score 4/5. "When there are no cases, Tasleem tells you that clearly, but it could be more helpful when cases actually appear."

- Worked: Clear indication that work list is empty; No extra navigation needed
- Friction: Had to finish twice to exit

What they did:

- R1: finished. No cases to handle right now, so I’ll finish for now.
- R2: finished. No cases to handle, finishing

### Dr. Fatima, family physician (org-ghaf) (family physician)

**Job to be done.** When one of my positive-FIT patients is stuck, I want to see who, why, and the one thing I must do, so I can act between patients without chasing anyone.

**Verdict:** job done: yes, score 5/5. "Tasleem tells me exactly who, why, and what to do for a stuck FIT case—exactly what I need between patients."

- Worked: Shows who is responsible; Shows why the case is stalled (referral rejected); Provides a single clear next action

What they did:

- R1: opened case case_0b0c21d60192. Need to see Ahmed's case details to fix the rejected referral and resend it
- R1: opened case case_0b0c21d60192. Need to see Ahmed's case details to understand why the referral was rejected and fix it
- R1: opened case case_0b0c21d60192. Need to see Ahmed's case details to fix the rejected referral.
- R2: opened case case_0b0c21d60192. Need to see Ahmed's referral details to fix the rejection
- R2: opened case case_0b0c21d60192. Need to see Ahmed's case details to understand why the referral was rejected and fix it
- R2: opened case case_0b0c21d60192. Need to open Ahmed's case to see why the referral was rejected so I can fix it quickly

### Dr. Salma, family physician (org-samar) (family physician)

**Job to be done.** When a patient reports something worrying, I want it on top of my list today, so I can call them.

**Verdict:** job done: yes, score 4/5. "When a patient flags distress, Tasleem puts it front‑and‑center so I can act immediately."

- Worked: Distress case appears at top of my_work list; Next‑step reminder to call patient is clear; Quick logging of phone contact and distress resolution
- Friction: Second distress remains open, cluttering view; Barriers stay open after confirmation, requiring extra steps

What they did:

- R1: opened case case_e867ec7ffba2. Need to open Sunita's case to see her distress details before calling her urgently
- R1: log_contact case_e867ec7ffba2 {"channel": "phone", "result": "left_message"} -> 200 ok. Need to call Sunita urgently about her bleeding, so log a phone contact attempt
- R1: log_contact case_e867ec7ffba2 {"channel": "phone", "result": "reached"} -> 200 ok. I need to call Sunita urgently about her bleeding, so I’ll log a phone contact attempt as reached.
- R2: resolve_distress case_e867ec7ffba2 {"distress_id": "dis_7061b3658302", "note": "Called patient, discussed bleeding, advised urgent evaluation and provided reassurance."} -> 200 ok. I’ve called Sunita and need to record that I dealt with her distress now.
- R2: confirm_barrier case_e867ec7ffba2 {"barrier_id": "bar_c3ceaf8d3e70", "code": "FEAR"} -> 200 ok. Need to confirm Sunita's reported fear barrier before closing case
- R2: confirm_barrier case_e867ec7ffba2 {"barrier_id": "bar_b064f8a57fc0", "code": "FEAR"} -> 200 ok. Need to confirm Sunita's second reported barrier before closing the case

### Dr. Hessa, clinic lead (org-ghaf) (clinic lead)

**Job to be done.** When cases escalate to me, I want to see which are truly stuck and reassign them safely, so nothing is lost when a doctor is away.

**Verdict:** job done: no, score 3/5. "I can see what’s stuck, but the system still blocks me from reassigning cases safely."

- Worked: Escalated cases list shows stalls and barriers clearly
- Friction: Cannot offer handoff without being the current owner, blocking safe reassignment

What they did:

- R1: opened case case_0b0c21d60192. Need to see the details of Ahmed’s case to understand why the referral was rejected before reassigning.
- R1: offer_handoff case_0b0c21d60192 {"to": "dr-omar", "reason": "Referral rejected, need GI specialist to address required changes and resend"} -> 409 {"error": {"code": "R2_NOT_OWNER", "message": "Only the current owner or a coordinator can offer a handoff.", "details": {}}}. Referral for Ahmed was rejected and overdue; I’ll hand it off to a GI specialist to fix it.
- R1: opened case case_d5918d8b08bd. Need to inspect Fatma's case to understand why the handoff is pending and see the barrier.
- R2: opened case case_1d371e34bc64. Need to inspect Khalfan's case to see why it’s overdue before deciding on reassignment.
- R2: request_consult case_0b0c21d60192 {"to": "dr-omar", "question": "Please review the referral rejection for Ahmed S. and make the required changes to resend it."} -> 200 ok. Ahmed’s referral was rejected and overdue – need a GI specialist to fix it.
- R2: opened case case_d5918d8b08bd. Need to inspect Fatma's case to understand the pending handoff and barrier.

### Sara, programme coordinator (program coordinator)

**Job to be done.** When I report to the programme, I want verified completion and where people are lost by clinic and language, so I can direct resources.

**Verdict:** job done: no, score 2/5. "It shows the stalls but lacks the clinic and language breakdown we need."

- Worked: Provides overall stall counts and case details; Shows open and escalated cases; Includes programme metrics
- Friction: No clinic information for stalled cases; No language breakdown of where patients are lost; Cannot directly see verified completion numbers by clinic/language

What they did:

- R1: opened case case_0b0c21d60192. I need more detail on a stalled case to understand why it’s not completed, so I’ll open one of them.
- R1: opened case case_eaf337336330. I need more detail on the stalled case for Grace to see clinic and language info
- R1: opened case case_0b0c21d60192. Need clinic and language details for stalled case Ahmed to see where lost
- R2: opened case case_0b0c21d60192. I need clinic and language details for the stalled case Ahmed to see where the loss occurred.
- R2: opened case case_0b0c21d60192. I need the clinic and language details for the stalled case Ahmed to see where the loss occurred
- R2: opened case case_0b0c21d60192. I need clinic and language details for the stalled case Ahmed to see where the loss occurred

## Refused or failed calls

Refusals are often correct (a rule protecting the patient). Each is listed so a human can judge.

- R1 `p-noura` give_consent: POST /v1/me/cases/-/consent -> 404 {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}
- R1 `p-sunita` give_consent: POST /v1/me/cases/-/consent -> 404 {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}
- R1 `p-rajesh` give_consent: POST /v1/me/cases/-/consent -> 404 {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}
- R1 `dr-hessa` offer_handoff: POST /v1/cases/case_0b0c21d60192/handoff -> 409 {"code": "R2_NOT_OWNER", "message": "Only the current owner or a coordinator can offer a handoff.", "details": {}}

Turns with no model decision (rate limit or invalid reply): 0.
