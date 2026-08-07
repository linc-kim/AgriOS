# Module 20 — Swine (Pig Framework) — M12 Production Readiness Audit

**Audit date:** 2026-08-07 · **Branch:** `phase-2-auth` · **Migration head:** `086`
**Verdict:** ✅ **Production Ready with Minor Limitations** (all limitations pre-existing and non-swine)

This is a comprehensive production-readiness audit of the Swine Module and a
verification that it is fully integrated into the Greena platform without
regressions. No new features were built — M12 is validation only. Evidence for
every claim is recorded inline.

---

## 1. Database Validation

| Check | Result | Evidence |
|---|---|---|
| Single migration head | ✅ | `alembic heads` → `086 (head)` |
| No duplicate / conflicting heads | ✅ | Sequential `001`→`086`, one lineage |
| Empty DB → head | ✅ | Fresh `agrios_m12` DB: all 86 migrations apply, ends at `086` |
| Downgrade head → base | ✅ | Clean; only `alembic_version` remains — **no orphaned tables** |
| Re-upgrade base → head (round-trip) | ✅ | Returns to `086` cleanly |
| Foreign keys valid | ✅ | 130 FKs across 31 `swine_*` tables, all with explicit delete rules |
| Cascade behavior correct | ✅ | See below |
| Constraints enforced | ✅ | CHECK constraints on **every** table (enum + range enforcement at DB layer) |
| Indexes present | ✅ | 165 indexes; **all FK columns indexed** |
| No orphaned data possible | ✅ | `farm_id` CASCADE + owned-child CASCADE guarantee teardown |

**Cascade design (verified correct and intentional):**
- `farm_id → farms ON DELETE CASCADE` — farm/org teardown removes all swine data.
- `created_by / recorded_by → users ON DELETE SET NULL` — records survive user deletion.
- `pig_id → swine_pig ON DELETE CASCADE` for **owned child rows** (weight, event,
  media, document, movement, body_condition, stage_transition).
- `pig_id → swine_pig ON DELETE SET NULL` for **clinical/historical rows**
  (mortality, disease_case, sale, litter, breeding sire/dam) — history stays
  traceable after a pig row is gone.

**Multi-tenant uniqueness:** 8 composite unique constraints, all **farm-scoped**
(`uq_swine_pig_farm_ear_tag`, `uq_swine_pig_farm_internal_ref`,
`uq_swine_{herd,group,pen,bloodline,litter,farrowing}_farm_code`).

---

## 2. Backend Validation

| Check | Result | Evidence |
|---|---|---|
| App boots | ✅ | `app.main:app` imports; logs "Greena API started" |
| Dependency injection | ✅ | All routers register; OpenAPI resolves every dependency |
| Services initialize | ✅ | 21 swine services import without error |
| No import cycles | ✅ | `import app.main` succeeds (fatal cycles would abort) |
| No mapper issues | ✅ | `configure_mappers()` succeeds |
| No schema conflicts | ✅ | `app.openapi()` generates — 632 paths, no response-model collisions |
| No route conflicts / duplicate endpoints | ✅ | 828 routes, **0 duplicate `(method, path)`** |
| No startup warnings (swine) | ✅ | Only warning is upstream `python_multipart` PendingDeprecationWarning (third-party) |
| No runtime exceptions | ✅ | Full suite (below) exercises every endpoint |

Swine contributes **118 routes** and is wired into Mission Control at
`/api/v1/farms/{farm_id}/mission/swine/briefing`.

---

## 3. Full Backend Test Suite (entire Greena, not swine-only)

```
1846 passed, 0 failed, 0 skipped in 250.42s (4m10s)
```

| Metric | Value |
|---|---|
| Total | **1846** |
| Passed | **1846** |
| Failed | **0** |
| Skipped | **0** |
| Duration | **250.42 s** |
| Warnings | 1773 (pre-existing platform-wide `datetime.utcnow()` deprecations — not swine) |

The suite spans Swine, Poultry, Rabbit, BSF, Small Ruminant, Shared Finance,
Operations, Planner, Permissions, Reporting, Analytics, ARIA, Mission Control and
platform tests. **All previously-completed modules still pass** → no regressions.

Swine-specific: **136 tests** (67 unit engine/foundation + 69 integration API).

---

## 4. Frontend Validation

