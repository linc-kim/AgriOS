# Sprint 9 Completion Report — PWA + Offline-Aware + Settings

**Sprint:** 9 of 10  
**Tier:** Offline Sync Layer  
**Theme:** PWA installability · Offline-aware UI · User settings  
**Status:** ✅ COMPLETE  
**Date:** 2026-06-26  
**Frozen Constraint Reference:** AGRIOS_V1_MASTER_BLUEPRINT_FROZEN.md

---

## Sprint Objective

Deliver the V1-scoped offline layer and settings module:

- **PWA** (AD-09): Already configured in `vite.config.ts` with `vite-plugin-pwa`, web app manifest, and Workbox caching strategy. Sprint 9 adds the runtime UI components that make offline state visible and actionable.
- **Offline-aware UI**: Connection detection hook, offline banner, offline screen, PWA update prompt.
- **Settings screens S-01 to S-04**: Profile, notifications, language, about — completing the blueprint's "Settings" screen group.
- **Utility screens**: OfflineScreen, NotFoundScreen, ErrorScreen — completing the blueprint's "Shared/Utility" screen group.
- **No new migrations** — DB-10 frozen at 30. User preferences stored in `user.metadata_` JSONB.

**Scope boundary:** "Full offline-first operation (local SQLite queue + background sync)" is explicitly deferred to Phase 3 (blueprint line 122). V1 scope = cached data visible offline + service worker for static assets — both now complete.

---

## Quality Gates

| Gate | Status | Notes |
|------|--------|-------|
| QG-1: Schema syntax | ✅ PASSED | `schemas/auth.py`, `endpoints/auth.py` both `py_compile` clean |
| QG-2: i18n JSON validity | ✅ PASSED | EN + SW both parse; 57 EN = 57 SW sprint keys |
| QG-3: File completeness | ✅ PASSED | All screens, hooks, components, routes present |
| QG-4: Test coverage | ✅ PASSED | 27 unit + 16 integration = 43 total tests |
| QG-5: RBAC matrix | ✅ PASSED | Unauthenticated GET/PATCH rejected; farmer token accepts all settings ops |
| QG-6: Frozen constraint audit | ✅ PASSED | No new migrations; sms pref in metadata_ JSONB; DB-10 intact |

---

## Deliverables

### Backend

**Extended schema** — `backend/app/schemas/auth.py`:
- `UserUpdateIn` — added `sms_notifications_enabled: bool | None` field
- `UserUpdateIn` — added `full_name` blank-string validator (strips whitespace, rejects empty)
- `UserOut` — added `sms_notifications_enabled: bool = True` (derived from `user.metadata_["sms_notifications_enabled"]`)

**Extended endpoint** — `backend/app/api/v1/endpoints/auth.py`:
- `PATCH /auth/me` — writes `sms_notifications_enabled` to `user.metadata_` dict (no migration needed — `metadata_` JSONB exists from Sprint 0)

No new router registration. No new permissions. No new migrations.

---

### Frontend

**New hook** — `frontend/src/hooks/useNetworkStatus.ts`:
- `useNetworkStatus()` — reactive `{ isOnline }` from `navigator.onLine` + window events

**New PWA components** — `frontend/src/components/pwa/`:
- `OfflineBanner.tsx` — fixed top banner when offline (uses `useNetworkStatus`)
- `PWAUpdatePrompt.tsx` — bottom sheet when service worker update is waiting; posts `SKIP_WAITING` + reloads

**AppLayout updated** — `frontend/src/layouts/AppLayout.tsx`:
- `<PWAUpdatePrompt />` injected before bottom nav tab bar

**New utility screens** — `frontend/src/screens/utility/`:

| Screen | File | Description |
|--------|------|-------------|
| Offline | `OfflineScreen.tsx` | No-connection state; live status indicator; retry/go-home |
| 404 | `NotFoundScreen.tsx` | Unmatched routes (replaces `Navigate to="/"`) |
| Error | `ErrorScreen.tsx` | Generic error boundary fallback with optional message + retry |

**New settings screens** — `frontend/src/screens/settings/`:

| Screen | Code | File | Description |
|--------|------|------|-------------|
| Settings Hub | S-00 | `SettingsScreen.tsx` | User card + 4 nav links + logout |
| Profile | S-01 | `ProfileSettingsScreen.tsx` | Update display name; phone read-only |
| Notifications | S-02 | `NotificationSettingsScreen.tsx` | SMS master toggle; per-type toggles (informational) |
| Language | S-03 | `LanguageSettingsScreen.tsx` | EN/SW toggle; persists to server + `i18n.changeLanguage` |
| About | S-04 | `AboutScreen.tsx` | Version, region, support, legal |

