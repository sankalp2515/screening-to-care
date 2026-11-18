# Motion audit and review (18 Nov 2026)

Scope: the 12 screens of the Tasleem design canvas (`docs/design/canvas`). Method: the improve-animations audit (recon, then eight categories), then a strict review-animations pass against Emil Kowalski's ten standards. Rules and values: DESIGN.md section 8.

## 1. Recon

- **Stack:** plain HTML and CSS artboards; the production frontend will be React with shadcn/ui and CSS transitions, with no motion library.
- **Motion before this pass:** none. A search for `transition`, `animation`, `@keyframes` and `transform` found only `text-transform`. There were no easing tokens and no reduced-motion handling.
- **Personality:** a clinical work tool, so motion stays crisp and quiet. The website hero is the one rare, first-impression moment.
- **How often each element is used:**

  | Frequency | Elements |
  |---|---|
  | Tens of times a day | Case list rows, tabs, buttons |
  | Occasional | The close dialog, handoff, outcome selection |
  | Rare | The website hero, patient replies |

## 2. Prioritised findings (audit)

| # | Severity | Category | Where | Finding | Fix |
|---|---|---|---|---|---|
| 1 | HIGH | Missed opportunity (feedback) | Every button and pressable row, all screens | Presses gave no physical feedback, so taps felt dead, worst on the patient phone | `transform: scale(0.97)` on `:active`, 160ms `cubic-bezier(0.23,1,0.32,1)`; 0.98 for wide rows |
| 2 | HIGH | Missed opportunity (jarring change) | `CloseDialog.dc.html`, evidence and reason fields | Picking an outcome made required fields pop in and push the layout | Fields enter with opacity and translateY(4px), 200ms ease-out, via `@starting-style` (interruptible, no keyframes) |
| 3 | MEDIUM | Missed opportunity (spatial) | `CloseDialog.dc.html` dialog | The dialog appeared with no sense of arriving over the case | Opacity plus scale 0.97→1, 200ms ease-out, centred (modals are exempt from trigger origin) |
| 4 | MEDIUM | Missed opportunity (state) | Outcome options, patient choice rows, language switch | Selected and unselected states swapped instantly | Border, background and colour cross-fade over 150ms `ease` (colour only, no movement) |
| 5 | MEDIUM | Accessibility | All screens | No `prefers-reduced-motion` handling and no consistent focus ring | Reduced motion removes every transform and keeps colour and opacity; 2px biro `:focus-visible` ring everywhere |
| 6 | LOW | Cohesion and tokens | All screens | No shared easing or duration tokens | `--ease-out` token in every screen; durations fixed at 150, 160, 200 and 240ms (DESIGN.md 8.1) |
| 7 | LOW | Delight (rare) | `Main.dc.html` hero | The first screen of the website appeared all at once | One entrance on load: opacity plus 8px rise, 400ms, 60ms stagger; reduced motion keeps the fade only |

**Deliberately not animated:** distress alerts, overdue banners, R3 blocks, timers, the audit log, table sorting, tabs and anything triggered from the keyboard. An urgent message must never wait for an animation.

All seven are applied.

## 3. Strict review against Emil's rules (after the fixes)

| Before | After | Why |
|---|---|---|
| (no motion) | `transition: transform 160ms var(--ease-out), background-color 150ms ease, border-color 150ms ease, color 150ms ease` | Exact properties only; never `transition: all` |
| `scale(0.97)` on wide option rows (first pass) | `scale(0.98)` on `.opt` and `.row` | A 600px-wide row shrinking 3% moves its edges about 9px, which reads as a jump; wide elements get the subtler end of the 0.95 to 0.98 range |
| (no reduced-motion) | `@media (prefers-reduced-motion: reduce)` drops transforms, keeps colour and opacity | Standard 8: gentler, not zero |
| Hero entrance 400ms | Kept at 400ms | Exempt: a rare marketing moment, not UI. Every in-app animation stays at or under 240ms |
| Hero entrance with `@keyframes` | Kept | It runs once on load and is never re-triggered, so interruptibility does not apply. The dialog and the reveal use transitions plus `@starting-style` because they can re-trigger |

Checks against the ten standards:

1. **Justified motion:** passes. Every animation is feedback, a state change, spatial context or a one-off first impression.
2. **Frequency-appropriate:** passes. Case-list rows and tabs get colour only; keyboard actions get nothing.
3. **Easing:** passes. Custom strong ease-out on everything entering or pressed, `ease` for colour, and no `ease-in` anywhere (checked by search).
4. **Duration:** passes. 150 to 240ms in the app; the 400ms hero is exempt as above.
5. **Origin:** passes. Only the modal scales, from its centre; nothing starts at `scale(0)`.
6. **Interruptibility:** passes. Repeatable motion uses transitions and `@starting-style`.
7. **Performance:** passes. Only `transform` and `opacity` move; colours change without layout.
8. **Accessibility:** passes. Reduced motion is honoured, hover changes colour only (no hover motion to gate), and the focus ring is visible.
9. **Asymmetric timing:** passes. Simple taps use one short duration; there are no hold-to-confirm interactions. Destructive steps use a confirm dialog, not a timed hold.
10. **Cohesion:** passes. One curve and one duration scale across all 12 screens, crisp enough for a clinical tool.

**Verdict: Approve.** There are no feel-breaking regressions, no `transition: all`, `ease-in` or `scale(0)`, and only GPU properties move. Two things can only be judged in a real browser (feel cannot be fully judged from code):
- watch the close dialog reveal at 4× slow motion in DevTools;
- try the patient press feedback on a real phone.
