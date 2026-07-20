# Greena — Deployment Hardening & Launch Runbook

Audit date: 2026-07-20 · Version 1.0.0 · Target: Vercel + Railway + Supabase

This document covers the production launch: what must be configured, how to
deploy, how to roll back, and what to verify afterwards. It is written to be
followed literally.

**Read `## 1. Critical launch blockers` first.** Three of them break the
product outright, and two are invisible until real users are on the system.

---

## 1. Critical launch blockers

These MUST be resolved before real users. Each is a genuine failure, not a
best-practice nit.

### BLOCKER-1 — The frontend and API must share a registrable domain

**Impact:** every user is silently logged out every 15 minutes.

The refresh token cookie is set `SameSite=Strict`
(`backend/app/api/v1/endpoints/auth.py`). A browser sends a `Strict` cookie
only when the request is same-site with the page in the address bar. SameSite
compares the *registrable domain* (eTLD+1).

- `app.greena.app` → `api.greena.app` — both are `greena.app`. **Same-site, works.**
- `greena.vercel.app` → `greena-api.up.railway.app` — `vercel.app` and
  `up.railway.app` are both on the Public Suffix List, so each hostname is its
  own registrable domain. **Cross-site: the cookie is never sent.**

In the second case `POST /api/v1/auth/refresh` receives no cookie, returns 401,
and the user is logged out the moment their 15-minute access token expires.
`SameSite=Lax` would not help — Lax only relaxes top-level GET navigations, not
the XHR the app uses.

**Required:** serve both from subdomains of one apex you control:

| Component | Hostname |
|---|---|
| Frontend (Vercel) | `app.greena.app` |
| Backend (Railway) | `api.greena.app` |

If you must ship on platform default hostnames, the cookie has to become
`SameSite=None; Secure`, which re-opens CSRF and requires a token or
origin-check defence. That is a code change, not a config change — do not
attempt it as a launch-day workaround.

**Verify:** log in on the deployed site, wait 15+ minutes (or delete the access
token from memory by reloading), and confirm the session survives. Check the
`Set-Cookie` on `/auth/login` shows `Secure; HttpOnly; SameSite=Strict`.

---

### BLOCKER-2 — CSP `connect-src` must name the real API origin

**Impact:** the app loads and then every API call fails.

`frontend/vercel.json` sets a Content-Security-Policy whose `connect-src` lists
the API origin explicitly. A browser blocks any request to an origin absent
from that list. It has been updated to `https://api.greena.app`; **if your API
lives anywhere else, change it or the deployed app is inert.**

The failure is quiet — the page renders, then every fetch is refused with only
a console CSP violation. It will not show up in backend logs at all, because
the requests never leave the browser.

Three values must agree:

| Where | Value |
|---|---|
| `frontend/vercel.json` → `connect-src` | `https://api.greena.app` |
| Vercel env → `VITE_API_BASE_URL` | `https://api.greena.app/api/v1` |
| Railway env → `ALLOWED_ORIGINS` | `https://app.greena.app` |

**Verify:** open the deployed site, DevTools → Console, confirm no
`Refused to connect` violations; Network tab shows API calls returning 200.

---

### BLOCKER-3 — Confirm the scheduler advisory lock on the real deployment

**Impact if wrong:** every farmer receives duplicate SMS; SMS spend doubles.

The Dockerfile runs `uvicorn --workers 2`. Each worker executes the FastAPI
lifespan, so before this audit each worker started its own APScheduler and all
six cron jobs fired twice a day — including the four that send SMS through
Africa's Talking, which bills per message.

Fixed in this audit: startup now takes a Postgres advisory lock
(`pg_try_advisory_lock`) and only the holder runs the scheduler. This is also
correct if you scale to multiple Railway replicas.

**This fix has not been verified against hosted Postgres** (see §9). Confirm on
first staging deploy before enabling SMS.

**Verify:** in Railway logs after boot, expect exactly one
`background scheduler started (holds scheduler lock)` and one or more
`Scheduler lock held elsewhere — this worker serves HTTP only`. Two of the
former means the lock is not working: do not set `AT_API_KEY` until resolved.

---

## 2. Environment variable checklist

`backend/.env.example` is the authoritative list and is verified complete —
all 46 settings read by `config.py` are documented, with no phantom entries.

### Railway (backend service, Root Directory = `backend`)

**Required — the app will not boot without these**

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | Supabase **session pooler**, port 5432 | Not the transaction pooler — see §6 |
| `SECRET_KEY` | 64 hex chars | `python -c "import secrets;print(secrets.token_hex(32))"` |
| `JWT_SECRET` | 64 hex chars, **different** from `SECRET_KEY` | Rotating logs everyone out |

