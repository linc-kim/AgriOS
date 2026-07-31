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

## Milestone E — Mortality, Health, Finance P&L & Sustainability · commit `07fd529`

Finance P&L contract (below, §Finance → P&L computation) written & verified **before** any Finance code.

| Field | Detail |
|---|---|
| **Spec sections** | Part 3 §17 (mortality); Part 4 §14 (Sustainability), §15 (Health Monitoring), §16 (finance/reporting); Part 7 §10 (financial analytics), §20 (sustainability metrics) |
| **Migrations** | `064_bsf_mortality` (down_revision 063; round-trips) — 1 table |
| **Models** | `BsfMortalityEvent` |
| **Services/engines** | Engines (pure): `bsf_health_engine` (mortality rate/trend, pattern flag — never a diagnosis), `bsf_sustainability_engine` (waste diverted, conversion efficiency, carbon *estimate* only with a supplied factor), `bsf_finance_engine` (P&L arithmetic; confirmed vs calculated). Services: `bsf_mortality_service` (record → decrement population; health summary), `bsf_finance_service` (**reuse** finance ledger; feedstock/operational cost posting; computed P&L), `bsf_analytics_service` (sustainability) |
| **API routes** | +7 under `/farms/{farm_id}/bsf`: batches/{id}/mortality (record/list), batches/{id}/health, feedstock-lots/{id}/post-expense, finance/expenses, finance/summary, analytics/sustainability. Total BSF routes now **43** |
| **Frontend** | Not started |
| **Tests** | `test_bsf_analytics_engines` (8) unit; `test_bsf_analytics_finance_api` (7) integration — **113 BSF tests pass**; Finance regression (39) green; ruff clean |
| **Integrations** | **Finance ✅ REUSED** — costs post via `finance_service.record_category_expense(flock_id=None)` tagged `Expense.metadata_["module"]="bsf"`; P&L reads revenue from recorded harvest facts + cost from tag-filtered ledger (the verified `aviculture_finance_service` query, retargeted). No BSF finance table; feedstock cost posts **once** (idempotent via `lot.metadata_["expense_id"]`). Audit ✅ |
| **Deviations** | **RBAC refinement (spec-alignment, not a deviation):** `farm_worker` no longer holds `BSF_FINANCE_VIEW`/`BSF_REPORT_VIEW`/`BSF_GROWTH_VIEW` — strategic/financial views are manager/owner concerns (Spec §6, §8-9). Foundation RBAC test updated. No spec deviations. |

## Milestone F — Forecasting, Bottleneck analysis & Executive reporting · commit `39491bb`

Forecasting & Reporting Contract (below) recorded & verified **before** any forecast/report code.

| Field | Detail |
|---|---|
| **Spec sections** | Part 4 §11 (Forecast Engine), §13 (Bottleneck Engine), §16 (Reporting composes, not recalculates); Part 7 §11–13 (growth/bottleneck/forecasting analytics), §18–19 (reporting, executive dashboards) |
| **Migrations** | None — reporting is computed on demand, nothing stored (Spec Part 3 §20) |
| **Models** | None new |
| **Services/engines** | Engines (pure): `bsf_forecast_engine` (linear flow/stock projections, always `forecast`-labelled + method/assumptions/confidence/limitations), `bsf_bottleneck_engine` (severity-ranked constraints w/ evidence + action), `bsf_score_engine` (bounded 0–100 composite scores; growth `unavailable`). Service: `bsf_reporting_service` (composes engines + Part-5 finance/sustainability into the executive dashboard, forecast bundle, CSV export) |
| **API routes** | +4 under `/farms/{farm_id}/bsf/reports`: dashboard, forecast, bottlenecks, production.csv. Total BSF routes now **47** |
| **Frontend** | Not started |
| **Tests** | `test_bsf_forecast_bottleneck_score_engines` (9) unit; `test_bsf_reports_api` (7) integration — **129 BSF tests pass**; ruff clean |
| **Integrations** | **Reporting/Analytics REUSED** — composes existing `bsf_*_engine` outputs + Part-5 services; CSV via platform `Response`/`text/csv` (as `aviculture_reports`). **No parallel reporting framework, no recomputation.** Dashboard exposes `recorded_facts` + `analytics` blocks → full traceability for ARIA/Mission Control/users. Audit — read-only, none needed |
| **Deviations** | None. **Growth score is `unavailable`** (not faked) pending the Growth Planner milestone. Farm-wide capacity utilisation is `unknown` on the dashboard (no aggregate unit-capacity roll-up yet) — a known gap, not a fabricated value. |

