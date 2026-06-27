# AGRIOS Sprint Execution Framework

**Version:** 1.0  
**Project:** AGRIOS — Agricultural Operating System (Poultry Module 1, Kenya)  
**Stack:** FastAPI + SQLAlchemy 2.x async + Alembic + React 18 + Vite + TypeScript  
**Currency:** KES (locked)  
**Locale:** Kenya-first, English + Swahili i18n  

---

## 1. Purpose

This document is the authoritative governance standard for all AGRIOS sprint execution. Every sprint — regardless of scope — must pass through the five phases defined here before it is considered complete. No sprint is done when code is written; a sprint is done when every gate in this framework is cleared and a handover report is filed.

---

## 2. Frozen Architecture Decisions

The following decisions are permanently frozen. They must not be re-litigated in sprint planning and must not be violated during implementation.

| Code | Decision | Rule |
|------|-----------|------|
| AD-01 | Primary keys | UUID v4, all tables |
| AD-02 | ORM | SQLAlchemy 2.x async (`Mapped[]`, `mapped_column`) |
| AD-03 | Migrations | Alembic only — no schema mutations outside migration files |
| AD-04 | Frontend framework | React 18 + Vite + TypeScript |
| AD-05 | State management | Zustand (auth/global), TanStack Query (server state) |
| AD-06 | Styling | Tailwind CSS — AGRIOS Design System tokens only |
| DB-01 | Soft deletes | `deleted_at TIMESTAMPTZ NULL` on all operational tables |
| DB-02 | Audit columns | `created_at`, `updated_at` on all tables via `AGRIOSBase` |
| DB-04 | Farm scoping | `farm_id` FK on every operational table |
| DB-05 | Metadata | `metadata JSONB` on all tables (mapped as `metadata_` in Python) |
| DB-07 | Financial snapshots | Never computed real-time in API responses. Always read from `financial_snapshots`. `recompute_snapshot()` is the only aggregate query point, called after every mutation. |

Any implementation that violates a frozen decision must be flagged before the sprint starts and requires an explicit Architecture Decision Record (ADR) to proceed.

---

## 3. Phase 1 — Pre-Sprint Validation

Complete all items before writing any code. A sprint that begins without this phase is invalid.

### 3.1 Scope Lock

- [ ] Sprint scope is defined in the AGRIOS Build Manifest with migration numbers, screen IDs, and task IDs
- [ ] All migration revisions are identified (`revision`, `down_revision`)
- [ ] All API endpoint paths are listed with HTTP method and permission
- [ ] All frontend screen IDs (e.g. FI-01 through FI-08) are enumerated
- [ ] i18n namespaces and key count are estimated
- [ ] No scope is added to a sprint in-flight without explicit approval

### 3.2 Dependency Check

- [ ] `down_revision` of the first new migration matches the `revision` of the last completed migration
- [ ] All models referenced by FK in new migrations are confirmed present in `backend/app/models/__init__.py`
- [ ] All new Permission enum values are identified and their role assignments planned
- [ ] Frontend query key namespace is planned in `queryClient.ts`

### 3.3 Frozen Constraints Review

- [ ] Every new table has `farm_id` FK (or a documented exception approved for this sprint)
- [ ] Every new table has `deleted_at TIMESTAMPTZ NULL` (or a documented exception)
- [ ] Every new table has UUID PK
- [ ] JSONB `metadata` column is included where AGRIOSBase is used
- [ ] No real-time aggregate queries are planned — snapshot pattern confirmed if P&L is in scope

---

## 4. Phase 2 — Development Rules

These rules apply throughout the development phase of every sprint.

### 4.1 Backend Rules

**Models**

- Use `AGRIOSBase` for all new models. Override only what the table requires.
- `Mapped[uuid.UUID | None]` for nullable FKs; `Mapped[uuid.UUID]` for required FKs.
- `RevenueTypeEnum` and similar DB-level enums use `create_constraint=True` and `checkfirst=True` on both upgrade and downgrade.
- Relationships that appear in list queries use `lazy="joined"` to avoid N+1.
- Register every new model in `backend/app/models/__init__.py` under a sprint-labelled comment.

**Migrations**

- Every migration must have a working `downgrade()` that cleanly reverses the upgrade.
- ENUM types created in migrations must be dropped in downgrade via `sa.Enum(name=...).drop(op.get_bind(), checkfirst=True)`.
- Seed data inserted via `bulk_insert` in upgrade must be removed in downgrade.
- FK constraints use `RESTRICT` when deleting a referenced row should be an error; `SET NULL` when the reference is optional.