| Check | Result | Notes |
|---|---|---|
| `vite build` | ✅ **clean** | 260 precache entries; the established module gate |
| `tsc --noEmit` (swine) | ✅ **0 errors in swine** | `src/screens/swine/*`, `src/api/swine.ts` type-clean |
| `tsc --noEmit` (whole app) | ⚠️ 2 errors | **Both in the rabbit module (Module 17)** — pre-existing |
| Broken routes / imports / components | ✅ none | `/swine/*` lazy routes resolve; build would fail otherwise |
| Lint | ⚠️ non-functional repo-wide | ESLint 9 installed, **no flat `eslint.config.js`** — pre-existing tooling gap |

The 2 TypeScript errors are in `RabbitBreedingScreen.tsx` (unused import) and
`RabbitHealthScreen.tsx` (mutation type union) — last touched by rabbit commit
`9217fde`. Git confirms **no swine commit touched any rabbit frontend file**, so
these are pre-existing debt, not a swine regression. The swine frontend contains
no `@ts-ignore`, `@ts-expect-error`, or `any` casts.

---

## 5. Integration Validation (shared infra reused — no parallel systems)

| System | Reuse mechanism | Evidence |
|---|---|---|
| Authentication | Platform `CurrentUser` dependency | endpoints |
| Organizations / Farms | `farm_id`/`organization_id` FKs + `require_farm_access` | 130 FKs |
| RBAC | 77 `SWINE_*` entries in **shared** `app/core/permissions.py` | one enum, no parallel system |
| Finance | `finance_service.record_category_expense` (shared ledger, `metadata.module="swine"`) | **no swine cost/ledger table** |
| Inventory | `inventory_service.record_movement` (`consumption`, no re-expense) | `swine_feed_service.py` |
| Operations | `reminder_id` soft-link to Operations reminder/task | `swine_biosecurity_service.py` |
| Reports | Read-only composition over domain engines | `swine_reporting_service.py` |
| Analytics | Pure engines, computed-never-stored | 6 `_engine.py` files |
| ARIA | `ai_provider` + `ai_settings_service` (shared router, deterministic-first) | no swine AI perms/tables |
| Mission Control | `/mission/swine/briefing` | registered route |
| Audit logging | `audit_service` called by **all 10** write services | coverage verified |

**No duplicated systems exist.** There is no swine-local finance, inventory,
ledger, or AI implementation.

---

## 6. Security Validation

| Check | Result | Evidence |
|---|---|---|
| Permissions enforced | ✅ | Every endpoint: `require_permission(Permission.SWINE_*)` |
| Authorization / role gating | ✅ | Writes gated by `require_farm_access(_MANAGER_ROLES)` |
| Organization isolation | ✅ | Access flows through platform `require_farm_access` (org→farm) |
| Farm isolation (query level) | ✅ | **70** `farm_id ==` filters across services |
| IDOR protection | ✅ | `get_by_id` enforces `id == X AND farm_id == farm AND deleted_at IS NULL` |
| Input validation | ✅ | Pydantic schemas + DB CHECK constraints |
| Injection protection | ✅ | SQLAlchemy parameterized queries throughout (no raw string SQL) |
| Audit logging | ✅ | All write paths logged |
| Sensitive-data handling / §4.4 | ✅ | Health engine never diagnoses; always emits §4.4 vet disclaimer |

A user **cannot** access data outside their org/farm: the endpoint gate and the
query-level `farm_id` filter are defense-in-depth, and cross-farm ID access is
blocked at the lookup.

---

## 7. Performance Validation

- **Indexes:** all 130 FK columns indexed; 165 indexes total. Hot filter columns
  on `swine_pig` (status, production_stage, sex, ear_tag, location FKs) indexed.
- **Query scoping:** every list/summary is `farm_id`-scoped and soft-delete filtered.
- **Engines:** pure in-memory math over pre-fetched data — no query fan-out.
- **One bounded loop:** `organization_report` iterates **farms in an org** (small
  business-bounded N), not pigs — the natural shape for a cross-farm executive
  report. Not a pig-count-scaled N+1.

**Optimizations made:** none required. No premature optimization performed, per mandate.

---

## 8. Code Quality Review

| Check | Result |
|---|---|
| Ruff | ✅ **All checks passed** (all swine services, endpoints, models, schemas) |
| Formatting | ✅ consistent |
| Dead code | ✅ none |
| TODO / FIXME / XXX / HACK | ✅ **none** in swine |
| Placeholder / stub implementations | ✅ none (only `# pragma: no cover` integrity safety-nets) |
| Duplicated business logic | ✅ none (engines are the single source of math) |
| Unused imports / unreachable code | ✅ none (ruff-clean) |
| Commented-out legacy code | ✅ none |

---

## 9. Architecture Review

