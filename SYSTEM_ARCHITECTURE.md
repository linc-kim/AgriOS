# AGRIOS SYSTEM ARCHITECTURE

**Read `AGRIOS_MASTER_CONTEXT.md` first.** This document describes *how* AGRIOS is built; the master context describes *why* it is built that way. Where this document states a rule without justifying it, the justification almost always lives in the master context or in the Frozen Decision Register referenced throughout.

---

## 1. The Four-Pillar Model

AGRIOS V1 is organized as four pillars with a strict dependency chain. No pillar is independently accessible without its prerequisites being operational — this is a design statement as much as a build-order statement: it means, for example, that ARIA cannot exist without the Poultry Module producing real data for it to reason over, and the Poultry Module cannot exist without farm and auth infrastructure to scope it.

```
┌──────────────────────────────────────────────────────────┐
│                    AGRIOS V1 SYSTEM                       │
├──────────────────┬───────────────────────────────────────┤
│  PILLAR 1        │  CORE PLATFORM                         │
│  (Foundation)    │  Auth · Roles · Farms · SMS · Jobs     │
├──────────────────┼───────────────────────────────────────┤
│  PILLAR 2        │  POULTRY MODULE                        │
│  (Product)       │  Flocks · Ops · Health · Finance       │
├──────────────────┼───────────────────────────────────────┤
│  PILLAR 3        │  ADMIN MODULE                           │
│  (Operations)    │  Users · Alerts · Market · Analytics   │
├──────────────────┼───────────────────────────────────────┤
│  PILLAR 4        │  ARIA — AI ASSISTANT                   │
│  (Intelligence)  │  Context · Chat · Insights · Recs      │
└──────────────────┴───────────────────────────────────────┘
```

The critical path used to build the MVP, in order, was: Auth → Roles → Farm Infrastructure → Flock Management → Daily Operations → Financial Engine → ARIA Context Compiler → Conversation Engine → Dashboard integration → Admin. This ordering is recorded here because it is also the correct mental model for *understanding* the system, not only for having originally built it: to understand Finance, you must understand Flocks; to understand ARIA, you must understand Finance and Health, because ARIA's context package is assembled from both.

---

## 2. Backend

### 2.1 Stack and why each piece was chosen

| Layer | Technology | Why |
|---|---|---|
| Framework | FastAPI (Python 3.12) | Async-first, strong typing via Pydantic, and the natural home for the AI integration work the product depends on. |
| ORM | SQLAlchemy 2.x, async style (`Mapped[]`, `mapped_column`) | Type-safe models, async-compatible end to end — no sync/async impedance mismatch between the ORM and FastAPI's event loop. |
| Migrations | Alembic | The natural migration partner for SQLAlchemy; every schema change is a linear, reversible migration file — see `DATABASE_ARCHITECTURE.md`. |
| Validation | Pydantic v2 + `pydantic-settings` | Request/response schemas and application configuration share one validation model. |
| Database driver | `asyncpg` via `postgresql+asyncpg://` | Required for true async DB I/O under FastAPI; a sync driver would block the event loop under load. |

The backend is a **single deployable service** — a monolith, deliberately (`AGRIOS_MASTER_CONTEXT.md` Section 4.5). There is one `app/main.py` FastAPI application; there are no separate microservices for auth, AI, or notifications, even though the codebase is organized into strongly-separated internal modules that *could* be extracted later with comparatively little pain, because they already communicate through well-defined service functions rather than reaching into each other's internals.

### 2.2 Directory shape and the reasoning behind the layering

