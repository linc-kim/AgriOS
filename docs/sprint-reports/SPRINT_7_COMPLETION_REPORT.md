## Sprint 7 Handover Report

**Sprint:** 7 — Platform Layer (Notifications, Market Prices, APScheduler)
**Tier:** 7
**Date closed:** 2026-06-26
**Status:** COMPLETE

---

### Migrations delivered

| Revision | Table | Notes |
|----------|-------|-------|
| 028 | `notifications` | AGRIOSBase (soft-delete). Farm + user scoped. Indexed on user_id, is_read composite. |
| 029 | `audit_logs` | Base only — append-only (DB-08). No updated_at, no soft-delete. Nullable farm_id / user_id for system events. |
| 030 | `market_prices` | Base only — historical record (DB-09). No farm_id (DB-04 exception). Decimal price_kes (14,2). |

All three migrations include working `downgrade()` functions. Migration chain: 027 → 028 → 029 → 030.

---

### Backend delivered

**Models:** `Notification` (AGRIOSBase), `AuditLog` (Base, immutable), `MarketPrice` (Base, immutable) — all registered in `backend/app/models/__init__.py` under `# Platform Layer (Migrations 028-030)`.

**Schemas:** `app/schemas/platform.py`
- `NotificationCreate`, `NotificationResponse`, `NotificationListResponse`, `NotificationMarkRead`
- `AuditLogCreate`, `AuditLogResponse`, `AuditLogListResponse`
- `MarketPriceCreate` (with `date_not_future` + `price_positive` validators), `MarketPriceResponse` (Decimal → string via `from_orm_with_decimal()`), `MarketPriceListResponse`, `CommodityListResponse`

**Services:** `app/services/`
- `notification_service.py` — create, bulk-create, list, mark-read, mark-all-read, delete, unread-count
- `market_service.py` — create-price, list-latest, list-history, list-commodities (with `KNOWN_COMMODITIES` seed list)
- `audit_service.py` — `log_action()` (flush-within-caller-transaction) + `log_action_safe()` (fire-and-forget)
- `sms_service.py` — lazy-loaded Africa's Talking wrapper; 6 SMS template functions (vaccination_reminder, vaccination_overdue, daily_log_reminder, disease_alert, weekly_summary, farm_invite)
- `scheduler.py` — `AsyncIOScheduler` with 5 `CronTrigger` background jobs (all Africa/Nairobi timezone)

**APScheduler wiring (Sprint 6 carryover AR-06):** `app/main.py` updated with `@asynccontextmanager async def lifespan(app)` — starts scheduler on startup, stops on shutdown.

**Endpoints:** 8 total — router registered in `app/api/v1/router.py`
- `notifications.py` (4): GET list, PATCH mark-read, POST read-all, DELETE notification
- `market.py` (4): GET latest prices, GET price history, GET commodities, POST create-price (admin-only, 201)

---

### Scheduler jobs delivered

| Job | Schedule (EAT) | Grace |
|-----|---------------|-------|
| `job_aria_daily_insights` | Daily 06:00 | 300s |
| `job_vaccination_reminders` | Daily 08:00 | 300s |
| `job_vaccination_overdue` | Daily 08:05 | 300s |
| `job_daily_log_reminder` | Daily 20:00 | 300s |
| `job_weekly_summary` | Friday 18:00 | 600s |

All jobs open their own `AsyncSessionLocal()` session and are wrapped in `try/except` — scheduler failures never propagate to the request path.

---

### Permissions added

| Permission | Value | Roles |
|-----------|-------|-------|
| `NOTIFICATION_VIEW` | `"notification:view"` | enterprise_owner, farm_owner, farm_manager, vet_consultant, farm_worker, viewer |
| `MARKET_VIEW` | `"market:view"` | enterprise_owner, farm_owner, farm_manager, vet_consultant, farm_worker, viewer |

Market prices are platform-wide and readable by all authenticated users. The `POST /market/prices` endpoint uses `Permission.ADMIN_MARKET_MANAGE` (super_admin only, pre-existing).

---

### Frontend delivered

**Screens:**
- N-01 `NotificationsScreen.tsx` — `/farms/:farmId/notifications` — list with unread badge, filter toggle (All/Unread), mark-read, mark-all-read, delete, empty state
- FR-01 `MarketPricesScreen.tsx` — `/market/prices` — latest price per commodity, county filter dropdown, link to history
- FR-02 `PriceHistoryScreen.tsx` — `/market/prices/history?commodity=X` — paginated price history for one commodity

**Routes:** 5 new routes registered in `src/routes/index.tsx`
- `/notifications` → Navigate to `/farms`
- `/farms/:farmId/notifications` → `NotificationsScreen`
- `/market/prices` → `MarketPricesScreen`
- `/market/prices/history` → `PriceHistoryScreen`
- Existing `/notifications` ComingSoon placeholder replaced