**Production-critical — startup refuses unsafe values**

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `ALLOWED_ORIGINS` | `https://app.greena.app` (no wildcard, no `http://`) |
| `FRONTEND_URL` | `https://app.greena.app` — email links point here |

**Strongly recommended**

| Variable | Value |
|---|---|
| `SENTRY_DSN` | Backend Sentry project DSN. Unset logs a startup warning; it no longer blocks boot |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | Defaults `5` / `10`. See §6 before raising |

**Optional — features stay dormant until set**

`GEMINI_API_KEY`, `CLAUDE_API_KEY` (ARIA falls back to its offline model),
`AT_API_KEY` + `AT_USERNAME` (SMS — do not set until BLOCKER-3 is confirmed),
`EMAIL_PROVIDER` + `ZOHO_SMTP_*` (required before enabling
`REQUIRE_EMAIL_VERIFICATION`), `GOOGLE_CLIENT_ID`/`SECRET` (required before
`ENABLE_GOOGLE_OAUTH`).

### Vercel (frontend project, Root Directory = `frontend`)

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `https://api.greena.app/api/v1` | Must include `/api/v1`; must match the CSP |
| `VITE_ENVIRONMENT` | `production` | |
| `VITE_SENTRY_DSN` | Frontend Sentry DSN (separate project) | Optional |

`VITE_*` values are baked into the client bundle at build time and are
**public**. Never put a secret in one. Changing any of them requires a
**rebuild**, not just a redeploy.

### Secrets inventory

| Secret | Where generated | Rotation impact |
|---|---|---|
| `SECRET_KEY` | `secrets.token_hex(32)` | None today (reserved; no code path reads it) |
| `JWT_SECRET` | `secrets.token_hex(32)` | All access tokens invalid → users re-authenticate |
| `DATABASE_URL` password | Supabase dashboard | Restart required |
| `GEMINI_API_KEY` | Google AI Studio | ARIA falls back to Claude, then offline |
| `CLAUDE_API_KEY` | Anthropic Console | ARIA falls back to offline |
| `AT_API_KEY` | Africa's Talking | SMS stops; app unaffected |
| `SENTRY_DSN` × 2 | Sentry | Error tracking stops; app unaffected |

---

## 3. Deployment runbook

### 3.1 One-time setup

**Supabase**
1. Create the project. Region close to users (Kenya → `eu-central-1` or `ap-south-1`).
2. Project Settings → Database → Connection string → **Session pooler**.
3. Copy the URI, keeping the `postgres.<project-ref>` username form.
4. Note the connection cap for your plan (free = 60 total).

**Railway**
1. New project → Deploy from GitHub → select the repo.
2. **Root Directory = `backend`** (Settings → Source).
3. Builder is picked up from `railway.toml` (Dockerfile).
4. Add every Railway variable from §2.
5. Settings → Networking → add custom domain `api.greena.app`, then create the
   `CNAME` Railway shows you at your DNS provider.

**Vercel**
1. New project → import the repo.
2. **Root Directory = `frontend`**.
3. Framework preset: Vite. Build/install commands come from `vercel.json`.
4. Add the Vercel variables from §2 (Production scope).
5. Domains → add `app.greena.app` → create the `CNAME`.

### 3.2 Deploy

```bash
# 1. Confirm the tree is clean and tests pass locally
cd backend
./.venv/Scripts/python.exe -m pytest -q          # expect: 499 passed

cd ../frontend
npm run type-check                                # expect: no output
npm run build                                     # expect: built in ~12s

# 2. Tag the release so a rollback has a target
cd ..
git tag -a v1.0.0 -m "Phase 3 launch"
git push origin v1.0.0

# 3. Push to the deploy branch — Railway and Vercel both build from git
git push origin main
```

Railway runs `alembic upgrade head` as a **pre-deploy step**
(`railway.toml → preDeployCommand`), so migrations complete before the health
check window opens and before the server starts. A migration failure aborts the
deploy and leaves the previous release serving.

### 3.3 Migration commands

```bash
# Inspect before applying — never run a migration you have not read
alembic history --verbose | head -40
alembic current                      # revision the database is on

# Apply (Railway does this automatically; this is for manual/staging runs)
DATABASE_URL="<supabase-session-pooler-url>" alembic upgrade head

# Verify
DATABASE_URL="<...>" alembic current # expect: 050 (head)
```

---

## 4. Rollback procedure

### 4.1 Decide what actually broke

