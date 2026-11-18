# Real-world fit: does Tasleem help real users on a realistic cohort?

Run: `python -m tasleem.bench.reality --n 2000 --seeds 2026,2027,2028`. Synthetic cohort of 2,000 people with a positive FIT per seed, 24,606 delivered messages (seed 2026). Numbers are seed 2026; brackets give the range across seeds.

**Why a second run.** The [three-arm benchmark](benchmark.md) deliberately over-samples rare failures so each one is tested. This run uses a failure mix taken from published data (below), so the headline reflects what a clinic would actually see. It also tightens the status-only baseline until it is as fast as it can be, and measures how much of the result depends on AI.

**What it cannot tell you:** whether patients then get their colonoscopy. That needs a pilot.

## 1. The cohort

Failure share 41.9% of people never get a colonoscopy (published: 42.3%, Martin et al. 2017). Including reports never shared and distress messages, 941 of 2,000 journeys need a person to act.

| Scenario | Per 1,000 (design) | In this cohort | Source of the rate |
|---|---|---|---|
| CLEAN_COMPLETE | 486 | 979 | Remainder |
| CLEAN_IN_PROGRESS | 40 | 80 | Window effect |
| NEVER_INVITED | 10 | 13 | Martin 2017: other or unknown |
| NOT_DISCUSSED | 10 | 22 | Martin 2017: other or unknown |
| NOT_REFERRED | 77 | 150 | Martin 2017: not ordered, refused, not indicated |
| REFERRAL_REJECTED | 23 | 58 | Martin 2017: endoscopy capacity |
| NOT_BOOKED | 70 | 128 | Martin 2017: referral not processed or not scheduled |
| NO_SHOW | 189 | 373 | Martin 2017: no-show 48.1% of failures |
| NO_PROCEDURE | 14 | 26 | Martin 2017: work-up not completed |
| FALSE_DONE | 30 | 67 | **Assumption** (no published rate) |
| REPORT_NOT_COMMUNICATED | 41 | 93 | Casalino 2009: 7.1% of abnormal results |
| DISTRESS | 10 | 11 | **Assumption** (1%) |

## 2. Headline on the realistic mix

| Measure | A: reminders only | B: status only, generous (14 d / 30 d) | C: Tasleem |
|---|---|---|---|
| People who never got a colonoscopy, flagged to a named person | 0.0% | 92.0% (92.0–92.7) | 100.0% |
| …median days from care stopping to the alert | — | 16.5 (16.3–16.6) | 1.9 (1.9–3.0) |
| All journeys needing action, flagged | 0.0% | 81.8% (81.8–84.6) | 99.9% (99.5–99.9) |
| Counted as done | — | 1150 (1113–1159) | 990 (985–1020) |
| …of which care was not complete (false done) | — | 160 (128–160) | 0 |
| Clean journeys given a false alert | 0.0% | 0.0% | 0.2% (0.1–0.2) |
| Staff alerts per 100 patients | 0.0 | 38.5 (38.1–40.0) | 53.5 (52.0–53.5) |
| Open cases without a named owner | — | — | 0 |

## 3. Is the baseline a straw man? Tighten it and see

Arm B's rules are our reconstruction. A sceptical judge may say a real status monitor would check sooner. So we ran it at three settings on the same cohort.

| Baseline | Never-colonoscopy flagged | Median days | False done | Alerts per 100 | Clean journeys falsely alerted |
|---|---|---|---|---|---|
| B: status only, generous (14 d / 30 d) | 92.0% (92.0–92.7) | 16.5 (16.3–16.6) | 160 (128–160) | 38.5 (38.1–40.0) | 0.0% |
| B': status only, tight (7 d / 14 d, repeats) | 92.6% (92.6–93.0) | 6.4 (6.4–7.3) | 160 (128–160) | 275.8 (275.8–293.4) | 57.0% (57.0–57.9) |
| B'': status only, very tight (3 d / 7 d, repeats) | 93.5% (93.3–94.1) | 2.8 (2.8–2.9) | 160 (128–160) | 725.3 (725.3–764.1) | 99.9% (99.5–99.9) |
| C: Tasleem | 100.0% | 1.9 (1.9–3.0) | 0 | 53.5 (52.0–53.5) | 0.2% (0.1–0.2) |

**Reading it.** Tighter thresholds make a status monitor faster, at the price of alerting on journeys that are fine. No threshold lets it see the two failures that are invisible in status: a referral marked COMPLETED with no colonoscopy, and a report never shared with the patient. Those stay at 0% for every B setting, because the information is not in the status feed.

### Sensitivity to the one unsourced assumption (false done)

No published rate exists for Malaffi marking a referral COMPLETED while no colonoscopy happened. Holding everything else fixed, the status-only monitor counts every such case as done:

Status-only "false done" in section 2 has two causes: this one, and reports never shared with the patient (the referral shows COMPLETED once the report exists). The table isolates the first cause.

| False-done rate (per 1,000 FIT-positive) | Status-only false done from this cause | Tasleem false done |
|---|---|---|
| 0 (the hypothesis is wrong) | 0 | 0 |
| 10 | 10 (every one) | 0 (every one caught: the evidence check needs a procedure and a report) |
| 30 | 30 (every one) | 0 (every one caught: the evidence check needs a procedure and a report) |
| 60 | 60 (every one) | 0 (every one caught: the evidence check needs a procedure and a report) |