**Schemas**

- All schemas extend `AGRIOSSchema` (Pydantic BaseModel subclass with project-standard config).
- Validators follow this order: `@field_validator` for single fields, `@model_validator(mode="after")` for cross-field rules.
- `ExpenseUpdate`, `RevenueRecordUpdate`, and similar correction schemas require `correction_reason: str = Field(..., min_length=5, max_length=500)`.
- Update schemas that allow partial updates must include a `@model_validator` that rejects payloads where no actual field is changed.
- All API responses use `SuccessResponse[T]` — never return raw dicts.

**Endpoints**

- Write operations: `require_farm_access({"farm_owner", "farm_manager"})` + `require_permission(Permission.X)`.
- Read operations: all 6 roles + a `_VIEW` permission.
- Pure calculators (no farm data): `CurrentUser` dependency only — no farm access guard.
- Router registration in `backend/app/api/v1/router.py` must be added before the sprint is considered backend-complete.

**Permissions**

- New permissions are added to the `Permission` enum in `backend/app/core/permissions.py`.
- Role assignments are updated in the `ROLE_PERMISSIONS` dict in the same file.
- Every new write permission must be assigned to `enterprise_owner`, `farm_owner`, and `farm_manager` at minimum.
- Every new read permission must be assigned to `farm_worker` and `viewer`.

**Correction Pattern**

All record corrections append inline to the `notes` field:

```
\n[Corrected by {user_id} at {ISO timestamp}: {reason}]
```

No separate correction log table. This is the project standard.

### 4.2 Frontend Rules

**Types**

- All new API types are added to `frontend/src/types/index.ts` under a sprint-labelled comment.
- Decimal/Numeric fields returned from the API are typed as `string` in TypeScript (API serialises Python `Decimal` as string).

**API Client**

- All functions live in `frontend/src/api/{domain}.ts`.
- All functions unwrap the `APISuccess<T>` envelope before returning.
- Query param interfaces (`XListParams`) are defined in the same file, not inline.

**Query Keys**

- All new query key functions are added to the `queryKeys` object in `frontend/src/lib/queryClient.ts`.
- Keys follow the pattern `["farms", farmId, "domain", "resource"]`.
- After any write mutation, invalidate the affected resource + parent aggregates (e.g. invalidate `expenses` + `financeDashboard` + `flockSnapshot` after logging an expense).

**Screens**

- Every screen follows the AGRIOS Design System: `bg-gray-50` page background, `bg-white` card surfaces, `brand-600` for primary actions.
- Every screen has a loading state (`<Spinner />`), an error state, and an empty state.
- Currency values are formatted with `fmtKES()` (`toLocaleString("en-KE")`).
- All user-facing strings use `t("namespace.key")` — no hardcoded English strings.
- `useSearchParams` for optional query param pre-fills (e.g. `?flockId=`).

**Routes**

- New screens are lazy-loaded in `frontend/src/routes/index.tsx`.
- Tab-level paths (e.g. `/finance`) redirect to `/farms` — never render blank screens.
- Farm-scoped screens use the pattern `/farms/:farmId/...`.

**i18n**

- English keys in `frontend/src/locales/en/common.json`.
- Swahili keys in `frontend/src/locales/sw/common.json`.
- Both files must be syntactically valid JSON after every write.
- Key count must be equal between EN and SW for every sprint.
- Validate with `python3 -c "import json; json.load(open('path/to/file.json'))"` before committing.

---

## 5. Phase 3 — Quality Gates

All gates must pass before moving to Phase 4. A failing gate is a blocker, not a warning.

### Gate 1: Schema Syntax

```bash
# Validate all new Python files
python3 -m py_compile backend/alembic/versions/0XX_*.py
python3 -m py_compile backend/app/models/domain.py
python3 -m py_compile backend/app/schemas/domain.py
python3 -m py_compile backend/app/services/domain_service.py
python3 -m py_compile backend/app/api/v1/endpoints/domain.py
```

All files must compile without error.

### Gate 2: i18n JSON Validity

```bash
python3 -c "import json; json.load(open('frontend/src/locales/en/common.json'))"
python3 -c "import json; json.load(open('frontend/src/locales/sw/common.json'))"
```

