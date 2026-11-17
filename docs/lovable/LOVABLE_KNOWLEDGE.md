# Tasleem: standing rules for this project

Tasleem is a product for Abu Dhabi primary care that makes sure every positive screening result turns into care that actually happened. Malaffi (the health information exchange) shows that a referral exists. Tasleem shows whether the care happened, why not, and who is fixing it. The backend already exists (Python services). This project is the frontend only.

## Never break these
1. **No invented data.** Every case, number, name and message on screen comes from the demo bundle or the live API. The only static numbers allowed are the benchmark and test figures listed in the build prompt, always labelled "synthetic cohort".
2. **Synthetic data only.** Show "Demo with synthetic data. No real patients." on the landing page footer, the guest login and the app top bar.
3. **Provenance on everything.** Every timeline item, value and text block shows where it came from, using the `provenance` field:
   - `fact`: "Fact" badge, green outline;
   - `computed`: "Computed by rule", blue outline;
   - `ai_suggestion`: "AI suggestion · needs a person to confirm", purple dashed outline plus sparkle icon;
   - `human`: "Recorded by {name}", grey;
   - `template`: "From the approved library", grey outline.

   AI text must never look like a fact or a decision.
4. **Rules decide what is clickable.** Case responses include `actions`. A button whose action has `allowed: false` is disabled. It shows the backend `message` in a tooltip and the rule code (R2, R3 and so on) as a small monospace chip. Never enable it client-side.
5. **AI suggests, people decide.** Never auto-send an assistant draft. Never call AI output a "diagnosis", "decision" or "recommendation"; call it a suggestion.
6. **Patients never see clinical values.** The patient view shows only the plain-language `message`, appointment, consent, barrier chips and preparation questions. SMS is shown as a content-free nudge, never as carrying the message.
7. **Named people, never "unassigned".** Every case shows its owner; every stall shows who it was escalated to and at which level (1 owner, 2 clinic lead, 3 programme coordinator).
8. **No real logos.** No DoH, Malaffi, Sahatna, M42 or government logos. Malaffi and Sahatna are named in text only.

## Data layer
- One API module, `src/lib/api/`. It has two modes:
  - **demo** (default): replays `demo-bundle.json`, fetched once from the pinned GitHub raw URL in the build prompt and kept in an in-memory store;
  - **live**: calls `VITE_API_BASE_URL`, `VITE_AGENT_BASE_URL`, `VITE_NOTIFIER_BASE_URL` and `VITE_CONNECTOR_BASE_URL`.
- Every request carries the current persona as the `X-Demo-User` header. In demo mode the persona selects the persona-specific entry in the bundle.
- **Demo clock:** in demo mode, "now" is `bundle.meta.generated_at`. All relative times ("4 days ago", SLA timers) are computed against it, never against the real date.
- **Errors** look like `{ "error": { "code", "message", "details" } }`. Show the message, with the code in small monospace text. Show a demo-limit error (`DEMO_NOT_RECORDED`) as a neutral info toast, not as a red error.
- TanStack Query for all reads. After a successful command, the response is the updated case: put it in the cache and show a toast.

## Look and feel
- **Mood:** a calm, credible clinical product at the level of a top SaaS company. No cartoon illustrations, no stock photos of doctors, no gradients on data.
- **Colours** (set as CSS variables):
  - primary deep teal `#0F5C6E`;
  - ink `#101828`;
  - muted `#475467`;
  - surfaces white and `#F9FAFB`;
  - amber attention `#B7791F`;
  - red distress or safety only `#B42318`;
  - green verified `#1E7A4C`;
  - AI purple `#7A5AF8`.
- **Fonts:** Inter for Latin text; IBM Plex Sans Arabic for Arabic. Arabic text is `dir="rtl"` wherever it appears.
- **Spacing and shape:** 8 px grid; radius 10–14 px; hairline borders `#EAECF0`; dense but readable tables.
- **Accessibility:** WCAG AA contrast, visible focus rings, every icon button labelled, full keyboard navigation.
- **Responsive:** staff screens work from 1280 px down to tablet; the landing page and patient view are mobile-first.

## Words
- Plain, short sentences. Say "care that actually happened", not "outcomes optimisation".
- Use the domain labels from the API (`label`, `text`) rather than rewriting them.
- Never claim real-world results, deployments, customers or partners. The proof is tests and a benchmark on synthetic data, and the copy says so.
