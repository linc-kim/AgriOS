# Disaster Recovery Runbook

Authoritative DR procedures for Greena. Built on the **measured** backup verification
(`GATE_6_PRODUCTION_READINESS_AUDIT.md §Backup/restore verification`), not assumptions.
Indexed from `RUNBOOK_INDEX.md`. Deploy stays gated on Gate 5.

## 1. Recovery coverage — what is and isn't recoverable

| Tier | Covers | Mechanism | Self-service? | RTO / RPO |
|---|---|---|---|---|
| **App-level backup/restore** | **Only the 6 legacy poultry-era entities**: `flocks, daily_logs, expenses, revenue_records, vaccination_records, inventory_items` (per `backup_service.BACKUP_ENTITIES`) | `backup_service` (checksum-gated, safety-backup-before-restore); `POST/GET /farms/{id}/data/backups` | Yes (per farm) | **RTO measured ~<1 s for a small farm** (scales with rows; 32 MB payload cap). RPO = time since last snapshot (schedule policy). |
| **Database PITR** | **Every table / every module** (aviculture, BSF, rabbit, small-ruminant, swine, media metadata, AI, auth, finance, …) | **Supabase** point-in-time recovery + automated daily backups | No — operator/Supabase console | **Environment-dependent (Supabase); NOT measured here** — verify on staging/production. |
| **No app-level recovery** | Newer modules listed above have **no application self-service restore** — they depend entirely on **DB PITR** until app-level coverage is expanded | — | — | Same as DB PITR |

> **Explicit gap (do not forget):** application backups currently cover **only the legacy
> poultry-era entities**. All newer modules depend on **database PITR** until app-level
> coverage is expanded. Expanding `BACKUP_ENTITIES` to the newer modules is tracked
> tech-debt, not a launch blocker (DB PITR is the safety net).
>
> **Stateful surfaces:** the **database is the only stateful component we own.** Uploaded
> files are processed in-memory (not stored on our servers); media are URL references;
> AI/email providers hold no Greena state. So if the database is recoverable, the platform
> is recoverable — external providers are stateless from our side.

## 2. Scenario procedures

Each: **Owner · Prerequisites · Detection · Recovery · Verification · Rollback criteria · Recovery validation.**

### 2.1 Database failure (unavailable / corrupted)
- **Owner:** on-call engineer + Supabase.
- **Prerequisites:** Supabase console access; the DB password; PITR enabled (confirm in Supabase → Database → Backups).
- **Detection:** `GET /health` → `503 {db: error}`; `/production/diagnostics` `database`/`schema`/`migrations` checks fail; Sentry SQLAlchemy errors.
- **Recovery:** for transient loss → the connection pool reconnects automatically (verify). For data corruption/loss → Supabase **PITR** to the last-good timestamp (RPO per Supabase). If only a farm's poultry-era data is affected, an **app-level restore** may be faster (measured <1 s small farm).
- **Verification:** `GET /health` → 200 `db: connected`; `/production/diagnostics` all critical checks pass; spot-check row counts vs `/production/status` `entities`.
- **Rollback criteria:** if PITR restores to a bad point, re-run PITR to a different timestamp (Supabase keeps the prior state until confirmed).
- **Recovery validation:** run the isolation probe + a smoke login + a couple of module reads.

### 2.2 Application failure (crash / bad image / boot failure)
- **Owner:** on-call engineer + Railway.
- **Prerequisites:** Railway access; a previous known-good deployment (tag the release — `DEPLOYMENT_HARDENING.md §3.2`).
- **Detection:** Railway health check red; `GET /health` unreachable; Railway restarts > 1.
- **Recovery:** Railway → Deployments → **rollback** to the last green image (~2 min). Boot-time config errors are caught by `run_startup_validation` (the process refuses to start rather than serve broken — the orchestrator never routes to it).
- **Verification:** `/health` 200 green for 10 min; smoke tests (`LAUNCH_RUNBOOK.md §3`).
- **Rollback criteria:** any 5xx spike or restart loop post-deploy → roll back.
- **Recovery validation:** login + module read + `/production/status` healthy.