Both must parse without exception. A truncated or malformed JSON file is a build-breaking defect.

### Gate 3: File Completeness

- [ ] Every planned migration file exists and has both `upgrade()` and `downgrade()`
- [ ] Every planned model is in `models/__init__.py`
- [ ] Every planned endpoint is registered in `router.py`
- [ ] Every planned screen file exists in `src/screens/domain/`
- [ ] Every planned screen is registered in `src/routes/index.tsx`
- [ ] Every planned API function exists in `src/api/domain.ts`
- [ ] Every planned query key exists in `queryClient.ts`

### Gate 4: Test Coverage

Every sprint must ship:

| Layer | File | Minimum tests |
|-------|------|---------------|
| Unit | `tests/unit/api/v1/test_{domain}.py` | 20 schema validation tests |
| Integration | `tests/integration/test_{domain}_flow.py` | 15 lifecycle + RBAC tests |

Integration test coverage requirements:
- Full CRUD lifecycle for every primary resource
- Soft-delete verification (deleted items excluded from list)
- At least one snapshot/recompute test if aggregation is in scope
- RBAC: write role succeeds, read-only role 403 on write, read-only role 200 on read
- At least one 404 test for non-existent resources

### Gate 5: RBAC Matrix

For every new endpoint, verify:

| Role | Write endpoint | Read endpoint |
|------|---------------|---------------|
| enterprise_owner | 200/201 | 200 |
| farm_owner | 200/201 | 200 |
| farm_manager | 200/201 | 200 |
| farm_worker | 403 | 200 |
| vet_consultant | 403 (unless domain-specific grant) | 200 |
| viewer | 403 | 200 |

Any deviation from this matrix requires explicit documentation in the sprint handover report.

### Gate 6: Frozen Constraint Audit

Review every new migration and model against the frozen decisions list (Section 2). Confirm:

- [ ] No real-time P&L aggregation added to response paths
- [ ] No UUID PK skipped in favour of integer/serial
- [ ] No hard-deletes introduced (only `deleted_at` pattern)
- [ ] No migration that mutates schema outside its own `upgrade()`/`downgrade()`

---

## 6. Phase 4 — Sprint Completion Checklist

Run through this checklist in order. Check each item only after it is verified, not assumed.

### Backend

- [ ] All migration files present with correct `revision` chain
- [ ] All models registered in `__init__.py`
- [ ] All schemas include required validators (date not future, amount positive, correction_reason where applicable)
- [ ] All endpoints registered in router
- [ ] Permissions enum updated, role assignments updated
- [ ] `recompute_snapshot()` called after every mutation that affects P&L (if in scope)
- [ ] All Python files pass `py_compile` AST check

### Frontend

- [ ] All TypeScript types added to `types/index.ts`
- [ ] All API functions added to `api/{domain}.ts`
- [ ] All query keys added to `queryClient.ts`
- [ ] All screens created in `screens/{domain}/`
- [ ] All screens lazy-imported and routed in `routes/index.tsx`
- [ ] All screens have loading / error / empty states
- [ ] No hardcoded currency strings — all use `fmtKES()`
- [ ] No hardcoded user-facing English — all use `t()`
- [ ] Write mutations invalidate affected query keys

### i18n

- [ ] EN keys added and file is valid JSON (verified with `json.load`)
- [ ] SW keys added and file is valid JSON (verified with `json.load`)
- [ ] Key count matches between EN and SW for sprint additions

### Tests

- [ ] Unit test file present with ≥ 20 tests
- [ ] Integration test file present with ≥ 15 tests
- [ ] All test files pass `py_compile`
- [ ] RBAC matrix covered in integration tests

---

## 7. Phase 5 — Handover Report

Filed at sprint close. Format is fixed — do not omit sections.

