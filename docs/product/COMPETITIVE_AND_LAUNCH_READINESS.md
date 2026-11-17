# Can Tasleem win first place, and is it ready to launch?

Written 17 Nov 2026, three days before the deadline. It answers two questions. Is the product and architecture strong enough to win Challenge 05? Is everything a product needs for launch done, apart from the frontend?

**Short answer**
- **Competitiveness:** strong on the criteria judges score from documents (problem fit, technical depth, safety, evidence), with one gap the team must close: a working demo a reviewer can click.
- **Readiness:** ready for a judged prototype and a supervised pilot conversation, but not for a commercial launch. The missing pieces are listed in section 5, and most are not code.

---

## 1. What the evidence says the winning design looks like

**The clinical evidence matches our design.**
- **Source:** a systematic review published on 1 Oct 2026 covers 25 studies of follow-up colonoscopy after an abnormal stool test (Naserrudin et al., *BMJ Open* 16(10):e115052, doi:10.1136/bmjopen-2025-115052).
- **Completion:** colonoscopy completion runs from about 30–55% in safety-net settings to 70–80% or more in organised programmes.
- **Delay:** time to colonoscopy ranges from 42 to 184 days.
- **What higher performers combine:** real-time tracking, clearly assigned responsibility, outreach or navigation, and coordinated scheduling.
- **Caveat:** the authors rate the certainty of evidence as low.
- **Our mapping:** Tasleem's four parts are the same four things:
  - a case for every positive result;
  - one named owner;
  - barrier-aware outreach;
  - referral options and booking evidence.
- **Why it matters:** this is the strongest outside support we have that the design targets the right mechanism. Use it in the deck: "we built what the evidence says high-performing programmes have."

**The regulation makes the problem real right now.**
- **Circular 210/2026** (DoH, 27 Oct 2026):
  - every licensed facility must send all referrals to Malaffi as HL7 REF messages within three months;
  - facilities receive inbound referrals through the Malaffi Referral API;
  - DoH will judge compliance on actual use, not only on being connected.
- **Circular 212/2026**, issued the same day, adds data standards and audit logs over patient data.

Consequences:
- **Referral status becomes visible across providers.** Once referrals flow through Malaffi, everyone can see a status, but a status is still not care. Our benchmark arm B ("Malaffi status only") is exactly the system DoH is now mandating. Tasleem is the layer that tells you whether the care happened.
- **Audit is now a requirement.** Our hash-chained audit log answers the 212 audit-log duty directly.
- **No competing exchange.** We never build a referral exchange; we consume Malaffi's (HL7 REF via our connector).

Source for both circulars: the DoH documents as summarised by Avior Advisory, 2026; read the circulars themselves before quoting clause numbers.

## 2. Who else solves this

| Who | What they do | Where Tasleem differs |
|---|---|---|
| Innovaccer ("Agentic Cloud", closed-loop referrals, care-gap closure) | US enterprise platform. Agents route referrals and close quality-measure gaps; strong on referral leakage and revenue | Closes a loop when the referral is scheduled or the gap code is filed. Tasleem closes only on clinical evidence (report received, or a signed clinician decision). US payer and HEDIS focus; no Malaffi, IFHAS or Arabic-first patient side |
| Epic (referral work queues, Healthy Planet) | Referral tracking inside one Epic instance | Inside one EHR. Abu Dhabi patients cross providers and EHRs, which is the gap Malaffi exists to bridge. Industry writers make the same point: Epic work queues are a system of record, not cross-EHR loop closure |
| Malaffi itself (Referral API, Circular 210) | Carries the referral and its status between providers | Status only. Our benchmark: a status-only monitor flags 70% of stalled journeys and counts 125 of 528 "done" journeys that never got care; Tasleem flags 98.5% with 0 false "done" (synthetic, seed 2026) |
| Sahatna (DoH app, built by M42) | Patient app: records, booking, teleconsults, IFHAS | A channel, not a follow-through engine. Tasleem uses Sahatna as the patient's front door (message channel and embeddable patient view) |
| Patient navigation programmes (people) | Navigators call FIT-positive patients | The proven human intervention. Tasleem makes navigators reach the right person sooner and tells them the barrier; it does not replace them |
| Other teams on Challenge 05 (from the 16 Nov live chat) | A WhatsApp bot (Hausa and English); a three-surface decision-support system on Microsoft Foundry | Both centre on the patient conversation or on decision support. Neither shows verified closure, a benchmark against the mandated baseline or a hard-case suite |

