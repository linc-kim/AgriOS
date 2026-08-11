# Greena (AGRIOS) Launch Runbook

**Version:** 1.0.0  
**Refreshed:** 2026-08-11 (Gate 6 — reconciled to current repo state)  
**Environment:** Production  
**Infra:** Railway (backend) + Vercel (frontend) + Supabase (PostgreSQL)  

> **Launch is NOT authorized yet.** Production deployment stays gated on Gate 5
> (performance) resuming and passing on staging, and on the Gate 6 items still open
> (DR runbook, alerting, tested restore, security review). The GitHub-Actions deploy
> workflows remain **parked** (`infrastructure/github/workflows/deploy-*.yml`).
>
> **Naming:** the platform is mid-rebrand **AGRIOS → Greena** (`config.PROJECT_NAME =
> "Greena"`, `EMAIL_FROM` uses `greena.app`; some infra/domains below still say
> `agrios`). **Confirm the authoritative production domain, sender ID, Sentry org and
> Slack channel before launch** — the placeholders below are marked ⚠️CONFIRM.
>
> **Related:** `DEPLOYMENT_HARDENING.md` (blockers, env checklist, rollback),
> `GATE_6_PRODUCTION_READINESS_AUDIT.md`, and the Gate 6 DR / alerting / security-review
> docs once they land.

---

## 1. Pre-Launch Checklist

Complete every item in order. Do not proceed to deployment until all boxes are checked.

### 1.1 Infrastructure

- [ ] Supabase production project created and database URL recorded
- [ ] Railway project created, linked to `main` branch of the repo
- [ ] Vercel project created, linked to `frontend/` directory of the repo
- [ ] Domain `api.agrios.app` pointed to Railway service
- [ ] Domain `app.agrios.app` pointed to Vercel deployment
- [ ] SSL certificates active on both domains (verify in browser — padlock visible)
- [ ] Africa's Talking production account live (not sandbox), sender ID `AGRIOS` approved

### 1.2 Secrets — Railway (Backend)

Set each secret in Railway → Project → Variables before first deploy. Reconciled to
`backend/app/config.py`; the app **fails to boot** if a required value is missing or
invalid (`diagnostics_service.run_startup_validation`). Full annotated list:
`backend/.env.example`.

**Required**

| Variable | Notes |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://…@…supabase.co:5432/postgres` |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_hex(64))"` |
| `ALLOWED_ORIGINS` | comma-separated live frontend origin(s) ⚠️CONFIRM domain |

**Auth / cookies / DB tuning**

| Variable | Notes |
|----------|-------|
| `REFRESH_COOKIE_SAMESITE` | `strict` if frontend+API share a registrable domain; else `none` (see `DEPLOYMENT_HARDENING.md` BLOCKER-1) |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | size so `(pool+overflow)×workers×instances + 1 ≤ Supabase max_connections` |
| `DATABASE_SSL` / `DATABASE_SSL_CA` | `true`; point CA at Supabase's bundle to authenticate the connection |

**AI (Gate 4 — AI Provider Manager)**

| Variable | Notes |
|----------|-------|
| `GEMINI_API_KEY`, `GEMINI_API_KEY_2` | one or both keys; the manager round-robins + fails over. Backend-only. |
| `AI_KEY_ROUTING` | `round_robin` \| `primary` \| `least_failures` (default round_robin) |
| `AI_RESPONSE_CACHE_TTL_SECONDS` | `0` disables (default); set >0 to enable the deterministic cache |
| `CLAUDE_API_KEY` | optional fallback provider |

**Email / SMS (launch = email; SMS dormant)**

