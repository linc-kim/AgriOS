# Greena — Session Handoff (2026-07-10)

Continuation handoff for **Phase 2 — Production Authentication & Onboarding + Application Shell**.
Read this top-to-bottom before writing code.

---

## 0. Session Close Update (2026-07-10, evening)

Phase 2 milestone completed this session. Everything below §1 describes the
mid-session state; this section supersedes it where they differ.

**Done & committed (branch `phase-2-auth`):**
- **Full end-to-end browser journey verified** against live backend + vite:
  signup → onboarding (organization + farm) → dashboard → refresh persistence
  (session restored via refresh cookie) → logout → login → dashboard. Dark mode,
  command palette (⌘K + Esc), and org/farm switcher all exercised.
- **Application shell committed** (`72c0410`) — the registry-driven shell,
  dashboard, primitives, and status screens.
- **Bug fixes found during verification:**
  - Farm `location` was saved but not shown on the dashboard (summary API
    omitted it). Added `location` to `FarmSummaryResponse` + frontend type +
    dashboard (`f6a75cf`).
  - Command palette showed an "Esc" hint but had no Escape handler — added one.
- **AGRIOS → Greena text sweep committed** (`c1746fd`) — 176 product-name
  replacements across 106 files (backend/app, frontend/src, i18n, PWA manifest).
  Deliberately **preserved** as identifiers/infra (NOT branding): base classes
  `AGRIOSException`/`AGRIOSBase`/`AGRIOSSchema`; cookie `agrios_refresh_token`;
  DB names `agrios`/`agrios_test`; domains/emails (`agrios.app`, `api.agrios.app`,
  `support@agrios.app`); cache/release keys (`agrios-api-cache`,
  `agrios-frontend@1.0.0`). Rename of the base classes is a structural refactor
  left out of scope.
- **Production build passes** — `npm run build` green (0 errors), PWA service
  worker generated, `dist/` fully Greena-branded (title "Greena", manifest
  "Greena — Farm Operating System").
- Backend imports clean and serves as **"Greena API"**; frontend `tsc --noEmit`
  clean.

**Known issue (pre-existing, NOT a Phase 2 regression — flagged as a separate task):**
- Backend pytest: **227 passed, 30 failed, 123 errors**. All errors are a
  missing `auth_headers` fixture in `backend/tests/conftest.py`; the failures are
  schema/test drift (e.g. `ExpenseCreate` now requires `description`). `conftest.py`
  was untouched this session. Needs a dedicated test-suite repair pass.

**Env note:** local Postgres stops between sessions and must be started first
(`scripts/dev/pg.ps1 start`); a 500 on signup/refresh this session was traced to
Postgres being down, not app code. `frontend/vite.config.ts` now honours
`PORT` env; `.claude/launch.json` uses `autoPort`.

---

## 1. TL;DR / Current State