If the rate is 0, Tasleem's advantage comes only from speed (section 3) and from reports never shared. The pilot's first job is to measure this rate.

## 4. Can the real users absorb the work?

Tasleem raised **53.5 first alerts per 100 FIT-positive patients** on this mix (an alert is counted once, when a stall first reaches its owner; later escalation steps are not counted again). Who gets the first alert (seed 2026):

| Recipient | Tasleem alerts | Status-only alerts |
|---|---|---|
| Physician | 1037 | 746 |
| Programme coordinator | 33 | 24 |

Workload per family physician, assuming 15 minutes per alert (every input below is an assumption to be replaced with clinic data):

| FIT-positive patients per physician per year | Alerts per year | Per week | Minutes per week | Navigator covering 15 physicians: alerts per week |
|---|---|---|---|---|
| 10 (low) | 5 | 0.1 | 2 | 2 |
| 20 (mid) | 11 | 0.2 | 3 | 3 |
| 40 (high) | 21 | 0.4 | 6 | 6 |

Each alert then needs action (a call, a rebooking, a clinical decision), which the 15 minutes is meant to cover. At these volumes the load is minutes per week for a physician and a short daily list for a navigator. The real risk is not volume but whether the alert reaches a person with time to act, which is why escalation goes to a named navigator and then the clinic lead.

## 5. How much of the result depends on AI? (ablation)

Every number above was produced with the AI provider **off** (`AGENT_LLM_PROVIDER=offline`). Nothing in detection, ownership, escalation or closure calls a model.

| Capability | Who decides | With AI off (this run) | What AI adds when on |
|---|---|---|---|
| Detect a stalled journey, name the reason | Rules | 99.9% (99.5–99.9) flagged | Nothing, by design (R5) |
| Give every open case a named owner | Rules | 0 cases without an owner | Nothing, by design (R1) |
| Refuse an unsafe closure | Rules | 0 false done | Nothing, by design (R3) |
| Route a distress message to a clinician in 24 h | Keyword rules | 10 of 11 | Nothing today. A model could be a second, escalate-only reader for the messages with no cue word |
| Suggest a barrier code from a free-text reply | Keyword suggestion, staff confirm | 164 right, 0 wrong, 40 no suggestion (n = 204) | LLM 14/15 vs keyword 13/15 on the labelled set ([eval](LLM_BARRIER_EVAL.md)); too small to call better |
| Brief a physician on a case | Template; LLM optional | Fixed template from cited facts | Shorter readable summary; every number must match a cited fact or the draft is rejected |
| Draft or translate a patient message | Template; LLM optional | Fixed bilingual templates | Personalised wording; passes the same result-disclosure policy before a human sends |

**Verdict.** The measured outcomes come from deterministic code. AI is an assistant layer for language: reading free text, drafting and translating. Removing it changes no detection, ownership or closure number.

## Sources

- Martin J, et al. Reasons for lack of diagnostic colonoscopy after positive result on fecal immunochemical test in a safety-net health system. Am J Med. 2017;130(1):93.e1-93.e7. https://pmc.ncbi.nlm.nih.gov/articles/PMC5164844/. *Used for:* Failure share (42.3%) and the reason mix.
- Ciemins EL, et al. Development of a follow-up measure to ensure complete screening for colorectal cancer. JAMA Netw Open. 2024. https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2816737. *Used for:* Follow-up within 180 days across 38 organisations: median 47.9% (13.1-66.9%); sets the sensitivity range.
- Forbes N, et al. Association between time to colonoscopy after positive FIT and colorectal cancer outcomes. Clin Gastroenterol Hepatol. 2021. https://www.sciencedirect.com/science/article/pii/S1542356520313781. *Used for:* Why days matter: colonoscopy beyond 9 months linked to more cancer.
- Issaka RB, et al. Interventions to increase follow-up of abnormal stool-based colorectal cancer screening. Gastroenterology. 2024. https://www.gastrojournal.org/article/S0016-5085(24)05302-2/fulltext. *Used for:* Outreach alone moved completion 40.6% -> 45.6%: finding people is not enough, someone must act.
- Casalino LP, et al. Frequency of failure to inform patients of clinically significant outpatient test results. Arch Intern Med. 2009;169(12):1123-9. *Used for:* 7.1% of abnormal results not communicated; used for REPORT_NOT_COMMUNICATED.

## Data files

- [synthetic_cohort_calibrated.csv](data/synthetic_cohort_calibrated.csv): one row per synthetic patient, ground truth and what each arm concluded.
- [synthetic_events_calibrated.csv](data/synthetic_events_calibrated.csv): every delivered message, including duplicates and late arrivals (10% repeated, 5% up to 36 h late).
- [real_world_fit.json](data/real_world_fit.json): every number in this file.

## Limits

- The failure mix comes from one US safety-net system. Abu Dhabi's insured population and family-physician model may lose fewer people, or lose them at different steps. Ciemins 2024 shows completion varies from 13% to 67% between organisations.
- The false-done rate is the product's central hypothesis and has no published value. Section 3 shows what happens if it is zero.
- The workload model is arithmetic on assumptions. Replace them with a clinic's panel size and FIT volume in the pilot.
- Detection is not care. Outreach alone moved completion by 5 points in Issaka 2024; Tasleem's value depends on the named person acting.

Runtime (all arms): seed 2026: 217.7 s, seed 2027: 219.5 s, seed 2028: 221.9 s.
