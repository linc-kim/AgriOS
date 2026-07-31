# Module 16 — Black Soldier Fly (BSF) — Implementation Ledger

Running record of Module 16 delivery against the authoritative BSF specification
(Parts 1–10). One section per milestone. Kept in lock-step with the code so the
implementation never drifts from the spec.

**Module model:** batch-centric (aggregate root = Production Batch). Template =
Module 15 Aviculture. All tables `bsf_`-prefixed; farm-scoped (org isolation via
`farms.organization_id`); catalog carries nullable `organization_id`
(NULL = global). Deterministic-first: pure engines compute, services orchestrate,
ARIA/Mission Control explain/prioritise. Reuse-first for all platform services.

**Cadence:** milestone-based; local commits per milestone on `phase-2-auth`; no
push/deploy without explicit per-action approval.

**Legend — integration points:** ✅ done · ◻ planned (with milestone) · — n/a.

---

## Milestone A — Part 1: Foundation · commit `a799f10`

| Field | Detail |
|---|---|
| **Spec sections** | Part 1 (mission/philosophy); Part 2 §3–5, §17 (structure, batch-centric, multi-tenancy); Part 3 §1–10, §18, §21–23 (domain model, lineage, audit, tenancy); Part 8 §4–5 (org ownership, RBAC) |
| **Migrations** | `061_bsf_foundation` (down_revision 060) — registers `species_profiles` row `species_key='bsf'`; 8 tables; round-trips |
| **Models** | `BsfSpecies`, `BsfProductionUnit`, `BsfColony`, `BsfBatch` (root), `BsfLifecycleEvent`, `BsfBatchEvent`, `BsfBatchMedia`, `BsfBatchDocument` (`app/models/bsf.py`) |
| **Services/engines** | — (foundation only) |
| **API routes** | — |
| **Frontend** | Not started (deferred to a dedicated frontend milestone) |
| **Tests** | `tests/unit/test_bsf_foundation.py` — 14 passing (enum contracts, model surface, soft-delete, RBAC grading) |
| **Integrations** | RBAC ✅ (23 `BSF_*` perms in `permissions.py`); Files ◻ (media/document rows reference platform store); ARIA/Mission Control reuse platform `AI_QUERY`/`AI_INSIGHT_VIEW` ✅ |
| **Deviations** | None |

## Milestone B — Part 2: Batch operational backbone · commit `da1479b`

| Field | Detail |
|---|---|
| **Spec sections** | Part 2 §5–6 (batch, lifecycle); Part 3 §7–10, §19–20 (batch, lifecycle history, split/merge, relationships, computed-vs-stored); Part 4 §1–6, §18–19 (backend philosophy, service architecture, Batch/Lifecycle/Production engines, API design, error handling) |
| **Migrations** | None (uses Part 1 schema) |
| **Models** | None new |
| **Services/engines** | Engines (pure): `bsf_lifecycle_engine`, `bsf_production_engine`. Services: `bsf_service` (species/units/colonies), `bsf_batch_service` (create/advance/move/split/merge/terminate/metrics) |
| **API routes** | 21 under `/farms/{farm_id}/bsf` — species, production-units, colonies, batches (+ advance/move/split/merge/terminate/lifecycle/timeline); registered in `api/v1/router.py` |
| **Frontend** | Not started |
| **Tests** | `test_bsf_lifecycle_engine` (14) + `test_bsf_production_engine` (12) unit; `test_bsf_batch_api` (16) integration — all passing (84 green incl. aviculture regression slice) |
| **Integrations** | Audit ✅ (`audit_service.log_action` on every write); Auth/RBAC ✅ (`require_farm_access` + `require_permission`); Finance ◻ (Part-7 group); Inventory ◻ (Part-5 group); Reminders/Notifications ◻ (Part-4 group / automation); ARIA ◻; Mission Control ◻ |
| **Deviations** | None. "Batch Engine" (Spec Part 4 §4) is realised as service orchestration (`bsf_batch_service`) delegating pure maths to `bsf_lifecycle_engine`/`bsf_production_engine`, rather than a third engine file — same layering Aviculture uses; all §4 responsibilities covered. |

## Milestone C — Feedstock, Feeding & Environment · commit `707985a`