```
backend/
├── app/
│   ├── main.py                # App factory, middleware stack, lifespan (scheduler startup/shutdown)
│   ├── config.py               # pydantic-settings; single source of runtime configuration
│   ├── database.py             # Async engine + session factory
│   ├── core/
│   │   ├── security.py         # Password/PIN hashing, JWT creation/verification, OTP generation
│   │   ├── permissions.py      # Permission enum (~30 values) + ROLE_PERMISSIONS mapping
│   │   ├── middleware.py       # RequestIDMiddleware, TimingMiddleware, SecurityHeadersMiddleware
│   │   └── deps.py              # Shared FastAPI dependencies (CurrentUser, require_farm_access, require_permission)
│   ├── exceptions.py            # Project exception hierarchy + handlers
│   ├── models/                  # SQLAlchemy ORM models, one file per domain (auth, farm, flock, health, finance, ai, platform)
│   ├── schemas/                 # Pydantic request/response schemas, mirroring the models/ layout
│   ├── services/                # Business logic — "fat services, thin endpoints" (Section 2.3)
│   └── api/v1/
│       ├── router.py             # Aggregates every domain router
│       └── endpoints/            # One file per domain; endpoints call services, never touch the DB directly
├── alembic/versions/            # 30 linear migrations — see DATABASE_ARCHITECTURE.md
└── tests/
    ├── unit/                     # Schema/validation-level tests
    └── integration/              # Full request lifecycle + RBAC tests
```

This shape is not incidental — it directly mirrors the domain boundaries described in `AGRIOS_MASTER_CONTEXT.md` (auth/roles/farms, flocks/ops/health/finance, admin, ARIA), so that a new contributor can navigate the codebase using the same mental model they use to understand the product.

### 2.3 The "fat services, thin endpoints" rule

Every endpoint function is intentionally shallow: it authenticates, authorizes, calls exactly one service-layer function, and formats the response. All business logic — validation beyond simple schema shape, database queries, cross-record consistency rules — lives in `app/services/*.py`. The reasoning: endpoints are what changes when an HTTP contract changes (a new query param, a new route path), while services are what changes when *business rules* change, and conflating the two makes both harder to reason about and impossible to unit test in isolation from the HTTP layer. Every service in the codebase is instantiated once as a module-level singleton (e.g. `auth_service = AuthService()` at the bottom of `auth_service.py`) and imported by name elsewhere — this is why an import like `from app.services.sms_service import sms_service` fails when `sms_service.py` only exports module-level functions rather than a class instance: the two service files follow genuinely different internal patterns (a class-based singleton for `AuthService`, and bare async functions for the SMS module), and a contributor must check which pattern a given service file actually uses before assuming the other.

### 2.4 Middleware stack and its order

Registered in `app/main.py`, outermost first: **CORS → SecurityHeadersMiddleware → RequestIDMiddleware → TimingMiddleware**. CORS must be outermost so that even rejected/errored requests still receive correct CORS headers back to the browser. `SecurityHeadersMiddleware` injects `X-Content-Type-Options`, `X-Frame-Options: DENY`, a restrictive `Content-Security-Policy`, `Permissions-Policy` (camera/mic/geolocation/payment/USB all denied), and — production only — `Strict-Transport-Security`. `RequestIDMiddleware` stamps every request/response pair with a UUID for log correlation. `TimingMiddleware` records `X-Process-Time` for performance visibility. None of these were retrofitted casually; the security headers in particular were added in the final "production hardening" sprint specifically because they cost nothing functionally but close off a whole category of drive-by attacks (clickjacking, MIME-sniffing, XSS via CSP).

### 2.5 The Permission system

`app/core/permissions.py` defines a `Permission` enum with roughly 30 fine-grained values (e.g. `FARM_CREATE`, `FLOCK_CLOSE`, `HEALTH_VACCINATION_LOG`, `FINANCE_EXPENSE_LOG`, `AI_QUERY`, `AI_INSIGHT_VIEW`, `ADMIN_USER_MANAGE`, `ADMIN_FARM_MANAGE`) and a `ROLE_PERMISSIONS` dict mapping each of the 8 roles to the set of permissions it holds. Every write endpoint checks both **farm membership** (`require_farm_access({"farm_owner", "farm_manager"})`, or the relevant role set for that action) and a **specific permission** (`require_permission(Permission.X)`) — the two checks are deliberately kept separate because "is this user on this farm" and "is this user's role allowed to do this specific thing" are logically independent questions, and collapsing them into one check has historically been the source of privilege-escalation bugs in systems like this. Read-only endpoints are granted to all 6 farmer-facing roles plus a `_VIEW`-suffixed permission where the distinction between "read" and "write" access to a resource matters (e.g. `HEALTH_VACCINATION_LOG` vs `HEALTH_VACCINATION_VIEW`).

