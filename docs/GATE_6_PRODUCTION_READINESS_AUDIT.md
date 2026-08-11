# GATE 6 — Production Readiness Audit (Increment 1)

**Status:** audit only (evidence-based). No code changed. **Production deployment stays disabled until Gate 5 resumes and its criteria are met.** Awaiting approval. Not committed.
**Date:** 2026-08-11 · Scope: the 11 staging-independent readiness items.

## Method
Reviewed the repo's existing production-readiness artifacts and classified each area **COMPLETE / PARTIAL / MISSING** with evidence, then a gap + recommended action. A lot already exists — this gate mostly reconciles, tests, and fills specific gaps rather than building from scratch (Master Index §10, §51).

## Readiness matrix

| # | Area | State | Evidence | Gap → action |
|---|---|---|---|---|
| 1 | **Deployment architecture** | PARTIAL | `SYSTEM_ARCHITECTURE.md`, `DEPLOYMENT.md`/`_GUIDE`/`_ENVIRONMENTS`/`_HARDENING.md`, `backend/Dockerfile`, `backend/railway.toml`, `frontend/vercel.json`; `DEPLOYMENT_HARDENING.md §1` names the real launch blockers (shared registrable domain, CSP `connect-src`, scheduler advisory lock) | Docs carry stale details (AGRIOS↔Greena naming; runbook migration head). **Action:** consolidated current-state architecture note + reconcile stale bits. |
| 2 | **Secrets verification** | COMPLETE | This audit's scan: **no tracked `.env`**, no live-key patterns, no hardcoded secret literals in `backend/app`; `config.py` fail-fast env validation; secrets inventory in `DEPLOYMENT_HARDENING.md §2`; AI keys backend-only (Gate 4) | Frontend **production bundle** secret scan (Doc 4 §109) still runs at deploy time. **Action:** add to the release checklist. |
| 3 | **Backup & restore** | PARTIAL | App-level per-farm logical backup **implemented**: `backup_service.create_backup / verify_backup (checksum) / restore_backup / apply_retention`; `production.py` endpoints; DB-level PITR is Supabase (documented in HARDENING) | **No tested restore evidence** (Doc 4 §106: "a backup isn't reliable until restoration is tested"). **Action:** run an app-level backup→restore→verify locally and record it. |
| 4 | **Disaster recovery documentation** | MISSING (dedicated) | Rollback procedures exist (`DEPLOYMENT_HARDENING.md §4` code/schema/data) but no consolidated DR doc | **Action:** build a DR runbook — scenarios (DB loss, region/provider outage, corruption), RTO/RPO, recovery steps, degradation behavior. |
| 5 | **Monitoring configuration** | PARTIAL | Sentry (prod-gated, `main.py`), Prometheus-style `metrics_service` + `MetricsMiddleware`, `/health` (503 on DB down), `diagnostics_service`, `release_service` (release/rollback record) | No single doc of *what is monitored and where*. **Action:** monitoring configuration doc (signals, dashboards, retention). |
| 6 | **Alerting configuration** | MISSING | No alert rules found | **Action:** define alerts (error-rate, health-check failing, DB/pool pressure, AI failures, payment/webhook once integrated, cost spikes) + delivery + thresholds. |
| 7 | **Release checklist** | PARTIAL / STALE | `docs/LAUNCH_RUNBOOK.md` pre-launch checklist + smoke tests + security-header checks exist, **but reference migration head `030`** (actual head `086`) and old scope | **Action:** refresh into a current, authoritative release checklist. |
| 8 | **Operational runbooks** | PARTIAL | `DEPLOYMENT_HARDENING.md` (deploy/migrate/rollback), `LAUNCH_RUNBOOK.md` (smoke), `GATE_5_STAGING_RUNBOOK.md` | Missing: incident response, secret rotation, AI-provider outage, scheduler/queue recovery. **Action:** runbook set + an index. |
| 9 | **Production security review** | PARTIAL | Gate 2/3 hardening (Argon2id, IDOR sweeps, upload validation, SQLi-clean), security headers/HSTS/CSP, RLS-disabled recorded as defense-in-depth gap; `DEPLOYMENT_HARDENING.md` | No single prod security-review checklist mapped to the Security Standard. **Action:** consolidated review + explicit RLS decision. |
| 10 | **Environment validation** | COMPLETE | `diagnostics_service.run_startup_validation` + `environment_problems` — an invalid production config **fails boot** so the orchestrator never routes traffic (`main.py` lifespan) | KEEP; reference it in the release checklist. |
| 11 | **Paystack integration planning** | MISSING (by decision) | Not integrated; owner deferred payments to a separate post-hardening project (Gate 4 §6.2); DB has `subscription_plans`, manual M-Pesa today | **Action:** planning doc only (architecture, webhooks, idempotency, entitlements, test matrix) — implementation stays separate. |

## Summary
- **Solid already:** secrets hygiene, environment validation, monitoring instrumentation, app-level backup/restore code, deployment + rollback runbooks.
- **Real gaps to fill (staging-independent):** DR documentation, alerting configuration, a refreshed release checklist, additional operational runbooks, a consolidated production security review, a tested restore, and a Paystack **plan**.

## Recommended Gate 6 increment order (each: build → report → approval → commit)
1. **This audit** ✅
2. **Release checklist refresh** + operational-runbook index (reconcile stale runbook: migration head, naming) — highest leverage, unblocks the rest.
3. **Disaster recovery doc + alerting configuration** (the two clear MISSINGs).
4. **Backup/restore test** (real local evidence) + **monitoring configuration doc**.
5. **Consolidated production security review** (+ explicit RLS defense-in-depth decision).
6. **Paystack integration plan** (planning only).

No production deployment is enabled by any of this; deploy stays gated on Gate 5 resuming and passing.
