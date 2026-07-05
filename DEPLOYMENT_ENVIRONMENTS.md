# AGRIOS — Production Environment Variables

Authoritative, code-verified list of every environment variable AGRIOS uses.
Verified against: `backend/app/config.py` (pydantic Settings), all
`os.environ` reads (`backend/app/services/aria_service.py`),
`backend/Dockerfile`, `backend/railway.toml`, `frontend/vercel.json`,
`frontend/vite.config.ts`, and every `import.meta.env.*` reference in
`frontend/src`.

Legend — **Req** = Required / Opt = Optional / Prod = Production-required.
"Prod default" = the value the platform should run with. Secrets are never
committed and never placed in `VITE_*` (which are public, baked into the build).

---

## 1. Railway Backend Variables (non-secret configuration)

| Variable | Status | Prod default | Example | Consumed by |
|---|---|---|---|---|
| `ENVIRONMENT` | **Prod** | `production` | `production` | `config.py` → security headers, Sentry gate, `/docs` off |
| `ALLOWED_ORIGINS` | **Prod** | — | `https://app.agrios.app,https://admin.agrios.app` | `config.py` → CORS middleware |
| `TZ` | Opt | `Africa/Nairobi` | `Africa/Nairobi` | Dockerfile `ENV` + OS/scheduler (config field itself unused) |
| `GEMINI_MODEL` | Opt | `gemini-2.0-flash` | `gemini-2.0-flash` | `aria_service.py` via `os.environ` |
| `CLAUDE_MODEL` | Opt | `claude-haiku-4-5-20251001` | (same) | `aria_service.py` via `os.environ` |
| `AT_USERNAME` | Opt | *(empty)* | `agrios` | `sms_service.py` (SMS dormant until set) |
| `AT_SENDER_ID` | Opt | `AGRIOS` | `AGRIOS` | `sms_service.py` |
| `JWT_EXPIRE_MINUTES` | Opt | `15` | `15` | `security.py` (frozen; rarely overridden) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Opt | `30` | `30` | `security.py` |
| `OTP_EXPIRE_MINUTES` | Opt | `10` | `10` | `auth_service.py` |
| `OTP_MAX_ATTEMPTS` | Opt | `3` | `3` | `auth_service.py` |
| `OTP_MAX_REQUESTS_PER_PHONE` | Opt | `3` | `3` | `auth_service.py` |
| `OTP_REQUEST_WINDOW_MINUTES` | Opt | `10` | `10` | `auth_service.py` |
| `PORT` | **Injected** | *(set by Railway)* | `8080` | `railway.toml` / Dockerfile start command — **do not set manually** |

## 2. Railway Secrets (sensitive — set as secret values)

| Variable | Status | Example (never commit) | Consumed by |
|---|---|---|---|
| `DATABASE_URL` | **Req** | `postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres` | `config.py`→engine, Alembic (pre-deploy) |
| `JWT_SECRET` | **Req** | `<64 hex>` (≠ SECRET_KEY) | `security.py` — access/refresh JWT signing |
| `SECRET_KEY` | **Req** | `<64 hex>` | `config.py` requires it to boot; **currently not read by any code path** — reserved |
| `AT_API_KEY` | Opt | `atsk_...` | `sms_service.py` (activates SMS with AT_USERNAME) |
| `GEMINI_API_KEY` | Opt | `AIza...` | `aria_service.py` (ARIA primary) |
| `CLAUDE_API_KEY` | Opt | `sk-ant-...` | `aria_service.py` (ARIA fallback) |
| `SENTRY_DSN` | Opt | `https://<key>@o0.ingest.sentry.io/0` | `main.py` (backend error monitoring) |

## 3. Vercel Variables (frontend — all PUBLIC, build-time)

| Variable | Status | Prod default | Example | Consumed by |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | **Req** | — | `https://api.agrios.app/api/v1` | `api/client.ts` (must include `/api/v1`) |
| `VITE_ENVIRONMENT` | Opt | `production` | `production` | `lib/sentry.ts` (env tag + dev gate) |
| `VITE_SENTRY_DSN` | Opt | *(empty)* | `https://<key>@o0.ingest.sentry.io/1` | `lib/sentry.ts` (disabled if empty) |

`vercel.json` contains **no** env block — install/build/output/rewrites/headers
are static; only the three `VITE_*` above are configured in the Vercel dashboard.

## 4. Shared Variables

There are **no literally-shared variable names** across Railway and Vercel — the
two apps are configured independently (correct for a decoupled deploy). Two
*concepts* are paired and must be kept consistent by hand:

| Concept | Backend (Railway) | Frontend (Vercel) |
|---|---|---|
| Environment tag | `ENVIRONMENT=production` | `VITE_ENVIRONMENT=production` |
| Error monitoring | `SENTRY_DSN` (backend project) | `VITE_SENTRY_DSN` (separate FE project) |
| API origin ↔ CORS | `ALLOWED_ORIGINS` must include the Vercel origin | `VITE_API_BASE_URL` must point at the Railway origin `+/api/v1` |

---

## 5. Detected: unused / missing / undocumented

**Declared but NOT read by any code path (safe to leave unset except where the
config marks them required):**
- `SECRET_KEY` — **required to boot** (no default in `config.py`) yet never
  referenced; JWT signing uses `JWT_SECRET`. Keep setting it; treat as reserved.
- `AT_ENVIRONMENT` — defined in config but unused; the Africa's Talking SDK is
  initialised with `AT_USERNAME` + `AT_API_KEY` only.
- `PROJECT_NAME` — defined, unused (cosmetic).
- `AI_CONTEXT_MAX_TOKENS`, `AI_CALL_TIMEOUT_SECONDS`, `AI_RESPONSE_MAX_WORDS` —
  defined in config, but the caps are applied in `aria_service.py` directly, not
  via these settings. Config drift, not a runtime risk.

**Referenced in documentation but NOT in code (do not set — no effect):**
- `EMAIL_PROVIDER_API_KEY`, `EMAIL_FROM_ADDRESS` — described in
  `DEPLOYMENT_GUIDE.md`, but Email OTP is unimplemented (Phase 2) and
  `config.py` does not read them.

**Referenced in code but potentially surprising (documented here):**
- `GEMINI_API_KEY` / `GEMINI_MODEL` / `CLAUDE_API_KEY` / `CLAUDE_MODEL` are read
  via `os.environ.get(...)` in `aria_service.py` *in addition to* being declared
  in `config.py`. Set them once in Railway; both access paths see the same value.

**Missing:** none. Every variable the running application reads is represented in
`backend/.env.example` / `frontend/.env.example`. No code path references an
undocumented variable.

**Dev-only (not for production):** `infrastructure/docker-compose.yml` sets
`POSTGRES_USER/PASSWORD/DB` and a local `DATABASE_URL` for the local Postgres
container — never used by Railway/Vercel.

---

## 6. Minimum viable production set

**Railway (backend) — must set:** `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`,
`ENVIRONMENT=production`, `ALLOWED_ORIGINS`. Strongly recommended:
`GEMINI_API_KEY`, `CLAUDE_API_KEY`, `SENTRY_DSN`, `TZ=Africa/Nairobi`.
(`PORT` is injected by Railway.)

**Vercel (frontend) — must set:** `VITE_API_BASE_URL`. Recommended:
`VITE_ENVIRONMENT=production`, `VITE_SENTRY_DSN`.

Full annotated templates: `backend/.env.example`, `frontend/.env.example`.