Any new permission must be added to both the enum and the `ROLE_PERMISSIONS` dict in the same change — a permission that exists in the enum but is not assigned to any role is a silent dead end, and a permission checked in an endpoint but absent from the enum will fail to import at all.

### 2.6 Background jobs — the scheduler

`app/services/scheduler.py` runs an `AsyncIOScheduler` (APScheduler) with five cron-triggered jobs, all on the `Africa/Nairobi` timezone, each opening its own `AsyncSessionLocal()` session and wrapped in `try/except` so that a scheduler failure never propagates into the request path:

| Job | Schedule (EAT) | Purpose |
|---|---|---|
| `job_aria_daily_insights` | 06:00 daily | Runs the 8 proactive insight generators across all active farms — see `ARIA_AI.md`. |
| `job_vaccination_reminders` | 08:00 daily | Notifies farms with a vaccination due within 3 days. |
| `job_vaccination_overdue` | 08:05 daily | Notifies farms with a vaccination whose due date has passed. |
| `job_daily_log_reminder` | 20:00 daily | Notifies farms that have not submitted a daily log today. |
| `job_weekly_summary` | Friday 18:00 | Sends the weekly mortality/financial/insight summary. |

The scheduler is started and stopped inside the FastAPI `lifespan` context manager in `app/main.py` — it lives inside the same process as the web server (AD-13, frozen). This is a deliberate simplification: a separate worker process (Celery + Redis) is the correct answer once a job's execution time risks exceeding roughly 60 seconds, or once job volume is high enough to compete with request-handling resources, but until then an embedded scheduler avoids an entire class of operational complexity (a second deployable, a message broker, worker autoscaling) that a solo founder cannot easily operate.

---

## 3. Frontend

### 3.1 Stack

| Layer | Technology | Why |
|---|---|---|
| Framework | React 18.3 | Mature ecosystem, wide hiring pool, strong PWA tooling support. |
| Build tool | Vite 6 | Fast dev server and production build; native `vite-plugin-pwa` integration. |
| Language | TypeScript, strict mode | Type safety across the API boundary — types are hand-mirrored from backend schemas in `src/types/index.ts`. |
| Routing | React Router 6, data router | Enables route-level lazy loading, which matters directly for first-load performance on 3G. |
| Global/auth state | Zustand | Minimal-boilerplate store for auth state (access token, current user) — deliberately not Redux, because the amount of genuinely global state in this app is small. |
| Server state | TanStack Query | Caching, invalidation, and background refetch for all API data — this is the mechanism behind the app "feeling" fast and behind cached data remaining visible offline. |
| Forms | React Hook Form + Zod | Schema-driven validation that can share shape assumptions with the backend Pydantic schemas conceptually, even though the two are not code-shared. |
| Styling | Tailwind CSS | Utility-first, and the exclusive styling mechanism — see `DESIGN_SYSTEM.md`; no CSS-in-JS, no component library beyond what AGRIOS defines itself. |
| Charts | Recharts | SVG-based, mobile-compatible. |
| i18n | i18next / react-i18next | English + Swahili, with runtime language switching (no page reload) — see `DESIGN_SYSTEM.md` Section on Swahili/English parity. |
| PWA | `vite-plugin-pwa` (Workbox under the hood) | Auto-generated service worker, web app manifest, `StaleWhileRevalidate` runtime caching for API calls. |
| Error monitoring | Sentry (`@sentry/react`) | Session replay with `maskAllText`/`blockAllMedia` for PII protection; a branded `ErrorBoundary` fallback that never surfaces a stack trace to a farmer. |

### 3.2 Directory shape

