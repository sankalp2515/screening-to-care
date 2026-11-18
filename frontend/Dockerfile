# Tasleem web app: the staff console and the patient companion, as one static bundle behind nginx.
# Build from the repository root so the synthetic demo bundle (docs/lovable/demo) is in the context:
#   docker build -f frontend/Dockerfile -t tasleem-frontend:local .
#
# Two modes, chosen at build time (Vite inlines VITE_* variables):
#   live (default in compose)  the app calls case-core, agent, notifier and the HL7 connector through this
#                              container's nginx at /api/<service>/, so the browser never needs CORS
#   demo (VITE_DEMO_MODE=true) the app replays the recorded synthetic bundle and needs no backend
FROM node:22-alpine AS build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY docs/lovable/demo/demo-bundle.json /src/docs/lovable/demo/demo-bundle.json
# The frontend tests check that every landing-page number appears in this evidence file.
COPY docs/evidence/REAL_WORLD_FIT.md /src/docs/evidence/REAL_WORLD_FIT.md
ARG VITE_DEMO_MODE=false
ARG VITE_API_BASE_URL=/api/core
ARG VITE_AGENT_URL=/api/agent
ARG VITE_NOTIFIER_URL=/api/notifier
ARG VITE_CONNECTOR_URL=/api/connector
# Local placeholder that matches NOTIFIER_OPS_KEY in docker-compose.yml. It is inlined into public JavaScript,
# so it must never be a real secret: production puts the ops action behind staff sign-in instead.
ARG VITE_NOTIFIER_OPS_KEY=local-ops-key
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_AGENT_URL=$VITE_AGENT_URL \
    VITE_NOTIFIER_URL=$VITE_NOTIFIER_URL VITE_CONNECTOR_URL=$VITE_CONNECTOR_URL \
    VITE_NOTIFIER_OPS_KEY=$VITE_NOTIFIER_OPS_KEY
# Tests exercise the demo replayer, so they always run in demo mode whatever the build mode is.
RUN VITE_DEMO_MODE=true npm test && npm run build

# Unprivileged nginx: runs as a non-root user and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY frontend/deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/deploy/proxy.inc /etc/nginx/conf.d/proxy.inc
COPY frontend/deploy/security.inc /etc/nginx/conf.d/security.inc
COPY --from=build /src/frontend/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=10 CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
