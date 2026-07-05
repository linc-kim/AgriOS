# AGRIOS — Deployment Guide

Operational, step-by-step instructions to deploy AGRIOS from a **fresh clone** to
production. Targets: **Railway** (backend), **Supabase** (PostgreSQL), **Vercel**
(frontend). For the *why* behind these choices see `DEPLOYMENT_GUIDE.md`
(architecture handbook); this file is the *how*.

- **Repo shape:** monorepo — `backend/` (FastAPI/Python 3.12) and `frontend/`
  (React/Vite) are deployed independently.
- **Node:** 20.x (pinned via `frontend/package.json` engines + `frontend/.nvmrc`).
- **Python:** 3.12 (pinned via `backend/Dockerfile`).

---

## 1. Local setup

```bash
git clone <repo> && cd "AGRIOS Project"

# ── Backend ──────────────────────────────────────────────────────────────────
cd backend
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill DATABASE_URL, SECRET_KEY, JWT_SECRET
alembic upgrade head            # apply migrations to your local Postgres
uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)

# ── Frontend ─────────────────────────────────────────────────────────────────
cd ../frontend
npm ci
cp .env.example .env            # VITE_API_BASE_URL defaults to /api/v1 (proxied)
npm run dev                     # http://localhost:5173
```

A local Postgres is available via `infrastructure/docker-compose.yml`
(`docker compose up -d db`). The dev server proxies `/api` → `:8000`
(`frontend/vite.config.ts`).

---

## 2. Database — Supabase

1. Create a Supabase project (PostgreSQL 16).
2. Copy **Connection string → Session pooler** (Project Settings → Database).
   Use the session pooler: it is IPv4 (Railway-reachable) and supports prepared
   statements. Keep the username form `postgres.<project-ref>`.
3. Use that string as `DATABASE_URL` in Railway. Any scheme is accepted —
   `app/config.py` rewrites it to `postgresql+asyncpg://` automatically. Strip any
   `?sslmode=...` query parameter (asyncpg rejects it).
4. Migrations run automatically on deploy (§3). RLS is intentionally disabled;
   authorization is enforced at the application layer.

---

## 3. Backend — Railway

**Service settings**
- **Root Directory:** `backend`  ← the single most common first-deploy mistake if missed.
- **Builder:** Dockerfile (auto-detected from `backend/railway.toml`).

`backend/railway.toml` already defines:
- `preDeployCommand = "alembic upgrade head"` — migrations run **before** the
  server starts and **outside** the health-check window (so a long migration can
  never trip the health timeout).
- `startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"`.
- `healthcheckPath = "/health"`, `healthcheckTimeout = 60`, restart on-failure ×3.