| Symptom | Roll back? |
|---|---|
| Bad frontend build, API healthy | Vercel only — instant, safe |
| API 5xx, schema unchanged | Railway only |
| API broken **and** a migration ran | Code first, then assess the schema (§4.3) |
| Data corruption | Do **not** roll back blindly — restore from backup (§4.4) |

### 4.2 Code rollback

**Vercel** — Deployments → previous deployment → **Promote to Production**.
Instant; static assets only, no data risk.

**Railway** — Deployments → last known-good → **Redeploy**. Note that
`preDeployCommand` runs again; `alembic upgrade head` is a no-op if the schema
is already current.

```bash
# Or by git, if you prefer an auditable revert
git revert --no-edit <bad-sha>
git push origin main
```

### 4.3 Schema rollback

Every Greena migration implements `downgrade()`, and 049/050 have been verified
to round-trip. Still, **prefer rolling forward**: a downgrade that drops a
column destroys the data in it.

```bash
alembic current                                   # confirm where you are
DATABASE_URL="<...>" alembic downgrade -1         # one step back
DATABASE_URL="<...>" alembic current              # confirm
```

After any rollback, confirm the schema and the running code agree:

```bash
curl -s -X POST https://api.greena.app/api/v1/production/rollback/verify \
  -H "Authorization: Bearer $TOKEN" | jq
```

`schema_compatible: false` means the database is **ahead** of the code — older
code against a newer schema. Roll forward again or downgrade the database;
do not leave it in that state.

### 4.4 Data rollback

Restores are farm-scoped, checksum-verified, and take a safety snapshot first.
**Always dry-run.**

```bash
# 1. List and verify
curl -s .../farms/$FARM/data/backups -H "$AUTH" | jq '.data[] | {id,label,created_at}'
curl -s .../farms/$FARM/data/backups/$BACKUP/verify -H "$AUTH" | jq '.data.valid'

# 2. Dry run — writes nothing, reports what would change
curl -s -X POST .../farms/$FARM/data/restore -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"backup_id":"'$BACKUP'","dry_run":true}' | jq '.data.summary'

# 3. Apply only after reading the summary
curl -s -X POST .../farms/$FARM/data/restore -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"backup_id":"'$BACKUP'","dry_run":false}' | jq '.data'
```

A tampered or corrupted snapshot is refused with 422 and never partially
applied. The applied restore's `safety_backup_id` is your undo point.

---

## 5. Post-deployment verification checklist

Run in order. Stop at the first failure.

**Infrastructure**
- [ ] `curl https://api.greena.app/health` → `200`, `"db":"connected"`
- [ ] `curl https://api.greena.app/api/v1/production/version` → correct version + git SHA
- [ ] Railway logs: `Environment validation passed for production.`
- [ ] Railway logs: exactly **one** `holds scheduler lock` across all workers
- [ ] Railway logs: `Release recorded: v1.0.0`
- [ ] `alembic current` → `050 (head)`

**Security** (authenticated as an owner)
- [ ] `POST /api/v1/production/deployment/verify` → `passed: true`, all four checks
- [ ] `GET /api/v1/production/diagnostics` → `status: healthy`
- [ ] `curl -sI https://api.greena.app/health | grep -i strict-transport` → present
- [ ] `curl -s https://api.greena.app/docs` → `404` (OpenAPI closed in production)
- [ ] `Set-Cookie` on login shows `Secure; HttpOnly; SameSite=Strict`
- [ ] CORS from an unknown origin → no `Access-Control-Allow-Origin`
- [ ] 25 rapid failed logins → `429` with `Retry-After`

