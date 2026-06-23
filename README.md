# devrails-core

**DevRails** is a lightweight GCP-only usage guardrail tool for builders who want to experiment on Google Cloud without surprise invoices. It alerts users of GCP usage in near real-time, allowing them to stay within the GCP free tier for $1/month.

DevRails is a product of [Elmscorp](https://thecollcon.com) and part of the Coll-Con ecosystem.

---

## Execution Contract

This repository is governed by **PRD-001 v1.0 — DevRails Proof of Concept**.

Target milestone: **July 4, 2026 PoC Production**

If a feature, requirement, architecture choice, or deployment decision is not in PRD-001 v1.0 or explicitly approved by E, it is not part of this build.

---

## Repository Structure

```
devrails-core/
├── web-app/          # Next.js App Router + TypeScript + Tailwind — authenticated dashboard UI
├── spike-engine/     # Python — Cloud Monitoring polling and usage guardrail logic
├── docs/             # Setup guides, Firestore contract, deployment docs, teardown steps
├── infra/            # Infrastructure configs (Cloud Run, Scheduler, Secret Manager references)
├── .gitignore        # Excludes credentials, env files, build artifacts, venvs
├── .env.example      # Sanitized placeholder — never put real values here
└── README.md         # This file
```

---

## Local Setup

See [`docs/local-setup.md`](docs/local-setup.md) for full local development instructions.

Quick orientation:

- `web-app/` runs with `npm install && npm run dev` (requires Node 18+)
- `spike-engine/` runs in a Python virtual environment (requires Python 3.11+)
- Local GCP credential goes at `spike-engine/credentials/devrails-poc-sa.json` — **never commit this file**
- All environment variables use `.env.local` (web-app) — copy from `.env.example` and fill in values

---

## Credential Safety

The local GCP Service Account JSON key must **never** be committed to this repository.

The `.gitignore` explicitly excludes `spike-engine/credentials/devrails-poc-sa.json` and all `*.json` files inside `spike-engine/credentials/`.

For production PoC, the credential is stored in GCP Secret Manager as `devrails-poc-monitoring-sa-key` and mounted into Cloud Run. It is never stored in Firestore, never exposed to the frontend, and never logged.

---

## PoC Scope

PRD-001 validates **Free Tier Watch** only. The following are explicitly out of scope for this PoC:

- Monthly Budget Watch
- Billing or cost estimation of any kind
- User-facing credential upload
- Alerts, killswitches, or guardrail actions
- Multi-project or multi-environment support
- Bucket 3 / Cloud Asset API / IAM analysis
- Payment or Stripe integration

---

## Team

| Role | Person |
|---|---|
| Founder / CEO / AI Orchestrator | E |
| CFO / Finance | Valerie |
| Product Manager | Lexie (GPT) |
| System Architect / GCP Backend | Kate (Gemini) |
| Tech Lead / Full-Stack | Claudia (Claude) |
| UI/UX / Frontend | Lovable |
