# Security policy

Tasleem is a prototype that runs on synthetic data only. It still treats security as part of patient safety.

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private reporting instead: **Security → Report a vulnerability** on this repository. Include the steps to reproduce, the affected service (case-core API, notifier, agent, connector or web) and the impact you see.

We aim to acknowledge a report within 3 working days and to share a fix plan within 10.

## In scope

- The code in this repository and the public demo at https://tasleem.swedencentral.cloudapp.azure.com.
- Anything that could let one clinic see another clinic's cases, bypass a safety rule (R1–R6), break the audit chain, disclose a result in a patient message, or give the AI agent write access.

## Out of scope

- Denial-of-service or load testing against the public demo.
- Findings that need real patient data. The demo has none, and testers must never add any.
- The demo's guest personas. They are open on purpose so reviewers can try every role; production uses UAE Pass and Entra ID sign-in (see the roadmap, TSL-169).

## What is already in place

Scoped service keys, per-clinic data scoping that hides existence (404), rate limits, security headers, HTTPS only, secrets in Azure Key Vault through a managed identity, no payloads or names in logs, a pinned and audited dependency set, and a hash-chained audit log. Details and open items: [docs/engineering/SECURITY_AUDIT.md](docs/engineering/SECURITY_AUDIT.md).