## Milestone G — Growth Planner (platform-level, canonical) · commit `a0db832`

Growth Planner Contract (below) recorded & verified **before** implementation.

| Field | Detail |
|---|---|
| **Spec sections** | Part 4 §12 (Growth Planner Engine); Part 5 §5–7 (building/adaptive plans, progress); Part 6 §3–7 (planner vs Mission Control, discovery, roadmap, adaptive revisions, tracking) |
| **Migrations** | `065_growth_planner` (down_revision 064; round-trips) — 4 **platform** tables (`growth_plan`, `growth_goal`, `growth_milestone`, `growth_plan_revision`) |
| **Models** | `app/models/growth.py`: `GrowthPlan`, `GrowthGoal`, `GrowthMilestone`, `GrowthPlanRevision` — **NOT `bsf_`-prefixed**; `module` discriminator for cross-module reuse |
| **Services/engines** | Engine (pure): `growth_planner_engine` (goal_progress, required_run_rate, realism_verdict, milestone_rollup, diff_revisions). Services: `growth_planner_service` (platform; provider registry, revision-on-every-mutation, compare), `bsf_growth_provider` (BSF "actual" from recorded harvest/biomass/revenue facts). Reporting now feeds the primary plan's progress into the dashboard **growth score** (was `unavailable`) |
| **API routes** | +8 under `/farms/{farm_id}/bsf/growth`: plans (list/create/detail/patch/archive), milestones/{id} status, revisions, compare. Total BSF routes now **55** (8 growth) |
| **Frontend** | Not started |
| **Tests** | `test_growth_planner_engine` (9) unit; `test_bsf_growth_api` (7) integration — **145 tests pass** (module + planner); migration round-trips; ruff clean |
| **Integrations** | **New platform capability** (no existing planner to reuse — verified `aria_planning`=forecast helpers, `Mission`=Mission Control). Reuses the `MissionRevision` versioning pattern, `audit_service`, RBAC (`BSF_GROWTH_VIEW/EDIT`), farm-scoping. ARIA/Mission Control will *recommend* changes (later milestone) but **only explicit user calls mutate a plan** — no auto-overwrite |
| **Deviations** | None. **Cross-module by design** (per instruction): the planner is the canonical long-term-growth store for all future Greena modules via the `module` key + per-module metric providers — not a BSF-specific planner. |

## Milestone H — ARIA & Mission Control integration · commit `__H__`

ARIA & Mission Control Contract (below) recorded & verified **before** implementation. **Final backend milestone.**

| Field | Detail |
|---|---|
| **Spec sections** | Part 6 (whole — ARIA/Mission Control/Growth Planner integration); Part 5 §8–13 (bottlenecks, daily execution, ARIA advisor, evidence-based recs, honesty); Part 4 §12 explain-layer |
| **Migrations** | None — intelligence/ARIA read the deterministic engines; nothing stored |
| **Models** | None new |
| **Services/engines** | `bsf_intelligence` (PURE briefing — reads dashboard/forecast/growth/bottlenecks, emits evidence-citing Insights, recomputes nothing); `bsf_aria_service` (deterministic-first Q&A; reuses `ai_provider` + `ai_settings_service`; bounded context; read-only); `mission_control_data.bsf_briefing` (orchestration) |
| **API routes** | +3: `POST/GET /bsf/aria/ask|context` (`AI_QUERY`/`AI_INSIGHT_VIEW`), `GET /mission/bsf/briefing` (`AI_INSIGHT_VIEW`). Total BSF routes **58** |
| **Frontend** | Not started |
| **Tests** | `test_bsf_intelligence` (4) unit; `test_bsf_aria_mission_api` (6) integration — Module 16 suite: **95 unit + 61 integration pass**; mission/aviculture regression green; ruff clean |
| **Integrations** | **ARIA/Mission Control REUSED** — platform `ai_provider` (offline-grounded), `ai_settings_service` (usage log), `mission_control_data`, `InsightOut`/`InsightEvidenceOut` schemas. Poultry/aviculture AI untouched (extended). ARIA reads the Growth Planner progress; **never mutates a plan** (read-only routes; verified in test). Every insight/answer cites `evidence`/`sources` + honesty label |
| **Deviations** | None. Cross-module Mission Control roll-up (BSF + aviculture + future in one view) is a **documented future enhancement** — each module exposes its own `/mission/{module}/briefing` today, all consumed identically. |

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

