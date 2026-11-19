# Contributing to Tasleem

Thank you for helping close the screening-to-care loop. Tasleem handles health workflows, so a few rules are stricter than in most projects.

## Ground rules

1. **Synthetic data only.** Never commit real patient data, real names, Emirates ID numbers, secrets or live keys. Seed and test data use fictional people.
2. **The six safety rules are not negotiable.** A change that weakens R1–R6 is rejected, even if an issue seems to ask for it:
   - R1: an open case always has exactly one named owner.
   - R2: handoff is two-step; the sender owns the case until the receiver accepts.
   - R3: a case closes only with an allowed outcome plus evidence or a signed clinician decision.
   - R4: every missed deadline escalates to a named human.
   - R5: AI never closes a case, sets priority, changes a plan or advises. It suggests; a person confirms.
   - R6: every state change is an event in the hash-chained audit log.
3. **Decisions are code.** Rules, scores and timers are deterministic. A language model may only draft, translate or suggest.
4. **Every change ships with tests.** Record each new benchmark or hard case in [docs/evidence/TEST_CASES.md](docs/evidence/TEST_CASES.md): input, expected, actual, component.
5. **Keep the demo path working.** Seeded cases must still load, and the guided tour must still run end to end.

## Set up

```bash
# backend
cd backend
pip install -c constraints.txt -e ".[dev]"
python -m pytest -q
ruff check .

# web
cd frontend
npm ci
npm test && npm run typecheck && npm run build

# everything, end to end
docker compose up -d --build --wait
cd backend && python -m tasleem.smoke --stack
```

## Rules of the codebase

- **Decisions, scores and timers live in `tasleem/domain`.** Language models only draft, translate or suggest, and only in `tasleem_agent`.
- **Service boundaries:** the satellites (`tasleem_notifier`, `tasleem_agent`, `tasleem_connector`) never import `tasleem`; they call its HTTP API. Shared code goes in `tasleem_common`. `test_service_boundaries_hold` enforces this.
- **Every cross-service write is idempotent.** Give it a natural key.
- **Schema changes need an Alembic migration** in `backend/migrations/versions`: additive first, removals one release later. The drift test fails otherwise.
- **Dependencies:** add the range to `pyproject.toml`, regenerate `constraints.txt` in a clean environment, and run `pip-audit -r constraints.txt --no-deps`.
- **Test before code:** write the test case first, then make it pass.

## Pull requests

- Keep each pull request to one change, and say which rule, user journey or backlog item it serves (see [docs/ROADMAP.md](docs/ROADMAP.md)).
- CI must pass: lint, dependency audit, backend tests, hard cases, benchmark, migrations on PostgreSQL, the web build and the full-stack smoke test.
- Pathway changes (deadlines, codes, playbooks in `backend/pathways/*.yaml`) need review by the programme's clinical lead before a pilot uses them.
- Patient-facing text goes through the message policy (no results, no advice, no links) in both Arabic and English.

## Reporting bugs

Open an issue with the steps, what you expected and what happened. Never paste real patient information into an issue. For security problems, follow [SECURITY.md](SECURITY.md) instead.
