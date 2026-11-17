# One image, several services. Each compose/Kubernetes service picks its command:
#   case-core API   uvicorn tasleem.api.app:app --port 8000        (default)
#   scheduler       python -m tasleem.workers.scheduler
#   migrations      python -m tasleem.migrate
#   notifier        uvicorn tasleem_notifier.app:app --port 8010
#   agent           uvicorn tasleem_agent.app:app --port 8020
#   HL7 connector   uvicorn tasleem_connector.app:app --port 8030
# One image keeps the shared library and dependency versions identical across services; each service
# still scales, deploys and fails on its own.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml alembic.ini constraints.txt ./
COPY migrations ./migrations
COPY pathways ./pathways
COPY tasleem ./tasleem
COPY tasleem_common ./tasleem_common
COPY tasleem_notifier ./tasleem_notifier
COPY tasleem_agent ./tasleem_agent
COPY tasleem_connector ./tasleem_connector
RUN pip install -c constraints.txt ".[postgres,redis,agent]" && useradd --create-home --uid 10001 app
USER app

ENV TASLEEM_PATHWAYS_DIR=/app/pathways
EXPOSE 8000 8010 8020 8030
CMD ["uvicorn", "tasleem.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
