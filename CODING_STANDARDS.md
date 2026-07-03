# AGRIOS CODING STANDARDS

**Read `AGRIOS_MASTER_CONTEXT.md` and `SYSTEM_ARCHITECTURE.md` first.** This document is the concrete, file-level rulebook that keeps AGRIOS's codebase internally consistent across every sprint and every contributor. Every rule here exists because deviating from it has already caused, or was judged likely to cause, a specific class of bug or inconsistency — this is a document of hard-won convention, not stylistic preference.

---

## 1. Sprint Governance — Every Change Passes Through Five Phases

AGRIOS was built, and should continue to be built, under a formal sprint execution framework: **Phase 1 (Pre-Sprint Validation)** — scope is locked with migration numbers, screen IDs, and task IDs before any code is written; dependencies are checked (does the new migration's `down_revision` match the current head; are all referenced models already registered); frozen constraints are reviewed against the new scope. **Phase 2 (Development Rules)** — the concrete backend/frontend rules in Sections 2–3 below. **Phase 3 (Quality Gates)** — six mandatory gates (Section 4) that are blockers, not warnings. **Phase 4 (Completion Checklist)** — a final verification pass before a sprint is considered done. **Phase 5 (Handover Report)** — a fixed-format report filed at sprint close (Section 5). **A sprint is not done when code is written — it is done when every gate is cleared and a handover report is filed.** This is not bureaucracy for its own sake: it is what allowed ten sprints of work, much of it AI-assisted, to remain internally consistent enough that this documentation set could be written from the actual delivered artifacts rather than from aspirational plans.

---

## 2. Backend Standards

### 2.1 Models

- Every new model uses `AGRIOSBase` (`DATABASE_ARCHITECTURE.md` Section 1) and overrides only what the table specifically requires beyond the five inherited columns.
- Nullable foreign keys are typed `Mapped[uuid.UUID | None]`; required foreign keys are typed `Mapped[uuid.UUID]`. This distinction is not cosmetic — it is how SQLAlchemy 2.0's typed mapping communicates nullability to both the type checker and the generated schema.
- Database-level enums (e.g. `RevenueTypeEnum`) use `create_constraint=True` and `checkfirst=True` on both upgrade and downgrade, for the exact reasons documented in `DATABASE_ARCHITECTURE.md` Section 4.4 — idempotency against partial upgrade/downgrade cycles.
- Relationships that appear in list queries use `lazy="joined"` specifically to avoid N+1 query patterns; a relationship added without considering its `lazy` strategy is a latent performance bug that will not surface until a list endpoint is exercised with real data volume.
- Every new model must be registered in `backend/app/models/__init__.py` under a sprint-labeled comment block — a model that exists as a file but is not imported here will not be picked up by Alembic's autogenerate tooling and will not appear in `__all__` for other modules to import cleanly.

### 2.2 Migrations

- Every migration must have a working `downgrade()` that cleanly reverses its `upgrade()` — an untested downgrade is treated as an incomplete migration, not an acceptable shortcut.
- ENUM types are dropped in `downgrade()` only by the migration that created them (`DATABASE_ARCHITECTURE.md` Section 4.4, Pattern A).
- Seed data inserted via `bulk_insert` in `upgrade()` must be explicitly removed in `downgrade()`.
- Foreign key `ondelete` behavior is a deliberate choice per relationship, not a default: `RESTRICT` when a dangling reference must be impossible, `SET NULL` when the reference is optional and the child record should outlive the deleted parent, `CASCADE` when the child record has no independent meaning (`DATABASE_ARCHITECTURE.md` Section 10).

### 2.3 Schemas

- All schemas extend a project-standard `AGRIOSSchema` base (a Pydantic `BaseModel` subclass with project-wide config), not bare `BaseModel`.
- Validator ordering is fixed: `@field_validator` for single-field rules first, `@model_validator(mode="after")` for cross-field rules second.
- Any correction-style update schema (`ExpenseUpdate`, `RevenueRecordUpdate`, and any future equivalent) requires `correction_reason: str = Field(..., min_length=5, max_length=500)` — this is not optional, because the correction pattern (`DATABASE_ARCHITECTURE.md` Section 8) depends on every correction carrying a real, minimally-descriptive reason.
- Partial-update schemas must include a `@model_validator` that rejects a payload where no field actually changed — an update request that changes nothing should fail loudly rather than silently succeed and produce a confusing audit-log entry.
- Every API response uses the project's `SuccessResponse[T]` envelope. **No endpoint returns a raw dict.** This is what allows the frontend's API client layer to unwrap every response identically regardless of domain (`SYSTEM_ARCHITECTURE.md` Section 3.2).

### 2.4 Endpoints

- Write operations require both a farm-access role check (e.g. `require_farm_access({"farm_owner", "farm_manager"})`) and a specific permission check (`require_permission(Permission.X)`) — the two are always applied together and are never substituted for one another (`SYSTEM_ARCHITECTURE.md` Section 2.5).
- Read operations are generally open to all six farmer-facing roles, gated by a `_VIEW`-suffixed permission where the read/write distinction is meaningful for that resource.
- Pure calculators that do not touch farm data (break-even, profitability projections) require only the `CurrentUser` dependency — no farm-access guard, since there is no farm-scoped data being read or written.
- Every new endpoint must be registered in `backend/app/api/v1/router.py` before a sprint touching it is considered backend-complete — an endpoint that exists as a function but is not wired into the router is invisible to the running application.

### 2.5 Permissions

- New permissions are added to the `Permission` enum in `app/core/permissions.py` and to the `ROLE_PERMISSIONS` dict in the same file, in the same change — never one without the other (`SYSTEM_ARCHITECTURE.md` Section 2.5).
- Every new write permission is assigned, at minimum, to `enterprise_owner`, `farm_owner`, and `farm_manager`.
- Every new read permission is assigned, at minimum, to `farm_worker` and `viewer` — the two most restricted farmer-facing roles.

### 2.6 The Correction Pattern (Backend Enforcement)

All record corrections append inline to the `notes` field using the fixed format `\n[Corrected by {user_id} at {ISO timestamp}: {reason}]`. There is deliberately no separate correction-log table anywhere in the schema for this — this is the project standard across every correctable domain, and a future correctable domain should follow it rather than introducing a bespoke correction-tracking mechanism (`DATABASE_ARCHITECTURE.md` Section 8).

---

## 3. Frontend Standards

### 3.1 Types

Every new API-facing type is added to `frontend/src/types/index.ts`, under a sprint-labeled comment, hand-mirroring the corresponding backend Pydantic schema. Decimal/Numeric fields returned by the API are typed as `string` in TypeScript — **not** `number` — because the API serializes Python's `Decimal` type as a string to avoid floating-point precision loss on financial figures; a type mismatch here is a common source of silent currency-formatting bugs.

### 3.2 API Client Layer

All API functions live in `frontend/src/api/{domain}.ts`, one file per backend domain, mirroring the backend's `endpoints/` structure. Every function unwraps the `APISuccess<T>` envelope before returning — callers never see the raw envelope. Query-parameter interfaces (e.g. `ExpenseListParams`) are defined in the same file as the functions that use them, not inlined at each call site, so a parameter shape change only needs to happen in one place.

### 3.3 Query Keys

Every new query key function lives in the single `queryKeys` object in `frontend/src/lib/queryClient.ts` — there is deliberately one canonical source of cache-key truth for the entire application. Keys follow the pattern `["farms", farmId, "domain", "resource"]`. **After any write mutation, invalidate both the directly affected resource and its parent aggregates** (`SYSTEM_ARCHITECTURE.md` Section 3.4) — forgetting the aggregate invalidation is the single most common frontend bug class in this codebase, because the financial snapshot pattern in particular means a narrow write can make several broader cached views stale simultaneously.

### 3.4 Screens

- Every screen follows the AGRIOS Design System exactly: `bg-gray-50` page background, white card surfaces, `brand-600` reserved for the single primary action (`DESIGN_SYSTEM.md`).
- Every screen has all three of: a loading state (`<Spinner />`), an error state, and an empty state. A screen missing any one of these three is considered incomplete, not merely unpolished.
- Currency values are always formatted with `fmtKES()` (`toLocaleString("en-KE")`) — never a hand-rolled number format.
- All user-facing strings use `t("namespace.key")`. **No hardcoded English string is acceptable anywhere in a shipped screen** — this is the mechanism that makes the Swahili/English parity requirement enforceable at all (Section 3.6).
- `useSearchParams` is the standard mechanism for optional query-param pre-fills (e.g. `?flockId=` to pre-select a flock in a form).

### 3.5 Routes

New screens are lazy-loaded in `frontend/src/routes/index.tsx` — this is a direct performance requirement given the 3G-first design constraint (`SYSTEM_ARCHITECTURE.md` Section 3.1), not a style preference. Tab-level paths (e.g. `/finance` with no further path) redirect to `/farms` rather than rendering a blank screen when no farm context is yet established. Farm-scoped screens consistently follow the `/farms/:farmId/...` pattern.

### 3.6 i18n

English keys live in `frontend/src/locales/en/common.json`; Swahili keys in `frontend/src/locales/sw/common.json`. **Both files must be syntactically valid JSON after every single write** — validated with `python3 -c "import json; json.load(open(path))"` before committing, because a truncated or malformed locale file is a build-breaking defect, not a cosmetic one. **Key counts must be equal between the two files for every sprint's additions** — a Swahili translation that lags behind English is treated as an incomplete sprint deliverable, not a follow-up task, precisely because Swahili parity is a core, not peripheral, product requirement (`DESIGN_SYSTEM.md` Section 3.4).

---

## 4. Quality Gates — All Six Are Blockers, Not Warnings

| Gate | What it checks | Why it is a hard blocker |
|---|---|---|
| 1 — Schema syntax | Every new/changed Python file passes `python3 -m py_compile` | A file that does not even compile cannot be meaningfully reviewed for anything else. |
| 2 — i18n JSON validity | Both locale files parse via `json.load` | A malformed locale file breaks the production build entirely, not just the untranslated screen. |
| 3 — File completeness | Every planned migration, model, endpoint, screen, route, API function, and query key actually exists where planned | A sprint that "mostly" wired something in is a sprint with a dead end waiting to be discovered later. |
| 4 — Test coverage | Minimum 20 unit tests + 15 integration tests per sprint domain | Numbers below this floor have historically correlated with under-tested RBAC and lifecycle edge cases. |
| 5 — RBAC matrix | Every new endpoint tested against all 6 roles for the correct 200/403 outcome | RBAC bugs are invisible in a happy-path demo and only surface as real security incidents — this gate exists to catch them before that happens. |
| 6 — Frozen constraint audit | No real-time P&L aggregation, no skipped UUID PKs, no hard deletes, no migration mutating schema outside its own `upgrade()`/`downgrade()` | These are exactly the frozen decisions (`AGRIOS_MASTER_CONTEXT.md` Section 9) most likely to be violated by a well-intentioned shortcut under time pressure. |

A failing gate blocks progress to the next phase. A passing gate "with a documented exception" is acceptable only at Amber status (Section 6) and must be explicitly called out in the sprint's handover report — it is never silently waved through.

---

## 5. The Handover Report — Fixed Format

Every sprint files a handover report at close, in this exact shape (do not omit sections): Sprint name/tier/date/status; migrations delivered (table); backend delivered (models, schemas, service functions, endpoint count); permissions added (table); frontend delivered (screens, routes, query keys, i18n key counts for both languages); tests delivered (unit/integration file names and counts); known carryovers (Section 7); frozen decision compliance (table); gate summary (table, all six gates). This fixed format exists so that ten different sprints, potentially executed months apart or by different contributors (including AI agents), produce directly comparable records — `PROJECT_HISTORY.md` is, in large part, a synthesis of these reports, and that synthesis is only possible because the format never drifted.

---

## 6. Readiness Assessment Before Starting a New Sprint

**Green (proceed):** the previous sprint's handover report is filed; all six gates passed; no open frozen-decision violations; `alembic heads` returns exactly one head; both i18n files are valid JSON; `tsc --noEmit` introduces no new TypeScript errors; test files compile without AST errors.

**Amber (proceed with caution):** a carryover from the previous sprint falls within the next sprint's scope; a gate passed with a documented exception; a planned screen is deferred but its route is registered with an acceptable placeholder. Amber status requires a brief risk note in the next handover report — it is not free of consequence, just not blocking.

**Red (do not proceed):** any frozen architecture decision was violated; either i18n file is invalid JSON; `alembic heads` returns more than one head (a forked migration chain); a required unit or integration test file is missing entirely; the RBAC matrix has an untested 403 path for a write endpoint. Red status must be resolved, as its own tracked patch task, before the next sprint begins under any circumstances.

---

## 7. Carryover Policy — "Known Issue" (KI) Codes

Deferred items are **carryovers**, not failures, and are tracked with a `KI-NN` code that appears in the handover report under "Known carryovers." The next sprint's plan must explicitly state which KIs it resolves. **A KI deferred across three consecutive sprints is automatically escalated to Architecture Review** — this threshold exists because a carryover that keeps slipping is usually a signal of an underlying design gap, not merely a scheduling issue, and treating it as routine backlog indefinitely would hide that signal. The full current and historical KI list is maintained in `KNOWN_TECHNICAL_DEBT.md`, not duplicated here.

---

## 8. Testing Philosophy

Every sprint ships both a unit test file (`tests/unit/api/v1/test_{domain}.py`, minimum 20 schema-validation tests) and an integration test file (`tests/integration/test_{domain}_flow.py`, minimum 15 lifecycle-and-RBAC tests). Integration coverage is expected to include, at minimum: a full CRUD lifecycle for every primary resource in the domain; soft-delete verification (a deleted item must be excluded from subsequent list queries — this is the single most valuable and most frequently-skipped integration test in a soft-delete-everywhere system); at least one snapshot/recompute test if the domain touches financial aggregation; the full RBAC matrix (a write-permitted role succeeds, a read-only role receives 403 on write and 200 on read); and at least one 404 test against a non-existent resource ID. Tests are not treated as a documentation exercise after the fact — they are the mechanism by which a frozen decision's compliance is actually verified rather than merely asserted in a handover report.

---

## 9. Comment and Documentation Philosophy

Model docstrings state which migration number a table corresponds to and cross-reference the frozen decision IDs that govern it (for example, `health.py`'s module docstring explicitly notes "VaccinationRecord is farm-scoped (DB-04 Frozen)"). This convention — annotating code with the specific frozen-decision ID it complies with — is deliberate and should be continued: it means a future contributor reading the model file directly, without first reading this documentation set, still encounters the governing constraint at the point where it matters most. New models introducing a frozen-decision-relevant pattern should follow this same annotation convention rather than relying on documentation alone to carry that context.