| Rule | Result | Evidence |
|---|---|---|
| Services orchestrate workflows | ✅ | Services own DB writes + audit |
| Engines contain business logic | ✅ | 6 engines with **0 DB access** (pure) |
| Analytics compose existing engines | ✅ | `swine_reporting_service` composes, never recalculates |
| Reports read-only | ✅ | `swine_reporting_service`: **0 writes** |
| ARIA interprets existing outputs | ✅ | `swine_aria_service`: only write is `ai_settings.record_usage` (metering) — **PD-07/08 preserved** |
| Finance reuses shared ledger | ✅ | §5 |
| Inventory reused | ✅ | §5 |
| Operations reused | ✅ | §5 |
| Shared components reused | ✅ | frontend reuses `useWorkspace`/Query/Button/Modal/FactBadge |

**No parallel implementations exist.** Layering (endpoint → service → engine) is
consistent with the Rabbit and Small Ruminant precedents.

---

## 10. Regression Audit

The full 1846-test suite passing — including Finance, Operations, Planner,
Reporting, Analytics, ARIA, Mission Control, and every prior livestock module —
demonstrates **no regressions** introduced by the Swine Module. Swine writes only
to `swine_*` tables plus the shared ledger/inventory via their public service APIs;
it adds no columns to and alters no behavior of shared tables.

---

## 11. Production Readiness Report

### Test Summary
- **Backend:** 1846 total · 1846 passed · 0 failed · 0 skipped · 250.42 s.
- **Frontend:** `vite build` clean (260 precache entries). No frontend unit test
  suite is wired for swine (consistent with sibling modules; the build is the gate).

### Migration Summary
- **Latest migration:** `086` (single head).
- **Round-trip:** base→head→base→head verified clean; no orphaned tables.
- **Database status:** 31 swine tables, 130 FKs, 165 indexes, 8 farm-scoped unique
  constraints, CHECK constraints on every table.

### Integration Summary
Finance ✅ · Operations ✅ · Inventory ✅ · Planner ✅ (Growth Planner reuse) ·
Reports ✅ · Analytics ✅ · ARIA ✅ · Mission Control ✅ — all via shared
infrastructure, no duplication.

### Performance Summary
- Significant findings: none.
- Optimizations made: none (not warranted).
- Remaining concerns: `organization_report` scales with farms-per-org (bounded,
  acceptable); revisit only if a single org reaches hundreds of farms.

### Security Summary
- Permission verification: ✅ every endpoint double-gated (RBAC + farm access).
- Organization/farm isolation: ✅ endpoint gate + 70 query-level `farm_id` filters + IDOR-safe lookups.
- API validation: ✅ Pydantic + DB CHECK constraints; parameterized queries.

### Known Limitations (non-critical, all pre-existing and **not** swine)
1. **2 TypeScript errors in the Rabbit module** (`RabbitBreedingScreen.tsx`,
   `RabbitHealthScreen.tsx`) — Module 17 debt; swine is type-clean.
2. **Repo-wide lint non-functional** — ESLint 9 upgraded with no flat
   `eslint.config.js`; affects the whole frontend, predates swine.
3. **Platform `datetime.utcnow()` deprecation warnings** (1773) — cosmetic, platform-wide.

### Technical Debt (intentional deferrals within swine)
- Vaccine/drug Inventory decrement: soft `inventory_item_id` present, stock
  movement wiring deferred (M6 note).
- Treatments carry no cost column: health cost is derived from the tagged shared
  ledger (vet/medication slugs) by design (M8 note).
- Frontend covers the core workspace (directory/profile/dashboard + domain
  read screens + ARIA/mission); deeper data-entry screens can reuse the shared
  component pattern next.

---

## 12. Final Production Decision

### ✅ Production Ready with Minor Limitations

**The Swine Module itself is fully production-ready:** clean migrations and
round-trip, 136/136 tests green within an all-green 1846-test platform suite, a
clean `vite build`, ruff-clean and TODO-free code, correct layering, complete
reuse of shared Finance/Inventory/Operations/ARIA/Mission infrastructure with no
parallel systems, and verified org/farm isolation with IDOR-safe lookups. It
introduces **no regressions**.

The "minor limitations" qualifier reflects **three pre-existing, non-swine
platform issues** (2 rabbit TypeScript errors, broken repo-wide lint tooling, and
cosmetic datetime deprecation warnings). None originate from the Swine Module and
none block swine deployment; they are documented so the platform-level frontend
gate can be restored independently.

**Deployment note:** the module is on `phase-2-auth`, **unpushed and undeployed**,
awaiting explicit go-ahead per the locked module cadence.
