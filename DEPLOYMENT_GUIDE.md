# AGRIOS DEPLOYMENT GUIDE

**Read `AGRIOS_MASTER_CONTEXT.md` Section 7 first** (Deployment Philosophy) — the single governing idea behind everything in this document is that a non-developer founder must be able to operate this business day to day, so every mechanism described here is chosen to minimize operational burden over almost every other consideration, including raw cost or theoretical scalability.

---

## 1. The Three Services and Why Each Was Chosen

AGRIOS runs across exactly three managed platforms, deliberately avoiding any self-managed infrastructure:

| Service | Platform | Role | Why this platform specifically |
|---|---|---|---|
| Backend / API | Railway | Runs the FastAPI application 24/7, executes migrations on deploy | Git-push-to-deploy with zero infrastructure management; a Dockerfile-based deploy that "just works" without a founder needing to understand containers deeply. |
| Frontend / App | Vercel | Serves the built React SPA to farmers' browsers | Best-in-class static/SPA hosting, instant CDN propagation, trivial custom-domain setup, and preview deployments per branch. |
| Database | Supabase | Managed PostgreSQL, automated backups | Removes the need to operate PostgreSQL directly — backups, connection pooling, and a web-based Table Editor are included, which matters enormously for a founder who may need to look at raw data without writing SQL. |

None of these were chosen for being the cheapest or the most powerful option in isolation — they were chosen because, together, they let one non-technical founder run a production system with a git push and a web browser.

---

## 2. Git and GitHub

The entire codebase lives in a single GitHub repository containing both `backend/` and `frontend/` as sibling directories (a monorepo, not two separate repos) — this mirrors the "monolith first" philosophy (`AGRIOS_MASTER_CONTEXT.md` Section 4.5) at the repository level: one place to look, one PR that can touch both sides of a full-stack change atomically, one commit history. `main` is the only branch that Railway and Vercel watch; every deployment, backend and frontend alike, is triggered purely by a push (usually a merge) to `main`. Feature work happens on branches, and a GitHub Actions workflow is intended to run tests and type checks on every pull request before merge — **note:** the workflow files for this currently live at `infrastructure/github/workflows/` rather than the `.github/workflows/` path GitHub actually reads, which means CI is not currently active on pull requests; this is tracked in `KNOWN_TECHNICAL_DEBT.md` rather than silently corrected in this document, since this guide's job is to describe the deployment system as it actually behaves today.

---

## 3. Backend Deployment — Railway

### 3.1 Configuration

Railway's `railway.toml` (project root) configures: builder `Nixpacks` (auto-detects Python from `requirements.txt`) or the project `Dockerfile` directly depending on how the service is configured; build command `pip install -r requirements.txt`; start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`; restart policy on-failure with a maximum of 3 retries; and a health check against `GET /health` with a 30-second timeout and 10-second polling interval. The **Root Directory** setting for the Railway service must be set to `backend` — if this is skipped or misconfigured, Railway attempts to build the entire monorepo root and the build fails, which is the single most common first-deployment mistake described in the operator-facing documentation.

### 3.2 The deployment sequence, mechanically

1. `git push origin main` (or a merged PR) triggers Railway automatically.
2. Railway runs `pip install -r requirements.txt`.
3. The Dockerfile-based start sequence runs `alembic upgrade head` **before** starting Uvicorn — migrations are applied automatically on every deploy, which is why the migration chain being strictly linear and always reversible (`DATABASE_ARCHITECTURE.md` Section 4) matters operationally, not just architecturally: a broken migration blocks the entire deploy, not just a schema change.
4. Uvicorn starts with 2 workers.
5. Railway polls `GET /health` every 10 seconds; three consecutive healthy (200) responses and the deploy is considered live; failure to become healthy within the timeout triggers an automatic rollback to the previous running version.

### 3.3 Why 2 workers, and when to change it

Two Uvicorn workers is the V1 default, sized for the concurrency the product expects at launch scale (up to roughly 200 concurrent users without any changes, per the operational capacity planning). Increasing workers (`--workers 4`) is a one-line, no-code-change scaling lever documented explicitly for the founder to use if Railway metrics show CPU pressure or health-check failures under load — but it is explicitly framed as a stopgap, not a solution: if 4 workers still is not enough, the next correct step is a Railway plan upgrade or, at real scale, migrating off Railway entirely (Section 8).

---

## 4. Frontend Deployment — Vercel

