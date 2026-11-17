# Demo video script (draft for TSL-131): 2:45 target, under 3:00

The organisers evaluate the video first and want the **live app running**, not slides (Additional.md §6). The structure follows Stephan Geyer's four beats: problem → user → solution → outcome. Poke the pain first, then show one wow moment. Rehearse three times with a timer, keep the same data every run, and record a clean backup.

Before recording:
1. `POST /v1/admin/reset-demo`.
2. Open the Lovable app as **Dr. Fatima** in one tab and **Aisha** in another.
3. Open Noura's Sahatna view on a 375 px phone frame.

| Time | Screen | Say (about 130 words per minute) |
|---|---|---|
| 0:00–0:20 | Black screen, then Malaffi-style status "COMPLETED" | "Rajesh had a positive bowel-cancer screening test. Malaffi says his colonoscopy referral is completed. It never happened. No report exists. Nobody notices, because everyone trusts the status. In Abu Dhabi, only three in ten positive tests were followed by a colonoscopy." |
| 0:20–0:35 | Dr. Fatima's **My work**, false-done case on top | "This is Dr. Fatima, his family physician. Tasleem checks clinical evidence, not status. It flagged Rajesh the moment the status said completed and no report arrived, and it named her as the owner." |
| 0:35–1:00 | **Wow moment:** the case view with reported versus verified bars and the gap; "Close" greyed with the rule | "On the left, what Malaffi reports. On the right, what is verified. The close button tells her why it is blocked: no report. She can't mark it done, and neither can anyone else." |
| 1:00–1:15 | Feed simulator: run "report arrives"; the bars meet, the stall clears | "When the GI centre sends the report, the stall clears on evidence, and only then can she close it." |
| 1:15–1:45 | Noura's phone: Sahatna message in Arabic; she taps "I'm scared" and "No one can take me home" | "Noura missed her colonoscopy. Tasleem noticed the next morning and asked her, in Arabic and without any result in the message, what got in the way." |
| 1:45–2:10 | Aisha's worklist: barrier task, AI draft labelled "AI suggestion", Aisha edits and sends | "Aisha, the navigator, gets the task and the playbook. The AI drafts a message from an approved library. She reads it and sends it. The AI cannot send, close or decide anything. And if Noura can't be reached by app or SMS, Aisha gets a call task." |
| 2:10–2:25 | A distress message; Dr. Fatima's EMR task and phone page appear | "If a patient writes about bleeding, a clinician is alerted the same minute, in the inbox they already use." |
| 2:25–2:40 | Programme view, then the benchmark chart | "For the screening programme: 98.5% of stalled journeys reach a named person, against 70% with status-only monitoring, and zero journeys falsely counted as done. Synthetic data; software results, not patient outcomes." |
| 2:40–2:50 | Title card: pilot ask | "Next: a 90-day pilot, the FIT pathway, three to five primary-care centres and one GI centre on a read-only Malaffi feed. Tasleem: whether the care actually happened, why not, and who is fixing it." |

Do not open with the architecture or the scale numbers. If time is short, cut the distress beat, not the wow moment.