**Environment variables** (Railway → service → Variables). Required:
`DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, `ENVIRONMENT=production`,
`ALLOWED_ORIGINS` (your Vercel origin[s], comma-separated, no spaces). Recommended:
`GEMINI_API_KEY`, `CLAUDE_API_KEY`, `SENTRY_DSN`, `TZ=Africa/Nairobi`. Leave `AT_*`
and email vars unset at launch. Full list: `backend/.env.example`.

**Deploy sequence** (automatic on push to `main`):
1. Docker build (`python:3.12-slim`, `pip install -r requirements.txt`).
2. **Pre-deploy:** `alembic upgrade head` → applies migrations `001 … 031`.
3. **Start:** uvicorn (2 workers) binds `$PORT`.
4. Railway polls `/health`; 3 consecutive 200s → live; failure → auto-rollback.

Verify: `/health` returns `{"status":"ok","db":"connected"}` (200). It returns
**503** when the DB is unreachable, so a bad DB never passes health.

---

## 4. Frontend — Vercel

**Project settings**
- **Root Directory:** `frontend`.
- Framework **Vite**, Install `npm ci`, Build `npm run build`, Output `dist`
  (all declared in `frontend/vercel.json`).
- Node 20 (from `engines` / `.nvmrc`).

**Environment variables** (Vercel → project → Settings → Environment Variables):
`VITE_API_BASE_URL` (backend URL **including `/api/v1`**), optional
`VITE_ENVIRONMENT=production`, `VITE_SENTRY_DSN`. These are **public** (baked into
the build).

`vercel.json` provides SPA rewrites (all non-asset paths → `/index.html`),
immutable asset caching, `sw.js` no-cache (so PWA updates reach users), and the
production security-header set (CSP, HSTS, X-Frame-Options, etc.).

Deploy is automatic on push to `main` (1–4 min). Verify: app loads on mobile
Chrome, PWA installable, API calls reach the backend (check `ALLOWED_ORIGINS`).

---

## 5. Required secrets (generate fresh, never reuse)

| Secret | Where | Generate |
|---|---|---|
| `SECRET_KEY` | Railway | `python -c "import secrets;print(secrets.token_hex(32))"` |
| `JWT_SECRET` | Railway | same, **must differ** from SECRET_KEY |
| `DATABASE_URL` | Railway | Supabase session-pooler string |
| AI keys | Railway | provider dashboards (optional) |
| Sentry DSNs | Railway + Vercel | Sentry project settings (optional) |

Never commit `.env`. `VITE_*` are public by design — no secrets there.

---

## 6. Build & verification commands

```bash
# Frontend (exact Vercel pipeline)
cd frontend && npm ci && npm run build && npm run type-check

# Backend
cd backend && python -m py_compile app/**/*.py
alembic upgrade head          # apply
alembic downgrade base        # full teardown (reversible; verified)
alembic current               # expect: 031 (head)
```

---

## 7. Rollback procedure

- **Backend (Railway):** Dashboard → service → Deployments → select last good →
  Rollback (~2 min; previous image kept hot).
- **Frontend (Vercel):** Deployments → previous successful → Promote to
  Production (~30 s; CDN pointer swap).
- **Database:** migrations are reversible (`alembic downgrade -1`), but a V1
  release ships no destructive migrations, so DB rollback is not normally part of
  a release rollback. Prefer a forward-fix migration.

---

## 8. Recovery procedure (data loss / corruption)

1. **Stop.** Do not run further commands. Confirm data is actually gone (check the
   Supabase Table Editor — often it is a connectivity error, not data loss).
2. If a restore is genuinely required: take a manual `pg_dump` snapshot first,
   then restore from a Supabase automatic backup (understand it overwrites
   current state and loses writes after the backup point).
3. Security incident: rotate `SECRET_KEY`, `JWT_SECRET`, the Supabase DB password,
   and every provider key in use; redeploy. Rotating the JWT secrets invalidates
   all sessions (users re-verify via OTP) — the intended cost.

---

## 9. Production checklist (Go / No-Go)

- [ ] Railway Root Directory = `backend`; Vercel Root Directory = `frontend`.
- [ ] All **required** env vars set on each platform (§3, §4).
- [ ] `DATABASE_URL` = Supabase **session pooler** (`postgres.<ref>@…pooler…:5432`).
- [ ] Backend deploy log shows `Running upgrade … -> 031` complete in pre-deploy.
- [ ] `GET /health` → 200 `{"db":"connected"}`; security headers present; `/docs`
      returns 404 in production.
- [ ] Frontend loads on mobile Chrome; PWA installable; no CORS errors in console.
- [ ] Sentry receiving events (if DSNs set); no error spike in first 10 min.
- [ ] Railway health green ≥10 min; process not restarting.

---

## 10. Known launch configuration (not defects)

- **Email OTP is not yet wired** (Phase 2). Authentication in code today is
  phone/PIN + OTP hashing; SMS delivery is dormant until `AT_*` are set. Plan the
  first-user auth path accordingly.
- **SMS is dormant** by design until Africa's Talking credentials are added — the
  `africastalking` package is installed, so activation is env-vars-only.
- **CI** workflows live under `infrastructure/github/workflows/` and are not yet
  active on GitHub (`.github/workflows/`); deployment does not depend on CI.
