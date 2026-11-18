# Product-fit analysis: real problem, real users, and the role of AI

18 Nov 2026. Three questions, answered with synthetic data built from published rates, and with a plain statement of what the data cannot show.

- Numbers: [REAL_WORLD_FIT.md](../evidence/REAL_WORLD_FIT.md) (2,000 synthetic patients × 3 seeds, failure mix from the literature) and [benchmark.md](../evidence/benchmark.md) (1,000 × 3, a stress mix).
- Data: [synthetic_cohort_calibrated.csv](../evidence/data/synthetic_cohort_calibrated.csv) (one row per patient: ground truth and what each approach concluded) and [synthetic_events_calibrated.csv](../evidence/data/synthetic_events_calibrated.csv) (every HL7 REF, FHIR and patient message, with duplicates and late arrivals).
- Reproduce: `cd backend && python -m tasleem.bench.reality` (about 11 minutes).

## Short answers

| Question | Answer | Confidence |
|---|---|---|
| Is the problem real? | **Yes.** In a published cohort of 1,267 people, 42% never had a colonoscopy within a year of a positive FIT. Completion ranges from 13% to 67% between organisations. Delay beyond 9 months is linked to more cancer | High: peer-reviewed and consistent across studies |
| Is it Abu Dhabi's problem in this exact form? | **Probably, not proven.** Circular 210 makes referral *events* visible in Malaffi for the first time, but nothing checks them against clinical evidence. Our core claim, that a referral can show COMPLETED with no colonoscopy behind it, has **no published rate** | Low: this is the hypothesis the pilot must measure first |
| Does Tasleem solve it for real users? | **It solves the finding and routing half.** On a realistic mix it flags 100% of people who never get a colonoscopy, at a median of 1.9 days, against 92% at 16.5 days for a status-only monitor. It costs a physician about 3 minutes a week. Whether patients then *complete* the colonoscopy depends on people acting; that is not proven | Medium: proven on synthetic data, untested with real staff and patients |
| Is AI the core of the product? | **No, and by design it should not be.** With the AI switched off, every detection, ownership, escalation and closure number is unchanged. AI is the language layer: reading free text, drafting and translating, always confirmed by a person | High: measured by ablation |

## 1. The problem, from the evidence

Where people are lost after a positive FIT (Martin et al. 2017, 536 people with no colonoscopy):

| Where the journey stops | Share of failures | Who could fix it | Tasleem's answer |
|---|---|---|---|
| Missed a booked visit or the procedure | 48% | Navigator: call, find the barrier, rebook | Flags a missed appointment in about a day; the patient app asks why, in their language |
| Never ordered, refused or not indicated | 18% | Family physician: refer, or record refusal or plan change | Step-overdue alert to the named physician; closing needs a signed reason (R3) |
| Referral never processed or never scheduled | 17% | GI centre and navigator | Step-overdue alert; escalation ladder |
| Pre-procedure work-up not completed | 7% | Clinic | "Seen, no procedure" stall |
| Cancelled for lack of endoscopy capacity | 5% | Programme | Rejection alert the same day; programme view shows it by centre |
| Other or unknown | 5% | — | Generic step-overdue alert |

Two further failures the study did not measure, and which status monitoring cannot see:

- **Report back, patient never told.** About 7% of abnormal outpatient results are never communicated (Casalino 2009).
- **Status says COMPLETED, no colonoscopy.** Our hypothesis; no published rate.

**What this means for the product.** Nearly half of all losses are patients who miss an appointment, so the value is decided at the patient and navigator end. Tasleem is the part that finds them early and names who acts. The literature is clear that finding alone is not enough: in Issaka 2024, outreach alone moved completion only from 40.6% to 45.6%. Navigation (a person calling and helping) is what moves completion.

## 2. Real users: does it work for each of them?

| User | Job to be done | What the synthetic run shows | What is not proven | Risk |
|---|---|---|---|---|
| **Family physician** | Know which of my positive-FIT patients are stuck, and why, without another inbox | 100% of never-colonoscopy journeys reach them; median 1.9 days; 53.5 first alerts per 100 positive results, about **3 minutes a week** at 20 positives a year (15 minutes per alert assumed) | Whether physicians trust the reason and act on it; real deadlines (ours are placeholders until a clinical lead sets them) | Medium |
| **Care navigator** | Reach the patient, understand the barrier, rebook | The barrier suggestion was right for 164 of 204 free-text replies, wrong for 0, and abstained on 40. Every suggestion is confirmed by the navigator, and the task comes with a due date | Navigator capacity. The provider has to staff it; Tasleem does not call anyone | **High**: the outcome depends on this person |
| **Programme lead** | Verified completion and where people are lost, by clinic and language | 0 cases counted done without evidence (status only: 160 of 2,000) | Whether these measures match ADPHC's reporting | Low |
| **Patient** | Know the next step, say what is in the way, get a call | Arabic and English, one question at a time, never a result by text. Distress routed to a clinician in 24 h for every message with a cue word | Usability with real patients; Sahatna embedding | Medium |