- **Product** renamed **AGRIOS → Greena** (wordmark only; emblem unchanged). Backend `PROJECT_NAME = "Greena"`.
- **Backend Phase 2 is complete & verified**: email signup/login (dev-auth mode, Argon2id, sessions, audit), organizations + farm↔org link. Migrations `032–036` applied and reversible on local Postgres.
- **Brand pipeline is complete**: `brand/Greena.ai` → `brand/build_assets.py` regenerates master SVG + variants + favicon/manifest/OG suite; `brand/build_story_splash.py` → Greena splash.
- **Frontend Phase 2 in progress**:
  - ✅ Committed: Greena **auth** (Login + SignUp) and **onboarding** wizard.
  - ⚠️ **Uncommitted (this session's work): the entire application shell** (sidebar, topbar, command palette, org/farm switcher, dashboard, module screens, status screens, theme, primitives). It **typechecks clean** and the dev server compiles it, but it is **NOT committed** and the end-to-end browser journey was only **partially verified** (signup → onboarding reached; org/farm/dashboard not yet confirmed).

**Current branch:** `phase-2-auth` (branched from `main`).

---

## 2. Overall Architecture

**Monorepo:** `backend/` (FastAPI + async SQLAlchemy + Alembic + PostgreSQL), `frontend/` (React 18 + Vite + Tailwind + React Router v6 + TanStack Query + Zustand), `brand/` (logo pipeline).

**Identity-first / workspace-first** (see memory `auth-architecture-principles`):
`Identity (user) → Organization (workspace, owns farms + team) → Farm → (future modules)`.

**Auth mechanics:** JWT HS256 access token (in-memory on client) + rotating opaque refresh token (httpOnly cookie `agrios_refresh_token`, path `/api/v1/auth`, SameSite=strict). Refresh uses SHA-256 `token_lookup` for O(1) lookup; legacy OTP/PIN sessions fall back to a bcrypt scan.

**Development-auth mode (current):** the full permanent auth system ships with external verification **gated off** by config flags, so a user can sign up → log in → onboard with **no SMTP/SMS/OTP/Google**. Flags in `backend/app/config.py`: `REQUIRE_EMAIL_VERIFICATION`, `ENABLE_GOOGLE_OAUTH`, `ENABLE_SMS_OTP`, `ENABLE_LOGIN_ALERTS` (all default `False`). Enabling production auth later = flip flags, not rewrite. Email provider = **Zoho** (abstraction planned, dormant).

**Frontend shell = registry-driven:** `frontend/src/shell/registry.tsx` is the single source of truth; the sidebar, routes, breadcrumbs, and command palette all derive from it. New modules register there — no shell redesign needed.

---

## 3. Features Completed

### Backend (complete & verified)
- Email **signup** (Argon2id hash, dev-mode marks email verified, issues session; **no** role/farm assignment — that's onboarding).
- Email **login** (enumeration-safe: constant-time dummy hash; generic 401), **logout**, **logout-all** (O(1)).
- **Session** issuance with device label + remember-me TTL + SHA-256 token_lookup.
- **Organization** create/list/get; creator becomes `enterprise_owner`; unique slug; free plan; audit-logged.
- **Farm** creation extended with `organization_id` + org-membership enforcement (403 for non-members).
- Fixed real 500 bug: `validation_exception_handler` serialized raw `ValueError` from field validators.

### Frontend (committed)
- **Auth**: Login + SignUp (email/password) — validation (zod), password toggle, remember-me, error/loading states, backend-code mapping, cross-links. `AuthLayout` (split brand panel). `Logo` component (approved assets only).
- **Onboarding wizard**: Welcome → Organization (name/country/currency/timezone) → Farm (name/type/location) → Finish. Progress bar, back nav, autosave (localStorage), transitions. On finish: create org → create farm → dashboard.

### Frontend (UNCOMMITTED — this session)
- **App shell**: `AppShell` layout (fixed sidebar + mobile drawer), `Sidebar` (registry nav + org/farm switcher + Greena logo), `Topbar` (breadcrumbs, ⌘K search trigger, notification center, theme toggle, profile menu with logout).
- **Command palette** (⌘K / Ctrl-K): navigate modules + actions (theme, logout), keyboard nav.
- **Org/Farm switcher**, **theme toggle** (light/dark/system, class-based), **loading skeletons**, **empty states**, **status screens** (Unauthorized, Session-expired).
- **Dashboard** (rewritten): greeting + org/farm stat cards + quick actions + recent-activity empty state, skeleton loading.
- **Module screen**: generic calm empty state for registered-but-unbuilt modules.

---

## 4. Files Modified / Added

### Backend (committed)
- `app/config.py` — Greena name, dev-auth flags, password/email/Google/Zoho settings.
- `app/core/security.py` — Argon2id `hash_password`/`verify_password`, `validate_password_strength`, `generate_url_token`, `sha256_hex`.
- `app/models/auth.py` — User (password_hash, email_verified(_at), password_changed_at; phone nullable); Session (token_lookup, device_name, remember_me, last_used_at); new `IdentityProvider`, `EmailToken`.
- `app/models/organization.py` (new) — `Organization`, `OrganizationMember`.
- `app/models/farm.py` — `organization_id` + relationship.
- `app/models/__init__.py` — registrations.
- `app/schemas/auth.py` — `EmailSignupIn`/`EmailLoginIn`; `UserOut` phone-optional + `email_verified`/`has_password`.
- `app/schemas/organization.py` (new); `app/schemas/farm.py` — `organization_id`.
- `app/services/auth_service.py` — `signup_email`, `login_email`, `_create_session`, `logout`/`logout_all`.
- `app/services/organization_service.py` (new).
- `app/services/farm_service.py` — org-membership check + set org_id.
- `app/api/v1/endpoints/auth.py` — `/signup`, `/login`, `/logout-all`.
- `app/api/v1/endpoints/organizations.py` (new); `app/api/v1/router.py` — register.
- `app/exceptions.py` — `EmailNotVerifiedException` + validation-handler fix.
- `requirements.txt` — `argon2-cffi==23.1.0`.

### Frontend (committed)
- `index.html` (Greena branding/favicons/OG), `src/types/index.ts` (User/Org/FarmCreate), `src/api/auth.ts` (+signup/login/logoutAll), `src/api/organizations.ts` (new), `src/lib/cn.ts`, `src/lib/completeAuth.ts`, `src/components/ui/{Logo,Button,TextField,Select}.tsx`, `src/layouts/AuthLayout.tsx`, `src/screens/auth/{EmailLoginScreen,SignUpScreen}.tsx`, `src/screens/onboarding/OnboardingScreen.tsx`, `src/index.css` (keyframes + reduced-motion), `src/assets/brand/*.svg`.

### Frontend (UNCOMMITTED — commit these next)
- Modified: `src/routes/index.tsx` (rewritten: AppShell + registry routes, legacy AGRIOS routes dropped), `src/screens/DashboardScreen.tsx` (rewritten), `tailwind.config.ts` (`darkMode: "class"`).
- New: `src/stores/shellStore.ts`, `src/hooks/useClickOutside.ts`, `src/lib/logout.ts`, `src/layouts/AppShell.tsx`, `src/shell/{registry.tsx,useWorkspace.ts,Sidebar.tsx,Topbar.tsx,OrgFarmSwitcher.tsx,CommandPalette.tsx}`, `src/components/ui/{Skeleton,Avatar,EmptyState,StatusScreen}.tsx`, `src/screens/modules/ModuleScreen.tsx`, `src/screens/utility/{UnauthorizedScreen,SessionExpiredScreen}.tsx`.

> Note: legacy AGRIOS screens under `src/screens/{admin,farms,flocks,health,finance,aria,market,notifications,settings}/` still exist but are **no longer routed** (kept for later module re-integration). They may carry stale types (e.g. `user.phone` now nullable) — harmless because `vite build` does not typecheck and they aren't imported.

---

## 5. Database Migrations Completed (Alembic head = `036`)

All additive / non-destructive / **reversible** (round-trip verified on local Postgres):
- `032_auth_users_email_password` — users: password_hash, email_verified(_at), password_changed_at; phone → nullable.
- `033_create_identity_providers` — generic federated identity (Google now; Apple/MS/GitHub later add rows, not schema).
- `034_create_email_tokens` — single-use verify/reset/change-email tokens (SHA-256 lookup).
- `035_sessions_phase2_columns` — token_lookup, device_name, remember_me, last_used_at.
- `036_create_organizations` — organizations + organization_members; farms.organization_id (nullable FK). Reuses `member_status` enum.

Dev DB (`agrios`) is seeded: 8 roles (incl. `enterprise_owner`, `farm_owner`) + 3 subscription plans (incl. `free`).

---

## 6. API Endpoints Completed (Phase 2, under `/api/v1`)

- `POST /auth/signup` — email + password → 201, session cookie, `is_new_user`.
- `POST /auth/login` — 200 + cookie (enumeration-safe).
- `POST /auth/logout`, `POST /auth/logout-all`, `POST /auth/refresh`, `GET /auth/me`, `PATCH /auth/me`.
- `POST /organizations`, `GET /organizations`, `GET /organizations/{id}`.
- `POST /farms` (existing) now accepts `organization_id` + enforces membership.
- Legacy OTP/PIN endpoints remain (dormant).

Verified end-to-end earlier this session: signup→/me→login, dup 409, bad/no-account 401, weak-pw 422, org create/list/get, farm↔org link + non-member 403.

---

## 7. Frontend Pages Completed

Routed (in `src/routes/index.tsx`):
- **Auth** (`AuthLayout`): `/login`, `/signup`, `/phone-login`, `/verify-otp`, `/set-pin`, `/pin-login`.
- `/session-expired` (public status).
- **Onboarding** (protected): `/onboarding`.
- **App shell** (protected, `AppShell`): `/` (Dashboard), plus one route per registry module (`/livestock`, `/crops`, `/inventory`, `/finance`, `/analytics`, `/reports`, `/ai`, `/marketplace`, `/settings`, `/billing`, `/admin`) → `ModuleScreen` empty state; `/unauthorized`, `/offline`.
- Catch-all → `NotFoundScreen`.

---

## 8. Pending Bugs / Known Issues

1. **Shell increment is uncommitted** — commit it first (see §11).
2. **End-to-end journey only partially verified.** Confirmed: signup → `/onboarding`. NOT yet confirmed in-browser: onboarding org+farm creation, dashboard render with real data, refresh persistence, logout→login.
3. **Browser automation gotchas** (verification only, not app bugs):
   - `preview_click` on the SignUp submit did **not** fire the form; `document.querySelector('form').requestSubmit()` worked. Use `requestSubmit()`.
   - `preview_fill` sets `.value` but may **not** trigger React controlled-input `onChange` (onboarding uses controlled inputs). To set a controlled input reliably, use the native setter + dispatch an `input` event, e.g.:
     ```js
     const set = (el, v) => { const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; d.call(el, v); el.dispatchEvent(new Event('input',{bubbles:true})); };
     ```
   - `preview_screenshot` has been timing out all session — use `preview_snapshot` (accessibility tree) instead.
4. **Legacy `AGRIOS`/`agrios` strings** remain in ~130 files (docstring headers, legacy UI copy, cookie name `agrios_refresh_token`). Branding assets are fully Greena; this is a separate surgical text sweep.
5. **Onboarding "Farm type"** is persisted into the farm `description` (backend has no farm_type field) — acceptable, revisit if a real field is wanted.

---

## 9. Environment / How to Run

- **Postgres**: native cluster at `%LOCALAPPDATA%\AGRIOS\pgsql`, data `%LOCALAPPDATA%\AGRIOS\pgdata`, port **5432**, superuser `postgres/postgres`, DBs `agrios` (dev) + `agrios_test`. **It stops between sessions** — start with `scripts/dev/pg.ps1 start` (or `pg_ctl -D <pgdata> start`).
- **Backend**: `backend/.venv` (Python **3.12**). Run: `backend/.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Health: `GET http://127.0.0.1:8000/health` → `{"status":"ok","db":"connected"}`. `.env` DATABASE_URL uses the `postgres` superuser (NOT `agrios` — conftest derives the test DB by name-swap and an `agrios` username collides).
- **Frontend**: `frontend/` → `npm run dev` (Vite :5173). Proxy `/api → http://localhost:8000`. Preview launch config: `.claude/launch.json` name `greena-web`.
- **Brand pipeline**: `backend/.venv/Scripts/python brand/build_assets.py` (needs Inkscape at `C:\Program Files\Inkscape` + Pillow).
- **Verify** (per-phase gate): `scripts/dev/verify.ps1`.

---

## 10. Last Successful Build / Verification

- **Backend**: uvicorn up, `GET /health` = 200, DB connected. Migrations at `036`. Alembic up/down round-trip clean.
- **Frontend**: `npx tsc --noEmit` — **0 errors** in all new/shell files. Vite dev server compiles the full shell (all module chunks return 200). Login + SignUp screens render (verified via accessibility snapshot). Signup POST succeeds and routes to `/onboarding`.
- **Not yet built for production**: `npm run build` (production bundle) has not been re-run after the shell increment — run it as part of final verification.

---

## 11. Remaining Work (Phase 2)

1. **Commit the uncommitted shell increment** (see §4 list) — message e.g. `Phase 2 frontend: registry-driven application shell + dashboard`.
2. **Finish the end-to-end browser verification** (live backend + vite):
   signup → onboarding (create org + farm) → dashboard shows org/farm → refresh persists (session restore via refresh cookie) → logout → login again → still works. **Fix every issue found.**
3. Run `npm run build` and confirm the production bundle succeeds.
4. Polish/verify shell UX states: sidebar active states, dark mode across surfaces, command palette (⌘K), org/farm switching updates the dashboard, mobile drawer, focus/keyboard/a11y.
5. (Deferred, not blocking Phase 2 completion) surgical `AGRIOS→Greena` text/comment/cookie sweep; wire real Settings; Google OAuth + email (Zoho) when verification is switched on.

---

## 12. EXACT NEXT TASK

**Start the environment, then verify the shell renders, then commit it.**

1. Start Postgres: `scripts/dev/pg.ps1 start` → confirm `pg_isready -p 5432`.
2. Start backend: `backend/.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` → confirm `GET /health` 200.
3. Start frontend preview `greena-web` (:5173).
4. Complete onboarding for the test account already created this session (`ada.e2e@greenafarm.co`, password `a-strong-greena-passphrase`) — it is currently sitting at **`/onboarding` step 1 (Organization)**. Drive the controlled inputs via the native-setter+`input`-event helper in §8, click **Continue**, fill the Farm step, click **Finish setup**, and confirm it lands on `/` (dashboard) with the org/farm shown.
5. Verify refresh-persistence, then logout → login.
6. **Commit** the shell increment. Then continue Phase 2 §11 items.

Do not declare "Phase 2 Complete" until the full journey (signup → login → org → farm → dashboard → refresh → logout → login) passes in the browser and `npm run build` succeeds.