```
frontend/src/
├── main.tsx                # Sentry init → React root → ErrorBoundary wrap
├── routes/index.tsx         # All route definitions, lazy-imported per screen
├── layouts/                 # AppLayout (farmer, bottom-tab), AdminLayout (desktop, side-nav)
├── screens/                 # One directory per domain, mirroring backend domains
├── api/                     # One file per domain; every function unwraps the API envelope
├── types/index.ts           # Hand-mirrored TypeScript types for every backend schema
├── lib/queryClient.ts        # TanStack Query client + the queryKeys object (single source of cache-key truth)
├── hooks/                   # Shared hooks (useNetworkStatus, useActiveFarm, etc.)
├── components/              # Shared UI primitives + PWA components (OfflineBanner, PWAUpdatePrompt)
└── locales/{en,sw}/common.json   # i18n key files — must always have matching key counts
```

### 3.3 Navigation architecture

There are two entirely separate layouts, reflecting two entirely separate user populations (`AGRIOS_MASTER_CONTEXT.md` Section 3): a mobile-first, bottom-5-tab `AppLayout` for farmers (Home, Flock, Health, Finance, ARIA), and a desktop-first, left-sidebar `AdminLayout` for `super_admin`, gated by a `RequireAdmin` route guard that checks `user.role === "super_admin"`. These are not themeable variants of one layout — they are architecturally distinct because the devices, contexts, and information density of the two audiences are distinct (`DESIGN_SYSTEM.md` Section 6 covers the visual reasoning in full).

### 3.4 Query key discipline

Every TanStack Query cache key is defined once, centrally, in the `queryKeys` object inside `lib/queryClient.ts`, following the pattern `["farms", farmId, "domain", "resource"]`. After any write mutation, the convention is to invalidate both the directly affected resource and its parent aggregates — for example, logging an expense invalidates `expenses`, `financeDashboard`, and `flockSnapshot` together, because the financial snapshot pattern (`DATABASE_ARCHITECTURE.md`) means a single write can make several cached views stale at once. A new mutation that only invalidates its own narrow resource and forgets the aggregate is a common and easy-to-miss bug class in this codebase.

---

## 4. The API Layer

All backend routes are versioned under `/api/v1/`. Every response — success or failure — is wrapped in a consistent envelope (`SuccessResponse[T]` on the backend), so the frontend API layer can unwrap responses identically regardless of domain. Farm-scoped resources consistently follow the path shape `/farms/{farm_id}/...`, and nested operational resources follow `/farms/{farm_id}/flocks/{flock_id}/...` — this nesting is not just a URL style choice, it mirrors the farm-scoping rule (DB-04) at the routing layer, making it visually obvious in the route table which endpoints require farm-membership checks.

The full endpoint inventory (Authentication, Farm, Flock, Health, Finance, ARIA AI, Platform/Notifications/Market, Admin, System) is large — approximately 40+ endpoints across all domains — and is not repeated in full here to avoid this document going stale independently of the code; the authoritative list is `backend/app/api/v1/router.py` plus each `endpoints/*.py` file's route decorators. The one universally important endpoint is `GET /health`, which returns `{"status": "ok", "version": ..., "environment": ..., "db": "connected"}` and is the single signal Railway uses to decide whether a deployment is healthy (`DEPLOYMENT_GUIDE.md`).

---

## 5. Authentication and Session Architecture

The full philosophy and its reasoning are covered in `AGRIOS_MASTER_CONTEXT.md` Section 6.1 — **read that section first**, since it establishes that AGRIOS authenticates through verified communication channels rather than any single assumed technology, and that this is now a permanent architectural principle, not a description of whatever happens to be wired up today. This section is the implementation map for that principle.

### 5.1 Channel-agnostic OTP flow

