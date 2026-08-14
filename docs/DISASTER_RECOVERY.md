# Greena Disaster Recovery

Recovery procedures per failure mode. Status marks what is **verified** vs.
**owner-gated**. Nairobi time throughout.

## Recovery point / recovery time
- **RPO (data loss window)**: currently **unbounded** — Supabase free tier has no PITR/automated backups. *This is the top DR gap; see §Backups.*
- **RTO (time to restore service)**: minutes — Render/Vercel redeploy or rollback; the app is stateless (all state in Supabase).

## Failure modes

| Failure | Detection | Recovery | Status |
|---|---|---|---|
| **Backend crash / OOM** | `/health` down; Render restart event | Render auto-restarts the container; migration re-runs (idempotent), scheduler re-elects leader. Verify `/health` 200. | ✅ Verified (multiple deploys) |
| **Bad deploy** | Deploy `update_failed`; `/health` 404/503 | Render keeps the prior live deploy serving. Roll back: dashboard → Deploys → last-good → Rollback, or `POST /deploys {"commitId":"<sha>"}`. | ✅ Verified |
| **Server reboot** | Instance restart | Stateless app reboots, migration runs, health gates traffic. | ✅ Verified |
| **Scheduler stops / lock lost** | Missing job effects | Advisory lock is re-acquired by the next instance (handover). Restart the service to force re-election. | ✅ Verified |
| **Database disconnect** | `/health` → 503 | Health gate stops traffic to the instance. Check Supabase project not **paused**; check pooler host resolves; app reconnects when DB returns. | ✅ Verified (503 gate) |
| **Database corruption / bad data** | Anomalies, failed queries | Restore from backup (see §Backups). Additive-only migrations mean schema rollback is rarely needed. | ⛔ Needs backups |
| **AI (Gemini/Claude) timeout/outage** | ARIA slow/failing | Calls bounded at 15s; ARIA is deterministic-first with an **offline fallback** — the app keeps working, AI degrades gracefully. Key rotation via env if a provider key fails. | ✅ By design |
| **Paystack timeout/outage** | Checkout/verify failing | Calls bounded at 20s. Initialization failures surface to the user; webhooks are retried by Paystack and are idempotent + re-verified, so no double effect. Subscriptions already active are unaffected. | ✅ By design |
| **Email/SMTP outage** | Verification/reset emails not sent | Auth works without email (verification gated off by config); transactional emails queue/fail without blocking core flows. Switch `EMAIL_PROVIDER` if needed. | ✅ Non-blocking |
| **Supabase full outage** | `/health` 503, DB unreachable | No app-side fix — wait for Supabase, or restore to a new project from backup and repoint `DATABASE_URL`. | ⛔ Needs backups |
| **Frontend (Vercel) issue** | Site down/broken | `vercel rollback <prev-url>` or promote a prior deployment. | ✅ Verified path |
| **Exposed credential** | Key leak | Rotate in the provider dashboard → redeploy → verify. (Live Paystack, Render, Northflank keys were shared in setup chat — rotate.) | ⚠ Owner action |

## Backups (the priority DR action — owner)
Free Supabase has no automated backup. Choose one:
1. **Upgrade Supabase** to a paid plan → automated daily backups + PITR (recommended).
2. **Scheduled `pg_dump`** to off-site storage (e.g. daily cron via a small worker):
   `pg_dump "$DATABASE_URL" --no-owner --format=custom -f greena_$(date +%F).dump`
   Store encrypted, off the same provider. Test a restore quarterly.

Until one is in place, **RPO is unbounded** — do not run risky data operations without a manual `pg_dump` first.

## Restore drill (run once backups exist)
1. Provision a fresh Supabase project (or use PITR).
2. `pg_restore` the latest dump.
3. Point a staging Render service's `DATABASE_URL` at it; boot; `/health` 200; spot-check row counts and `alembic_version = 091`.
4. Record the measured restore time as the real RTO.

## Contacts & ownership
Record out-of-band: account owners + 2FA recovery for Render, Vercel, Supabase, Paystack, GitHub; the password-manager entry for each production secret (names only in [OPERATIONS_AND_RBAC.md](OPERATIONS_AND_RBAC.md)).
