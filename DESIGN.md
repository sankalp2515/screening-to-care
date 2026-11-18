# DESIGN.md: Tasleem design system, "Sheet and biro"

Every screen, component and generated UI in this repository follows this file. Give it to any coding agent before it writes UI. If a screen needs something this file does not cover, add it here first, then build it.

Stack (no migrations, no extra UI libraries): React, Vite, TypeScript, Tailwind CSS, shadcn/ui (Radix primitives), lucide-react icons, Recharts for charts, TanStack Query. Motion is plain CSS transitions (shadcn's `tailwindcss-animate` is already present). Do not add Framer Motion, MUI, Chakra, Bootstrap or a second icon set.

---

## 1. Brand character and principles

**Mood in one sentence:** a well-kept paper medical record, written in blue biro: calm, exact and signed by a person.

Tasleem is the layer that says whether care actually happened. The look must feel like evidence, not like marketing. Paper is the ground, ink is the text, and blue biro marks the one thing you should do next.

Principles, in priority order:

1. **One next step per screen.** Every screen has one primary action. It is the only blue-filled thing on the screen.
2. **Show the source of every fact.** UI separates three kinds of content, always the same way (section 6.4): recorded facts, computed results and AI-drafted text.
3. **A person is always named.** Owners, signers and escalation targets appear by name and role, never as "the system".
4. **Plain words.** Patient copy reads at about age 9 to 11, with sentences of 12 words or fewer. Clinician copy uses clinical terms without jargon.
5. **Quiet until it matters.** Colour is reserved for status and the next action. Nothing moves unless it explains a change.
6. **Arabic is not a translation.** RTL layouts are designed, not mirrored by accident (section 10.5).

Research behind the direction: Refero style references for Stripe, Linear, Attio, Mercury and Ui (single action colour, hairlines instead of shadows, a mono face for identifiers), the 60/30/10 colour rule from the team's reference reels, and the "give the AI a documented token table" method from the UI Collect video. The cta.gallery, navbar.gallery and footer.design galleries render as images only, and automation could not read them, so they informed nothing beyond site names. References are inspiration, not templates.

## 2. Colour

### 2.1 The 60/30/10 rule

| Share | Role | Token | Light | Dark |
|---|---|---|---|---|
| 60% | Paper: page and sheets | `--paper`, `--sheet` | `#F6F4EE`, `#FFFFFF` | `#121316`, `#1A1C20` |
| 30% | Ink: text, rules, dark bands | `--ink` | `#14171F` | `#ECE9E1` |
| 10% | Biro: the one action, links, focus, selection | `--biro` | `#1A4BE0` | `#7C9BFF` |

The biro blue is never decoration. If something is blue, a user can click it, or it is selected.

### 2.2 Full token table

| Token | Light | Dark | Use it for |
|---|---|---|---|
| `--paper` | `#F6F4EE` | `#121316` | Page background |
| `--sheet` | `#FFFFFF` | `#1A1C20` | Cards, tables, dialogs, the patient's card |
| `--sheet-2` | `#FAF8F3` | `#202227` | Table header, quiet panel, hover row |
| `--rule` | `#E7E2D7` | `#2C2F35` | Hairlines, card edges, dividers |
| `--rule-strong` | `#D5CFC2` | `#3B3F46` | Input borders, unselected options |
| `--ink` | `#14171F` | `#ECE9E1` | Headings, body text, icons |
| `--ink-2` | `#3A3E47` | `#C9C5BC` | Secondary text, computed values |
| `--muted` | `#6B6F78` | `#9A978F` | Labels, timestamps, captions (never below 12px) |
| `--biro` | `#1A4BE0` | `#7C9BFF` | Primary button, link, focus ring, selected state |
| `--biro-ink` | `#1238B0` | `#A9BCFF` | Biro hover and pressed, link hover |
| `--biro-wash` | `#EEF1FC` | `#1D2440` | Selected row, selected option fill |
| `--done` | `#1E7A4C` | `#5CC48E` | Verified outcome, evidence received |
| `--done-wash` | `#ECF6F0` | `#14261C` | Background for verified states |
| `--attn` | `#B54708` | `#F0A060` | Due soon, a gap between reported and verified |
| `--attn-wash` | `#FEF4EC` | `#2A1D12` | Background for attention states |
| `--stop` | `#B42318` | `#F38B80` | Overdue, blocked, distress, unsafe close attempt |
| `--stop-wash` | `#FEF3F2` | `#2B1615` | Background for stop states |
| `--ai` | `#C11574` | `#F06BB0` | AI-drafted text: dashed outline and label only |
| `--ai-wash` | `#FDF2F8` | `#2A1421` | Background behind an AI draft |

**Never use violet or purple anywhere.** The earlier violet for AI was retired; AI is magenta with a dashed outline.

### 2.3 Contrast rules

- Body text is `--ink` on `--sheet` or `--paper` (about 17:1).
- `--muted` on `--paper` is 5.0:1, so it is allowed for text 12px and up, never for anything a user must act on.
- `--biro`, `--done`, `--attn`, `--stop` and `--ai` all reach 5.3:1 or better on white, so they are safe for text at 14px and up.
- White text is allowed only on `--biro`, `--ink` and `--stop` fills.
- Status is never colour alone. Every status pairs colour with a word and an icon ("Overdue 3 days", a clock icon).
- Focus ring: 2px `--biro`, 2px offset, on every focusable element. Never remove outlines without this replacement.

## 3. Typography

| Role | Family | Size / line height | Weight | Notes |
|---|---|---|---|---|
| Display (website hero only) | Source Serif 4 | 64/68, 44/48 on mobile | 600 | One word may be set in italic to carry the stress ("care *actually* happened") |
| H1 page title | Source Serif 4 | 32/38 | 600 | One per screen |
| H2 section | Source Serif 4 | 22/28 | 600 | |
| H3 card title | Libre Franklin | 16/22 | 600 | |
| Body | Libre Franklin | 15/22 (app), 17/26 (patient) | 400 | |
| UI label, button | Libre Franklin | 14/20 | 500, button 600 | Sentence case, no all caps on buttons |
| Overline | Libre Franklin | 12/16, tracking 0.06em, upper case | 600 | Section labels in the care-team app only |
| Identifier, number, time | IBM Plex Mono | 13/18 | 400 to 500 | Case IDs, FHIR references, rule codes, durations, hashes. Use `tabular-nums` on numbers |
| Arabic (all roles) | IBM Plex Sans Arabic | +1px over the Latin size, line height ×1.15 | 400 to 700 | Serif display is not used for Arabic |

Rules:
- At most two weights per screen, plus the mono face.
- Numbers in tables are right-aligned and tabular.
- Never put text below 12px. The patient app never goes below 14px.
- Load fonts from Google Fonts with `display=swap`. Fallbacks are Georgia (serif), system-ui (sans) and ui-monospace.

## 4. Space, grid, containers and breakpoints

- **Base unit 4px.** Space scale: 4, 8, 12, 16, 20, 24, 32, 40, 56, 80, 120.
- **Breakpoints:** `sm` 390 (phone), `md` 768 (tablet), `lg` 1024 (laptop), `xl` 1440 (desktop).
- **Containers:**
  - Website: max 1200px, side gutter 24px (16px on phones).
  - Care-team app: full width, with a 240px left rail and a 12-column fluid grid with 24px gutters. The case view uses a split of 8 columns (case) and 4 (actions and audit).
  - Patient companion: one column, max 440px, 16px gutter. It is designed to sit inside Sahatna.
- **Vertical rhythm:** sections on the website are 120px apart (72px on phones). Cards inside the app are 16px apart.
- Left and right content edges are always equal.

## 5. Components, surfaces, borders, radii and shadows

### 5.1 Surfaces and elevation
- **No drop shadows.** Elevation is a step in surface colour plus a 1px `--rule` hairline (`paper` → `sheet` → `sheet-2`).
- Dialogs and drawers: `--sheet`, a 1px `--rule-strong` edge, over a scrim of `--ink` at 40%.
- Ruled sections: page sections are separated by a full-width hairline with a small overline label, like a form.

### 5.2 Radii
| Element | Radius |
|---|---|
| Care-team app: cards, inputs, buttons, tables | 4px |
| Tags, rule chips | 2px |
| Patient companion: cards | 10px |
| Patient companion: buttons, inputs, choice rows | 8px |
| Avatars, status dots | full |

### 5.3 Buttons (three variants only)
| Variant | Look | Use |
|---|---|---|
| Primary | `--biro` fill, white text, 40px tall (patient 52px) | The one next step on the screen |
| Secondary | `--sheet` fill, 1px `--rule-strong` edge, `--ink` text | Other actions |
| Quiet | No fill, `--ink-2` text, underline on hover | Cancel, "Not now", tertiary links |

Destructive actions (reject a handoff, withdraw consent, discard a draft) use Secondary with `--stop` text, never a red fill, and always open a confirm step. Closing a case is the primary action of its own dialog, enabled only once the outcome and its required evidence or signed decision are present (R3).

### 5.4 Status tags
A tag is a 2px-radius label: an icon, a word, and a wash background. Tags: `Verified` (done), `Reported, not verified` (attn, hatched icon), `Overdue` (stop), `Waiting on patient` (muted), `Escalated` (stop outline). Never a coloured dot alone.

### 5.5 The journey bar
The signature component. Nine cells for the FIT-positive journey (Invited → Result → Referred → Booked → Attended → Procedure → Report → Reviewed → Closed). Each cell is one of:
- **Verified:** solid `--done`.
- **Reported, not verified:** hatched in `--rule-strong` (`repeating-linear-gradient(135deg, #A29D91 0 3px, #D5CFC2 3px 7px)`).
- **Gap:** `--attn` outline. This is where "Malaffi says completed" and "no colonoscopy found" disagree.
- **Not yet:** `--sheet-2`.
Every cell has a text label for screen readers ("Procedure: reported, not verified").

### 5.6 Signature line
Closing a case with a clinician decision (rule R3) shows a signature line: the clinician's name in Libre Franklin, a biro-blue underline, the time in mono. It is the visual promise that a person, not the software, closed the case.

## 6. Information density and tables

### 6.1 Density modes
- **Care-team app:** comfortable-dense. Table rows are 44px, cells have 12px horizontal padding, and 14px text.
- **Programme view:** dense. 36px rows, 13px text; charts carry the story.
- **Patient companion:** sparse. One card at a time, 17px body text, 52px buttons.

### 6.2 Table pattern
- Header row on `--sheet-2`, overline style, sticky.
- Row hover `--sheet-2`; the selected row has `--biro-wash` and a 2px `--biro` left edge.
- Columns in fixed order for case lists: Patient, Stage (journey bar), Owner, Next due, Status. The first column is the click target; the whole row is clickable too.
- Long text is truncated to one line with a full-text tooltip. IDs are never truncated: they wrap in mono.
- Empty, loading and error states replace the table body, never the header (section 9).

### 6.3 Numbers and time
Absolute dates for deadlines ("Due Tue 18 Nov"), relative only for recency ("3 h ago"). Durations in mono (`16 d`).

### 6.4 Source of truth labels (Additional.md, V1)
| Kind | Look | Label |
|---|---|---|
| Recorded fact (from Malaffi, HL7, a clinician) | Plain `--ink` text, source reference in mono `--muted` | `FACT` tag + source, e.g. `Encounter/enc-p-rajesh` |
| Computed result (deterministic rule) | `--ink-2` text in a 1px `--rule-strong` box, rule code in mono | `RULE` tag + rule id, e.g. `R3_EVIDENCE_REQUIRED` |
| AI-drafted text | Text on `--ai-wash`, 1px dashed `--ai` outline | `AI DRAFT` tag + "A person must confirm this" |
| Human decision | `--ink` text with the signature line | Name, role, time |

AI text is never shown without the dashed outline, and never in a primary button.

## 7. Icons and visual assets

- **lucide-react only**, 1.75px stroke, 16px in tables, 20px in cards, 24px in the patient app. Icons are `--ink` unless they carry status.
- Every icon next to text is `aria-hidden`. Icon-only buttons have an `aria-label` and a tooltip.
- **Photographs:** website only, people in a care context (a clinician on a call, a family), licensed stock with a credit line in the footer. No photographs in the app. Never a patient's face presented as real.
- **Illustration:** none. The journey bar and the real product UI are the visuals.
- **Logo:** the wordmark "Tasleem" in Source Serif 4 600 with a short biro underline. "Tasleem" (تسليم) means handover.
- The HL7, FHIR and Malaffi names are shown as text, not logos, unless permission is given.

## 8. Motion and interaction

Motion follows Emil Kowalski's rules, enforced by the review-animations checklist. Motion explains a change; it never decorates.

### 8.1 Tokens
```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);   /* things appearing, presses */
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1); /* things moving on screen */
--dur-press: 160ms;  --dur-fast: 150ms;  --dur-ui: 200ms;  --dur-panel: 240ms;
```
Never `ease-in`, never `transition: all`, never `scale(0)`. UI motion stays under 300ms.

### 8.2 What moves
| Element | Motion | Why |
|---|---|---|
| Any button or pressable row | `transform: scale(0.97)` on press, 160ms ease-out | Feedback |
| Hover (pointer devices only) | Colour change, 150ms ease | State |
| Choice rows, barrier chips, outcome options | Border and background colour, 150ms ease | Selection state |
| Revealed requirement (e.g. "evidence needed" appears in the close dialog) | Opacity 0→1 and translateY 4px→0, 200ms ease-out | Prevents a jarring jump |
| Dialogs | Opacity plus scale 0.97→1, 200ms ease-out, from centre | Spatial |
| Drawer (case audit) | translateX(100%)→0, 240ms `--ease-drawer` `cubic-bezier(0.32,0.72,0,1)` | Spatial |
| Toast ("Handoff sent") | translateY(8px)→0, opacity, 200ms ease-out, CSS transition so it is interruptible | Feedback |
| Website hero | One entrance on load: heading, text, product frame, 60ms stagger, 400ms ease-out | First impression, rare |

### 8.3 What never moves
- Keyboard shortcuts, the command palette, table sorting and tab switches.
- **Distress alerts, overdue banners and safety blocks appear instantly.** An urgent message must never wait for an animation.
- Numbers in tables, timers and the audit log.

### 8.4 Gating
- Hover motion sits inside `@media (hover: hover) and (pointer: fine)`.
- `@media (prefers-reduced-motion: reduce)`: remove every transform; keep colour and opacity changes at 150ms or less.

## 9. States

Every list, card and form has all five states designed before it ships.

| State | Pattern | Example copy |
|---|---|---|
| **Loading** | Skeleton rows in `--sheet-2` matching the final layout; no spinner for under 300ms; never a full-page spinner | (no text) |
| **Empty** | One sentence on why it is empty and one action | "No cases need you today. New cases arrive from Malaffi as referrals are sent." |
| **Failure** | `--stop` tag, what failed, what still works, a retry | "Could not reach Malaffi. Cases shown are from 09:40. Retry" |
| **Warning** | `--attn` panel above the content it concerns, with the rule code | "Reported as completed, but no procedure report found. R3_EVIDENCE_REQUIRED" |
| **Success** | `--done` tag inline plus a toast for actions; never a modal | "Handoff sent to Dr. Fatima. You stay owner until she accepts." |
| **Blocked** | Secondary button disabled with a visible reason under it, not just greyed out | "Closing needs a procedure report or a signed decision." |

Patient-side states use reassurance, not system words: "Sent. Your care team will reply by Thursday."

## 10. Accessibility

1. **WCAG 2.2 AA** is the floor. Contrast per section 2.3.
2. **Targets:** 44×44px minimum in the app, 48px in the patient companion, with 8px between targets.
3. **Keyboard:** every action reachable by keyboard in a logical order; shadcn/Radix focus management for dialogs; visible focus ring always.
4. **Screen readers:** status tags and journey cells have text; live regions (`aria-live="polite"`) for toasts and "case updated"; `aria-live="assertive"` only for distress alerts.
5. **RTL:** Arabic pages set `dir="rtl"` and `lang="ar"` on the root; use logical CSS (`margin-inline-start`, `ps-*` and `pe-*` in Tailwind), mirror directional icons (arrows, chevrons) but not clocks or checkmarks; numbers and IDs stay LTR inside `<bdi>`.
6. **Language:** the patient chooses English or Arabic on first open; the choice is remembered; every patient string exists in both.
7. **Forms:** labels above inputs, never placeholder-only; errors next to the field in words; required fields marked with the word "required".
8. **Reduced motion and zoom:** layouts hold at 200% zoom and at 320px width with no horizontal scroll.

## 11. Patient companion: the simplicity rules

The patient side decides whether people come back. These rules beat everything else in this file for that surface.

1. **The first thing on screen is the next step,** in one sentence, with one big biro button. Nothing else competes with it.
2. **One question at a time,** with "1 of 2" progress. Never a form wall.
3. **Choices are big rows with an icon and plain words,** never small chips or dropdowns.
4. **Every action gets an instant, human reply:** "Thank you, Noura. Aisha from your care team will call you by Thursday."
5. **No results, diagnoses or advice by message** (IFHAS 4.9.2.3). The app invites to a conversation; it never discloses.
6. **Asking for help is always one tap away:** "I want someone to call me" stays visible on every screen.
7. **Consent is a plain sentence and a switch,** reversible at any time, shown once at the start.
8. **No sign-up inside the companion.** It lives in Sahatna, which already knows who the patient is.

## 12. Checklist before any UI ships
- [ ] One primary (biro) action per screen.
- [ ] Facts, rules and AI drafts labelled as in 6.4.
- [ ] All five states designed (section 9).
- [ ] No violet, no shadows, no `transition: all`, no `ease-in`.
- [ ] Works at 390px and in Arabic RTL.
- [ ] Keyboard and screen reader pass on the main path.
- [ ] Synthetic data only, labelled as synthetic.