Vercel's **Root Directory** must be set to `frontend`, Framework Preset to `Vite`, Build Command to `npm run build`, Output Directory to `dist`. `vercel.json` defines SPA rewrite rules (every path except `/assets/`, `/icons/`, `/manifest.webmanifest`, `/sw.js`, and Workbox files rewrites to `/index.html`, which is required for a client-side-routed React app to handle direct URL navigation correctly), cache headers (`/assets/**` immutable for one year, `sw.js` explicitly `no-cache` — this last one is critical: caching the service worker file itself would prevent PWA updates from ever reaching installed users), a `Service-Worker-Allowed: /` header enabling root-scope service worker registration, and the same security header set the backend applies (`X-Content-Type-Options`, `X-Frame-Options`, CSP, HSTS with preload).

Every push to `main` triggers an automatic Vercel deploy, typically completing in 1–4 minutes. Environment variables (Section 6.2) must be set with the `VITE_` prefix, since Vite only exposes environment variables to client-side code when they carry that prefix — a variable set without it will silently be `undefined` in the built frontend, which is one of the more confusing failure modes for a first-time deployer.

---

## 5. Database — Supabase

Supabase provisions managed PostgreSQL 16. Row Level Security (RLS) is available but deliberately left disabled in V1 — AGRIOS enforces all authorization at the application layer (the permission system in `SYSTEM_ARCHITECTURE.md` Section 2.5), and RLS is treated as an optional additional layer for a future hardening pass rather than a V1 requirement, since the application-layer checks are already the actual security boundary. Supabase's automatic daily backups (7-day retention on the free tier, 30-day plus point-in-time recovery on Pro) are the primary disaster-recovery mechanism (Section 9).

The connection string follows the `postgresql+asyncpg://` scheme specifically — **not** plain `postgresql://` — because the async SQLAlchemy engine requires the `asyncpg` driver to be named explicitly in the URL scheme; a connection string copied directly from Supabase's dashboard (which shows plain `postgresql://`) must have `+asyncpg` inserted before use. A missing `+asyncpg` typically surfaces as a `ModuleNotFoundError: No module named 'psycopg2'`, since without the explicit async driver the code falls back toward a sync driver path that isn't installed.

---

## 6. Environment Variables — Complete Reference

### 6.1 Backend (Railway)

| Variable | Purpose | Notes |
|---|---|---|
| `ENVIRONMENT` | Gates security headers and Sentry activation | Must be exactly `production` in production. |
| `SECRET_KEY` | General application signing secret | 64-byte random hex; generate via `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `JWT_SECRET` | JWT signing secret | Must be different from `SECRET_KEY`; same generation method. |
| `JWT_EXPIRE_MINUTES` | Access token lifetime | `15` — frozen, see `AGRIOS_MASTER_CONTEXT.md` Section 6.2. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `30` — frozen. |
| `DATABASE_URL` | Full Postgres connection string | Must use `postgresql+asyncpg://` scheme (Section 5). |
| `ALLOWED_ORIGINS` | CORS allow-list | Comma-separated, no spaces; must include the live Vercel/custom frontend domain(s). |
| `EMAIL_PROVIDER_API_KEY` | Transactional email provider credential | **Required at V1 launch** — this is the credential Email OTP delivery actually depends on (`AGRIOS_MASTER_CONTEXT.md` Section 6.1; `SYSTEM_ARCHITECTURE.md` Section 5.2). The specific provider is an infrastructure choice, not an architectural one; whichever is chosen, its credential belongs here. |
| `EMAIL_FROM_ADDRESS` | The "from" address OTP and notification emails are sent as | Should be a domain-verified sending address (e.g. `noreply@agrios.app`) to avoid landing in spam. |
| `AT_API_KEY` / `AT_USERNAME` | Africa's Talking credentials | **Optional at V1 launch.** SMS OTP and SMS notifications are inactive until these are set — this is expected, deliberate V1 launch configuration, not a defect (`AGRIOS_MASTER_CONTEXT.md` Section 6.1). Add these later, purely as an environment variable change, to activate SMS with zero code or schema changes. |
| `AT_SENDER_ID` | SMS sender name | `AGRIOS` — must be pre-approved by Africa's Talking / the Communications Authority of Kenya, or SMS delivery silently fails. Only relevant once `AT_API_KEY`/`AT_USERNAME` are set. |
| `AT_ENVIRONMENT` | AT sandbox vs. live | Must be `production`, not `sandbox`, for real SMS to send once SMS is activated — this is the single most common "OTP never arrives" root cause **for deployments that have already enabled SMS**; it is irrelevant while Africa's Talking credentials are absent and Email OTP is the active channel. |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Primary AI provider | Model pinned to `gemini-2.0-flash`. |
| `CLAUDE_API_KEY` / `CLAUDE_MODEL` | Fallback AI provider | Model pinned to `claude-haiku-4-5-20251001`. |
| `SENTRY_DSN` | Backend error monitoring | From the Sentry project's Client Keys settings. |
| `TZ` | Scheduler and timestamp timezone | `Africa/Nairobi` — must not be changed; every cron job in `scheduler.py` (`SYSTEM_ARCHITECTURE.md` Section 2.6) assumes this timezone. |

