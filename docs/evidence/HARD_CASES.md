# Hard cases

Run: `python -m tasleem.bench.hardcases` (16 Nov 2026). **64 of 67 match the expected result.** Expected results were written before running; misses stay in the table with the reason.

| Category | Passed |
|---|---|
| ingest | 23 / 23 |
| safety | 10 / 10 |
| barrier | 13 / 15 |
| distress | 18 / 19 |

Labels for barrier and distress texts were written by the team, not by independent clinicians. That is a limit; an independent labelled set is the first thing to add in a pilot.

| # | Category | Input | Expected | Actual | Result | Note |
|---|---|---|---|---|---|---|
| H01 | ingest | Observation without subject | 422 subject | 422 subject | pass |  |
| H02 | ingest | Resource without resourceType | 422 resourceType | 422 resourceType | pass |  |
| H03 | ingest | Resource without id | 422 id | 422 id | pass |  |
| H04 | ingest | Unreadable date string | 422 resource | 422 resource | pass |  |
| H05 | ingest | Code sent as a bare string, not a CodeableConcept | 422 resource | 422 resource | pass | Found by this set: was silently read as 'no code'; fixed 16 Nov |
| H06 | ingest | Positive result with a non-FIT LOINC code | no case | no case | pass |  |
| H07 | ingest | Negative FIT | no case | no case | pass |  |
| H08 | ingest | Preliminary FIT result | ignored | ignored | pass |  |
| H09 | ingest | Patient not in directory | unmatched | unmatched | pass |  |
| H10 | ingest | Same message delivered twice | duplicate | duplicate | pass |  |
| H11 | ingest | Booked appointment without start time | 422 start | 422 start | pass |  |
| H12 | ingest | Resource type no pathway uses | ignored | ignored | pass |  |
| H13 | ingest | Empty bundle | 422 entry | 422 entry | pass |  |
| H14 | ingest | Bundle with FIT and invitation | invited | invited | pass |  |
| H15 | ingest | Invitation delivered before the FIT it follows | invited | invited | pass | Found by the benchmark: was dropped; now replayed when the case opens |
| H16 | ingest | Report delivered before the procedure record | both recorded | both recorded | pass |  |
| H17 | ingest | Referral status COMPLETED, no report for 8 days | flagged | flagged | pass |  |
| H18 | ingest | Referral status for another service on a FIT case | NONE | NONE | pass |  |
| H19 | ingest | Timestamp without timezone | case opened | case opened | pass | Treated as UTC; Malaffi feeds should send offsets |
| H20 | ingest | HbA1c 6.4 % (below threshold) | no case | no case | pass |  |
| H21 | ingest | HbA1c 6.5 % (at threshold) | case opened | case opened | pass |  |
| H22 | ingest | Body over 1 MB | 413 | 413 | pass |  |
| H23 | ingest | JSON array instead of a resource | 422 | 422 | pass | Rejected by request validation before the adapter |
| H24 | safety | Close the false-done case as completed | 409 R3_EVIDENCE_REQUIRED | 409 R3_EVIDENCE_REQUIRED | pass |  |
| H25 | safety | Patient tries to close their own case | 403 | 403 | pass |  |
| H26 | safety | Navigator signs a clinical closure | 409 R3_SIGNATURE_REQUIRED | 409 R3_SIGNATURE_REQUIRED | pass |  |
| H27 | safety | Someone other than the handoff target accepts | 409 R2_NOT_HANDOFF_TARGET | 409 R2_NOT_HANDOFF_TARGET | pass |  |
| H28 | safety | Patient reports a barrier on another patient's case | 404 | 404 | pass | Changed 17 Nov from 403: same answer as a missing case, so the case's existence is not revealed |
| H29 | safety | Close while a distress flag is open | 409 R3_DISTRESS_OPEN | 409 R3_DISTRESS_OPEN | pass |  |
| H30 | safety | Signed informed refusal closes, but is never counted as care | care_completed=false | care_completed=false | pass | First attempt without the signed document was refused (R3) |
| H31 | safety | Arabic bleeding message through the API | distress routed | distress routed | pass |  |
| H32 | safety | Clinician from another clinic opens a patient's case | 404 NOT_FOUND | 404 NOT_FOUND | pass | Org scoping: same answer as a missing case, so existence is not revealed |
| H33 | safety | Specialist outside the case tries to accept its handoff | 404 NOT_FOUND | 404 NOT_FOUND | pass |  |
| H34 | barrier | I am really scared of the camera test | FEAR | FEAR | pass |  |
| H35 | barrier | والله خايف من المنظار | FEAR | FEAR | pass |  |
| H36 | barrier | I don't understand what to drink the night before | PREP_UNCLEAR | PREP_UNCLEAR | pass |  |
| H37 | barrier | وش اسوي في التحضير؟ ما فهمت | PREP_UNCLEAR | PREP_UNCLEAR | pass |  |
| H38 | barrier | Nobody can take me home after the sedation | NO_ESCORT | NO_ESCORT | pass |  |
| H39 | barrier | ما في احد يوصلني | NO_ESCORT | NO_ESCORT | pass |  |
| H40 | barrier | I can't get a taxi that early | TRANSPORT | TRANSPORT | pass |  |
| H41 | barrier | Is this covered by my insurance? | COST_OR_INSURANCE | COST_OR_INSURANCE | pass |  |
| H42 | barrier | My manager won't give me the day off | TIME_OR_WORK | none | **miss** | Cue words absent ('manager', 'day off'); human confirms the code anyway |
| H43 | barrier | I need an Urdu interpreter | LANGUAGE | LANGUAGE | pass |  |
| H44 | barrier | Can someone call me please | WANTS_CALLBACK | WANTS_CALLBACK | pass |  |
| H45 | barrier | I did it in India last month | DONE_ELSEWHERE | none | **miss** | No cue ('in India'); human confirms the code anyway |
| H46 | barrier | ok thanks | none | none | pass |  |
| H47 | barrier | I'll think about it | none | none | pass |  |
| H48 | barrier | My kids are sick this week | none | none | pass | Arguably TIME_OR_WORK; abstaining sends it to a human, which is safe |
| H49 | distress | I saw blood when I went to the toilet | flag | flag | pass |  |
| H50 | distress | Black stool for two days | flag | flag | pass |  |
| H51 | distress | فيه دم مع البراز | flag | flag | pass |  |
| H52 | distress | صار عندي نزيف | flag | flag | pass |  |
| H53 | distress | I fainted this morning | flag | flag | pass |  |
| H54 | distress | I feel hopeless about all of this | flag | flag | pass |  |
| H55 | distress | انا منهار | flag | flag | pass |  |
| H56 | distress | The pain is unbearable | flag | flag | pass | Missed in v0.1 (no cue word); fixed in v0.2 by the pain-severity rule |
| H57 | distress | I had a blood test last week | flag | flag | pass | Over-flag by design: high recall; a clinician sees it and clears it |
| H58 | distress | No bleeding, just nervous | no flag | flag | **miss** | Negation not handled: over-flag, safe direction |
| H59 | distress | عدم الحضور بسبب الدوام | no flag | no flag | pass |  |
| H60 | distress | Booked for Spain trip, can we move it? | no flag | no flag | pass |  |
| H61 | distress | The pain is getting worse and worse | flag | flag | pass |  |
| H62 | distress | I have terrible stomach pain since yesterday | flag | flag | pass |  |
| H63 | distress | Worst pain I have ever had | flag | flag | pass |  |
| H64 | distress | الالم ما يتحمل | flag | flag | pass |  |
| H65 | distress | وجع شديد في بطني | flag | flag | pass |  |
| H66 | distress | Mild pain after the injection, nothing else | no flag | no flag | pass |  |
| H67 | distress | I'm worried the procedure will cause pain | no flag | no flag | pass |  |