#### P&L computation (Milestone E) — verified against `aviculture_finance_service`
- **Cost posting mechanism (reuse, verified):** `finance_service.record_category_expense(
  db, farm_id, flock_id=None, category_slug, amount, description, user, date)` returns an
  `Expense`; the caller then tags `expense.metadata_["module"] = "bsf"` (+ source ids) and
  flushes — exactly the Aviculture pattern (`Expense` carries `metadata_` JSONB from
  `AGRIOSBase`). No BSF cost table.
- **Idempotency (verified requirement):** a feedstock lot posts its cost **once** — the
  lot stores the resulting `expense_id`; re-posting is a no-op. The source BSF record id is
  the dedup key.
- **P&L read model — every figure traces to a stored fact, confirmed vs projected:**
  - *Revenue (CONFIRMED / recorded fact):* `Σ bsf_harvest_event.revenue_amount` — BSF-owned
    facts. Never from `revenue_records`.
  - *Operating cost (CONFIRMED / recorded fact):* `Σ Expense.amount WHERE farm_id=? AND
    metadata_["module"].astext='bsf'` — the shared ledger, filtered by tag (the exact
    `aviculture_finance_service.finance_summary` query, retargeted to `'bsf'`).
  - *Gross profit / cost-per-kg / ROI (CALCULATED):* derived from the two confirmed sums +
    recorded harvest mass; each output honesty-labelled and citing its inputs.
  - *Projected revenue / break-even (FORECAST):* clearly labelled projections from the
    Forecast engine (Milestone F) — never mixed into the confirmed figures.
  - No value is stored as a competing snapshot; the P&L is computed on demand (Spec Part 3
    §20). Confirmed financial records and module-level projections are separate fields with
    distinct honesty labels (Spec Part 1 §8, Part 9 §17).
- **No platform expansion:** uses existing slugs (`feed_purchase` for feedstock, `labour`,
  `utilities` if present else `other`) and the existing `metadata_` column; Finance is not
  extended.

### Deviations captured here
1. **BSF revenue is a recorded fact, not a `revenue_records` row** — forced by the
   frozen flock-only revenue/snapshot model; avoids inventing a `flock_id`. (Same as
   Aviculture.)
2. **No new movement type added** — `adjustment` is reused for produced-goods inbound;
   the platform is not extended.

---

## Forecasting & Reporting Contract (authoritative; recorded before Milestone F code)

Governs the Forecast/Bottleneck engines and the executive reporting layer. Reuses
the platform's honesty-label convention (from `analytics_engine`) and export
mechanism (FastAPI `Response`, CSV) — **no parallel reporting/analytics framework**.

### Output classification (every reported figure carries exactly one)
| Class (spec) | Engine label | Meaning | Example |
|---|---|---|---|
| **Recorded** | `recorded` | A stored fact, unmodified | Σ harvest revenue; total feed logged |
| **Calculated** | `calculated` | Deterministic from stored facts only | FCR, gross profit, health/production score |
| **Forecast** | `forecast` | A model projection of a future value | projected biomass/harvest/revenue at horizon |
| **Estimated** | `estimate` | Needs an assumption supplied by user/config | carbon diversion (emission factor), any user-set ratio |
| *(missing)* | `unknown` / `unavailable` | Inputs absent — never guessed | forecast with no history window |

### Rules
- **Forecasts are never presented as confirmed.** Every forecast field is labelled
  `forecast` and additionally carries `method`, `assumptions[]`, `confidence`
  (low/medium/high from the count of recorded observations) and `limitations[]` —
  mirroring `analytics_engine.population_forecast`. A dashboard never places a
  forecast in a "recorded" or "confirmed" position.
- **Estimates declare their assumption.** An `estimate` figure is produced only when
  the required assumption (e.g. emission factor, horizon) is explicitly supplied;
  otherwise the figure is `unknown`. No default assumption is invented.
- **Traceability — dashboards expose facts AND analytics.** The executive dashboard
  returns a `recorded_facts` block (raw counts/sums straight from stored rows)
  alongside the `analytics` block (calculated + forecast). Every derived figure cites
  its inputs in `detail`, so ARIA / Mission Control / users can trace any conclusion
  back to the recorded rows that produced it (Spec Part 1 §8, Part 7 §2, Part 9 §17).