**Where we stand:** nobody we found combines four things:
1. cross-provider events from the regional exchange;
2. evidence-based closure instead of status;
3. a named owner with timed escalation;
4. a reproducible comparison against the status-only baseline the regulator just mandated.

That combination is the pitch.

## 3. Scorecard against the six judging criteria

Scores are our honest estimate of where a well-informed judge lands today, with a frontend of the quality section 6 asks for.

| Criterion | Strength now | Evidence a judge can check | Gap that costs points |
|---|---|---|---|
| 1. Health impact and clinical relevance | High | The problem owner's 5-step journey followed exactly; systematic-review fit; IFHAS 4.9.2.3 respected (no results by text); distress routed to a clinician | No clinician or patient interviews in Abu Dhabi. No letter of interest. A judge from ADPHC will notice |
| 2. Technical depth and architecture | High | Safety core plus four services with reasons (ADR-001); FHIR R4, HL7 v2 (ORU, REF, SIU), SNOMED CT and LOINC; outbox; idempotent cross-service writes; Postgres stack runs in Docker | The scheduler, notifier and connector are not visible in a demo unless the UI shows them. Section 6 makes them visible |
| 3. Working solution and demo quality | **At risk** | Backend proven: 198 tests, 32 of 32 stack checks | **No live link yet, and no frontend.** This is the criterion the organisers said they evaluate first ("a detailed video showing the whole workflow") |
| 4. Responsible AI, safety and data governance | Very high | R1–R6 enforced in code and tested; AI suggests only and has no write path; patient-message policy blocks results and advice; hash-chained audit; LLM eval run and reported honestly with its sample-size limit; security audit S1–S16 | Consent capture is modelled but not shown in a patient flow. No DPIA document |
| 5. Scalability and deployment readiness | Medium-high | Single-tenant per programme, region-pinned; Postgres scale tests; Alembic migrations; CI workflow; operations guide | Not deployed anywhere (deliberately on hold). No sign-in through UAE PASS or an identity provider |
| 6. Commercial viability and path to pilot | Medium | Usage metering (active case per month); named pilot cohort (one family-medicine network plus one GI centre); Circular 210 creates a buyer need | Pricing is a hypothesis. No named partner, no conversation logged |

**Overall:** we can compete for first place, but it isn't safe yet.
- **Where we win:** criteria 1, 2 and 4, on the safety rules, the benchmark against the regulator's own baseline, and the hard-case suite.
- **Where we could lose:** criterion 3 if the demo is weak or broken, and criterion 6 if the pilot story stays generic.

The five actions that move the score most, in order:
1. **A demo link a reviewer can open with no install,** showing the wow moment within 60 seconds ("Malaffi says COMPLETED, Tasleem shows no colonoscopy, names the owner, escalates"). Section 6.
2. **The video:** under 3 minutes, using the live app, following the four-beat story (`docs/submission/VIDEO_SCRIPT.md`).
3. **One real conversation before 20 Nov** with a family physician, gastroenterologist, navigator or IFHAS staff member, even 15 minutes on a call. Quote it in the deck with permission. This closes the biggest credibility gap.
4. **Name the pilot step concretely:** one network, one GI centre, 90 days, measured on completed colonoscopies and days to procedure, with Tasleem consuming the Malaffi Referral API that Circular 210 obliges both to use.
5. **Show the cost of alerts honestly.** Tasleem raises 66 staff alerts per 100 patients against 38 for status-only monitoring. A clinical judge will ask about alert fatigue. Answer:
   - each alert names one person and one action;
   - none fire on clean journeys (0.0–0.2%);
   - the extra alerts are the stalls status-only monitoring misses.