**Flow:** `POST /auth/request-otp` (accepting either a phone number or an email address as the identifier) → an OTP is delivered via whichever channel corresponds to the identifier supplied → `POST /auth/verify-otp` (creates the user record on first verification, assigns default `farm_owner` role with `farm_id = NULL` until a farm exists, issues both tokens) → `POST /auth/set-pin` (first-time only) → subsequent logins use `POST /auth/verify-pin`. `POST /auth/refresh` rotates the refresh token on every use and revokes the prior session row in the `sessions` table; `POST /auth/logout` revokes the current session. None of this token/session mechanics changes based on which channel delivered the OTP — access tokens are JWTs signed with `JWT_SECRET`, created via `create_access_token(subject=str(user.id))`, and are never persisted server-side; only refresh tokens are, as hashed values in `sessions.refresh_token_hash`. The OTP request/verify contract is deliberately identifier-shaped, not phone-shaped or email-shaped — the endpoint's job is to recognize which kind of identifier it was given and route delivery accordingly, not to expose two structurally different registration flows.

### 5.2 Delivery routing — why this is a configuration concern, not a code-branching concern

`AuthService` (a class-based singleton, `app/services/auth_service.py`) owns every one of these flows and is responsible for routing an OTP to the correct delivery mechanism based on the identifier's shape (an email address vs. a phone number), delegating the actual send to whichever channel-specific service is available. SMS delivery calls the module-level `send_sms()` function — there is no class named `SMSService` anywhere in the codebase; `app/services/sms_service.py` exports bare async functions (`send_sms`, `send_bulk_sms`, and template-specific helpers like `sms_farm_invite`, `sms_vaccination_reminder`). Any code that imports a nonexistent `sms_service` object or a nonexistent `SMSService` class is not calling into an alternate SMS architecture — it is simply using the wrong import for the one SMS module that exists. Email OTP delivery is the V1 launch default and follows the same "bare async function, not a heavyweight class" pattern established by the SMS module, using whichever transactional email provider is configured via environment variables (`DEPLOYMENT_GUIDE.md` Section 6.1) — the specific provider is an infrastructure choice, not an architectural one, and should be swappable without touching `AuthService`'s calling code.

**The frozen rule this produces:** whether SMS OTP is "on" for a given deployment is determined entirely by whether Africa's Talking credentials are present in the environment (`DEPLOYMENT_GUIDE.md` Section 6.1) — never by a code branch, a feature flag requiring a deploy, or a schema difference. If Africa's Talking credentials are absent, phone-based registration should either queue/fail gracefully with a clear message rather than silently pretend to have sent an SMS, or the phone-registration entry point should be hidden until the channel is actually configured — but in either case, the fix for "SMS isn't working yet" is always an environment variable change, never a code change to `AuthService`, the `users` table, or the OTP request/verify endpoints themselves.

### 5.3 Identity model — one account, multiple verified channels

A `User` row conceptually owns zero or more verified channels (at minimum, in V1, a verified email and/or a verified phone number) rather than being defined by exactly one fixed identity field. Registering via email and registering via phone both produce the same kind of account; the only difference is which field was populated and verified first. Adding a second verified channel to an already-existing account — for example, a farmer who registered by email later verifying their phone number, or vice versa — must attach to the *existing* user record, never create a second one. This is the direct implementation of the identity rule in `AGRIOS_MASTER_CONTEXT.md` Section 6.1, and it is the reason any future lookup-by-identifier logic (finding a user by phone or by email during OTP request) must check both fields before deciding whether to create a new account, not just the field shape matching the current request.

### 5.4 Future channels are additive, not architectural forks

Authenticator apps, passkeys, and third-party identity providers (Google, Apple, Microsoft) are anticipated as additional verified-channel types hanging off the same single-identity model described above (`AGRIOS_MASTER_CONTEXT.md` Section 6.1) — each is expected to be implemented as one more way to prove control of, or link to, an existing AGRIOS identity, not as a competing registration system. Two-factor authentication, once built, is expected to reuse the same "verified channels" concept: a user configures a preferred and backup channel from among whichever they have already verified, rather than 2FA being a bolted-on, separately-modeled feature.

---

## 6. Notifications, SMS, and Email

