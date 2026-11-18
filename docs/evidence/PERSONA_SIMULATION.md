# AI-user simulation: personas with a job to be done, using the real product

Run on 18 Nov 2026. Agents: `groq:openai/gpt-oss-120b`. 11 personas, 2 rounds, 480 API calls against one shared synthetic world. Reproduce: `cd backend && python -m tasleem.bench.personas --provider groq`.

Method (after multi-agent simulators such as MiroFish): each AI user has a profile, incentives and a job to be done, keeps a memory of what it did, and acts only through the API the web app uses, signed in as its own demo user. Patients act first in each round, staff then see what patients reported, then the scheduler moves time on. **Pass/fail comes from deterministic checks on API state, never from the models' opinions.** The verdicts are each persona's own words and are kept for friction, not as proof.

## Summary: what the AI users found, and what was fixed

The same 11 personas ran twice on `groq:openai/gpt-oss-120b` (free tier): once on the code as it was, once after the fixes. The run before the fixes is kept in [data/persona_simulation_before_fixes.md](data/persona_simulation_before_fixes.md).

| | Before the fixes | After |
|---|---|---|
| Deterministic checks | 31 of 36 passed (5 failures) | **42 of 42** passed (6 checks added for the new findings) |
| AI users who said their job got done | 5 of 11, one of them wrongly (Rajesh believed he was finished) | 7 of 11 (one gave no verdict) |

| Found by | What failed | Fix | Test |
|---|---|---|---|
| Checks (scripted and AI runs) | Noura missed her colonoscopy; the case said **Aisha (navigator)** must rebook her, but Aisha's work list was **empty** | A navigator next step is now a task in the navigator's list | P1 |
| Checks | A patient's reply (Yousef: shift clash) waited for someone to confirm the AI suggestion, but was **in nobody's work list** | Unconfirmed replies go to the navigator's list (a person confirms, R5) | P2 |
| Checks | John (no family physician) said the test was **done abroad**; the report and the follow-up task went to the **programme coordinator**, who cannot accept evidence (R3) | "Clinician" tasks resolve to a clinician, never a non-clinician owner; a clinician sees "done elsewhere" at once | P3 |
| Rajesh's verdict | "It let me know I'm all set", while no colonoscopy report exists | The "attended" message now says the follow-up is not finished and the doctor will contact him | P5 |
| John's, Fatma's verdicts | John was still told to book a visit; Fatma did not know her call request arrived | The companion acknowledges any open request and says who acts next | P6 |
| Dr. Hessa's refused call | The clinic lead could see a case escalated to her but was **refused the handoff** | The person a stall is escalated to may offer a handoff; the owner stays owner until it is accepted (R2 unchanged) | P7 |

**Still open (honest limits).**
- Noura and Yousef still say "I still need real help". That is expected: Tasleem routes the problem to a named navigator, and a person then has to call and rebook. The simulated week is too short for that.
- There is no way for a patient to upload a report from another hospital. John's verdict ("after I sent the report") is the model's assumption. Document upload with recognition is the next AI feature in [PRODUCT_FIT_ANALYSIS.md](../product/PRODUCT_FIT_ANALYSIS.md).
- Sara still asks for more clinic and language detail. The Programme page filters by clinic and language; she wants a side-by-side comparison, which is not built.
- The agents are language models acting out personas, not real people. They find gaps in routing and wording; they cannot show whether real clinicians or patients would adopt the product.

## Deterministic checks: 42 of 42 passed