**A safety gap found by this analysis, and fixed.** In the realistic run, a patient with **no family physician** sent "عندي نزيف من امس" ("I've been bleeding since yesterday"). The message went to the programme coordinator, who is not a clinician and is not allowed to resolve a distress flag. The stress-mix benchmark never generated this combination. Distress now goes to a named clinician (the coordinator's clinical lead, else a clinic lead, else a family physician). Before the fix, 9 of 11 such messages reached a clinician; after it, 10 of 11. The one remaining miss is the deliberate message with no cue word. Test RW5 in [TEST_CASES.md](../evidence/TEST_CASES.md).

**Is the comparison fair?** A sceptic will say a real status monitor would check more often. We tightened it to 3 and 7 days, with repeat alerts. It became nearly as fast as Tasleem (2.8 days against 1.9), but then raised **725 alerts per 100 patients**, alerted on **99.9% of journeys that were fine**, and still counted every COMPLETED-without-colonoscopy case as done. Speed is not the difference. The difference is evidence: status cannot tell a referral that moved from care that happened.

## 3. Is AI the core? The ablation

| Capability | Decided by | Effect of switching AI off |
|---|---|---|
| Detect a stall and name the reason | Rules | None (99.9% of journeys needing action flagged, with AI off) |
| Name one owner for every open case (R1) | Rules | None (0 without an owner) |
| Refuse an unsafe closure (R3) | Rules | None (0 false done) |
| Escalate to a named person (R4) | Rules and timers | None |
| Route distress to a clinician | Keyword rules | None today |
| Suggest a barrier code from free text | Keywords, or an LLM when switched on | The LLM was 14/15 against keywords' 13/15 on 15 labelled messages. Too few to call it better |
| Brief a physician; draft or translate a patient message | Templates, or an LLM when switched on | Wording quality only. Every LLM draft passes the same validators (numbers must match cited facts; no results in patient text) |

**Verdict.** The product's value is a verification engine plus named human ownership. AI is the voice and the reading glasses, not the judge. That is what the organisers asked for:
- V1: "don't leave the judgment to the AI";
- V3: clinical teams remain central;
- V4: AI isn't mandatory.

**What this means for the pitch.** Don't sell it as "an AI product". Sell it as *an agent whose judgment is tested rules and whose voice is AI*: it senses Malaffi events, decides with rules, acts by assigning, escalating and drafting, and hands off to a clinician. When a judge asks "why AI?", the honest answer is that the hard problem (did care happen?) needs evidence, not a model. AI is used where language is the bottleneck: Arabic and Gulf-dialect free text, drafting and translation.

## 4. Where AI would add real value next (not built; each keeps R5)

Ranked by value to the users above, using only what the organisers allow:

1. **An escalate-only second reader for distress.** A model reads every patient message the keyword rules did *not* flag, and can only *add* a human review, never remove one. It targets the one miss in every run ("My stomach hurts so much I can barely stand"). It is safe under R5 because the model never decides; it asks a clinician to look. Measure it on a new, unseen labelled set before switching it on.
2. **Barrier reading for Gulf Arabic, Urdu and Hindi.** 40 of 204 replies got no suggestion. Grow the labelled set (the eval is one command) and switch the LLM suggestion on only if it beats keywords on unseen messages.
3. **Document recognition for "done elsewhere".** A patient uploads a colonoscopy report from abroad. Form recognition extracts the date, procedure and findings for a clinician to confirm as evidence. Stephan (V4) recommended document recognition over plain OCR.
4. **Physician brief.** Already built with citation checks. Measure the time saved in the pilot, not before.

Not to build, per the organisers: no-show prediction or risk models (no data to validate them), and anything that sets priority or closes a case.

## 5. What we do not know, and how the pilot answers it

| Unknown | Why it matters | Pilot measurement |
|---|---|---|
| How often Malaffi shows COMPLETED with no colonoscopy | It is the product's sharpest claim. If the rate is 0, the advantage is speed and reports never shared | Reconcile 3 months of REF COMPLETED against GI procedure and report records at one GI centre |
| Real deadlines per step | Detection delay depends on them | Set with the screening programme's clinical lead before go-live |
| Navigator capacity and response time | Detection only helps if someone acts | Time from alert to first contact; share of alerts closed with an action |
| Patient use of the companion | Nearly half of the losses are patient-side | Five-patient usability test in Arabic and English before the pilot; reply rate during it |
| Effect on completion | The outcome that matters | Verified colonoscopy completion and days to procedure against the previous 6 months at the same clinics |

## 6. Limits of this analysis

- The failure mix comes from one US safety-net system. Abu Dhabi's insured, family-physician-based system may lose fewer people, or lose them at different steps.
- Synthetic data, written by the team. It shows the software catches what it is designed to catch; it cannot show prevalence or patient outcomes.
- The workload model is arithmetic on stated assumptions (panel size, FIT volume, minutes per alert).
- Tasleem sees more data than the status-only baseline. That is the point being tested, but it means the comparison is of approaches, not of equally informed monitors.
