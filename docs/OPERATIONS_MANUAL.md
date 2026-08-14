# Greena Operations Manual

For whoever runs the platform. Everything here is executable against the real
production stack. Commit `beb8e8f` · schema head `091`.

## 1. Architecture at a glance
```
Browser ──► Vercel (agrioskenya.vercel.app)  ── static SPA, VITE_API_BASE_URL ─┐
                                                                               ▼
                                            Render web service greena-api  ──► Supabase Postgres
                                            (Docker, Frankfurt, 1 worker)      (pooler, eu-west-1)
                                                    │
                                                    ├─► Paystack (payments)
                                                    └─► Gemini / Claude (ARIA)
```
- Backend: `https://greena-api-v91z.onrender.com` · service `srv-d9uurhjncjis73ajvfbg`.
- DB reached over the **session pooler** `aws-0-eu-west-1.pooler.supabase.com:5432` (the direct `db.<ref>.supabase.co` host does not resolve externally).
- Health: `GET /health` → 200 `{"db":"connected"}`; returns **503** when the DB is unreachable so the orchestrator never routes to a degraded instance.

## 2. Deploying
**Backend** (auto on push to `phase-2-auth`, or manual):
```bash
curl -X POST https://api.render.com/v1/services/$SID/deploys \
  -H "Authorization: Bearer $RENDER_KEY" -H "Content-Type: application/json" -d '{}'
```
- Build = Dockerfile. Start = `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers ${WEB_WORKERS:-1}`.
- **Migrations run automatically on every boot** (idempotent; advisory-locked). Watch logs for `Application startup complete` + `Scheduler started — N jobs`.
- A deploy is healthy only when `/health` returns 200 — do not trust "live" alone.

**Frontend** (no upload; rebuilds from git with production env):
```bash
vercel redeploy <deployment-url> --target production
```
Verify the served CSP `connect-src` includes the backend origin, and `VITE_API_BASE_URL` points at `…/api/v1`.

## 3. Scheduled jobs (APScheduler, single leader via Postgres advisory lock)
All times **Africa/Nairobi**. Exactly one instance runs these regardless of replica count.

| Time | Job | Effect |
|---|---|---|
| 01:00 daily | Subscription Expiry Sweep | Expires lapsed subscriptions; downgrades entitlement |
| 02:30 daily | Backup Retention Sweep | Prunes old backup records per retention policy |
| Mon 04:00 | Operations Planner Optimisation Analysis | Weekly routine optimisation |
| 05:00 daily | Operations Planner Task Materialisation | Turns routines into concrete tasks |
| 06:00 daily | ARIA Daily Insights | Generates per-farm AI insights |
| 07:00 daily | Operations Planner Compliance Scan | Flags overdue/compliance gaps |
| 08:00 daily | Vaccination Reminders | Notifies upcoming vaccinations |
| 08:05 daily | Vaccination Overdue | Notifies overdue vaccinations |
| 20:00 daily | Daily Log Reminder | Reminds farms with no log that day |
| Fri 18:00 | Weekly Summary | Weekly performance digest |

Verify in logs: `APScheduler started`, then `this worker holds the scheduler lock`. On restart the lock is re-acquired by the next leader (handover, not duplication).

## 4. Monitoring
- **Health/uptime**: external pinger on `/health` (also keeps the free instance warm — cold start >60s after ~15 min idle).
- **Errors**: Sentry (initialised in prod). *Confirm event delivery in the Sentry dashboard and set an error-rate alert.*
- **Logs**: Render dashboard / API `GET /v1/logs?ownerId=…&resource=$SID`. Structured: `ts | level | logger | message`, with request-ids.
- **DB**: Supabase dashboard — watch pooler connections vs the 60 cap and DB CPU.
- **Payments**: Paystack dashboard — webhook delivery success, transactions, disputes.

## 5. Capacity (measured, not estimated)
Free tier (1 worker / 512 MB): **max ~8–10 rps, latency knee at ~5 concurrent**, 0 errors (graceful queueing); p95 833 ms @5 → 6.7 s @40. Not suitable for 250+ concurrent. Scale path: Render Standard+ (2 GB), 2+ instances, `WEB_WORKERS` 2–4, upgrade Supabase for connection headroom — then re-measure. Keep `(DB_POOL_SIZE + DB_MAX_OVERFLOW) × workers × instances + 1 < DB connection cap`.

## 6. Security posture (verified)
HSTS + CSP + X-Frame DENY + nosniff; refresh cookie `HttpOnly; Secure; SameSite=none; Path=/api/v1/auth`; rate limiting (RateLimitMiddleware → 429); CSRF origin check on cookie-bearing requests; webhook HMAC-SHA512 constant-time + Paystack re-verify; tenant isolation → 404 cross-org; JWT HS256. Docs disabled in prod. See OPERATIONS_AND_RBAC.md for the full hardening audit.

## 7. Common operational tasks
- **Rotate a secret**: update in Render (backend) / Paystack dashboard → redeploy → verify `/health` + a signed webhook.
- **Add an env var**: `PUT /v1/services/$SID/env-vars/{KEY}` (single-var; does not touch others) → redeploy.
- **Read prod DB safely**: connect via the pooler with `DATABASE_SSL=true`; read-only queries only in incident response.
- **Run/confirm a migration**: it runs on deploy; to check, `alembic current` against the pooler equals `alembic heads`.

## 8. Incident quick-reference → see [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md)
`/health` 503 → DB unreachable (check Supabase not paused, pooler host). Deploy `update_failed` → read logs; common causes: missing dep (prod-only import), bad start command. 429s → rate limit tripped. Cold-start latency → warm via `/health`.