**On activating SMS later:** the only action required to turn SMS OTP and SMS notifications on for a running V1 deployment is adding `AT_API_KEY`, `AT_USERNAME`, `AT_SENDER_ID`, and setting `AT_ENVIRONMENT=production` in Railway, then letting the automatic redeploy this triggers run its course (Section 8). No code changes, no migrations, and no manual data backfill are expected to be required — if any of those turn out to be necessary when this is actually attempted, that is a signal the channel-agnostic authentication principle (`AGRIOS_MASTER_CONTEXT.md` Section 6.1) has drifted somewhere and should be corrected before proceeding.

### 6.2 Frontend (Vercel)

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Full backend URL **including `/api/v1`** — a very common setup mistake is omitting the `/api/v1` suffix. |
| `VITE_SENTRY_DSN` | Frontend error monitoring (a separate Sentry project from the backend). |
| `VITE_ENVIRONMENT` | `production` — feeds Sentry environment tagging. |

**Never delete an environment variable without immediately replacing it** — a missing required variable is the single most common cause of an immediate crash loop on Railway, since several of them (the two secrets, the database URL) are read at application startup and their absence raises a validation error before the app can even begin serving `/health`.

---

## 7. Migrations in Production

`alembic upgrade head` runs automatically as part of the Railway deploy sequence (Section 3.2) — a founder never needs to run this manually in the normal case. It can be run manually from the Railway shell if needed (`cd backend && alembic upgrade head`), and its state can always be inspected with `alembic current` (expected: `030_market_prices` at head for a fully-deployed V1 database) and `alembic heads` (expected: exactly one head — more than one indicates a forked migration chain, which is a Red-status condition per the sprint execution framework and must be resolved before any further schema work proceeds). Because DB-10 freezes the V1 migration chain at exactly 30 migrations (`DATABASE_ARCHITECTURE.md` Section 4), a database rollback is not expected to be part of any V1 release's rollback procedure — see Section 9.3.

---

## 8. Production Workflow and CI/CD Philosophy

The intended workflow is: feature branch → pull request (GitHub Actions runs tests + type checks) → merge to `main` → Railway and Vercel both deploy automatically within minutes, gated by health checks, with zero manual deployment steps for either service. The CI/CD philosophy is deliberately "boring": no custom deployment scripts, no manual SSH, no hand-run build steps — the entire pipeline is "the platform watches `main` and reacts," because a founder without a DevOps background must be able to trust that merging a reviewed PR is sufficient, without needing to remember a manual follow-up step. As noted in Section 2, the CI workflow files are presently misplaced and therefore not actually running against pull requests — this does not change the intended philosophy, only the current state of its enforcement (`KNOWN_TECHNICAL_DEBT.md`).

---

## 9. Recovery and Rollback Strategy

### 9.1 Backend rollback

Railway keeps the previous deployment's image hot. Rollback is: Railway dashboard → the service → Deployments → select the last known-good deployment → Rollback (or `railway rollback` via CLI). Time to rollback is approximately 2 minutes.

### 9.2 Frontend rollback

Vercel dashboard → the project → Deployments → the previous successful deployment → "Promote to Production." Because Vercel's rollback is a CDN pointer swap rather than a rebuild, it completes in roughly 30 seconds — faster than the backend rollback, which matters when deciding which side of a bad deploy to revert first if only one side actually broke.

### 9.3 Database rollback

Only relevant if a migration was applied and must be reversed: `alembic downgrade -1` repeated until `alembic current` shows the desired revision. As noted in Section 7, this is not expected to be exercised for the V1 release itself, since DB-10 froze the chain before launch — but the mechanism remains available and correct for any future release that does ship new migrations.

### 9.4 Full disaster recovery (data loss or corruption)

The universal first instruction, regardless of what appears to have gone wrong: **stop, do not run further commands, do not make further changes.** Every additional action taken while panicked increases the chance of making recovery harder rather than easier. Confirm whether data is actually gone (often what looks like data loss is a connectivity error, not a database problem — check the Supabase Table Editor directly before assuming the worst). If a restore from an automatic Supabase backup is genuinely required, understand before restoring that it will overwrite the current database state and that any writes made after the backup's point in time will be lost — this should be communicated to affected farmers before, not after, the restore is executed, and a manual `pg_dump` snapshot immediately before restoring is cheap insurance against having guessed wrong about which backup point is correct.

