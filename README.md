# Tasleem

**Malaffi now tells you a referral exists. Tasleem tells you whether the care actually happened, why not, and who is fixing it.**

Entry for the Future Health Digital Innovation Challenge 2026 · Population Health · Challenge 05 "Closing the Screening-to-Care Loop". All data in this repository is synthetic.

## Read first
| File | What it is |
|---|---|
| [AGENTS.md](AGENTS.md) | Rules for anyone (or any coding agent) building here |
| [Additional.md](Additional.md) | Organizer guidance: what to do and not do |
| [docs/product/USER_JOURNEYS.md](docs/product/USER_JOURNEYS.md) | **The real problem, the real user, and each person's simple flow and channel** |
| [docs/product/00-PRODUCT-LIFECYCLE.md](docs/product/00-PRODUCT-LIFECYCLE.md) | Problem, evidence, users, market, metrics, risks, pilot path, and the status of each lifecycle stage |
| [docs/product/PRD.md](docs/product/PRD.md) · [BACKLOG.md](docs/product/BACKLOG.md) | Requirements and the prioritized backlog with status |
| [docs/product/WORKFLOW_AND_INTEGRATION.md](docs/product/WORKFLOW_AND_INTEGRATION.md) | How it fits the Abu Dhabi workflow (Malaffi, Sahatna, EMR) and how it scales |
| [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) · [ADR-001](docs/architecture/ADR-001-service-boundaries.md) | System design, services, API, schema; why the safety core is one service |
| [docs/engineering/](docs/engineering/) | [Security audit](docs/engineering/SECURITY_AUDIT.md), [failure modes](docs/engineering/FAILURE_MODES.md), [testing strategy](docs/engineering/TESTING_STRATEGY.md), [operations](docs/engineering/OPERATIONS.md) |
| [docs/evidence/](docs/evidence/) | [Test cases](docs/evidence/TEST_CASES.md), [hard cases](docs/evidence/HARD_CASES.md), [benchmark](docs/evidence/benchmark.md), [scale](docs/evidence/SCALE_POSTGRES.md), [review checklist](docs/evidence/REVIEW.md) |
| [docs/lovable/LOVABLE_BRIEF.md](docs/lovable/LOVABLE_BRIEF.md) | UI brief for Lovable, with the API contract, OpenAPI files and real response fixtures |
| [docs/submission/](docs/submission/) | Form text and video script drafts |

## The services
| Service | Port | What it does |
|---|---|---|
| case-core API (`tasleem`) | 8000 | The only writer of clinical state: rules R1–R6, audit chain, inboxes, outbox |
| scheduler | — | Deadlines and escalations, as its own process |
| notifier (`tasleem_notifier`) | 8010 | Reaches each person on their own channel: Sahatna, content-free SMS, EMR inbox, worklist, digest |
| agent (`tasleem_agent`) | 8020 | Suggest-only AI: cited case briefs and policy-checked patient drafts; no write access |
| HL7 connector (`tasleem_connector`) | 8030 | HL7 v2 ORU / REF / SIU from labs, GI centres and Malaffi to FHIR, with ACKs |

## Run it

Everything, on Docker (API, scheduler, notifier, agent, connector, PostgreSQL, Redis):
```bash
docker compose up -d --build --wait
```
```bash
cd backend && python -m tasleem.smoke --stack
```

Backend only, for development:
```bash
cd backend
pip install -c constraints.txt -e ".[dev]"
python -m pytest -q
TASLEEM_DEMO_MODE=true TASLEEM_SEED_ON_START=true uvicorn tasleem.api.app:app --reload
```
Open http://localhost:8000/docs. Demo mode is **off by default**. With it on, send `X-Demo-User: dr-fatima` (or any id from `GET /v1/directory/people`). The other services run the same way: `uvicorn tasleem_notifier.app:app --port 8010`, and likewise for `tasleem_agent` and `tasleem_connector`, each with `<PREFIX>_DEMO_MODE=true`. Every setting is in [backend/.env.example](backend/.env.example).

Evidence commands:
- `python -m tasleem.bench`: three-arm benchmark.
- `python -m tasleem.bench.hardcases`: 67 labelled hard cases.
- `python -m tasleem.loadtest --patients 5000`: scale run.
- `python -m tasleem.migrate`: database migrations.

## Demo personas (fictional)
| Id | Role | Their channel |
|---|---|---|
| `dr-fatima`, `dr-salma` | Family physicians (default case owners) | EMR inbox task; SMS page when urgent |
| `nav-aisha` | Care navigator | Tasleem worklist |
| `dr-omar`, `dr-lina` | Gastroenterologists | EMR inbox task |
| `dr-hessa` | Clinic lead (escalation level 2) | EMR inbox task |
| `coord-sara` | Programme coordinator (escalation level 3) | Daily e-mail digest |
| `p-noura`, `p-sunita`, … | Patients (companion view at `/v1/me/cases`) | Sahatna; SMS nudge; a navigator's call |

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).