| Variable | Notes |
|----------|-------|
| `EMAIL_PROVIDER` + `SMTP_*` / `FRONTEND_URL` | launch verification/reset channel is email; set the provider + credentials |
| `REQUIRE_EMAIL_VERIFICATION`, `ENABLE_SMS_OTP` | feature flags — SMS OTP stays OFF at launch (Africa's Talking dormant) |
| `AT_API_KEY` / `AT_USERNAME` / `AT_ENVIRONMENT` / `AT_SENDER_ID` | only when SMS is activated later ⚠️CONFIRM sender ID |

**Optional**

| Variable | Notes |
|----------|-------|
| `SENTRY_DSN` | error monitoring |
| `POSTHOG_ENABLED` / `POSTHOG_API_KEY` / `POSTHOG_HOST` | analytics — disabled by default (Gate 4) |
| `TZ` | `Africa/Nairobi` |

### 1.3 Secrets — Vercel (Frontend)

Set each in Vercel → Project → Settings → Environment Variables (Production scope).

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://api.agrios.app/api/v1` |
| `VITE_ENVIRONMENT` | `production` |
| `VITE_SENTRY_DSN` | From Sentry → Frontend project → Client Keys |

### 1.4 Database Migrations

Run from the Railway shell or a local machine with `DATABASE_URL` pointing to production.

```bash
cd backend
alembic upgrade head
```

Verify the migration chain is intact:
```bash
alembic current
# Expected: 086_swine_sales (head)   # current head as of 2026-08-11

alembic heads
# Expected: exactly one head
```

### 1.5 Seed Data (if required)

Role seed data is applied in migration 001. No additional seed step required.

---

## 2. Deployment Procedure

### 2.1 Backend — Railway

Deployment is triggered automatically on `git push origin main`.

Manual trigger (if needed):
1. Railway dashboard → AGRIOS service → Deployments → Deploy latest

Railway will:
1. Detect Python via Nixpacks
2. Run `pip install -r requirements.txt`
3. Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
4. Poll `GET /health` every 10 s — must return 200 within 30 s or deploy rolls back

### 2.2 Frontend — Vercel

Deployment is triggered automatically on `git push origin main`.

Manual trigger (if needed):
1. Vercel dashboard → AGRIOS project → Deployments → Redeploy

Vercel will:
1. Run `npm ci` in `frontend/`
2. Run `npm run build` (tsc + vite build)
3. Serve `dist/` with the rules in `vercel.json` (SPA routing + security headers)

---

## 3. Post-Deployment Smoke Tests

Run these **immediately** after every production deployment. Do not declare launch successful until all pass.

### 3.1 Backend Smoke Tests

```bash
BASE=https://api.agrios.app

# Health check
curl -sf "$BASE/health" | jq .
# Expected: {"status":"ok","version":"1.0.0","environment":"production","db":"connected"}

# Security headers present
curl -sI "$BASE/health" | grep -i "x-frame-options"
# Expected: x-frame-options: DENY

curl -sI "$BASE/health" | grep -i "x-content-type-options"
# Expected: x-content-type-options: nosniff

curl -sI "$BASE/health" | grep -i "strict-transport-security"
# Expected: strict-transport-security: max-age=31536000; includeSubDomains

# Docs disabled in production
curl -o /dev/null -w "%{http_code}" "$BASE/docs"
# Expected: 404

# Auth: launch channel is EMAIL + PASSWORD (SMS OTP is dormant at launch).
# Log in with a known test account:
curl -sf -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "..."}' | jq .
# Expected: {"success":true,"data":{"access_token":"...", ...}}
# (When SMS is later enabled, verify /auth/request-otp delivers to a Kenyan number.)
```

### 3.2 Frontend Smoke Tests

1. Open the production frontend URL ⚠️CONFIRM in an incognito window
2. Confirm redirect to `/auth` (not a blank screen)
3. Sign up / log in with **email + password** (SMS OTP dormant at launch) → confirm home loads
4. Confirm the launch modules load (Poultry, Aviculture, BSF, Rabbit, Goat/Sheep, Swine + Finance, Reports, ARIA) for a farm that has them
5. Open Settings → confirm language toggle works (EN ↔ SW)
6. Throttle network to "offline" in DevTools → confirm offline banner appears
7. Open DevTools → Application → Service Workers → confirm SW is registered

### 3.3 PWA Smoke Test

```bash
# Run Lighthouse from Chrome DevTools → Lighthouse tab
# Minimum scores for V1 launch:
# Performance: ≥ 80
# Accessibility: ≥ 90
# Best Practices: ≥ 90
# PWA: "Installable" badge must be present
```

---

## 4. Monitoring Setup

### 4.1 Sentry

- [ ] Backend project alert: any error with frequency > 5/min → Slack `#agrios-alerts`
- [ ] Frontend project alert: unhandled exceptions → Slack `#agrios-alerts`
- [ ] Performance alert: p95 response time > 2 s on `/api/v1/**` → Slack `#agrios-alerts`

### 4.2 Railway

- [ ] Uptime check on `https://api.agrios.app/health` every 5 min
- [ ] Alerting email set to engineering team

### 4.3 First-day Monitoring Checklist

Check these every hour on launch day:

- [ ] Railway → Metrics: CPU and memory not climbing unboundedly
- [ ] Sentry → Issues: no new error spikes
- [ ] Supabase → Database: connection count < 80% of pool limit
- [ ] Africa's Talking dashboard: SMS delivery rate > 95%

---

## 5. Rollback Procedure

### 5.1 Backend Rollback

```bash
# In Railway dashboard:
# Deployments → select the previous successful deployment → Rollback
# OR via CLI:
railway rollback
```

Time to rollback: ~2 min (Railway keeps the previous image hot).

### 5.2 Frontend Rollback

```bash
# In Vercel dashboard:
# Deployments → previous deployment → "..." menu → Promote to Production
```

Time to rollback: ~30 s (Vercel CDN swap is instant).

### 5.3 Database Rollback

Only required if a migration was run and must be reversed.

```bash
cd backend
alembic downgrade -1   # rolls back one migration
# Repeat until at the safe revision
alembic current        # confirm target revision
```

**Note:** the schema is now at head `086` (86 migrations, 001→086). Every migration
must be read before applying and be reversible/recoverable (Doc 4 §117). Full
code/schema/data rollback detail: `DEPLOYMENT_HARDENING.md §4`.

---

## 6. Go/No-Go Criteria

### GO — proceed with launch

All of the following are true:
- All backend smoke tests pass (Section 3.1)
- All frontend smoke tests pass (Section 3.2)
- Sentry is receiving events and showing 0 critical errors
- Railway health check: continuous green for 10 min post-deploy
- Email login/signup works end to end (SMS OTP not required at launch)
- PWA is installable on Android Chrome

### NO-GO — abort and rollback

Any of the following are true:
- `GET /health` returns anything other than `{"status":"ok",...}`
- Email login/signup fails end to end
- Frontend fails to load on mobile Chrome (primary target)
- Any unhandled exception in Sentry within 10 min of deploy
- Railway restarts the process more than once

---

## 7. Post-Launch Tasks (Day 1–7)

| Day | Task | Owner |
|-----|------|-------|
| 1 | Verify Sentry alert rules fire on a test error | Engineering |
| 1 | Confirm Africa's Talking delivery reports are accessible | Engineering |
| 2 | Run Lighthouse audit, file issues if scores dropped | Engineering |
| 3 | Check Supabase connection pool metrics | Engineering |
| 7 | First weekly error triage in Sentry | Engineering |
| 7 | Check Railway billing — confirm usage within plan limits | Operations |

---

## 8. Support Contacts

| Service | URL | Notes |
|---------|-----|-------|
| Railway | https://railway.app/dashboard | Backend infra |
| Vercel | https://vercel.com/dashboard | Frontend CDN |
| Supabase | https://supabase.com/dashboard | Database |
| Africa's Talking | https://account.africastalking.com | SMS gateway |
| Sentry | https://sentry.io/organizations/agrios | Error monitoring |
| Google AI Studio | https://aistudio.google.com | Gemini API |
| Anthropic Console | https://console.anthropic.com | Claude API |

---

*This runbook is the authoritative operational guide for the Greena (AGRIOS) launch. Update it whenever infrastructure or deployment procedure changes. Items marked ⚠️CONFIRM must be verified against the live production accounts (domain, sender ID, Sentry org, Slack channel) before launch.*
