# Contributing

1. Read [AGENTS.md](AGENTS.md) and [Additional.md](Additional.md) first. A change that weakens rules R1–R6 is rejected, whatever the backlog says.
2. Pick the highest-priority open item in [BACKLOG.md](docs/product/BACKLOG.md) and follow its acceptance criteria.
3. Write the test case before the code. Add benchmark and hard cases to [TEST_CASES.md](docs/evidence/TEST_CASES.md) (input, expected, actual, component).

## Workflow
```bash
cd backend
pip install -c constraints.txt -e ".[dev,postgres,redis,agent]"
ruff check . && python -m pytest -q
```
```bash
docker compose up -d --build --wait && cd backend && python -m tasleem.smoke --stack
```

## Rules of the codebase
- **Decisions, scores and timers are deterministic code** in `tasleem/domain`. LLMs only draft, translate or suggest, and only in `tasleem_agent`.
- **Service boundaries:** satellites (`tasleem_notifier`, `tasleem_agent`, `tasleem_connector`) never import `tasleem`; they call its HTTP API. Shared code goes in `tasleem_common`. `test_service_boundaries_hold` enforces this.
- **Every cross-service write is idempotent.** Give it a natural key.
- **Schema changes need an Alembic migration** in `backend/migrations/versions`: additive first, removals one release later. The drift test fails otherwise.
- **Dependencies:** add the range to `pyproject.toml`, regenerate `constraints.txt` in a clean venv, and run `pip-audit -r constraints.txt --no-deps`.
- **Data:** synthetic only. No real patient data, secrets or live keys in the repository.
- **The demo must keep working:** seeded cases load and `tasleem.smoke --stack` passes after your change.
