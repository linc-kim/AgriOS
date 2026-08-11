# Operational Runbook Index

Single navigation point for Greena's deployment/operations documentation. Several
deployment docs overlap; this index names the **authoritative** one for each concern
so contributors don't follow a stale copy. (Gate 6 — Production Readiness.)

> **Deploy is not authorized.** Production deployment stays gated on Gate 5
> (performance) passing on staging + the open Gate 6 items. Deploy workflows are parked.

## Authoritative runbooks

| Doc | Purpose | Status |
|---|---|---|
| `DEPLOYMENT_HARDENING.md` | **Authoritative** deploy runbook: launch blockers (shared domain, CSP, scheduler lock), env checklist, deploy/migrate commands, code/schema/data **rollback**, Supabase pooling | Current |
| `docs/LAUNCH_RUNBOOK.md` | Launch-day: pre-launch checklist, secrets (reconciled to `config.py`), smoke tests, monitoring setup, Go/No-Go, day-1–7 tasks | **Refreshed 2026-08-11** (migration head, secrets, email-first auth) |
| `docs/GATE_5_STAGING_RUNBOOK.md` | Staging deploy + load-test execution (Phase 2/3/4) | Current (Gate 5, paused) |
| `docs/GATE_5_PERFORMANCE_REPORT_TEMPLATE.md` | Reusable perf-run report template | Current |
| `docs/GATE_6_PRODUCTION_READINESS_AUDIT.md` | 11-area readiness matrix + gap plan | Current |

## Supporting / reference

| Doc | Purpose | Note |
|---|---|---|
| `SYSTEM_ARCHITECTURE.md` | Platform architecture | Reference |
| `DEPLOYMENT.md`, `DEPLOYMENT_GUIDE.md`, `DEPLOYMENT_ENVIRONMENTS.md` | Older deployment notes | **Overlap** `DEPLOYMENT_HARDENING.md` — treat HARDENING as authoritative; these may carry pre-Gate details (verify before use) |
| `docs/DEVELOPMENT_ENVIRONMENT.md` | Local dev setup | Reference |
| `KNOWN_TECHNICAL_DEBT.md` | Tracked debt (note: a couple entries are stale — feature flags exist, migration-028 fixed) | Reference |
| `backend/.env.example` | Full annotated env-var list | Authoritative for config |

## To be produced (Gate 6, in order)

| Concern | Planned home |
|---|---|
| Backup/restore **tested** evidence | Gate 6 Inc 2 report |
| Disaster recovery (scenarios, RTO/RPO) | new DR runbook |
| Alerting configuration | new alerting doc / extend monitoring |
| Monitoring configuration | monitoring doc |
| Production security review (RLS, secrets, auth, authz, upload, AI, ops) | security-review doc |
| Incident response, provider-outage, scheduler recovery, secret rotation | operational runbooks |
| Paystack integration **plan** (implementation deferred) | plan doc |