## 4. Product lifecycle status

| Stage | Status | Where |
|---|---|---|
| 1. Problem discovery | Done (desk research, organiser sessions, problem owner's brief) | `00-PRODUCT-LIFECYCLE.md`, `Additional.md` |
| 2. User research | **Partial:** published evidence only; no interviews | Gap: action 3 above |
| 3. Definition (PRD, personas, journeys) | Done | `PRD.md`, `USER_JOURNEYS.md` |
| 4. Solution design (architecture, ADRs, data model) | Done | `ARCHITECTURE.md`, `ADR-001` |
| 5. Build (backend, services, agent, connector) | Done | `backend/` |
| 6. Verify (tests, hard cases, benchmark, scale, security audit, LLM eval) | Done | `docs/evidence`, `docs/engineering` |
| 7. Frontend | In progress (Lovable) | Section 6 |
| 8. Release (deploy, demo access, video, deck) | Not started: deploy on hold by decision; deck and video need the UI | `docs/submission` |
| 9. Pilot and measure | Planned | Bulls-eye: Now / Next / Later |

## 5. Launch readiness: what a real launch needs that we do not have

None of these are needed to submit. All are needed before a hospital could use it. List them in the deck as "limits and next steps", which judges reward.

| Area | Needed for launch | Status | Owner and effort |
|---|---|---|---|
| Identity | Staff sign-in through the provider's identity system (OIDC); patients through UAE PASS or Sahatna | Demo header sign-in only | Engineering, 1–2 weeks with access |
| Hosting | UAE-region hosting with a DoH-acceptable provider; backups; disaster recovery | Docker stack only; deploy on hold | Engineering plus a partner |
| Malaffi | Onboarding as a Malaffi-connected system; test environment; Referral API credentials | Connector built to the standards; no access | Partner facility must sponsor |
| Regulatory | DoH data and cyber standards (ADHICS) review; data protection impact assessment; decision whether it counts as software as a medical device (we argue no: it routes and records, it does not diagnose) | Not started | Founder plus advisor |
| Clinical safety | Clinical safety case and hazard log, sign-off by a clinical safety officer | Hazards are in `FAILURE_MODES.md`; no sign-off | Needs a clinician |
| Consent | Consent capture and withdrawal in the patient flow; purpose of use shown | Modelled in the domain, not in a UI | Frontend plus legal review |
| Language | Arabic content reviewed by a native clinical writer | Machine-assisted drafts | Reviewer, 2–3 days |
| AI | Contracted model host in a UAE region; rerun the evaluation there; grow the labelled set | Evaluated on a free tier, synthetic data only | Engineering |
| Commercial | Pricing tested with one buyer; contract template; support model | Hypothesis: per active case per month | Founder |
| Evidence | Pilot protocol with outcome measures (completion within 90 days, days to colonoscopy) | Measures defined in the programme view | With pilot partner |

## 6. The frontend that gives us the best chance

The organisers warned against a 10-page UI and said the winning team in a previous programme used one page. A launch-quality product still needs a front door, so the frontend has two parts:

1. **A marketing landing page.** One scroll, five sections: the problem in one line, how it works in three steps, proof (benchmark numbers), safety, pilot call to action. It ends in **"Try the live demo"**.
2. **The product, built around one workspace:**
   - **My work:** the home screen; persona switcher; worklist with owner, next step and SLA timer.
   - **Case view:** where the wow moment happens:
     - timeline with facts, computed results and AI text visibly separated;
     - verification banner;
     - actions;
     - assistant panel;
     - audit.
   - **Programme view:** the measures, benchmark and channels.
   - **Patient companion:** mobile, Arabic and English, embeddable in Sahatna.
   - **Demo control room:** run the scenarios; HL7 feed.

The demo runs entirely on recorded API responses from the real backend (the fixtures in `docs/lovable/fixtures`), so a reviewer needs nothing installed. It switches to the live API when one is deployed. Every screen states that the data is synthetic.
