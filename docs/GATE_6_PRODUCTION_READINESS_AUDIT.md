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
| 3 | **Backup & restore** | **VERIFIED** (app-level) | App-level per-farm logical backup **tested end-to-end** (Inc 3 — see §Backup/restore verification below): create → verify(checksum) → data-loss → dry-run → applied restore → integrity + operability, plus missing/corrupted failure paths. `backup_service`; `production.py` endpoints; automated in `tests/integration/test_backup_restore_cycle.py`. | DB-level (Supabase PITR) is out-of-scope locally (needs the DB) — cover in the DR runbook (Inc 4). Interrupted-restore not tested (see limitations). |
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

---

## Backup/restore verification (Increment 3 — real execution, not inspection)

Exercised the **actual** `backup_service` against real rows (throwaway farm: 1 flock + 3 daily logs), automated in `tests/integration/test_backup_restore_cycle.py` (3 tests, all pass).

**Measured (small dataset, local embedded Postgres — sizes are real; times are local-dev and scale with data volume):**
| Metric | Value |
|---|---|
| Backup size | 2,658 bytes (JSON snapshot, 6 entity types) |
| Backup create time | ~130 ms |
| **Restore time (RTO)** | ~150 ms service / ~220 ms wall (incl. the safety backup) |
| Manual intervention | **none** — create/verify/restore are single service calls |

**Verified behaviors:**
- **Data integrity:** a soft-deleted flock was **revived** and hard-deleted logs **re-created**; restored counts matched the pre-loss state exactly.
- **App operability after restore:** the API served the restored farm (`GET /farms/{id}/flocks` → 200).
- **Dry-run** reports what would change and **writes nothing** (confirmed the flock stayed deleted after a dry run).
- **Safety-first:** an applied restore **takes a safety backup first** (observed `safety_backup_id`) → the restore is itself reversible.
- **Integrity gate:** `verify_backup` recomputes the checksum; a **tampered** payload verifies **invalid** and `restore_backup` **refuses** it.
- **Missing backup:** restoring an unknown id raises `NotFoundException` (404).

**RTO / RPO:**
- **RTO (measured):** the app-level per-farm restore completes in well under a second for a small farm; it grows with the farm's row count and the 32 MB payload cap. A production-scale RTO must be re-measured on staging with a large seed.
- **RPO (stated, not estimated):** app-level backups are **on-demand / scheduled snapshots**, so the RPO is *time since the last backup* — it depends on the backup **schedule**, which is an operational policy, not a code property. Continuous point-in-time recovery (sub-minute RPO) is provided by **Supabase PITR**, which **cannot be measured from this local environment** (no access to the managed DB); it must be verified on staging/production. I am not estimating a number.

**Honest limitations:**
- **Interrupted restore** was **not** tested — cleanly killing a process mid-transaction isn't reproducible in-test. Mitigation in the design: an applied restore runs inside a transaction and takes a safety backup first, so a crash rolls back rather than leaving a half-restored farm. Recommend a real interrupted-restore drill on staging.
- Scope is the **6 `BACKUP_ENTITIES`** (flocks, daily_logs, expenses, revenue, vaccinations, inventory). Other modules' data (aviculture/BSF/rabbit/SR/swine, media, AI) are **not** in the app-level backup — for those, **DB-level backup/PITR is the recovery path**. This boundary belongs in the DR runbook (Inc 4).
