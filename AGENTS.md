# AGENTS.md

Instructions for any coding agent (Claude Code, Codex or others) working in this repository.

## Read first, every task
1. **[Additional.md](Additional.md)**: organizer guidance (DO / DON'T) from the challenge sessions and rules. It overrides any backlog item that conflicts with it.
2. [docs/product/PRD.md](docs/product/PRD.md): what we are building and why.
3. [docs/product/BACKLOG.md](docs/product/BACKLOG.md): pick the highest-priority item that isn't done; follow its acceptance criteria.
4. [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md): how the system is built.

## Product in one line
Malaffi now tells you a referral exists. Tasleem tells you whether the care actually happened, why not, and who is fixing it.

## Non-negotiable safety rules (enforced in `backend/tasleem/domain/engine.py`; tested in `backend/tests`)
- **R1** An open case always has exactly one named owner.
- **R2** Handoff is two-step. The sender stays owner until the receiver accepts.
- **R3** A case closes only with an allowed outcome plus the evidence or signed clinician decision that outcome requires.
- **R4** Every missed deadline escalates to a named human.
- **R5** AI never closes a case, sets priority, changes a plan or advises. AI output is a suggestion that a human confirms.
- **R6** Every state change is an event in a hash-chained, tamper-evident audit log.

Any change that weakens one of these must be rejected, even if a backlog item seems to ask for it.

## Working rules
- Decisions, scores and timers are deterministic code. LLMs may only draft, translate or suggest.
- Write or update tests with every change: `cd backend && python -m pytest -q`.
- Synthetic data only. Never add real patient data, secrets or live keys to the repo.
- Keep the demo path working at all times. Seeded cases must still load after your change.
- Record every new benchmark case in `docs/evidence/TEST_CASES.md` (input, expected, actual, component).
