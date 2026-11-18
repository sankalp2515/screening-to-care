# Landing page strategy

The page lives at `/` ([frontend/src/pages/Landing.tsx](../../frontend/src/pages/Landing.tsx)). Its numbers come from one file, [landing-facts.ts](../../frontend/src/lib/landing-facts.ts), and each one points to the evidence that produced it.

## Who it has to convince, and of what

| Visitor | What they need before acting | The action we want |
|---|---|---|
| Challenge judge (clinical, commercial, regulatory, AI) | A real problem, a real user, proof they can check, honest limits | Open the demo and take the 60-second tour |
| Screening programme lead (buyer) | Fits Malaffi and Sahatna, adds little staff work, safe, priced per value | Email to plan a 90-day pilot |
| Family physician or navigator (user) | Less work, not more; they stay in charge | Try their own role in the demo |

There is one main action, **"Watch a stalled case get caught"** (the demo), and one secondary action, **"Plan a 90-day pilot"**. The page never offers more than these two.

## The sections, in order, and why each is there

The order follows how a cautious clinical buyer decides: *is this for me → is the problem real → what changes → how → can I trust it → what if it goes wrong → what does it cost → how do I start.*

| # | Section | Why it exists | Decision it supports |
|---|---|---|---|
| 1 | **Hero.** "Know whether the care actually happened." The live case card, both calls to action, and three proof numbers | It answers *what is this, for whom and why now* in five seconds. The card is the real product, not an illustration, so the claim and its proof share one screen. The numbers come with a "how it was measured" link, so a sceptic can check them straight away | Attention, and a first reason to believe |
| 2 | **Trust bar.** "Works beside Malaffi, Sahatna, HL7, FHIR…" | The biggest early objection is "another system to replace ours?" Naming the systems the buyer already runs removes it. We use plain text names, never their logos (we have no partnership to imply) | Lower switching risk |
| 3 | **Story.** "The same referral, twice", plus three published numbers | It follows Stephan's guidance: *poke the pain, tell the persona's story twice.* The red step in "Today" is the moment the buyer recognises. Each statistic is cited to a peer-reviewed study, so the pain is real and not invented by us | Problem acceptance |
| 4 | **Value by role.** Physicians, navigators, programme leads, patients | Each reader finds their own line in under ten seconds. Every card is written as an outcome for a person, not a feature list (Stephan: lead with value) | Personal relevance |
| 5 | **How it works.** Sense, decide, act, hand off | It makes the system look simple enough to adopt. Ending every step with a person answers "why an agent and not a chatbot" before it is asked | Perceived effort |
| 6 | **Feature highlights.** Six cards, each with a small view of the real interface | Each card pairs a mechanism with what it means for someone ("A COMPLETED status can no longer hide a missing colonoscopy"). The pictures use the product's own parts (the hatched reported bar, the magenta AI box), so the page and the app look like one product | Desire, and believing it is real |
| 7 | **Proof you can check.** Benchmark chart, four tiles, the "is the comparison fair?" panel, links to evidence and code | This replaces testimonials while we have none. A clinical panel trusts a rerunnable benchmark more than a quote. The fairness panel says what a judge would otherwise ask: we tightened the baseline until it was just as fast, and show the price it pays | Credibility |
| 8 | **Case studies (synthetic).** Rajesh, Noura, Sunita | Each covers a different failure point (false done, missed appointment, distress) and is labelled synthetic. Every card opens a live case, so the story continues inside the product | Picturing it working |
| 9 | **Safety and governance.** R1 to R6, consent, no results by message | For a health buyer, safety comes before desire. The rules are worded as promises a clinician can hold us to, and the page says they are enforced in code | Risk acceptance |
| 10 | **Objections.** "Fair questions" | It names the six real reasons a buyer says no (staff load, "we have Malaffi", AI errors, alert floods, privacy, integration time) and answers each with a fact. The staff-load and alert answers use the realistic-cohort numbers, not the stress test's | Removing blockers |
| 11 | **Pilot and pricing.** Pilot, Network, Programme | It shows the first step is small and low-risk (90 days, read-only feed), and that the price follows value (per active case, which the product already meters). The middle card is the one we want after the pilot, so it is highlighted | Commitment, and anchoring cost |
| 12 | **FAQ.** Seven collapsed questions | Practical questions (data, Arabic, deadlines, hosting, AI, synthetic data) that matter but would slow the main scan. Native `<details>` keeps it accessible without script | Final clarity |
| 13 | **Final call to action.** "See a stalled case get caught in sixty seconds" | Someone who scrolled this far is deciding. This repeats the lowest-effort action first, with the pilot beside it | Action |

## What we deliberately left out

- **Testimonials, customer logos and user counts.** We have none. Inventing them would be found out by a clinical panel and would cost all trust. When a pilot partner signs a letter of interest, it goes straight below the proof section.
- **Prices.** The repository records the pricing as a hypothesis (per active case per month). The page shows the unit and the scope, and says plainly that the price is set with the first partner. A made-up figure would be a claim we cannot defend.
- **Urgency tricks.** No countdowns and no "limited slots". They work on consumers and repel health-system buyers.
- **Outcome claims.** Every number says "on a synthetic benchmark" and links to how it was produced. Organiser rule: never claim real-world outcomes from a simulation.
- **"AI-powered" in the headline.** The value is verified care. AI appears where it really helps (drafting, translating, suggesting) and is labelled.

## Calls to action

- Every primary button points to `/demo`, the lowest-effort action: no sign-up, about 60 seconds.
- The primary button always says what happens ("Watch a stalled case get caught", "Start the guided tour"), not "Learn more".
- The secondary button opens an email titled "Tasleem pilot". It is a placeholder address on `.example` until the team has a real inbox.
- Calls to action appear at the hero, in every case-study card, in each pricing card and in the final band, never more than one screen apart.

## How to tell whether it works (once the page is live)

| Measure | Event | Target to test against |
|---|---|---|
| Hero click-through | Primary button in the hero clicked ÷ visits | First baseline; then test the button wording |
| Tour completion | Tour step 7 reached ÷ tour started | Above 60%; below that, shorten the tour |
| Deep interest | Evidence or GitHub link clicked | Shows a technical reader; check that the evidence pages hold them |
| Pilot intent | Pilot email clicked | The real conversion; every one is followed up by a person |

First tests to run: hero headline ("Know whether the care actually happened" against "Every positive result, followed to a verified outcome"), and whether moving the proof section above the features raises tour starts.

## Design rules it follows

Sheet and biro tokens from [DESIGN.md](../../DESIGN.md). One idea per section, equal side margins, no captions under visuals. Hover only on pointers that can hover: cards lift 2px, links draw an underline, the button arrow nudges. The hero enters once on load. Every effect respects reduced motion. Works at 375 px with no horizontal scroll.