AGRIOS now has two outbound communication channels for both authentication and notifications: **SMS** (Africa's Talking) and **Email**, alongside the always-available **in-app** channel (the `notifications` table, soft-deletable, surfaced in the Notifications screen). This is a deliberate change from an earlier design that assumed SMS as the only outbound channel — email is not a bolted-on addition, it is a first-class delivery mechanism on equal footing with SMS, reflecting the same channel-agnostic philosophy that governs authentication (Section 5; `AGRIOS_MASTER_CONTEXT.md` Section 6.1). A user's contact preference (email, SMS, or both) is intended to be a single profile-level setting that governs delivery for every outbound message type — login OTPs, the eight notification types below, and any future billing or security messages — rather than each message type independently deciding which channel to use.

The eight notification types (`vaccination_reminder`, `vaccination_overdue`, `daily_log_reminder`, `disease_alert`, `weekly_summary`, `aria_insight`, `system`, `farm_invite`) each have a fixed template per channel documented in the frozen blueprint; `aria_insight` and `system` are in-app only by design, since ARIA insights are meant to be discovered inside the product experience rather than pushed, and system messages are administrative, not urgent. `notification_service.py` provides create/bulk-create/list/mark-read/mark-all-read/delete/unread-count; `audit_service.py` provides `log_action()` (flushes within the caller's existing transaction) and `log_action_safe()` (a fire-and-forget variant for non-critical logging paths where a logging failure must never block the primary operation). Per-user delivery preference is gated by the same master-toggle mechanism the project already uses for SMS (`user.metadata_["sms_notifications_enabled"]`), generalized to represent a channel preference rather than a single on/off SMS switch — this is the same `metadata_` JSONB extensibility column described in `DATABASE_ARCHITECTURE.md` Section 1, which is exactly the kind of forward-compatible field it was designed to absorb without a migration.

---

## 7. AI (ARIA) — Summary Only

ARIA's full architecture — the Farm Context Package compiler, prompt structure, provider fallback mechanics, insight generation, and every safety boundary — is documented completely in `ARIA_AI.md` and is deliberately not duplicated here. The one fact worth stating at the system-architecture level: ARIA never has direct database access. Every AI call is preceded by a server-side context-compilation step that assembles a bounded JSON package from the farm's real data, and the AI provider (Gemini primary, Claude fallback) only ever sees that compiled package — never a live query path into Postgres. This is both a security boundary and the mechanism that makes ARIA's "never invents data" guarantee possible at all: the model has no way to reach for data outside what was deliberately handed to it.

---

## 8. Deployment and Cloud Infrastructure — Summary Only

Full operational detail lives in `DEPLOYMENT_GUIDE.md`. In architectural terms: Railway hosts the backend as a Dockerfile-based deploy (`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`), Vercel hosts the frontend as a static SPA build with rewrite rules for client-side routing, and Supabase provides managed PostgreSQL with automatic backups. GitHub Actions is the intended CI/CD layer (tests + type checks on every PR before merge to `main`), though its workflow files currently live at `infrastructure/github/workflows/` rather than the `.github/workflows/` path GitHub actually reads — this is tracked as a known defect in `KNOWN_TECHNICAL_DEBT.md` rather than fixed silently here, because a documentation set should describe the system as it actually is, not as it is intended to be.

---

## 9. Module Interaction and Data Flow — the Mental Model

The way to reason about any request in AGRIOS is a straight line: **Frontend screen → API client function (unwraps envelope) → FastAPI endpoint (auth + permission check) → service function (business logic + DB queries) → response schema → envelope → TanStack Query cache → screen re-render.** Every layer in that chain has exactly one job, and the "fat services, thin endpoints" rule (Section 2.3) exists specifically so that business logic can be reasoned about, tested, and modified without touching the HTTP contract layer above it or the ORM layer below it.

Cross-pillar data flow follows the dependency chain in Section 1: Auth produces a `User`; Farm Infrastructure scopes that user to a `Farm`; Flock Management produces `Flock` records that Daily Operations, Health, and Finance all attach to via `flock_id`; the Financial Engine's snapshot pattern turns raw expense/revenue rows into a fast-reading aggregate; and ARIA's context compiler reads across Flock, Health, and Finance data to assemble the package it hands to the AI provider. Understanding this chain is the fastest way to answer "what else might this change affect" — the answer is almost always "whatever sits downstream of it in this chain."
