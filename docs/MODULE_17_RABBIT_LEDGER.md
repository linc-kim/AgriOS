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

### Milestone 2 — Registry & Housing (GMIS Milestone B/C) — ✅ DONE (local, unpushed)

- **Pure engine** `app/services/rabbit_housing_engine.py` (Housing Capacity):
  `compute_occupancy` (occupied recorded, available/utilization calculated,
  unknown capacity → unknown never guessed), `is_overcrowded` (only vs recorded
  capacity), `rollup` (hierarchy aggregate; excludes unknown-capacity children
  from the total and counts them). Honesty-labelled throughout. 8 unit tests.
- **Service** `app/services/rabbit_service.py` — catalog (breeds org-level,
  bloodlines farm-level), rabbit register (auto `RB-#####`, duplicate ear-tag
  guard), list (filters + pagination), detail (+ parent refs), update (self-parent
  guard; full pedigree-cycle check deferred to the Breeding engine), move between
  cages, archive/restore, transfer/sell/death (terminal guards), timeline, media,
  documents. Every mutation appends a `rabbit_event` + audit-log entry.
- **Service** `app/services/rabbit_housing_service.py` — CRUD for all 5 levels
  with parent validation; cage occupancy derived on read via the engine;
  `housing_summary` farm roll-up with overcrowded-cage list (single grouped
  occupancy query — no N+1).
- **Schemas** `app/schemas/rabbit.py`; **endpoints** `app/api/v1/endpoints/
  rabbit.py` (registry+catalog) + `rabbit_housing.py` (hierarchy+occupancy+summary)
  — **38 routes** under `/farms/{id}/rabbit` (registered in the API router).
- **Tests:** 8 engine unit + 22 integration (registry lifecycle/RBAC/isolation +
  housing hierarchy/occupancy/overcrowding/RBAC). Ruff clean; aviculture+BSF
  regression green.
- **Contract:** sale/transfer/death record herd facts + timeline only; revenue
  posting to Finance is deferred to the Sales/Finance milestone (mirrors avi/bsf).

### Milestone 3 — Breeding, Pedigree & Genetics — 🚧 CONTRACTS (recorded before coding)

Architectural contracts fixed before implementation (GMIS §11.3):

- **CON-M3-1 — Reuse the platform Pedigree engine.** `app/services/pedigree_engine.py`
  (built for Aviculture, Module 15 Part 4) is a PURE, species-agnostic engine
  computing Wright's inbreeding `F`, kinship, coefficient of relationship,
  ancestry trees, founders and `would_create_cycle` from a plain
  `{id: (sire_id, dam_id)}` map. Rabbit **reuses these primitives directly** — the
  correctness-critical genetics math is NOT reimplemented. The rabbit breeding
  service builds the parent map from `rabbit.sire_id/dam_id` and delegates.
- **CON-M3-2 — Thin rabbit genetics wrapper only.** `pedigree_engine.compatibility()`
  hard-codes male/female sex semantics; rabbits use buck/doe. A small PURE
  `rabbit_genetics.py` maps buck→male/doe→female and adds rabbit-domain messaging +
  inbreeding-risk banding, reusing `relatedness`/`inbreeding_coefficient`. No
  duplicate Wright's implementation.
- **CON-M3-3 — Rabbit-domain deterministic engine.** `rabbit_breeding_engine.py`
  (PURE) owns rabbit reproduction math: breeding-eligibility rules,
  expected-kindling-date (gestation) + gestation progress, litter performance,
  doe productivity, buck fertility, herd reproduction summary, breeding-value
  ranking. Honesty-labelled (recorded/calculated/forecast/estimated/unknown).
- **CON-M3-4 — Gestation is data-driven.** Default rabbit gestation = **31 days**;
  overridable per breed via `rabbit_breed.profile["gestation_days"]`. Planned
  kindling dates are labelled **forecast**, never recorded fact.
- **CON-M3-5 — Kit → litter link.** Migration 067 adds nullable `rabbit.litter_id`
  (birth litter, SET NULL). Kits created at kindling get `litter_id` + `sire_id`
  (buck) + `dam_id` (doe) so pedigree links flow automatically; kit auto-creation
  is optional (bulk minimal rows in the kindling transaction, reusing the
  `RB-#####` ref generator). Mirrors Aviculture incubation→chick creation.
- **CON-M3-6 — One breeding row per mating attempt; one litter per kindling.**
  `rabbit_breeding` spans service→pregnancy-check→kindling (repeat services linked
  via `repeat_of_id`); `rabbit_litter` is created at kindling and updated through
  foster/weaning. No separate pregnancy/kindling/weaning tables (those are phases,
  not aggregates) — breeding milestones also append to the doe's `rabbit_event`
  timeline. Breeding eligibility is validated before recording a service (Spec Part 4 §6).
- **CON-M3-7 — RBAC.** breeding/litter writes → `RABBIT_BREEDING_MANAGE`;
  breeding/litter reads → `RABBIT_BREEDING_VIEW`; pedigree/genetics reads →
  `RABBIT_PEDIGREE_VIEW`; pedigree-link corrections continue through rabbit update
  (`RABBIT_EDIT`) with the engine's cycle guard.

### Milestone 3 — Breeding, Pedigree & Genetics — ✅ DONE (local, unpushed)

- **Migration `067`** (down_revision 066, single head): `rabbit_breeding` (mating
  cycle: service→pregnancy-check→kindling, `repeat_of_id` self-FK for repeat
  services), `rabbit_litter` (birth stats + foster/wean, `LT-#####`), and adds
  nullable `rabbit.litter_id` (kit→birth-litter link). Round-trips cleanly.
- **REUSE** `pedigree_engine` (Aviculture) for all Wright's math (CON-M3-1);
  `rabbit_genetics.py` is a thin PURE wrapper (buck/doe semantics + risk banding,
  CON-M3-2) — no duplicate genetics math.
- **PURE** `rabbit_breeding_engine.py`: eligibility, gestation forecast/progress
  (default 31d, breed-overridable), litter performance, doe productivity, buck
  fertility, herd reproduction summary, advisory breeding-value ranking. Zero
  denominators → `unknown`, never fabricated.
- **Service** `rabbit_breeding_service.py` (reuses `rabbit_service` helpers): full
  cycle create/service/pregnancy-check/prepare-kindling/kindling (creates litter +
  optional kit rabbit rows with sire/dam/litter links)/close; litter foster +
  weaning (advances kits to `weaner`, doe → `resting`); pedigree, compatibility,
  doe/buck performance, reproduction summary, genetic overview. Eligibility
  validated before service; open-cycle blocks re-breeding; every milestone appends
  a doe timeline event + audit entry.
- **Schemas** extended; **endpoints** `rabbit_breeding.py` = **17 routes** (55
  rabbit routes total). Writes → `RABBIT_BREEDING_MANAGE`; pedigree/genetics reads
  → `RABBIT_PEDIGREE_VIEW`; other reads → `RABBIT_BREEDING_VIEW`.
- **Tests:** 26 engine/genetics unit (incl. textbook full-sib F=0.25) + 9
  integration (full cycle, eligibility, open-cycle guard, kit creation, pedigree,
  compatibility, reproduction summary, genetics, RBAC). Full rabbit suite + avi
  breeding/BSF/mission regression = **107 pass**; ruff clean; app boots (55 routes).

## Deviations / decisions

- **DEC-1:** The `rabbit` species profile already existed (Migration 007 seeded it
  as an inactive "Future module"). Milestone 1 **activates** it in-place rather
  than inserting a new row — avoids a `species_key` unique-constraint violation
  and keeps the row owned by its originating migration.
