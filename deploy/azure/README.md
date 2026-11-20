# Tasleem on Azure (prototype)

Live link: **https://tasleem.swedencentral.cloudapp.azure.com**. All data is synthetic. Judges pick a role on
`/demo`; full hospital sign-in (OIDC) is not built yet.

## What runs where

| Part | Azure service | Why |
|---|---|---|
| All 5 services + web gateway + scheduler | 1 Linux VM, `Standard_B4als_v2` (4 vCPU, 8 GB), Docker Compose, started at boot by `tasleem.service` | Same images and the same compose file we test locally |
| Database (case-core, notifier, agent: one database each) | Azure Database for PostgreSQL Flexible Server 16, Burstable B1ms | Managed, encrypted at rest, TLS only, daily backups with 7-day point-in-time restore |
| AI drafting (agent) | Azure OpenAI, deployment `gpt-5-mini` (Global Standard), reasoning effort `minimal` | Suggest-only drafting; templates take over on any failure |
| Secrets | Azure Key Vault (RBAC), read by the VM's managed identity | No secret in the repository, the image or a hand-copied file |
| HTTPS | Caddy with an automatic Let's Encrypt certificate | HTTP redirects to HTTPS; HSTS |
| Monitoring | Application Insights standard test of `/api/core/healthz` from 3 locations every 10 min; alert to the subscription Owner when 2 fail | Someone knows within minutes if the link is down during judging |
| Cost guard | Free-trial spending limit; budget emails at 50 % and 80 % actual and 100 % forecast of $200 | The credit is the most it can cost |

Region: **Sweden Central**. The free trial offers no virtual machines in UAE North or UAE Central. Production
for Abu Dhabi would run in Azure UAE North under DoH data rules; nothing here depends on the region.

## Network exposure

- Internet → VM: 443 and 80 only (80 only redirects). SSH (22) from one admin IP only.
- No service port (8000–8030, 8080) is published; services talk on the private Docker network.
- PostgreSQL accepts only the VM's IP, over TLS.

## Files

| File | Purpose |
|---|---|
| `compose.azure.yml` | Overlay on `docker-compose.yml`: managed Postgres, no published ports, Azure OpenAI, Caddy |
| `Caddyfile` | HTTPS front door, proxies to the `web` gateway |
| `fetch-secrets.sh` | Runs before every start: managed identity → Key Vault → `/opt/tasleem/secrets.env` (root, 0600) |
| `tasleem.service` | systemd unit: fetch secrets, then `docker compose up -d` |

Key Vault secret names: `core-db-url`, `notifier-db-url`, `agent-db-url`, `core-integration-keys`, `notifier-key`,
`connector-key`, `azure-openai-key`, `azure-openai-base-url`, `site-host` (and `pg-admin-password`).

## Operate

```bash
ssh -i ~/.ssh/tasleem_azure tasleem@tasleem.swedencentral.cloudapp.azure.com
sudo systemctl restart tasleem          # fetch secrets again and restart the stack
cd /opt/tasleem/app && sudo docker compose -p tasleem -f docker-compose.yml -f deploy/azure/compose.azure.yml --env-file /opt/tasleem/secrets.env ps
```

Check from anywhere:

```bash
python -m tasleem.smoke --base https://tasleem.swedencentral.cloudapp.azure.com/api/core --stack \
  --notifier https://tasleem.swedencentral.cloudapp.azure.com/api/notifier \
  --agent https://tasleem.swedencentral.cloudapp.azure.com/api/agent \
  --connector https://tasleem.swedencentral.cloudapp.azure.com/api/connector
```

The smoke test writes test cases. Afterwards, reset to the clean seed: stop the service, drop and recreate the
three databases (`az postgres flexible-server db delete/create`), start the service (migrations and the seed run
on start).

## Update the code

Package the repository's tracked and unignored files (`git ls-files -co --exclude-standard`), copy the archive
to `/opt/tasleem/app`, then rebuild and restart:

```bash
sudo docker compose -p tasleem -f docker-compose.yml -f deploy/azure/compose.azure.yml --env-file /opt/tasleem/secrets.env build
sudo systemctl restart tasleem
```

## Daily audit anchor (TSL-173)

Each case's audit chain is hash-linked. Once a day the server also publishes one root hash over every chain
to the systemd journal, outside the database:

```bash
sudo cp deploy/azure/tasleem-audit-anchor.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tasleem-audit-anchor.timer
journalctl -u tasleem-audit-anchor --since today      # {"kind": "tasleem.audit_anchor", "root": "..."}
```

To check that history has not been rewritten, compare a published root with
`GET /api/core/v1/program/audit-anchor?as_of=<the same time>` (programme coordinator).