| Field | Detail |
|---|---|
| **Spec sections** | Part 2 §8–10 (feedstock, feeding, environmental); Part 3 §11–13 (feedstock lot, feeding events, environmental records); Part 4 §7, §10 (Feed Conversion Engine, Environment Engine); Part 7 §5–6, §9 (feedstock/feed-conversion/environmental analytics — deterministic core) |
| **Migrations** | `062_bsf_feeding_environment` (down_revision 061; round-trips) — 3 tables |
| **Models** | `BsfFeedstockLot`, `BsfFeedingEvent`, `BsfEnvironmentalReading` |
| **Services/engines** | Engines (pure): `bsf_feed_conversion_engine` (FCR, bioconversion, waste-processed, utilisation, efficiency-trend), `bsf_environment_engine` (range assessment, severity, stability). Services: `bsf_feedstock_service` (lots + feeding + FCR summary), `bsf_environment_service` (readings + assessment) |
| **API routes** | +10 under `/farms/{farm_id}/bsf`: feedstock-lots (list/create/get/patch), batches/{id}/feedings (record/list), batches/{id}/feed-conversion, environment/readings (list/record), environment/units/{id}/assessment. Total BSF routes now **31** |
| **Frontend** | Not started |
| **Tests** | `test_bsf_feed_conversion_engine` (8) + `test_bsf_environment_engine` (8) unit; `test_bsf_feeding_environment_api` (10) integration — **82 BSF tests pass**; ruff clean |
| **Integrations** | Audit ✅; Finance ◻ (feedstock `cost` captured on the lot now; posting to shared ledger in Part-7 group); Inventory ◻ (Part-5 group); Reminders/Notifications — threshold *detection* deterministic here, *emission* deferred to Automation milestone (see deviation) |
| **Deviations** | **Environmental alert emission → Automation milestone (P9).** Spec Part 2 §10 / Part 4 §10 require threshold violations to trigger Reminder/Notification. The Environment Engine computes violations deterministically now (returned live on each recorded reading); actual Reminder/Notification materialisation is centralised in the later Automation milestone (idempotent, `metadata.module='bsf'`, dedup keys) — mirroring Aviculture, and avoiding `create_notification`'s independent-commit coupling and duplicated alert logic. Capability is fully delivered; only its trigger seam moves. |

## Milestone D — Harvest, Frass & Inventory reuse · commit `afa281c`

Integration contract (below) was written and verified **before** any Finance/Inventory code.

