# Module 17 — Rabbit Management System — Implementation Ledger

Canonical, per-milestone record of what was built, what was reused, and what was
deferred. Maintained alongside implementation (GMIS §8; Spec Part 10 §15).

- **Spec:** `Rabbit_module_onlinenotepad.io.txt` (Parts 1–10), the business contract.
- **Standard:** `GREENA_MODULE_IMPLEMENTATION_STANDARD.md` (GMIS).
- **Aggregate root:** the individual **rabbit** (Spec Part 3 §4) — closest template
  is Module 15 Aviculture (`avi_*`); latest conventions from Module 16 BSF (`bsf_*`).
- **Branch:** `phase-2-auth`. Commits are **local only** — never pushed/deployed
  without explicit per-action approval.
- **Table prefix:** `rabbit` / `rabbit_*`. **Org isolation:** farm-scoped records
  carry `farm_id`; isolation flows through `farms.organization_id`. Catalog rows
  (`rabbit_breed`) carry nullable `organization_id` (NULL = global).

## Reuse-first inventory (no parallel systems — GMIS §1.2, §2)

| Platform capability | How the Rabbit module reuses it |
|---|---|
| Auth / RBAC | `app/core/permissions.py` — `RABBIT_*` perms layered on the 8 roles |
| Organizations / Farms | `farm_id` + `farms.organization_id`, no new tenancy tables |
| species_profiles engine | Activates the pre-seeded `species_key='rabbit'` row (id …0002) |
| Finance | (planned) shared expenses ledger via `finance_service`, `metadata.module='rabbit'` |
| Inventory | (planned) platform Inventory for feed/medicine/equipment — no rabbit stock table |
| Reminders / Tasks / Notifications | (planned) platform engines for vaccination/breeding tasks |
| Files / Media | `rabbit_media` / `rabbit_document` reference the platform file store |
| Audit / Timeline | `rabbit_event` append-only timeline complements platform Audit |
| Growth Planner | (planned) reuse platform `growth_planner_service` provider registry (migration 065) |
| ARIA | (planned) reuse `ai_provider` + `ai_settings`, deterministic-first |
| Mission Control | (planned) `rabbit_intelligence.build_briefing`, evidence-only |

## Milestones

### Milestone 1 — Foundation (GMIS Milestone A) — ✅ DONE (local, unpushed)

- **Migration `066_rabbit_foundation.py`** (down_revision 065, single head). 11 tables:
  - `rabbit_breed` — data-driven breed catalog (nullable `organization_id`, JSONB `profile`).
  - `rabbit_bloodline` — named genetic line (farm-scoped).
  - Housing hierarchy (Spec Part 1 §6): `rabbit_rabbitry` → `rabbit_building` →
    `rabbit_room` → `rabbit_row` → `rabbit_cage`. Cage occupancy is **derived**
    from `rabbit.cage_id`, never stored. `cage_type` also models colony pens,
    quarantine and isolation units (Spec Part 2 §11).
  - `rabbit` — **aggregate root**: identity (internal_ref, ear_tag, tattoo, qr_code,
    rfid), classification (breed/bloodline/variety/color/sex[buck|doe|unknown]/
    purpose+purposes), biology (dob, birth/current weight), lifecycle & repro
    (status, lifecycle_stage, reproductive_status, fertility_status), pedigree
    self-FKs (`sire_id`/`dam_id` — unknown stays NULL, never invented).
    Unique per farm on `internal_ref` and `ear_tag`.
  - `rabbit_event` (append-only timeline), `rabbit_media`, `rabbit_document`.
  - **species_profiles:** activates the Migration-007 placeholder `rabbit` row
    (`is_active=true`, refreshed display name/description) — does **not** insert a
    duplicate. Downgrade reverts it to the placeholder state (row owned by 007).
- **Models** `app/models/rabbit.py` (+ registered in `app/models/__init__.py`).
  All inherit `AGRIOSBase` (soft-delete only). Enum `*_VALUES` tuples validated at
  the schema/service layer (no DB enums), matching the avi/bsf convention.
  `Rabbit.is_in_herd` mirrors `AviBird.is_in_collection`.
- **RBAC** — 27 `RABBIT_*` perms (`rabbit:resource:action`). `_RABBIT_VIEW` /
  `_RABBIT_FULL` sets: owner/manager/enterprise full; worker operational
  (create/edit/breeding/health/weight/feed/automation) but NOT archive, transact,
  catalog/housing manage, sales, growth-edit, nor strategic finance/report/
  growth/sales **views**; vet read + `RABBIT_HEALTH_LOG`; viewer read-only.
  ARIA / Mission Control **reuse** platform `AI_QUERY` / `AI_INSIGHT_VIEW`
  (no rabbit-specific AI perms), same as avi/bsf.
- **Tests** `tests/unit/test_rabbit_foundation.py` — 18 pass (enum contracts,
  model surface, 5-level housing, soft-delete, RBAC grading).
- **Verification:** migration upgrades on dev + test DBs, downgrade→upgrade
  round-trips, single head 066. Ruff clean on changed files (pre-existing
  `permissions.py` F401 left untouched). Regression: rabbit+bsf foundation = 32 pass.

## Deviations / decisions

- **DEC-1:** The `rabbit` species profile already existed (Migration 007 seeded it
  as an inactive "Future module"). Milestone 1 **activates** it in-place rather
  than inserting a new row — avoids a `species_key` unique-constraint violation
  and keeps the row owned by its originating migration.
