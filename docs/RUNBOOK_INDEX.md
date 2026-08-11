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
| `docs/GATE_6_PRODUCTION_READINESS_AUDIT.md` | 11-area readiness matrix + gap plan + backup/restore verification evidence | Current |
| `docs/DISASTER_RECOVERY.md` | **Authoritative** DR: recovery coverage tiers (app-backup vs DB PITR vs no-recovery), 7 scenario procedures, RTO/RPO | Current (Gate 6 Inc 4) |
| `docs/ALERTING.md` | **Authoritative** alert matrix (Critical/High/Medium/Info) grounded on exposed signals only | Current (Gate 6 Inc 4) |

## Supporting / reference

| Doc | Purpose | Note |
|---|---|---|
| `SYSTEM_ARCHITECTURE.md` | Platform architecture | Reference |
| `DEPLOYMENT.md`, `DEPLOYMENT_GUIDE.md`, `DEPLOYMENT_ENVIRONMENTS.md` | Older deployment notes | **Overlap** `DEPLOYMENT_HARDENING.md` — treat HARDENING as authoritative; these may carry pre-Gate details (verify before use) |
| `docs/DEVELOPMENT_ENVIRONMENT.md` | Local dev setup | Reference |
| `KNOWN_TECHNICAL_DEBT.md` | Tracked debt (note: a couple entries are stale — feature flags exist, migration-028 fixed) | Reference |
| `backend/.env.example` | Full annotated env-var list | Authoritative for config |

## To be produced (Gate 6, in order)

| Concern | Status / planned home |
|---|---|
| Backup/restore **tested** evidence | ✅ `GATE_6_PRODUCTION_READINESS_AUDIT.md §Backup/restore verification` |
| Disaster recovery (scenarios, RTO/RPO) | ✅ `DISASTER_RECOVERY.md` |
| Alerting configuration | ✅ `ALERTING.md` |
| Monitoring configuration | Gate 6 Inc 4+ — extend `ALERTING.md` §Signal sources / a monitoring doc |
| Production security review (RLS, secrets, auth, authz, upload, AI, ops) | Gate 6 (next) — security-review doc |
| Incident response, provider-outage, scheduler recovery, secret rotation | provider-outage/scheduler/secret-rotation covered in `DISASTER_RECOVERY.md §2`; a general incident-response runbook still to add |
| Paystack integration **plan** (implementation deferred) | Gate 6 (last) — plan doc |