**API clients:**
- `src/api/notifications.ts` — list, markRead, markAllRead, delete
- `src/api/market.ts` — listLatestPrices, listPriceHistory, listCommodities, createPrice

**Query keys:** 5 new keys in `src/lib/queryClient.ts`
- `notifications(farmId)`, `unreadCount(farmId)`, `marketPrices()`, `marketPriceHistory(commodity)`, `marketCommodities()`
- `queryClient.ts` also repaired — file was truncated at `aiQuota:` from Sprint 6; complete content restored.

**Types:** Sprint 7 types appended to `src/types/index.ts`
- `Notification`, `NotificationListResponse`, `MarketPrice`, `MarketPriceListResponse`, `CommodityListResponse`, `MarketPriceCreate`

**i18n:** EN 31 keys, SW 31 keys — counts match
- `notifications.*` — 10 keys + 6 type labels
- `market.*` — 15 keys

---

### Tests delivered

| Layer | File | Tests |
|-------|------|-------|
| Unit | `tests/unit/api/v1/test_platform.py` | 30 tests |
| Integration | `tests/integration/test_platform_flow.py` | 20 tests |

**Unit test classes:** `TestNotificationCreate` (6), `TestNotificationListResponse` (3), `TestAuditLogCreate` (5), `TestAuditLogResponse` (2), `TestMarketPriceCreate` (8), `TestMarketPriceResponse` (4), `TestCommodityListResponse` (2)

**Integration test classes:** `TestNotificationList` (2), `TestNotificationLifecycle` (4), `TestNotificationRBAC` (3), `TestMarketPricesEmpty` (2), `TestMarketPriceCRUD` (5), `TestMarketPriceRBAC` (4)

---

### Known carryovers

| Code | Description | Reason |
|------|-------------|--------|
| KI-07 | `NotificationsScreen` accesses `/farms/:farmId/notifications` but the `/notifications` tab in `AppLayout` currently navigates to `/farms` redirect — needs a default-farm resolver to go directly to the right farm | Requires `useActiveFarm()` hook (Sprint 8 scope) |
| KI-08 | Admin UI for publishing market prices not built — super_admin must use the API directly in V1 | Admin console is Sprint 8+ scope |

KI-02, KI-03, KI-04 from Sprint 3 remain open — not in Sprint 7 scope.

---

### Frozen decision compliance

| Decision | Status |
|----------|--------|
| DB-07 (no real-time P&L) | N/A — no finance aggregation in Sprint 7 |
| DB-08 (audit_logs append-only) | Compliant — no UPDATE/DELETE endpoints exist; AuditLog inherits Base, no soft-delete |
| DB-09 (market_prices historical) | Compliant — no PATCH/PUT/DELETE endpoints; MarketPrice inherits Base; correction = new row |
| DB-04 (farm_id on all tables) | Compliant — documented exception for `market_prices` (platform-wide) |
| DB-01 (soft deletes) | Compliant — Notification has deleted_at; AuditLog + MarketPrice intentionally excluded (immutable records) |
| AD-01 (UUID PKs) | Compliant — all three tables use UUID v4 |
| AD-13 (APScheduler embedded) | Compliant — AsyncIOScheduler started in FastAPI lifespan |

---

### File repair log

Two pre-existing file corruptions discovered and repaired during Sprint 7:

1. `frontend/src/lib/queryClient.ts` — truncated at `aiQuota: ` (from Sprint 6 write-tool bug). File fully restored with complete `queryKeys` object + Sprint 7 additions.
2. `frontend/src/routes/index.tsx` — contained a duplicate `AppRouter` export block and a corrupted byte at the ARIA comment (U+FFFD replacement char). Both repaired via Python binary read + unicode error replacement.

All Sprint 7 file writes used the established `cat > file << 'PYEOF'` bash heredoc pattern (no Edit/Write tool for new file creation) to prevent null-byte truncation.

---

### Gate summary

| Gate | Result |
|------|--------|
| 1 — Schema syntax | PASS — 17 Python files compiled without error |
| 2 — i18n JSON validity | PASS — EN + SW valid; 31 Sprint 7 keys each |
| 3 — File completeness | PASS — all migrations, models, endpoints, screens, routes, query keys present |
| 4 — Test coverage | PASS — 30 unit + 20 integration tests (exceeds 20/15 minimums) |
| 5 — RBAC matrix | PASS — NOTIFICATION_VIEW + MARKET_VIEW granted to all 6 roles; ADMIN_MARKET_MANAGE (POST price) restricted to super_admin; 403 + 401 paths covered in integration tests |
| 6 — Frozen constraint audit | PASS — DB-08, DB-09, AD-13 honoured; DB-04 exception documented |