| Who | Check | Result | Detail |
|---|---|---|---|
| all | R1 one named owner (p-ahmed) | pass | dr-fatima |
| all | R6 audit chain intact (p-ahmed) | pass | 23 events checked |
| all | R1 one named owner (p-fatma) | pass | dr-fatima |
| all | R6 audit chain intact (p-fatma) | pass | 11 events checked |
| all | R1 one named owner (p-grace) | pass | dr-salma |
| all | R6 audit chain intact (p-grace) | pass | 17 events checked |
| all | R1 one named owner (p-noura) | pass | dr-fatima |
| all | R6 audit chain intact (p-noura) | pass | 25 events checked |
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
| dr-hessa | clinic lead can reassign the escalated case (p-khalfan) | pass | {"allowed": true} |
| dr-salma | distress (p-sunita) is in the clinician's distress section | pass | to=dr-salma |
| nav-aisha | navigator step for p-noura is in the navigator's work list | pass | Reach the patient, record what got in the way, and rebook. |
| nav-aisha | navigator step for p-yousef is in the navigator's work list | pass | The patient told us what got in the way. Review the suggestion and confirm it. |
| p-fatma | an open patient report is in an action list of the person who must act | pass | must act: ['dr-fatima']; sees it as an action: ['dr-fatima'] |
| p-fatma | companion acknowledges the open request and does not repeat the old prompt | pass | شكراً لك. وصل طلبك إلى فريق طبيبك وسيتصلون بك. |
| p-john | an open patient report is in an action list of the person who must act | pass | must act: ['coord-sara']; sees it as an action: ['coord-sara'] |
| p-john | 'done elsewhere' report reaches a clinician who can accept the evidence | pass | owner=coord-sara; clinicians who see it: ['dr-hessa'] |
| p-john | companion acknowledges the open request and does not repeat the old prompt | pass | Thank you. A doctor will review the test you had elsewhere. Please keep the report. You do not need to book anything for now. |
| p-noura | an open patient report is in an action list of the person who must act | pass | must act: ['dr-fatima', 'nav-aisha']; sees it as an action: ['dr-fatima', 'nav-aisha'] |
| p-noura | companion acknowledges the open request and does not repeat the old prompt | pass | شكراً لإخبارنا. وصلت رسالتك إلى فريق الرعاية وسيتواصلون معك للمساعدة. |
| p-rajesh | companion says the follow-up is not finished while no report exists | pass | Thank you for attending. Your follow-up is not finished yet: we are waiting for the report from the clinic, and your doctor will contact you about it. You do no |
| p-sunita | distress (p-sunita) routed to a clinician | pass | to=dr-salma |
| p-sunita | companion acknowledges the open request and does not repeat the old prompt | pass | Thank you for telling us. A doctor has been told and will contact you. |
| p-yousef | an open patient report is in an action list of the person who must act | pass | must act: ['dr-fatima', 'nav-aisha']; sees it as an action: ['nav-aisha'] |
| p-yousef | companion acknowledges the open request and does not repeat the old prompt | pass | شكراً لإخبارنا. وصلت رسالتك إلى فريق الرعاية وسيتواصلون معك للمساعدة. |

## Each persona: job to be done and verdict

### Noura A., 52 (patient)

**Job to be done.** When I am scared and cannot get there, I want to tell someone in Arabic and get practical help, so I can still have the test.

**Verdict:** job done: no, score 2/5. "أخبروا الفريق لكن ما زلت أحتاج مساعدة فعلية للوصول للمنظار"

- Worked: التواصل بالعربية; إرسال رسالتك للفريق
- Friction: لم يتم توفير وسيلة نقل بعد; الانتظار دون رد فوري

What they did:

- R1: tell_care_team case_13a570be1d6c {"codes": ["FEAR", "NO_ESCORT", "TRANSPORT"], "text": "أنا خايفة من التخدير وما عندي أحد يوديني ويرجعني للمنزل، أحتاج مساعدة."} -> 200 ok. أحتاج أبلغ فريق الرعاية بخوفي وعدم وجود مرافق أو وسيلة نقل.
- R1: give_consent case_13a570be1d6c {} -> 200 ok. أعطي موافقتي للمتابعة حتى يتواصلوا معي
- R1: finished. أنتظر رد فريق الرعاية الآن
- R2: finished. أنتظر رد فريق الرعاية الآن

### Sunita R., 53 (patient)

**Job to be done.** When something feels wrong with my body, I want a clinician to know today, so I am safe.

**Verdict:** job done: yes, score 4/5. "The app got my urgent message to a doctor quickly, but I’m still waiting for the call back today."

- Worked: tell_care_team; give_consent
- Friction: still waiting for the callback, no immediate contact

What they did:

- R1: tell_care_team case_f3074b42fd43 {"codes": ["WANTS_CALLBACK", "OTHER"], "text": "Since yesterday I have started bleeding and severe cramps. I am very worried and need a clinician to contact me today before my colonoscopy appointment next week."} -> 200 ok. I need a doctor to know I’m bleeding and have cramps right now, please call me back today.
- R1: give_consent case_f3074b42fd43 {} -> 200 ok. I need to give consent so the doctor can contact me today.
- R1: finished. Doctor has been notified, I’ll wait for a callback today.
- R2: finished. Doctor has been notified, I’ll wait for a callback today