### 9.5 Security incident response

If unauthorized access is suspected: rotate `SECRET_KEY` and `JWT_SECRET` immediately (this invalidates every active session platform-wide — every user will need to re-verify via OTP on whichever channel they use, which is the intended and acceptable cost of this action), redeploy immediately, rotate the Supabase database password, rotate the transactional email provider's API key, rotate the Africa's Talking API key if one is configured, and rotate both AI provider API keys. **After a security incident, no old key or secret should continue to be used even if it is merely suspected, not confirmed, to be compromised** — rotate every credential actually in use, not just the credential believed to be the point of entry, and this now explicitly includes whichever OTP-delivery channel(s) are active, not only SMS.

---

## 10. Debugging Deployment Failures — Common Symptoms and Root Causes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'psycopg2'` | `DATABASE_URL` missing the `+asyncpg` scheme segment | Correct the connection string scheme (Section 5). |
| Health check fails with 500 | Database connection failed — wrong `DATABASE_URL` or Supabase outage | Verify the connection string; check Supabase status. |
| Health check times out | Migrations taking longer than the configured timeout on a large first deploy | Increase `healthcheckTimeout` in `railway.toml`. |
| Crash loop immediately after deploy | A required environment variable is missing or malformed | Check Railway logs for `ValidationError`/`KeyError`; cross-check every variable in Section 6.1. Note that `AT_*` variables are optional at V1 launch (Section 6.1) — do not add them speculatively while debugging a crash loop, since an incomplete/placeholder Africa's Talking credential is itself a possible cause of a validation failure. |
| Email OTP never arrives | `EMAIL_PROVIDER_API_KEY` missing/invalid, or the sending domain is not verified with the provider (email lands in spam or is rejected outright) | Verify the credential and sending-domain configuration with the email provider directly; check the provider's own delivery/bounce dashboard before assuming an AGRIOS-side bug. |
| OTP SMS never arrives (only relevant once SMS has been enabled) | `AT_ENVIRONMENT` still set to `sandbox`, AT account has zero SMS credit, or `AT_API_KEY`/`AT_USERNAME` were never set at all (meaning SMS is simply not active for this deployment — Section 6.1) | Confirm SMS is actually meant to be active for this deployment first; if so, set `AT_ENVIRONMENT=production` and check AT billing balance. |
| CORS error in browser console | The live frontend origin is missing from `ALLOWED_ORIGINS` | Add it; multiple origins are comma-separated with no spaces. |
| Frontend blank screen / "Cannot GET /" | `VITE_API_BASE_URL` wrong, missing, or missing the `/api/v1` suffix | Correct and redeploy. |
| `alembic heads` returns more than one head | The migration chain has forked (two migrations both claim the same `down_revision`) | Must be resolved before any further schema work proceeds — this is a Red-status blocking condition, not a warning. |

---

## 11. Monitoring and the First 24 Hours After Any Deploy

Sentry alert rules: any backend error exceeding 5/minute, and any unhandled frontend exception, should page/notify the team channel. A p95 API response time above 2 seconds on `/api/v1/**` is treated as a performance regression worth investigating, not merely noting. In the first hour after any production deploy, the following should be actively watched rather than assumed fine: Railway CPU/memory (should not be climbing unboundedly), Sentry (no new error-rate spikes), Supabase connection count (should stay comfortably under the pool limit), and — specific to AGRIOS — the delivery dashboard for whichever OTP channel is actually active. At V1 launch this is the transactional email provider's delivery/bounce dashboard, since Email OTP is the primary launch mechanism; once SMS is activated (Section 6.1), the Africa's Talking delivery dashboard becomes equally important to watch. A broken OTP delivery pipeline on the active channel is invisible in every other monitoring surface but directly blocks new-user login, which is why it is called out separately here rather than assumed to be covered by general error monitoring.

---

## 12. Go/No-Go Criteria for a Launch or Major Release

**Go** requires all of: every backend smoke test passing (`/health` returns the expected JSON shape, security headers present, `/docs` returns 404 in production), every frontend smoke test passing (loads on mobile Chrome, an OTP arrives on the active channel — Email at V1 launch, SMS once activated per Section 6.1 — within roughly 60 seconds, all navigation tabs render), Sentry receiving events with zero critical errors, Railway health checks green continuously for at least 10 minutes post-deploy, and the PWA confirmed installable on Android Chrome. **No-Go** — abort and roll back — if any of: `/health` returns anything other than the expected healthy shape, an OTP on the active channel is not delivered within 3 minutes of a request, the frontend fails to load on mobile Chrome (the primary target device), any unhandled exception appears in Sentry within 10 minutes of deploy, or Railway restarts the process more than once in that window.