| Field | Detail |
|---|---|
| **Spec sections** | Part 2 §11–12 (harvest, frass); Part 3 §15–16 (harvest events, frass production); Part 4 §8–9 (Harvest Engine, Frass Engine); Part 8 §15 file/inventory reuse principle |
| **Migrations** | `063_bsf_harvest_frass` (down_revision 062; round-trips) — 2 tables |
| **Models** | `BsfHarvestEvent` (revenue as recorded fact; soft inventory refs), `BsfFrassProduction` |
| **Services/engines** | Engines (pure): `bsf_harvest_engine` (readiness, expected/actual yield, quantity validation), `bsf_frass_engine` (moisture-adjusted dry weight, frass yield/ratio). Service: `bsf_harvest_service` (harvest + frass; optional Inventory routing; batch close/biomass decrement) |
| **API routes** | +5 under `/farms/{farm_id}/bsf`: batches/{id}/harvests (record/list), batches/{id}/harvest-readiness, batches/{id}/frass (record/list). Total BSF routes now **36** |
| **Frontend** | Not started |
| **Tests** | `test_bsf_harvest_frass_engines` (8) unit; `test_bsf_harvest_frass_api` (8) integration — **98 BSF tests pass**; Inventory regression (13) green; ruff clean |
| **Integrations** | **Inventory ✅ REUSED** — `inventory_service.record_movement` (inbound `adjustment`), item quantity verified to increase, movement `direction=1`, no `stock_in` (so no expense double-book); BSF stores only `inventory_movement_id`. **Finance ✅ contract-honoured** — harvest revenue recorded as a fact (no `revenue_records` row, no expense written); Audit ✅ |
| **Deviations** | (1) **Harvest revenue is a recorded fact**, not a `revenue_records` row — forced by the frozen flock-scoped revenue ledger (contract §Finance). (2) **Harvested output uses an existing Inventory category** (catch-all `miscellaneous`; farmer's choice) — the platform has no "produce/output" category, but a catch-all suffices, so Inventory is **not** expanded (per instruction). A dedicated category is a possible future platform enhancement, not a BSF requirement. |

---

## Integration Contract — Finance & Inventory (authoritative; verified against platform code before Milestone D)

Verified against `finance_service`, `inventory_service` and the frozen finance
model. **No BSF-specific finance/stock logic is created; no platform capability
is expanded.** Where a platform constraint blocks reuse, BSF owns the fact and the
constraint is recorded as a deviation — it is never worked around by duplication.

### Inventory (reuse `inventory_service.record_movement`)
- **Reused pattern:** harvested larvae/prepupae and collected frass enter stock via
  `inventory_service.record_movement(db, farm, MovementCreate(...), user)` with
  `movement_type="adjustment"` (an inbound type: `_IN_TYPES = {stock_in, transfer_in,
  return, adjustment}`). **Never `stock_in`** — `stock_in` auto-books a purchase
  Expense (`inventory_service` lines ~340), which would double-count feedstock cost.
  `adjustment` adds quantity with no expense and no supplier requirement.
- **Ownership:** Inventory OWNS the `InventoryItem` and `InventoryMovement`. BSF OWNS
  `bsf_harvest_event` / `bsf_frass_production` and merely *references* the movement.
  The farmer supplies an existing `inventory_item_id`; BSF never creates items or a
  parallel stock table.
- **Cross-link / traceability:** the movement carries `reference = batch_number`; the
  returned `move.id` is stored on the BSF record as `inventory_movement_id`.
- **Idempotency:** the BSF harvest/frass record is the idempotency key — a movement is
  created at most once per record (guarded: skip if `inventory_movement_id` already
  set), inside the same DB transaction as the record. No automatic cross-module retry
  path exists in this milestone (the scheduled/reminder path with dedup_keys is the
  Automation milestone).
- **Scoping:** `record_movement` takes the BSF farm's `Farm` object; `_get_item`
  validates the item belongs to that farm → no cross-tenant movement is possible.

### Finance (reuse `finance_service`; do NOT duplicate the ledger)
- **Revenue — platform constraint:** `finance_service.log_revenue` **requires a valid
  `flock_id`** (validated against `flocks`); the finance dashboard/snapshot is
  flock-scoped (frozen DB-07). BSF has no flock. **Therefore BSF harvest revenue is a
  RECORDED FACT on `bsf_harvest_event`** (`revenue_amount`, `currency`, `buyer_name`),
  not posted to `revenue_records`. Consuming these facts into a P&L summary is the
  Part-7 finance milestone (computed, read-only — never a competing snapshot). This is
  the identical decision taken for Aviculture (`aviculture_finance_service`).
- **Cost:** operational costs post to the SHARED `expenses` ledger via
  `finance_service.record_category_expense(db, farm_id, flock_id=None, slug, amount,
  description, user, date)` (flushes in the caller's txn) — system slugs
  `feed_purchase` / `labour` / `other`. Feedstock `cost` is already a recorded fact on
  `bsf_feedstock_lot`; posting consumption/production cost to the ledger lands in the
  Part-7 finance milestone. Milestone D posts **no** expenses (harvest is output, not a
  purchase) and books **no** revenue.
- **Ownership:** Finance OWNS `Expense` / `RevenueRecord`. BSF OWNS its harvest/frass/
  feedstock facts and, in Part-7, calls finance services (never writes those tables
  directly) and *computes* the BSF P&L from recorded facts.
- **Idempotency:** cost postings (Part-7) will use `record_category_expense` once per
  source BSF record, tagged in the description for attribution; the source record id is
  the dedup key.
- **Scoping:** every finance call passes the BSF farm's `farm_id` and `flock_id=None` →
  costs are farm-scoped and never attributed to another tenant's flock.

### Deviations captured here
1. **BSF revenue is a recorded fact, not a `revenue_records` row** — forced by the
   frozen flock-only revenue/snapshot model; avoids inventing a `flock_id`. (Same as
   Aviculture.)
2. **No new movement type added** — `adjustment` is reused for produced-goods inbound;
   the platform is not extended.

---

## Cross-cutting spec coverage tracker

| Requirement | Status | Where |
|---|---|---|
| Deterministic-first calculations | ✅ ongoing | pure `bsf_*_engine` modules (lifecycle, production, feed-conversion, environment) |
| Honesty labels (fact/calculated/forecast/unknown/…) | ✅ ongoing | engine outputs `{label,value,detail}` |
| Feed conversion / waste conversion (Part 2 §13, Part 4 §7) | ✅ | `bsf_feed_conversion_engine` |
| Environmental threshold monitoring (Part 2 §10) | ✅ detection | `bsf_environment_engine`; emission → Automation |
| Organisation isolation / RBAC | ✅ | `farm_id` scoping + `BSF_*` perms |
| Audit log immutability | ✅ | `audit_service.log_action` |
| Complete lineage / traceability | ✅ | lifecycle events, batch events, split/merge links |
| Reuse Finance (no duplicate ledger) | ◻ Part-7 P&L (revenue fact captured) | contract §Finance |
| Reuse Inventory | ✅ | `bsf_harvest_service` → `inventory_service.record_movement` (adjustment) |
| Harvest / frass tracking & yield (Part 2 §11–12, Part 4 §8–9) | ✅ | `bsf_harvest_engine`, `bsf_frass_engine` |
| Reuse Reminders/Notifications | ◻ Automation | — |
| ARIA integration | ◻ | — |
| Mission Control integration | ◻ | — |
| Growth Planner integration | ◻ | — |
| Frontend workflows | ◻ frontend milestone | — |
| Performance / accessibility / QA audit (Part 9) | ◻ final | — |
