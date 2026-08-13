# Greena V1.0.0 — Release & Operations

Status: **READY FOR CONTROLLED (BETA) LAUNCH** — see [Known Limitations](#known-limitations) and [Go / No-Go](#go--no-go).
Date: 2026-08-13 · Backend commit: `89e5bc3` · Branch: `phase-2-auth`

Production stack: **Vercel** (frontend) → **Render** (backend) → **Supabase** (database) · **Paystack** (payments, test mode).

---

## Release Notes

First production release of the Greena Agricultural OS.

- **Commercial platform**: subscription plans (Free / Starter 999 / Professional 1499 / Farm Pro 2499 / Enterprise custom, KES), 21-day Professional trial on org creation, referral program (first-payment discount to KES 599, referrer credit), Paystack checkout, credit ledger, admin billing.
- **Species modules** (schema at head, migration 090): Poultry, Aviculture/Ornamental Birds, BSF, Rabbit, Small Ruminant (Goat/Sheep), Swine, plus Finance, Health, Reports, ARIA (AI assistant), Mission Control, Operations Planner.
- **Platform**: multi-tenant orgs/farms with RBAC and tenant isolation, JWT auth (HS256) with refresh-cookie sessions, APScheduler background jobs (9 registered, advisory-lock single-leader), Sentry monitoring.

### Changes made during launch (this release)
| Commit | Change | Why |
|---|---|---|
| `8853c0b` | Add `jinja2` to backend requirements | sentry-sdk Starlette integration crashed at prod startup without it |
| `3145d1c` | Frontend CSP `connect-src` → Render URL | browser blocked API calls to the new backend host |
| `ff1171d` | Run `alembic upgrade head` in Docker CMD + `render.yaml` | migration automation (Render free tier has no pre-deploy) |
| `89e5bc3` | Production Playwright e2e suite | none existed |

---

## Deployment Summary

| Component | Value |
|---|---|
| Backend | Render web service `greena-api` (`srv-d9uurhjncjis73ajvfbg`), Docker, Frankfurt, plan **free** |
| Backend URL | `https://greena-api-v91z.onrender.com` |
| Frontend | Vercel project `agri-os-ahn4` → `https://agrioskenya.vercel.app` |
| Database | Supabase `rdayjbfivwoztafvnghw` (eu-west-1), via session pooler `aws-0-eu-west-1.pooler.supabase.com:5432` |
| Schema | alembic head **090** (203 tables, 607 FKs) |
| Migrations | Run on container start (`alembic upgrade head`, idempotent, advisory-locked) |
| Health | `GET /health` → 200 `{"db":"connected"}` |
| Scheduler | APScheduler, 9 jobs, single leader via Postgres advisory lock |
| Deploy trigger | Push to `phase-2-auth` (autoDeploy) or Render API deploy |

### Verified this release (real evidence)
- Backend health 200 + DB connected; scheduler startup with 9 jobs; docs disabled in prod (404).
- Auth signup/login/me; org creation → 21-day trial + referral code; farm create/list.
- Paystack initialize → live `checkout.paystack.com` URL; referral discount 599.
- Webhook: invalid/missing sig → 401; tampered body → 401; forged charge.success re-verified against Paystack → 422 (no activation); duplicate webhook idempotent.
- Security headers (HSTS, CSP, X-Frame DENY, nosniff), refresh cookie `HttpOnly; Secure; SameSite=none`; tenant isolation / IDOR → 404; no-token → 401.
- Playwright: 8/10 pass (API journey + security); 2 UI-render tests blocked by browser-binary download in the CI environment.
- Load (free tier): max ~8–10 rps, latency knee at ~5 concurrent, 0 errors (graceful queueing).

---

## Known Limitations

1. **Paid-payment activation not executed end-to-end.** The full flow up to the Paystack checkout is verified; a genuinely *completed* card payment (→ activation, renewal, referrer-reward crediting, org upgrade, entitlement propagation) requires completing the Paystack test checkout, whose card fields are in a cross-origin PCI iframe that this session's non-displayed browser could not drive. **Owner action:** complete one Paystack test-card checkout (see runbook) and confirm activation.
2. **Free-tier scale ceiling.** Render free = 512 MB / 1 worker, spins down after ~15 min idle (cold start observed >60s). Sustains ~8–10 rps. **Not** suitable for the 500+ concurrent-user target. **Owner action:** upgrade Render plan before scale (see [Scaling](#scaling-recommendation)).
3. **No database backups on Supabase free tier** (no PITR). **Owner action:** upgrade Supabase for automated backups, or schedule external `pg_dump`.
4. **Exposed credentials.** Live Paystack `sk_live_…`, Northflank API token, and Render API key were shared in chat during setup. **Owner action:** rotate all three.
5. **2 UI Playwright tests** need a Playwright headless-shell download that failed in this environment (not an app defect; frontend independently verified).
6. **Admin billing grant/revoke** not exercised (no admin account available this session).
7. **Backend pytest suite** (regression) requires a non-production Postgres; not run against the live DB by design.

---

## Rollback Plan

Render keeps prior deploys; frontend keeps prior production deployments.

**Backend (Render):**
1. Render dashboard → service `greena-api` → *Deploys* → pick the last-good deploy → **Rollback**, or
2. API: `POST /v1/services/srv-d9uurhjncjis73ajvfbg/deploys` with `{"commitId":"<good-sha>"}`.
3. Verify `GET /health` → 200.

**Frontend (Vercel):** `vercel rollback <previous-deployment-url>` (or promote a prior deployment in the dashboard). Verify `https://agrioskenya.vercel.app` loads.

**Database:** migrations 051–090 are **additive only** (no drops) — a code rollback does **not** require a schema downgrade; older code runs against the newer schema. Only run `alembic downgrade` if a specific migration is proven at fault (none are).

**Config:** a bad env change → revert the single var in Render/Vercel and redeploy. Keep the last-known-good values recorded out-of-band.

---

## Disaster Recovery Checklist

- [ ] **DB restore capability**: enable Supabase backups/PITR (paid) or a scheduled `pg_dump` to off-site storage. *(Currently NONE — top DR gap.)*
- [ ] Store a recent `pg_dump` snapshot before any risky change.
- [ ] Record all production secrets in a password manager (not chat/repo).
- [ ] Document the Supabase project ref + region + pooler host (done: see Deployment Summary).
- [ ] Confirm Render + Vercel + Supabase + Paystack accounts have a recovery owner/2FA.
- [ ] Verify the deploy path is reproducible from `render.yaml` + `backend/Dockerfile`.
- [ ] Runbook for "DB unreachable": check Supabase project not paused; check pooler host; `/health` returns 503 (not 200) when DB down, so the health check gates traffic correctly.

---

## Operations Runbook

**Deploy backend:** push to `phase-2-auth` (autoDeploy) or `POST /v1/services/{id}/deploys`. Migrations run automatically on boot. Watch logs for `Application startup complete` + `Scheduler started`.

**Deploy frontend:** `vercel redeploy <deployment> --target production` (git-source, no upload) or push. Verify CSP `connect-src` includes the backend origin.

**Complete a Paystack test payment (validates activation):**
1. Create org → `POST /api/v1/billing/initialize` → open `authorization_url`.
2. Choose **Card**, enter test card `4084 0840 8408 4081`, any future expiry, CVV `408`, PIN `0000`, OTP `123456`.
3. On success, Paystack redirects to `/billing/callback` and fires the webhook.
4. Verify: `GET /api/v1/billing/trial/{org}` shows `subscription_active`; check `payment_transactions`, `credit_ledger` (referrer reward), `audit_logs`.

**Rotate a secret:** update in Render (backend) / Paystack dashboard (keys) → redeploy → verify `/health` and a signed webhook.

**Check scheduler:** logs show `APScheduler started — 9 jobs`; exactly one instance holds the lock. Restarting the instance re-elects a leader.

**Wake a cold instance (free tier):** first request after idle takes >60s; hit `/health` to warm before demos.

---

## Launch Checklist

- [x] Backend deployed & healthy (Render)
- [x] Frontend deployed & pointed at backend (Vercel)
- [x] DB at head (090) + migration automation on deploy
- [x] Auth / org / farm / trial / referral verified live
- [x] Paystack initialize + webhook security verified
- [x] Security headers / cookies / TLS / tenant isolation verified
- [x] Load profile measured; scaling limits known
- [x] Playwright suite committed (8/10 green)
- [x] Smoke/test data purged from production
- [ ] **One completed test payment confirms activation** (owner)
- [ ] **Exposed keys rotated** (owner)
- [ ] **Paid Render plan** provisioned if launching beyond a small pilot (owner)
- [ ] **Supabase backups** enabled (owner)

## Post-launch Monitoring Checklist

- [ ] Sentry: confirm events arrive (trigger a test error); set alert rules for error-rate spikes.
- [ ] Render: watch memory (512 MB cap) and restart/OOM events; enable deploy notifications.
- [ ] Supabase: monitor pooler connections vs the 60-connection cap; DB CPU.
- [ ] `/health` uptime check (external pinger; also keeps the free instance warm).
- [ ] Paystack dashboard: watch first real transactions, webhook delivery success, disputes.
- [ ] Track signup → trial → paid conversion and referral redemptions.

## 30-Day Monitoring Plan

- **Week 1** — daily: `/health`, error rate (Sentry), memory, first payments + webhook delivery. Confirm the completed-payment activation path end-to-end with real (test then first live) transactions. Rotate any remaining exposed keys.
- **Week 2** — trend latency (p95) under real traffic; verify scheduler jobs fire (trial-expiry sweep, reminders) by inspecting `audit_logs`/effects; validate referral rewards credited on real payments.
- **Week 3** — capacity review against measured ~8–10 rps ceiling; if traffic approaches it, execute the [scaling](#scaling-recommendation) upgrade. Confirm backups exist and test a restore.
- **Week 4** — security recheck (`pip-audit`/`npm audit` deltas, header scan); run the Playwright suite against production; review the 30-day cost/usage and finalize the paid-tier decision.

## Scaling Recommendation

Measured free-tier ceiling: **~8–10 rps, knee at ~5 concurrent** on `/health` (a light endpoint; real endpoints are heavier). For a 500-concurrent-user target:

- **Render**: move to **Standard** (2 GB) or higher, run **2+ instances** with autoscaling, set `WEB_WORKERS` to ~2–4 per instance (raise the pool accordingly). Re-measure; scale horizontally to hold p95 < 1s.
- **Supabase**: upgrade from free — raise the connection ceiling and add PITR/backups. Keep `(DB_POOL_SIZE + DB_MAX_OVERFLOW) × workers × instances + 1` under the plan's connection cap.
- Add an external uptime pinger to remove cold starts.

---

## Go / No-Go

**GO for a controlled beta / pilot launch** on the current stack — deployed, connected, secure, and functionally verified end-to-end at the API level, with 0 failing checks. **NO-GO for at-scale launch** until: (1) a completed test payment confirms activation, (2) a paid Render plan is provisioned, (3) Supabase backups are enabled, and (4) the exposed keys are rotated. All four are owner-controlled actions with steps above.