```
## Sprint N Handover Report

**Sprint:** N — {Name}
**Tier:** {Build Manifest tier number}
**Date closed:** YYYY-MM-DD
**Status:** COMPLETE

### Migrations delivered
| Revision | Table | Notes |
|----------|-------|-------|
| 0XX | table_name | Brief description |

### Backend delivered
- Models: {list}
- Schemas: {list}
- Service functions: {list}
- Endpoints: {count} endpoints, router registered

### Permissions added
| Permission | Value | Roles |
|-----------|-------|-------|
| PERMISSION_NAME | "domain:action" | role1, role2, role3 |

### Frontend delivered
- Screens: {screen IDs, e.g. FI-01 to FI-08}
- Routes: {count} new routes
- Query keys: {count} new keys
- i18n: EN {count} keys, SW {count} keys

### Tests delivered
- Unit: {filename} — {count} tests
- Integration: {filename} — {count} tests

### Known carryovers
{List any items explicitly deferred to a future sprint, with reason.}

### Frozen decision compliance
| Decision | Status |
|----------|--------|
| DB-07 (no real-time P&L) | Compliant / N/A |
| DB-04 (farm_id on all tables) | Compliant |
| DB-01 (soft deletes) | Compliant |
| AD-01 (UUID PKs) | Compliant |

### Gate summary
| Gate | Result |
|------|--------|
| 1 — Schema syntax | PASS |
| 2 — i18n JSON validity | PASS |
| 3 — File completeness | PASS |
| 4 — Test coverage | PASS |
| 5 — RBAC matrix | PASS |
| 6 — Frozen constraint audit | PASS |
```

---

## 8. Readiness Assessment

Use this assessment to determine whether the project is ready to begin the next sprint.

### Green — Proceed

All of the following are true:

- Previous sprint handover report is filed
- All 6 quality gates passed in the previous sprint
- No open defects in frozen-decision compliance
- `down_revision` chain is intact (verify: `alembic heads` returns exactly one head)
- Both i18n files are valid JSON
- No TypeScript type errors introduced in the previous sprint (verify: `tsc --noEmit`)
- Test files for the previous sprint compile without AST errors

### Amber — Proceed with Caution

One or more of the following apply, but no frozen decisions are violated:

- A carryover item from the previous sprint is in the scope of the next sprint
- A quality gate passed with a documented exception
- A planned screen is deferred but the route is registered (placeholder screen acceptable)

Amber sprints require a brief risk note in the next sprint's handover report.

### Red — Do Not Proceed

Any of the following are true:

- A frozen architecture decision (Section 2) was violated in the previous sprint
- i18n files are invalid JSON (build-breaking)
- `alembic heads` returns more than one head (migration chain forked)
- Unit or integration test file is missing
- RBAC matrix has an untested 403 path for a write endpoint

Red status requires resolution before the next sprint begins. The resolution must be documented as a patch task with its own completion checklist entry.

---

## 9. Carryover Policy

Items that are deferred out of a sprint are **carryovers**, not failures. Carryovers are managed as follows:

1. Each carryover is assigned a KI (Known Issue) code: `KI-01`, `KI-02`, etc.
2. The KI code appears in the handover report under "Known carryovers."
3. The next sprint plan explicitly lists which KIs it resolves.
4. A KI that is deferred across three consecutive sprints is escalated to the Architecture Review — it may indicate a design gap.

Current open carryovers as of Sprint 5:

| Code | Description | Sprint deferred | Target sprint |
|------|-------------|-----------------|---------------|
| KI-02 | `ProductionRecordScreen` uses `ComingSoonScreen` — API/schemas exist, UI form missing | Sprint 3 | Sprint 6 |
| KI-03 | `CreateFlockScreen` depends on houses list — requires farm structure to be set up first | Sprint 3 | Sprint 6 |
| KI-04 | `/flock` and `/health` tabs redirect to `/farms` — needs default-farm redirect or farm selector | Sprint 3 | Sprint 6 |

---

## 10. Sprint Sequence Reference

| Sprint | Tier | Scope | Status |
|--------|------|-------|--------|
| Sprint 0 | — | Foundation (DB, auth, core infrastructure) | Complete |
| Sprint 1 | — | Design system | Complete |
| Sprint 2 | 2 | Farm infrastructure (Migrations 006–011) | Complete |
| Sprint 3 | 3 | Flock operations (Migrations 014–016) | Complete |
| Sprint 4 | 4 | Health module (Migrations 017–018) | Complete |
| Sprint 5 | 5 | Finance module (Migrations 019–022) | Complete |
| Sprint 6 | 6 | ARIA AI assistant | Pending |
| Sprint 7 | 7 | Notifications + alerts | Pending |
| Sprint 8 | 8 | Enterprise multi-farm | Pending |
| Sprint 9 | 9 | Offline sync | Pending |
| Sprint 10 | 10 | Production hardening + launch | Pending |

---

*This document governs all AGRIOS sprint work. Amendments require agreement between the lead engineer and project owner and must be reflected in an updated version number at the top of this file.*
