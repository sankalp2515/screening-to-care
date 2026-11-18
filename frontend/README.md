# Tasleem frontend

React 18, Vite, TypeScript, Tailwind 4, Radix (shadcn-style primitives), TanStack Query, Recharts, lucide-react.
Design rules: [../DESIGN.md](../DESIGN.md) ("Sheet and biro"). Product spec for every screen: [../docs/lovable/LOVABLE_ONE_SHOT.md](../docs/lovable/LOVABLE_ONE_SHOT.md).

```bash
npm install
npm run dev      # http://localhost:5173, demo mode (synthetic data, no backend needed)
npm test         # demo replayer and safety-rule tests
npm run build    # static site in dist/
```

## Modes
- **Demo (default):** replays `docs/lovable/demo/demo-bundle.json`, real responses recorded from the Tasleem services (copied to `public/` by `scripts/sync-bundle.mjs`). Rule outcomes come from the recorded server `actions`; the patient-message policy is an exact port of `backend/tasleem/domain/messaging.py`. Actions that were not recorded answer `DEMO_NOT_RECORDED` instead of pretending.
- **Live:** set `VITE_API_BASE_URL` (core), `VITE_AGENT_URL`, `VITE_NOTIFIER_URL`, `VITE_CONNECTOR_URL` and leave `VITE_DEMO_MODE` unset. Requests carry `X-Demo-User: <persona>`. Never put live keys in a committed file.

## Container
The `web` service in [../docker-compose.yml](../docker-compose.yml) builds [Dockerfile](Dockerfile) from the repository root: Node 22 runs the tests and the build, then unprivileged nginx (port 8080) serves `dist/` with a single-page fallback and proxies `/api/<service>/` to case-core, agent, notifier and connector ([deploy/nginx.conf](deploy/nginx.conf)). It is built in live mode by default.

```bash
docker build -f frontend/Dockerfile -t tasleem-frontend:local .                                  # live (needs the stack)
docker build -f frontend/Dockerfile --build-arg VITE_DEMO_MODE=true -t tasleem-frontend:demo .   # standalone synthetic replay
```

Only `frontend/`, the demo bundle and `docs/evidence/REAL_WORLD_FIT.md` enter the build context (root [.dockerignore](../.dockerignore)), so `backend/.env` never does. `VITE_NOTIFIER_OPS_KEY` is inlined into public JavaScript and defaults to the local placeholder; it must never be a real secret.

## Routes
`/` landing · `/demo` persona picker and guided tour · `/app/work` · `/app/cases` · `/app/cases/:id` · `/app/programme` · `/app/simulator` · `/patient` (390 px companion, Arabic and English).

Static hosting needs a single-page fallback (all paths serve `index.html`).