**Frontend**
- [ ] Site loads at `https://app.greena.app`
- [ ] DevTools Console: **no CSP violations** (this is BLOCKER-2's canary)
- [ ] Network: API calls resolve to `api.greena.app` and return 200
- [ ] Log in, then hard-reload → session survives (BLOCKER-1's canary)
- [ ] Leave idle 16+ minutes → still logged in (access token refreshed)

**Observability**
- [ ] Trigger a deliberate 500 → appears in backend Sentry within ~1 min
- [ ] Trigger a frontend error → appears in frontend Sentry
- [ ] `GET /api/v1/production/metrics` → Prometheus text, `greena_build_info` present

---

## 6. Supabase connection pooling

**Use the session pooler (port 5432), not the transaction pooler (6543).**
The transaction pooler does not support the prepared statements asyncpg issues;
queries then fail at runtime rather than at startup, which is a bad way to find
out. If you are forced onto it, asyncpg needs `statement_cache_size=0`.

**Connection budget**

```
per worker  = DB_POOL_SIZE + DB_MAX_OVERFLOW   = 5 + 10 = 15
app total   = 15 × 2 workers                   = 30
+ scheduler advisory lock                      =  1
                                                 ──
                                                 31
```

Supabase free tier allows **60 total**, shared with migrations, `psql`
sessions, and admin tooling. 31 leaves comfortable headroom. Before raising
`DB_POOL_SIZE` or the worker count, recompute against your plan's cap —
exhausting it produces connection timeouts under load, which look like random
5xx rather than an obvious resource error.

`pool_pre_ping=True` and `pool_recycle=1800` are set so a connection dropped
server-side by the pooler is replaced rather than handed to a request.

---

## 7. Smoke tests — all Phase 3 modules

Run against staging as a farm owner after every deploy. Each is one user-visible
action; the point is to touch every module's write path once.

| # | Module | Action | Expected |
|---|---|---|---|
| 1 | Auth | Log in; reload; wait 16 min | Session persists across refresh |
| 2 | Organizations | Switch org in the switcher | Farm list changes |
| 3 | Farms | Open a farm, view dashboard | Real metrics, no placeholders |
| 4 | Flocks | Create a flock in an empty house | 201; appears in list |
| 5 | Daily Ops | Log a daily entry (feed, mortality) | Saved; flock count decreases |
| 6 | Health | Record a vaccination | Appears in flock history |
| 7 | Feed | Record a feed purchase | Stock rises; expense auto-created |
| 8 | Inventory | Adjust an item's stock | Movement recorded |
| 9 | Finance | Add an expense; open analytics | Totals include it |
| 10 | Reporting | Generate a farm summary; download CSV | File downloads, non-empty |
| 11 | Automation | View the activity centre | Recent actions listed |
| 12 | ARIA | Ask "how are my birds doing?" | Grounded answer citing real data |
| 13 | ARIA ops | Ask "are my backups healthy?" | Real backup counts |
| 14 | Admin | Open admin platform (as platform admin) | Orgs/users/health load |
| 15 | Production | Open `/production`, all seven tabs | All render, no console errors |
| 16 | Backups | Create a backup; verify it | `status: success`, `valid: true` |
| 17 | Restore | Dry-run a restore | Summary; **nothing written** |
| 18 | Export | Export expenses as CSV and Excel | Both download and open |
| 19 | Import | Upload a CSV with one bad row | 1 valid / 1 invalid; row number correct |
| 20 | Round trip | Import the file you just exported | `failed_rows: 0` |

Also verify on a real phone (not just a narrow desktop window) — the workspace
is used in the field on mobile.

---

## 8. Deployment configuration review

**Railway (`backend/railway.toml`)** — sound.
Migrations as `preDeployCommand` correctly decouple migration duration from
`healthcheckTimeout`, avoiding a container killed mid-migration and the deploy
retry loop that follows. `healthcheckPath=/health` returns 503 when the
database is unreachable, so Railway will not route to a degraded instance.
`restartPolicyMaxRetries=3` is sensible.

**Dockerfile** — sound. Non-root user, slim base, shell-form `CMD` so `${PORT}`
expands (the toml comment explaining why there is no `startCommand` is correct
and worth keeping).

**Vercel (`frontend/vercel.json`)** — sound apart from BLOCKER-2. The SPA
rewrite correctly excludes `assets`, `icons`, the manifest, and the service
worker, so `sw.js` is not shadowed by `index.html`. Immutable caching on
hashed assets, `no-store` on `sw.js` — both right.

---

## 9. What has NOT been verified

Stated plainly, because the gap matters more than the checklist:

- **Nothing in this audit has run against hosted infrastructure.** The local
  Postgres was lost mid-session (it was a Docker container; Docker Desktop is
  broken on this machine), so the regression suite could not be re-run after
  the changes below, and none of it has touched Supabase, Railway or Vercel.
- **The scheduler advisory lock is unverified at runtime.** The logic is sound
  and the code imports cleanly, but `pg_try_advisory_lock` has not been
  exercised across two live workers. This gates SMS — see BLOCKER-3.
- **The pool resize is unverified under load.** The arithmetic is in §6; the
  behaviour at the cap has not been observed.
- **SameSite cross-site behaviour is reasoned, not demonstrated.** It follows
  directly from the spec and the Public Suffix List, but no browser test was
  run against two real hostnames.

Verified in this session, without a database: startup validation (six config
permutations, plus a real boot that correctly refused to start), all security
headers, HSTS, OpenAPI closure, CORS allow/deny/credentials, and refresh cookie
flags — 22/22 checks.