**Types updated** — `frontend/src/types/index.ts`:
- `User` interface: added `sms_notifications_enabled: boolean`
- `UserUpdateInput` interface added

**API updated** — `frontend/src/api/auth.ts`:
- `UserUpdatePayload`: added `sms_notifications_enabled?: boolean`

**Query keys** — `frontend/src/lib/queryClient.ts`:
- `settingsProfile()` → `["auth", "me"]`

**Routes** — `frontend/src/routes/index.tsx`:
- `/settings` — `SettingsScreen` (replaces `ComingSoonScreen`)
- `/settings/profile` — `ProfileSettingsScreen`
- `/settings/notifications` — `NotificationSettingsScreen`
- `/settings/language` — `LanguageSettingsScreen`
- `/settings/about` — `AboutScreen`
- `/offline` — `OfflineScreen`
- `*` catch-all — `NotFoundScreen` (replaces `Navigate to="/"`)

**i18n** — 57 EN = 57 SW sprint-9 keys across namespaces: `offline`, `pwa`, `error`, `settings.hub`, `settings.profile`, `settings.notifications`, `settings.language`, `settings.about`.

---

### PWA Configuration (pre-existing, confirmed complete)

`frontend/vite.config.ts` — `VitePWA` plugin configured since Sprint 0 with:
- Web app manifest (name, icons, theme_color `#16a34a`, display `standalone`, start_url `/`)
- Workbox `globPatterns` — caches all `*.{js,css,html,ico,png,svg,woff2}`
- Runtime caching — `StaleWhileRevalidate` for `api.agrios.app/api/v1/*` (1-hour TTL)
- 6 icon sizes: 48, 72, 96, 144, 192, 512px (maskable)

Sprint 9 completes the runtime half: connection detection, update notification, offline screen, and the settings system that lets users adjust language (which affects the app's i18next locale in real time).

---

### Tests

**Unit Tests** — `tests/unit/api/v1/test_settings.py` (27 tests):
- `TestUserUpdateInFullName` (6): valid, strip, null, blank rejected, omitted, long
- `TestUserUpdateInLanguage` (6): en, sw, invalid, uppercase rejected, null, omitted
- `TestUserUpdateInSMSPref` (4): true, false, null, omitted
- `TestUserUpdateInCombined` (6): all fields, empty, language-only, sms-only, no-sms, strip+validate
- `TestUserUpdateInEdgeCases` (5): single char, Swahili name, full string rejected, number rejected, bool coercion

**Integration Tests** — `tests/integration/test_settings_flow.py` (16 tests):
- GET /auth/me: authenticated shape, unauthenticated blocked (2)
- Name update: valid, strip, blank rejected, null clear (4)
- Language update: to sw, to en, invalid rejected (3)
- SMS pref: disable, enable, persists across GET (3)
- Combined: all fields, empty body, unauthenticated, default-true check (4)

**Total Sprint 9 Tests: 43**

---

## Architecture Notes

### metadata_ JSONB for preferences
User preferences (`sms_notifications_enabled`) are stored in `user.metadata_` (JSONB, Sprint 0). No new column, no migration. `UserOut.model_validate` derives `sms_notifications_enabled` from `metadata_.get("sms_notifications_enabled", True)` — defaults to `True` for existing users without the key.

### Phase 3 boundary respected
Full offline-first (local write queue, background sync to server when reconnected) is deferred to Phase 3 as specified in the blueprint. V1 offline capability = cached reads visible during disconnection, which Workbox's `StaleWhileRevalidate` strategy provides automatically.

### NotFoundScreen replaces Navigate
The catch-all route now renders `NotFoundScreen` instead of silently redirecting to `/`. This is a UX improvement — users who follow broken links see a clear 404 rather than being dumped on the dashboard.

---

## Carryover Status

No new KIs introduced in Sprint 9.

---

## Gate Summary

| Gate | Result |
|------|--------|
| 1 — Schema syntax | PASS |
| 2 — i18n JSON validity | PASS |
| 3 — File completeness | PASS |
| 4 — Test coverage (43 tests: 27 unit + 16 integration) | PASS |
| 5 — RBAC matrix | PASS |
| 6 — Frozen constraint audit | PASS |

---

**Next:** Sprint 10 — Production Hardening + Launch
