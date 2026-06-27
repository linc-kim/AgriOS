## Sprint 10 Handover Report

**Sprint:** 10 — Production Hardening + Launch  
**Tier:** 10  
**Date closed:** 2026-06-26  
**Status:** COMPLETE  

---

### Migrations delivered

None. DB-10 (Frozen): the migration chain was sealed at 30 migrations (001–030) in Sprint 7. No schema mutations are permitted in Sprint 10.

---

### Backend delivered

**Version bump**
- `backend/app/config.py`: `VERSION` bumped from `"0.1.0"` → `"1.0.0"`
- `frontend/package.json`: `version` bumped from `"0.1.0"` → `"1.0.0"`

**SecurityHeadersMiddleware** (`backend/app/core/middleware.py`)
- New class `SecurityHeadersMiddleware(BaseHTTPMiddleware)` added alongside existing `RequestIDMiddleware` and `TimingMiddleware`
- Headers injected on every response:
  - `X-Content-Type-Options: nosniff` — MIME-sniffing prevention
  - `X-Frame-Options: DENY` — clickjacking protection
  - `X-XSS-Protection: 1; mode=block` — legacy XSS filter
  - `Referrer-Policy: strict-origin-when-cross-origin` — referrer leakage control
  - `Permissions-Policy` — camera, microphone, geolocation, payment, USB all denied
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` — API-specific CSP
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` — production only

**Middleware registration** (`backend/app/main.py`)
- `SecurityHeadersMiddleware` added to middleware stack between CORS and RequestID
- Middleware stack order documented inline (outermost-first: CORS → Security → RequestID → Timing)

**Rate limiting (confirmed, not newly implemented)**
- `backend/app/services/auth_service.py` already enforces Engineering Constitution SD-06:
  max 3 OTP requests per phone per 10-minute window, enforced at the service layer via DB query
- `OTP_MAX_REQUESTS_PER_PHONE: int = 3` and `OTP_REQUEST_WINDOW_MINUTES: int = 10` confirmed in `config.py`

---

### Frontend delivered

**Sentry integration** (AD-14 Frozen: Sentry is the error monitoring platform)
- `@sentry/react@^8.45.0` added to `frontend/package.json` dependencies
- `frontend/src/lib/sentry.ts` — Sentry initialisation module:
  - `initialiseSentry()` — initialises with DSN, environment, release tag, tracing (20%), and session replay (10% sample / 100% on error)
  - PII protection: `maskAllText: true`, `blockAllMedia: true` in replay integration
  - `beforeSend` filter: silently drops expected 401/403 auth errors
  - No-op in development (requires `VITE_SENTRY_DSN` to be set)
- `frontend/src/main.tsx` — updated:
  - `initialiseSentry()` called before `createRoot` so bootstrap errors are captured
  - Root component tree wrapped in `<Sentry.ErrorBoundary>` with a branded fallback UI (AGRIOS green "Try again" button, no stack trace exposed to users)

---

### Deployment configs delivered

**`railway.toml`** (project root)
- Builder: Nixpacks (auto-detects Python from `requirements.txt`)
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
- Restart policy: on-failure, max 3 retries
- Health check: `GET /health`, 30 s timeout, 10 s interval

**`frontend/vercel.json`**
- Framework: Vite
- SPA routing: all paths (excluding `/assets/`, `/icons/`, `/manifest.webmanifest`, `/sw.js`, workbox files) rewrite to `/index.html`
- Security headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, HSTS (preload), full Content-Security-Policy with Sentry CDN allow-listed
- Cache headers: `/assets/**` immutable 1-year, `/icons/**` 24-hour, manifest 1-hour, `sw.js` no-cache (critical for PWA update propagation)
- `Service-Worker-Allowed: /` header on `sw.js` to allow root-scope service worker

**`.env.example`** (both backend and frontend — confirmed already present and complete)

**Launch runbook**
- `docs/LAUNCH_RUNBOOK.md` — full operational guide: pre-launch checklist, secrets inventory, migration steps, deployment procedure, smoke tests, Sentry/Railway monitoring setup, go/no-go criteria, rollback procedure, post-launch 7-day task list, support contacts

---

### Permissions added

None. Sprint 10 contains no new API endpoints. All existing RBAC assignments are unchanged.

---

### Frontend delivered

- Screens: none (no new user-facing screens in Sprint 10)
- Routes: none added
- Query keys: none added
- i18n: no new keys (Sprint 10 is infrastructure-only; i18n key counts unchanged from Sprint 9)

