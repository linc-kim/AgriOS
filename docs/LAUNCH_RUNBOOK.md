# AGRIOS V1 Launch Runbook

**Version:** 1.0.0  
**Date:** 2026-06-26  
**Environment:** Production  
**Infra:** Railway (backend) + Vercel (frontend) + Supabase (PostgreSQL)  

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

Set each secret in Railway → Project → Variables before first deploy.

| Variable | Notes |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres` |
| `SECRET_KEY` | 32-byte hex: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET` | 64-byte hex: `python -c "import secrets; print(secrets.token_hex(64))"` |
| `ALLOWED_ORIGINS` | `https://app.agrios.app,https://admin.agrios.app` |
| `AT_API_KEY` | Africa's Talking production key |
| `AT_USERNAME` | Africa's Talking production username |
| `AT_ENVIRONMENT` | `production` |
| `AT_SENDER_ID` | `AGRIOS` |
| `SENTRY_DSN` | From Sentry → Project → Settings → Client Keys |
| `GEMINI_API_KEY` | Google AI Studio production key |
| `CLAUDE_API_KEY` | Anthropic Console production key |
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
# Expected: 030_market_prices (head)

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

# OTP request (verify SMS gateway is live)
curl -sf -X POST "$BASE/api/v1/auth/request-otp" \
  -H "Content-Type: application/json" \
  -d '{"phone": "+254700000000"}' | jq .
# Expected: {"success":true,"data":{"phone":"+254700000000",...}}
# Verify SMS is received on the test phone
```

### 3.2 Frontend Smoke Tests

1. Open `https://app.agrios.app` in an incognito window
2. Confirm redirect to `/auth` (not a blank screen)
3. Enter a Kenyan phone number — confirm OTP SMS arrives within 60 s
4. Complete OTP → confirm home screen loads
5. Navigate to all 5 tabs: Home, Flock, Health, Finance, ARIA
6. Open Settings → confirm language toggle works (EN ↔ SW)
7. Throttle network to "offline" in DevTools → confirm offline banner appears
8. Open DevTools → Application → Service Workers → confirm SW is registered

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

**Note:** DB-10 frozen — no migrations in Sprint 10. A database rollback is not expected for this release.

---

## 6. Go/No-Go Criteria

### GO — proceed with launch

All of the following are true:
- All backend smoke tests pass (Section 3.1)
- All frontend smoke tests pass (Section 3.2)
- Sentry is receiving events and showing 0 critical errors
- Railway health check: continuous green for 10 min post-deploy
- SMS OTP delivery confirmed on a live Kenyan number
- PWA is installable on Android Chrome

### NO-GO — abort and rollback

Any of the following are true:
- `GET /health` returns anything other than `{"status":"ok",...}`
- OTP SMS not delivered within 3 min of request
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

*This runbook is the authoritative operational guide for AGRIOS V1 launch. Update it whenever infrastructure or deployment procedure changes.*