### 2.3 AI provider outage (Gemini / Claude)
- **Owner:** on-call engineer.
- **Prerequisites:** none (self-healing by design).
- **Detection:** `GET /admin/ai/health` shows keys `rate_limited`/`quota_exhausted`/`failed`; rising AI failures.
- **Recovery:** **automatic** — the AI Provider Manager rotates keys, fails over Gemini→Claude→**offline**. No data impact; ARIA degrades to the grounded offline path. Optionally add/rotate a Gemini key (`GEMINI_API_KEY_2`) with no deploy.
- **Verification:** `/admin/ai/health` shows a key `available`; an ARIA query returns.
- **Rollback criteria:** n/a (degradation is the safe state).
- **Recovery validation:** confirm offline fallback answered during the outage (no fabricated data).

### 2.4 Email provider outage
- **Owner:** on-call engineer.
- **Prerequisites:** SMTP/provider credentials.
- **Detection:** signup/verification/reset emails failing; provider dashboard.
- **Recovery:** email is **not on the critical request path** — logins with existing accounts continue. Switch `EMAIL_PROVIDER`/`SMTP_*` to a working provider (config-only, no deploy); verification/reset resume. (SMS OTP stays dormant at launch.)
- **Verification:** trigger a password-reset email; confirm delivery.
- **Rollback criteria:** revert the provider config if the new one misbehaves.
- **Recovery validation:** end-to-end signup→verify on the new provider.

### 2.5 Scheduler / background-worker failure
- **Owner:** on-call engineer.
- **Prerequisites:** Railway access.
- **Detection:** `/production/diagnostics` `background_jobs` check (warning) shows failed jobs; expected reminders not sent.
- **Recovery:** the scheduler runs inside the app under a **Postgres advisory lock** (single leader across workers). Restart the service → the lock is re-acquired and jobs resume. Failed one-off jobs are visible in the `BackgroundJob` table for re-trigger.
- **Verification:** `background_jobs` check passes; a scheduled job runs on its next tick.
- **Rollback criteria:** n/a — restart is the recovery.
- **Recovery validation:** confirm one scheduled job completed post-restart.

### 2.6 Configuration or secret loss
- **Owner:** on-call engineer.
- **Prerequisites:** the secrets inventory (`DEPLOYMENT_HARDENING.md §2`, `LAUNCH_RUNBOOK.md §1.2`); ability to regenerate keys.
- **Detection:** app **fails to boot** (`run_startup_validation` rejects missing/invalid required vars) → orchestrator won't route traffic; `/production/diagnostics` `environment` check fails.
- **Recovery:** re-set the missing var in Railway/Vercel; for a **leaked** secret, **rotate** it (treat as compromised — Doc 3 §39): DB password (Supabase), `JWT_SECRET`/`SECRET_KEY` (regenerate — note: rotating `JWT_SECRET` invalidates active sessions), Gemini/Claude keys, SMTP. Redeploy.
- **Verification:** app boots, `/health` 200, `environment` diagnostic passes.
- **Rollback criteria:** if a rotated `JWT_SECRET` causes mass logout you didn't intend, that is expected — communicate rather than roll back a compromised secret.
- **Recovery validation:** login works with the new config.

### 2.7 Failed deployment
- **Owner:** on-call engineer.
- **Prerequisites:** tagged previous release; `DEPLOYMENT_HARDENING.md §4`.
- **Detection:** Railway health check fails post-deploy (auto-rollback triggers); smoke tests fail; Sentry spike.
- **Recovery:** Railway auto-rolls-back on failed health check; else manual rollback (§2.2). If a **migration** shipped, assess before reverting code (`alembic downgrade` only if safe — read the migration first).
- **Verification:** `/health` green 10 min; smoke tests pass.
- **Rollback criteria:** any NO-GO item (`LAUNCH_RUNBOOK.md §6`).
- **Recovery validation:** full smoke suite + `/production/status` healthy.

## 3. RTO / RPO summary

| Path | RTO | RPO |
|---|---|---|
| App-level restore (poultry-era) | **~<1 s small farm (measured)**; scales with rows | time since last snapshot (schedule policy) |
| Database PITR (all data) | **Supabase-dependent — not measured locally** | **Supabase continuous PITR — not measured locally** |
| App rollback (Railway) | ~2 min (previous image hot) | n/a |

RPO/RTO values marked *not measured locally* are **environment-dependent** and must be
established on staging/production against the real Supabase project — **not estimated here.**

## 4. DR validation cadence (recommended)
- App-level backup/restore: automated (`tests/integration/test_backup_restore_cycle.py`) — keep green.
- DB PITR restore drill: perform on staging before launch and quarterly (record RTO/RPO).
- Interrupted-restore drill: perform once on staging (not reproducible in-test).