---

### Tests delivered

- Unit: `tests/unit/api/v1/test_hardening.py` — **25 tests**
  - `backend/tests/unit/api/v1/test_hardening.py` — identical, runs in CI
  - Coverage: VERSION=1.0.0, Settings OTP config, SecurityHeadersMiddleware header values, dispatch behaviour (6 headers always present, HSTS production-only)

- Integration: `tests/integration/test_hardening_flow.py` — **19 tests**
  - `backend/tests/integration/test_hardening_flow.py` — identical, runs in CI
  - Coverage: GET /health (200, version, environment, db keys, db connected), security headers on live HTTP responses, X-Request-ID UUID format, X-Process-Time format, OTP rate limiting (4th request → 429 RATE_LIMITED), cross-phone rate limit isolation

---

### Known carryovers

None. Sprint 10 is the final V1 sprint. All V1 scope is complete.

Previously open KI items from earlier sprints that remain deferred to Phase 2:
- **KI-02** (ProductionRecordScreen placeholder) — deferred to Phase 2
- **KI-03** (CreateFlockScreen depends on houses list) — deferred to Phase 2
- **KI-04** (/flock and /health tab redirect) — deferred to Phase 2

These are Phase 2 concerns and do not block V1 launch.

---

### Frozen decision compliance

| Decision | Status |
|----------|--------|
| DB-07 (no real-time P&L) | Compliant — no aggregate queries added |
| DB-10 (migration chain sealed at 030) | Compliant — no new migrations |
| DB-04 (farm_id on all tables) | Compliant — no new tables |
| DB-01 (soft deletes) | Compliant — no new tables |
| AD-01 (UUID PKs) | Compliant — no new tables |
| AD-07 (Railway backend) | Compliant — `railway.toml` targets Railway |
| AD-08 (Vercel frontend) | Compliant — `vercel.json` targets Vercel |
| AD-09 (PWA, no native app) | Compliant — PWA only, no app store submission |
| AD-13 (APScheduler) | Compliant — scheduler unchanged |
| AD-14 (Sentry monitoring) | Compliant — frontend Sentry added, backend Sentry confirmed |

---

### Gate summary

| Gate | Result |
|------|--------|
| 1 — Schema syntax | PASS — all 5 Python files compile clean |
| 2 — i18n JSON validity | PASS — EN and SW both valid JSON (no new keys in Sprint 10) |
| 3 — File completeness | PASS — sentry.ts, railway.toml, vercel.json, both test files all present |
| 4 — Test coverage | PASS — 25 unit tests (req: ≥20), 19 integration tests (req: ≥15) |
| 5 — RBAC matrix | PASS — no new endpoints; existing RBAC unchanged |
| 6 — Frozen constraint audit | PASS — no migrations, no new tables, no real-time aggregates |

---

### V1 Build Summary

| Sprint | Scope | Status |
|--------|-------|--------|
| Sprint 0 | Foundation — DB schema (001–005), auth system, core infrastructure | COMPLETE |
| Sprint 1 | Design system — tokens, components, layouts | COMPLETE |
| Sprint 2 | Farm infrastructure — migrations 006–011, farm CRUD, enterprise | COMPLETE |
| Sprint 3 | Flock operations — migrations 014–016, flock lifecycle, production records | COMPLETE |
| Sprint 4 | Health module — migrations 017–018, vaccination records, disease alerts | COMPLETE |
| Sprint 5 | Finance module — migrations 019–022, expenses, revenue, P&L snapshots | COMPLETE |
| Sprint 6 | ARIA AI assistant — migrations 023–027, conversational AI, insights | COMPLETE |
| Sprint 7 | Notifications + alerts — migrations 028–030, SMS, audit log, market prices | COMPLETE |
| Sprint 8 | Enterprise multi-farm — admin portal, RBAC, 8 admin screens | COMPLETE |
| Sprint 9 | Offline sync + settings — offline UI, 4 settings screens, SMS preferences | COMPLETE |
| Sprint 10 | Production hardening — security headers, Sentry, deployment configs, v1.0.0 | **COMPLETE** |

**AGRIOS V1 is complete and launch-ready.**

Total migrations: 30 (001–030, chain intact)  
Total backend endpoints: 40+ across auth, farm, flock, health, finance, ARIA, notifications, admin  
Total frontend screens: 35+ across all modules  
Total test coverage: 250+ unit tests, 165+ integration tests across 10 sprints  