- **Composite scores are calculated, bounded, and degrade to unknown.** Health/
  production/financial/sustainability scores are deterministic functions of recorded
  ratios (0–100), labelled `calculated`, citing their formula; missing inputs →
  `unknown` (never a filler score). The **growth score is `unavailable`** until the
  Growth Planner milestone supplies a goal — not faked.
- **Reuse, not replacement.** The reporting service *composes* the existing
  `bsf_*_engine` outputs and the Part-5 finance/sustainability services; CSV export
  uses the platform `Response`/`text/csv` pattern (as `aviculture_reports`). No new
  report store, no recomputation of figures the engines already produce (Spec Part 4
  §16 "compose … rather than recalculating").
- **Scoping:** all reads are farm-scoped; forecasts/scores are computed on demand and
  never stored (Spec Part 3 §20).

---

## Growth Planner Contract (authoritative; recorded before Milestone G code)

The Growth Planner is built as a **platform-level, cross-module** capability — the
canonical long-term-growth store for BSF *and* future Greena agricultural modules
(Spec Part 4 §12, Part 5 §5-7, Part 6 §3-7). Verified: no existing platform planner
to reuse (`aria_planning` = pure forecasting helpers; `Mission`/`MissionRevision` =
Mission Control's strategic-initiative object, semantically distinct). It reuses the
`MissionRevision` versioning pattern rather than inventing a new one.

### Shape (generic, NOT `bsf_`-prefixed)
- New platform tables (migration 065): `growth_plan`, `growth_goal`, `growth_milestone`,
  `growth_plan_revision`. Farm-scoped (org isolation via `farms.organization_id`) with a
  **`module` discriminator** (`'bsf'`, later `'aviculture'`, `'poultry'`, …) so every
  module shares one planner. Models live in `app/models/growth.py`; the engine
  (`growth_planner_engine`) and service (`growth_planner_service`) are platform-level.
- **Recorded domain objects, not AI text (Spec discipline):** goals (`metric_key`,
  `baseline_value`, `target_value`, `unit`, `target_date`, `status`), milestones
  (`title`, `sequence`, `target_date`, `status`, `expected_impact`, `dependencies`) and
  progress are **structured rows**, never free-form AI-generated prose. ARIA may *draft*
  a plan, but what is stored is deterministic domain data.

### Rules
- **Version history is mandatory & immutable.** Every plan/goal/milestone mutation writes
  a `growth_plan_revision` (`revision_number` unique per plan, `reason`, `trigger`,
  `snapshot` JSONB of the full plan state) — mirroring `MissionRevision`. Revisions are
  never edited; any two are comparable via `growth_planner_engine.diff_revisions`.
- **Planned vs actual uses recorded operational data only.** "Actual" is supplied by a
  **per-module metric provider** registered with the planner
  (`register_metric_provider(module, fn)`); the BSF provider reads recorded reporting
  facts (harvest/biomass/revenue). The engine computes progress %/variance/status
  deterministically; a metric with no provider or no data is `unknown` — never invented.
- **Deterministic; advisors never overwrite.** The engine + service are deterministic.
  ARIA and Mission Control may surface *recommendations* (separate suggestion objects),
  but **only an explicit user action mutates a plan** — no automatic plan overwrite
  (Spec Part 6 §6, §10-11). Realism checks (feasible/ambitious/unrealistic) are
  deterministic and evidence-based; ARIA explains them, it does not enforce them.
- **Output classification** follows the Forecasting & Reporting Contract: baseline/target
  are `recorded`; progress %/variance/required-rate are `calculated`; projected
  completion dates are `forecast`; anything needing a user assumption is `estimate`.
- **Ownership & reuse.** The platform owns the `growth_*` tables/engine/service; each
  module owns its metric provider and its own permission-guarded API surface (BSF uses
  `BSF_GROWTH_VIEW`/`BSF_GROWTH_EDIT` under `/farms/{id}/bsf/growth/*`). No parallel
  planning store; audit/RBAC/farm-scoping reused.
- **Unlocks** the executive dashboard's growth score (was `unavailable` in Milestone F).

---

## ARIA & Mission Control Contract (authoritative; recorded before Milestone H code)

The intelligence layer *explains and orchestrates* the deterministic engines — it
never becomes a source of truth (Spec Part 6, Part 5 §8-13). Reuses the platform
AI router and Mission Control patterns (verified against `aviculture_aria_service`
/ `aviculture_intelligence` / `mission_control_data`); no parallel AI system.

### Hard separations (enforced in code + tests)
- **Deterministic engines are the ONLY source of calculations.** ARIA and the
  intelligence briefing *read* engine outputs; they never recompute a figure.
- **Growth Planner is the source of plans & progress.** ARIA/Mission Control read
  plan progress; **ARIA never mutates a plan** (no write path — `ask`/`context`
  are read-only; the only plan writes remain the explicit `bsf_growth` user calls).
- **Mission Control orchestrates.** `mission_control_data.bsf_briefing` *gathers*
  the BSF deterministic outputs (dashboard, forecast, growth progress, bottlenecks)
  and hands them to the pure `bsf_intelligence.build_briefing`; it owns no business
  logic. (Cross-module roll-up across BSF + aviculture + future modules is a
  documented future enhancement; each module exposes its own briefing today.)
- **ARIA explains / summarises / recommends / answers — never decides.** No
  autonomous action, no plan overwrite.

### Rules
- **Every AI output references its source.** Each briefing `Insight` carries
  `evidence[]` = `{source (dotted engine path), value, fact_type}`; every ARIA
  answer carries `sources[]` + a `fact_type` honesty label
  (`recorded`/`calculated`/`forecast`/`ai_suggestion`/`unavailable`).
- **Deterministic-first Q&A.** Factual questions are answered directly from
  recorded facts/engine outputs with **no LLM**; only open explanation routes to
  the AI router, always with a grounded offline fallback (`ai_provider.complete`).
  The LLM sees only a bounded context snapshot — never the DB.
- **Low confidence / assumptions are exposed, not hidden.** Insights carry
  `confidence` + `limitations`; ARIA labels uncertain answers and degrades to
  `unavailable`/offline rather than presenting certainty. No fabricated data.
- **Reuse.** `ai_provider` (+ offline fallback), `ai_settings_service` (usage log),
  `mission_control_data`, `InsightOut`/`InsightEvidenceOut` schemas, RBAC
  (`AI_QUERY` for ask, `AI_INSIGHT_VIEW` for reads). Poultry/aviculture AI code is
  untouched (extended, not modified).

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
| Reuse Finance (no duplicate ledger) | ✅ | `bsf_finance_service` → `record_category_expense` + tag; computed P&L (`bsf_finance_engine`) |
| Sustainability metrics (Part 4 §14, Part 7 §20) | ✅ | `bsf_sustainability_engine` |
| Health / mortality monitoring (Part 3 §17, Part 4 §15) | ✅ | `bsf_health_engine` (patterns, not diagnosis) |
| Confirmed records vs projections labelled | ✅ | P&L `recorded`/`calculated`; forecasts `forecast` (`bsf_forecast_engine`); estimates `estimate` |
| Forecasting (Part 4 §11, Part 7 §13) | ✅ | `bsf_forecast_engine` — never presented as confirmed |
| Bottleneck analysis (Part 4 §13, Part 7 §12) | ✅ | `bsf_bottleneck_engine` — ranked, evidenced |
| Executive reporting / dashboards (Part 7 §18–19) | ✅ | `bsf_reporting_service` — facts + analytics, CSV reuse |
| Reuse Inventory | ✅ | `bsf_harvest_service` → `inventory_service.record_movement` (adjustment) |
| Harvest / frass tracking & yield (Part 2 §11–12, Part 4 §8–9) | ✅ | `bsf_harvest_engine`, `bsf_frass_engine` |
| Reuse Reminders/Notifications | ◻ Automation | — |
| ARIA integration | ✅ | `bsf_aria_service` (deterministic-first, read-only, reuses AI router) |
| Mission Control integration | ✅ | `bsf_intelligence` + `mission_control_data.bsf_briefing` (`/mission/bsf/briefing`) |
| Growth Planner integration | ✅ | platform `growth_*` tables + `growth_planner_engine`/`_service` + BSF provider; canonical, cross-module |
| Frontend workflows | ◻ frontend milestone | — |
| Performance / accessibility / QA audit (Part 9) | ◻ final | — |