### Fatma N., 70 (patient)

**Job to be done.** When the app asks me things, I want a person to call me instead, so I do not have to use the phone.

**Verdict:** job done: yes, score 4/5. "I just asked for a call and they said they will call me, that’s exactly what I needed."

- Worked: Requested callback easily; Consent step confirmed
- Friction: Had to navigate a few screens despite low digital literacy

What they did:

- R1: tell_care_team case_72a76916992f {"codes": ["WANTS_CALLBACK"], "text": "أريد مكالمة من فريق الرعاية لتحديد موعد ومناقشة النتيجة"} -> 200 ok. I need someone to call me to discuss the result and set an appointment.
- R1: give_consent case_72a76916992f {} -> 200 ok. I need to give consent so the care team can call me about my result.
- R1: finished. I have already requested a callback and given consent, so I’ll finish for now.
- R2: finished. I have already asked for a callback and given consent, so I will finish for now.

### John D., 59 (patient)

**Job to be done.** When I have already had the test abroad, I want to tell them once and send the report, so they stop chasing me and my record is right.

**Verdict:** job done: yes, score 4/5. "Finally got them to stop chasing me after I sent the report."

- Worked: Successfully sent the colonoscopy report via tell_care_team; Received confirmation message that a doctor will review the test and no further booking is needed
- Friction: Case remains listed as open with an unresolved request count

What they did:

- R1: tell_care_team case_983ac7ab50ef {"codes": ["DONE_ELSEWHERE"], "text": "I had a colonoscopy three weeks ago in Kochi, India. I have the PDF report and want it added to my record so I’m not chased for this test."} -> 200 ok. I need to tell them I already had the colonoscopy abroad and attach the report.
- R1: finished. I’ve already told the care team and attached the report, so I can finish now.
- R2: finished. I’ve already told the care team and attached the report, so I can finish now.

### Rajesh K., 58 (patient)

**Job to be done.** When I think I am done, I want to know whether anything is still needed, so nothing is missed.

**Verdict:** job done: yes, score 4/5. "The app told me I don’t need to do anything now, which is clear, but I wish it was clearer that the follow‑up is still pending."

- Worked: Clear message that no further action is required now; Consent was recorded successfully
- Friction: Confusing that the app thanked me but said the follow‑up isn’t finished yet

What they did:

- R1: give_consent case_8c9193163719 {} -> 200 ok. Looks like I'm told to wait, but I need to give consent to finish the follow-up.
- R1: finished. Looks like I'm told to wait, nothing else needed now.
- R2: finished. Looks like I'm all set, nothing else needed now.

### Yousef H., 47 (patient)

**Job to be done.** When the appointment clashes with my shift, I want to move it easily, so I do not lose pay or skip it.

**Verdict:** job done: no, score 2/5. "They took my request but I still have to wait for a new slot."

- Worked: Message sent and acknowledged by care team
- Friction: No immediate appointment change, need to wait for response

What they did:

- R1: tell_care_team case_77c913ec95cf {"codes": ["TIME_OR_WORK"], "text": "موعد التنظير محجوز في يوم عمل ولا أستطيع الحضور بسبب دوامي. أحتاج تغيير الموعد إلى عطلة نهاية الأسبوع أو مساءً لتجنب فقدان الأجر."} -> 200 ok. أحتاج أبلغ فريق الرعاية أن الموعد يتعارض مع دوامي وأطلب تغيير للوقت.
- R1: finished. I’ve told the care team about the conflict and need to wait for them to get back, so I’ll stop for now.
- R2: finished. قمت بإبلاغ فريق الرعاية وأنتظر ردهم لتغيير الموعد، الآن سأتوقف مؤقتاً

### Aisha, care navigator (org-ghaf) (navigator)

**Job to be done.** When a patient misses an appointment or replies with a problem, I want to know who to call first and what is in the way, so I can rebook them this week.

**Verdict:** job done: yes, score 4/5. "Tasleem tells me exactly who to call and why, but I still have to chase them myself."

- Worked: Barrier confirmation for Noura A. was provided; Next step clearly indicated to reach patient and rebook; Message and call logs were recorded
- Friction: No direct rebooking action, must manually schedule; Repeated call attempts without answer

What they did:

- R1: confirm_barrier case_13a570be1d6c {"barrier_id": "bar_8edc639ee073", "code": "FEAR"} -> 200 ok. Need to confirm Noura's barrier before rebooking.
- R1: message_patient case_13a570be1d6c {"text": "نحن نتواصل معك لتحديد موعد جديد. هل يناسبك مكالمة الآن؟", "language": "ar"} -> 200 ok. Send Noura a quick Arabic message to arrange a call and rebook.
- R1: log_contact case_13a570be1d6c {"channel": "phone", "result": "no_answer"} -> 200 ok. Need to try calling Noura to get barrier details and rebook
- R2: log_contact case_13a570be1d6c {"channel": "phone", "result": "no_answer"} -> 200 ok. Need to call Noura to get barrier details and rebook
- R2: log_contact case_13a570be1d6c {"channel": "phone", "result": "no_answer"} -> 200 ok. I need to call Noura A. first; her confirmed barrier is fear of anesthesia and no escort/transport.
- R2: message_patient case_13a570be1d6c {"text": "نحن نحتاج لتحديد موعد جديد لكِ مع مراعاة مخاوفك بشأن التخدير وتوفير مرافق للعودة للمنزل. هل يمكنكِ الرد على هذه الرسالة لتحديد الوقت المناسب؟", "language": "ar"} -> 200 ok. Need to get Noura on the phone or via message to rebook now that her barrier is confirmed (fear and no escort).

### Dr. Fatima, family physician (org-ghaf) (family physician)

**Job to be done.** When one of my positive-FIT patients is stuck, I want to see who, why, and the one thing I must do, so I can act between patients without chasing anyone.

**Verdict:** job done: yes, score 4/5. "It shows me who, why, and the single action I need to take in seconds."

- Worked: Stalls listed; Next step clearly defined; Owner and next action shown
- Friction: Cannot answer consult as non‑specialist; Had to message patient separately

What they did:

- R1: request_consult case_e37da0fbd18a {"to": "dr-omar", "question": "Referral for Ahmed S. was rejected; what additional information does the GI centre need to accept and process the referral?"} -> 200 ok. Need to know why Ahmed's referral was rejected so I can fix it and resend
- R1: answer_consult None {"consult_id": "con_3bf72ee463e2", "answer": "The GI centre rejected the referral because the colonoscopy report and pathology results were missing. Attach the full colonoscopy report (including images) and the histopathology findings, and ensure the referral form includes the FIT result and a brief clinical summary. Once added, resend the referral."} -> 404 {"error": {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}}. Need to answer Dr Omar’s consult about why Ahmed’s referral was rejected so I can fix it and resend.
- R1: answer_consult case_e37da0fbd18a {"consult_id": "con_3bf72ee463e2", "answer": "The GI centre rejected the referral because the colonoscopy report and pathology results were missing. Attach the full colonoscopy report (including images) and the histopathology findings, and ensure the referral form includes the FIT result and a brief clinical summary. Once added, resend the referral."} -> 409 {"error": {"code": "NOT_CONSULT_TARGET", "message": "Only the consulted specialist can answer.", "details": {}}}. Need to answer Dr Omar's consult so I can fix Ahmed's referral and resend it.
- R2: message_patient case_e37da0fbd18a {"text": "يرجى إحضار تقرير تنظير القولون ونتائج الفحص النسيجي حتى نتمكن من إعادة الإحالة.", "language": "ar"} -> 200 ok. I need the colonoscopy report and pathology results to fix Ahmed's referral and resend it.
- R2: log_contact case_e37da0fbd18a {"channel": "sms", "result": "left_message"} -> 200 ok. Ahmed's referral was rejected; I need his colonoscopy and pathology reports, so I’ll log that I’ve messaged him to request them.
- R2: opened case case_e37da0fbd18a. I need to see the full case to know exactly which documents to attach before resending the referral for Ahmed S.

### Dr. Salma, family physician (org-samar) (family physician)

**Job to be done.** When a patient reports something worrying, I want it on top of my list today, so I can call them.

**Verdict:** job done: yes, score 4/5. "Tasleem gets the urgent patient to the top, but you still have work to finish the case."

- Worked: Urgent case surfaced at top of my_work list; Quick logging of contact and messaging
- Friction: Distress still shows as open, requiring further action; Barriers remain confirmed but not cleared

What they did:

- R1: opened case case_f3074b42fd43. Need to open Sunita's case to address her urgent distress
- R1: log_contact case_f3074b42fd43 {"channel": "phone", "result": "left_message"} -> 200 ok. Need to log that I attempted to call Sunita urgently
- R1: message_patient case_f3074b42fd43 {"text": "لقد استلمنا رسالتك ونحن نتصل بك الآن. يرجى البقاء قريبًا من هاتفك.", "language": "ar"} -> 200 ok. Need to quickly reassure Sunita and let her know I’m calling now
- R2: confirm_barrier case_f3074b42fd43 {"barrier_id": "bar_eb0c87d73adf", "code": "FEAR"} -> 200 ok. I need to confirm the fear barrier for Sunita so I can address her urgent distress
- R2: confirm_barrier case_f3074b42fd43 {"barrier_id": "bar_8066c7b53287", "code": "FEAR"} -> 200 ok. Need to confirm the remaining reported fear barrier for Sunita before I can resolve her distress.
- R2: resolve_distress case_f3074b42fd43 {"distress_id": "dis_eb2cfdc141a9", "note": "Contacted patient, addressed fear, provided reassurance and plan for immediate follow‑up."} -> 200 ok. Sunita’s distress is still open; I’ll record that I’ve dealt with one of her urgent messages after confirming her fear barriers.

### Dr. Hessa, clinic lead (org-ghaf) (clinic lead)

**Job to be done.** When cases escalate to me, I want to see which are truly stuck and reassign them safely, so nothing is lost when a doctor is away.

What they did:

- R1: opened case case_e37da0fbd18a. I need to see the details of Ahmed’s rejected referral to understand why it was rejected before reassigning.
- R1: opened case case_e37da0fbd18a. I need to open Ahmed’s case to see the full referral rejection details before I reassign it.
- R1: opened case case_e37da0fbd18a. Need to see full details of Ahmed's referral rejection before deciding reassignment.
- R2: opened case case_72a76916992f. I need to inspect Fatma N.’s case to understand why the handoff isn’t accepted and decide how to reassign it.
- R2: offer_handoff case_e37da0fbd18a {"to": "dr-omar", "reason": "Referral rejected, need GI specialist to correct and resend"} -> 200 ok. Ahmed’s referral was rejected and needs a GI specialist to fix it; I’ll hand it off to Dr Omar so it gets resolved promptly.
- R2: opened case case_422f89b0197e. I need to open Khalfan’s case to see why it’s overdue before deciding how to reassign it.

### Sara, programme coordinator (program coordinator)

**Job to be done.** When I report to the programme, I want verified completion and where people are lost by clinic and language, so I can direct resources.

**Verdict:** job done: no, score 2/5. "The dashboard gives some useful stats, but it lacks the clinic and language detail we need to direct resources."

- Worked: Overall stall reasons are listed; Barriers codes are shown
- Friction: No breakdown by clinic or language as needed for resource allocation; Unable to see verified completion numbers per clinic

What they did:

- R1: opened case case_e37da0fbd18a. I need more detail on the stalled cases to see which clinics and languages are losing patients, so I’ll open one of them.
- R1: opened case case_a71b33b324ec. I need more detail on the stalled cases to see which clinics and languages are losing patients, so I’ll open another stalled case.
- R1: opened case case_8c9193163719. I need to open the third stalled case to get details on clinic and language loss.
- R2: opened case case_13a570be1d6c. Open the next stalled case to see clinic and language details.
- R2: opened case case_e37da0fbd18a. I need more detail on the stalled cases to see which clinics and languages are losing patients, so I’ll open another stalled case.
- R2: opened case case_e37da0fbd18a. I need to see the full case details to get clinic and language info for the stalled cases.

## Refused or failed calls

Refusals are often correct (a rule protecting the patient). Each is listed so a human can judge.

- R1 `dr-fatima` answer_consult: POST /v1/cases/-/consults/con_3bf72ee463e2/answer -> 404 {"code": "NOT_FOUND", "message": "case '-' not found", "details": {"what": "case", "id": "-"}}
- R1 `dr-fatima` answer_consult: POST /v1/cases/case_e37da0fbd18a/consults/con_3bf72ee463e2/answer -> 409 {"code": "NOT_CONSULT_TARGET", "message": "Only the consulted specialist can answer.", "details": {}}

Turns with no model decision (rate limit or invalid reply): 0.
