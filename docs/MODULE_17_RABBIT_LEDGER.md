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

### Milestone 4 — Growth, Weight & Feed — 🚧 CONTRACTS (recorded before coding)

Verified Inventory contract (`inventory_service.record_movement`): a `consumption`
movement decrements stock and costs the line at the item's weighted-average cost
(`item.avg_cost`) and posts **no new expense** — the expense is booked once at
`stock_in` (category "feed" → finance slug `feed_purchase`). Returns
`(item, movement)`. Item categories include `feed`, `medication`, `vaccines`.

- **CON-M4-1 — Feed reuses platform Inventory; no duplicate inventory.**
  `rabbit_feed_record` is a **domain feeding log only** (who ate, when, how much).
  When a feeding references an Inventory feed item, the service posts a
  `consumption` movement (decrement; **no new expense** — feed was already
  expensed at purchase, so this avoids double-counting, mirroring the BSF
  harvest/adjustment contract). Links are **soft refs** `inventory_item_id` /
  `inventory_movement_id` (no FK — module decoupling). The feed record's `cost` is
  a snapshot allocation (`movement.total_cost` = qty × avg_cost), a RECORDED value
  used for cost-per-rabbit analytics — never re-posted to the finance ledger.
- **CON-M4-2 — Manual feeding allowed (hobby scale).** Feeding without an
  Inventory item records quantity + optional manual cost as a fact; no movement.
- **CON-M4-3 — Weight history is immutable** (Spec Part 3 §9). `rabbit.current_weight_g`
  mirrors the latest recorded weight for display; the weight table is authoritative.
  The Growth engine computes ADG / gain / percentile / deviation deterministically;
  missing data → `unknown`, never fabricated.
- **CON-M4-4 — Feed conversion (FCR)** is calculated only where both feed and
  weight-gain data exist over the same window; otherwise `unavailable`. Expected
  growth curves come from `rabbit_breed.profile` when present (else `unknown`).

### Milestone 4 — Growth, Weight & Feed — ✅ DONE (local, unpushed)

- **Migration `068`** (down_rev 067, single head): `rabbit_weight` (immutable
  measurements + `age_days` snapshot) and `rabbit_feed_record` (feeding log with
  soft Inventory refs). Round-trips cleanly.
- **PURE `rabbit_growth_engine.py`**: ADG, growth series, breed-curve expected
  weight (linear interpolation, unknown outside range), weight analysis
  (gain/deviation), herd percentile. **PURE `rabbit_feed_engine.py`**: FCR
  (unavailable without positive gain), feed summary (totals, cost/kg). Honesty-
  labelled; missing data → unknown.
- **`rabbit_growth_service.py`** (weights immutable; syncs `current_weight_g`;
  growth analysis + same-breed peer percentile) and **`rabbit_feed_service.py`**
  (Inventory reuse per CON-M4-1: `consumption` movement decrements stock, cost
  snapshot, no re-expense; manual feeding supported; FCR via growth gain). Reuse
  `rabbit_service` helpers + `inventory_service.record_movement`.
- **Endpoints** `rabbit_growth.py` = **6 routes** (61 rabbit routes total).
  Weight write → `RABBIT_WEIGHT_LOG`; feed write → `RABBIT_FEED_RECORD`; reads →
  `RABBIT_VIEW` / `RABBIT_FEED_VIEW`.
- **Tests:** 20 engine unit + 9 integration (weight sync, breed-curve deviation,
  manual + Inventory-linked feeding [stock decrement + cost snapshot, no double-
  count], FCR, RBAC). Ruff clean; app boots; regression green incl. Inventory +
  Finance (39) and avi/bsf (120 in the combined rabbit+regression run).

### Milestone 5 — Health, Vaccination & Mortality — 🚧 CONTRACTS (recorded before coding)

Verified platform contracts: `Reminder` (app/models/automation.py) carries JSONB
`metadata_`; Aviculture/BSF create reminders as `Reminder(farm_id, title, notes,
due_at, next_fire_at, priority, created_by, metadata_={"module": <mod>, "kind":
..., "dedup_key": ...})`, deduped by `dedup_key` among open reminders where
`metadata_['module']==<mod>`; the platform scheduler's `run_reminders` fires them
into the Notification engine. Timeline/audit are the shared `rabbit_event` +
`audit_service`. Frozen **§4.4** excludes disease *diagnosis* (see
[[greena-frozen-decisions]]).

- **CON-M5-1 — Vaccinations reuse the platform Reminder engine.** Recording a
  vaccination with `next_due_on` creates a `Reminder` (`metadata.module='rabbit'`,
  `kind='vaccination'`, idempotent `dedup_key`), fired by the platform scheduler →
  Notification engine. **No** rabbit reminder/notification table. The created
  reminder's id is a **soft ref** on `rabbit_vaccination.reminder_id` (no FK).
- **CON-M5-2 — Reuse shared timeline/audit.** Every health/vaccination/mortality
  event appends a `rabbit_event` + `audit_service` entry — no duplicate log tables.
- **CON-M5-3 — §4.4 diagnosis ban preserved.** `rabbit_health_record.diagnosis`
  stores **only a recorded veterinary input** (a fact). The deterministic
  `rabbit_health_engine` never infers a diagnosis — it emits *patterns* (mortality
  / recovery rates, cause & condition frequencies, vaccination compliance) with a
  "pattern, not a veterinary diagnosis" disclaimer; all honesty-labelled and
  traceable to recorded facts.
- **CON-M5-4 — Mortality is the authoritative clinical death record.** Recording
  mortality (RABBIT_HEALTH_LOG) creates one immutable `rabbit_mortality` row and
  transitions the rabbit to `deceased` + timeline `died`. The M2 `/death`
  (RABBIT_TRANSACT) remains a lightweight status-only path. Mortality records are
  immutable (Spec Part 3 §16).
- **CON-M5-5 — Attachments reuse existing `rabbit_document`/`rabbit_media`** (no
  new attachment tables) for vet/lab reports and postmortem photos.

### Milestone 5 — Health, Vaccination & Mortality — ✅ DONE (local, unpushed)

- **Spec sections:** Part 2 §10/§15, Part 3 §11-12/§16, Part 4 §9, Part 7 §7.
- **Migration `069`** (down_rev 068, single head): `rabbit_health_record`
  (chronological clinical events), `rabbit_vaccination` (+ soft `reminder_id`),
  `rabbit_mortality` (immutable, unique per rabbit). Round-trips cleanly.
- **PURE `rabbit_health_engine.py`**: mortality rate / by-cause / monthly trend,
  recovery rate (excludes still-open events), condition frequency, vaccination
  compliance, composite `health_summary` — every block honesty-labelled and
  stamped with the "pattern, not a veterinary diagnosis" disclaimer (§4.4).
- **`rabbit_health_service.py`**: health records, vaccinations, mortality. Reuses
  the platform **Reminder** engine (`_upsert_reminder`, `metadata.module='rabbit'`,
  idempotent `dedup_key`) for vaccination/follow-up due dates; reuses
  `rabbit_service` timeline helpers + `audit_service`. Mortality transitions the
  rabbit to `deceased` and is one-per-rabbit.
- **Endpoints** `rabbit_health.py` = **8 routes** (69 rabbit routes total). Writes
  → `RABBIT_HEALTH_LOG` (owner/manager/worker/vet); reads → `RABBIT_HEALTH_VIEW`.
- **Platform reuse:** Reminder engine (vaccination due), Notification (via
  scheduler), `rabbit_event` timeline, `audit_service`, `rabbit_document`/`_media`
  attachments — no rabbit-specific replacements.
- **Tests:** 12 engine unit + 15 integration (health history, vaccination Reminder
  reuse [linked only when a next dose is due], mortality→deceased + immutability,
  summary disclaimer, RBAC incl. vet-can-log). Full rabbit suite + Automation/
  Reminders + Aviculture-automation + BSF regression = **138 pass**; ruff clean;
  app boots.
- **Decision:** two death paths kept intentionally — M2 `/death` (RABBIT_TRANSACT,
  lightweight status) and M5 `/mortality` (RABBIT_HEALTH_LOG, authoritative
  clinical record). No deviation from spec.

### Milestone 6 — Sales & Finance — 🚧 CONTRACTS (recorded before coding)

Verified Finance contract: `finance_service.record_category_expense(db, farm_id,
flock_id=None, category_slug, amount, description, current_user, expense_date)`
creates an `Expense` under a system category (adds+flushes, no commit) or returns
`None` if the slug/amount is missing. `revenue_records` is **flock-scoped (frozen
DB-07)**. Valid system slugs include `feed_purchase`, `feed_supplements`,
`vaccination`, `medication`, `vet_fees`, `labour`, `electricity`, `water`,
`equipment`, `repairs`, `transport`, `bedding`, `other`. Aviculture/BSF post costs
to the shared ledger tagged `metadata_["module"]=<mod>` and keep revenue as a
recorded fact — **exactly** the pattern reused here.

- **CON-M6-1 — Reuse the shared Finance ledger; no rabbit finance table for costs.**
  Operational costs (vet, labour, housing/equipment, utilities…) post to the shared
  `expenses` ledger via `finance_service.record_category_expense(flock_id=None)` and
  are tagged `metadata_["module"]="rabbit"` for attribution. No modification to the
  Finance platform.
- **CON-M6-2 — Sale revenue is a recorded fact (DB-07).** Because `revenue_records`
  is flock-scoped, rabbit sale revenue is stored on the new `rabbit_sale` table
  (`total_price`) and **never** posted to `revenue_records` — mirroring Aviculture/
  BSF. Sales support live/breeding/pet/meat/fiber/manure types (Spec Part 2 §16).
- **CON-M6-3 — Feed cost = recorded consumption allocation, not a ledger re-post.**
  The rabbit P&L's feed cost is `Σ rabbit_feed_record.cost` (the M4 consumption
  snapshot, a recorded fact). Feed purchases are already expensed once at Inventory
  `stock_in` (untagged), so they are **excluded** from the rabbit-tagged sum — no
  double-count (consistent with CON-M4-1). Other operating costs come from the
  rabbit-tagged ledger.
- **CON-M6-4 — All P&L/unit-economics are computed by a PURE engine**
  (`rabbit_finance_engine`) from figures the service reads from recorded facts;
  nothing is stored as a competing snapshot. Confirmed records (`recorded`) are
  kept distinct from derivations (`calculated`); zero denominators → `unknown`.
- **CON-M6-5 — Permissions reuse.** Sales write → `RABBIT_SALES_RECORD`; sales read
  → `RABBIT_SALES_VIEW`; P&L read → `RABBIT_FINANCE_VIEW`; posting a cost to the
  shared ledger reuses the platform **`FINANCE_RECORD`** permission (owner/manager)
  — no new rabbit finance-write permission is introduced. Recording a sale for an
  active rabbit transitions it to `sold` (the M2 `/sell` transact path remains).

### Milestone 6 — Sales & Finance — ✅ DONE (local, unpushed)

- **Spec sections:** Part 2 §16 (Sales), Part 3 §15 (Sale entity), Part 4 §12
  (Sales & Finance logic), Part 7 §9 (Financial analytics).
- **Migration `070`** (down_rev 069, single head): `rabbit_sale` (revenue fact;
  live/breeding/pet/meat/fiber/manure). Round-trips cleanly. No finance/cost table.
- **PURE `rabbit_finance_engine.py`**: `pnl_summary` (revenue/feed/operating cost
  recorded; total cost, gross, margin, ROI calculated) and `unit_economics`
  (cost/revenue/profit per rabbit, cost per kg sold, profit per litter/doe, feed &
  vet cost %). Honesty-labelled; zero denominators → `unknown`.
- **`rabbit_finance_service.py`**: `record_sale` (revenue fact; transitions an
  active rabbit → sold), `list_sales`, `post_operational_expense` (SHARED ledger
  via `finance_service.record_category_expense`, tagged `metadata.module='rabbit'`),
  `finance_summary` (revenue = Σ sale facts; feed cost = Σ recorded feed-allocation;
  operating cost = rabbit-tagged ledger; vet cost via category join).
- **Endpoints** `rabbit_finance.py` = **4 routes** (73 rabbit routes total). Sales
  write → `RABBIT_SALES_RECORD`; sales read → `RABBIT_SALES_VIEW`; cost posting →
  platform `FINANCE_RECORD` (owner/manager); P&L read → `RABBIT_FINANCE_VIEW`.
- **Finance reuse verification:** no Finance-platform change; costs post through
  `finance_service` only; revenue never written to flock-scoped `revenue_records`
  (DB-07); feed not double-counted (allocation vs stock-in expense). Confirmed by
  green regression: finance flow/analytics + Aviculture-finance + BSF-finance.
- **Tests:** 9 engine unit + 12 integration (sale→sold, product sale, unit-price
  derivation, P&L tracing to recorded facts incl. vet_cost_pct, invalid category
  404, RBAC: worker no cost-post, viewer read-only). Full rabbit + finance
  regression = **176 pass**; ruff clean; app boots.

### Milestone 7 — Analytics, Reporting & Forecast — 🚧 CONTRACTS (recorded before coding)

Verified reuse targets: `bsf_forecast_engine` (`project_flow`/`project_stock`,
`forecast`-labelled with method/assumptions/confidence/limitations, `unknown`
without a window), `bsf_bottleneck_engine.analyze` (ranked constraints citing
evidence/impact/action/confidence; unsupplied metrics not evaluated), and the
platform CSV `Response` export (`text/csv` + `Content-Disposition`). The M3–M6
services already expose `reproduction_summary`, `health_summary`, `finance_summary`,
`housing_summary`.

- **CON-M7-1 — No migration.** Analytics/reporting/forecast are COMPUTED on demand
  from recorded facts; nothing is stored as a competing snapshot (mirrors avi/bsf).
- **CON-M7-2 — The reporting service composes, never re-implements.** The executive
  dashboard calls the existing M3–M6 services (`reproduction_summary`,
  `health_summary`, `finance_summary`, `housing_summary`) for their blocks; only the
  population roll-up (counts by sex / stage / status) is a rabbit-specific recorded
  aggregation. No module's math is duplicated.
- **CON-M7-3 — PURE `rabbit_forecast_engine`** mirrors the platform forecast honesty
  structure: herd (`project_stock`), feed / revenue / kits (`project_flow`) and a
  capacity requirement helper. Every projection is `forecast`-labelled and never a
  confirmed value; no window → `unknown`. This is the module short-range Forecast
  engine (Spec Part 4 §4, Part 7 §16); the long-range strategic **Growth Planner**
  stays separate (M8, reuses the platform `growth_planner_service`).
- **CON-M7-4 — PURE `rabbit_bottleneck_engine`** (Spec Part 7 §11) detects ranked
  operational constraints (fertility, mortality, weaning survival, housing capacity,
  FCR, overdue vaccinations, negative margin) with evidence/impact/action/confidence.
  Mission Control *orchestration* is M10; this engine supplies the deterministic
  detection it will consume.
- **CON-M7-5 — CSV export reuses the platform `Response` pattern** (no new export
  framework). Reads → `RABBIT_REPORT_VIEW`; export → `RABBIT_REPORT_EXPORT`
  (workers excluded — strategic views, Spec §8-9).

### Milestone 7 — Analytics, Reporting & Forecast — ✅ DONE (local, unpushed)

- **Spec sections:** Part 5 §3 (dashboard) & §12 (reporting), Part 7 §3 (executive
  analytics), §7-9 (health/housing/financial analytics, composed), §11 (Mission
  Control bottleneck detection — engine), §12 (reports), §13 (exports), §16 (forecasting).
- **No migration** — all analytics/reporting/forecast are computed on demand (CON-M7-1).
- **PURE `rabbit_forecast_engine.py`**: `project_flow` (kits/feed/revenue),
  `project_stock` (herd size), `capacity_requirement` (housing). Every projection
  `forecast`-labelled with method/assumptions/confidence/limitations; no window →
  `unknown`.
- **PURE `rabbit_bottleneck_engine.py`**: ranked constraints (reproduction,
  mortality, weaning survival, housing overcrowding/capacity, feed efficiency,
  vaccination compliance, profitability) with evidence/impact/action/confidence;
  unsupplied metrics not evaluated; highest-severity first.
- **`rabbit_reporting_service.py`** (composition only, CON-M7-2): `executive_dashboard`
  (recorded population facts + reproduction/health/finance/housing summaries +
  forecast bundle + bottlenecks), `forecast`, `bottlenecks`, `executive_summary`,
  `export_herd_csv`. Calls the M3–M6 services — no re-implemented math.
- **Endpoints** `rabbit_reports.py` = **5 routes** under `/rabbit/reports`
  (dashboard, forecast, bottlenecks, executive-summary, herd.csv) — 78 rabbit
  routes total. Reads → `RABBIT_REPORT_VIEW`; CSV → `RABBIT_REPORT_EXPORT`
  (workers excluded).
- **Platform reuse:** the forecast honesty structure and CSV `Response` export
  patterns (from avi/bsf); the M3–M6 rabbit services for every analytic block. No
  shared Finance/Reporting/Inventory/Growth-Planner/ARIA/Mission code modified.
- **Tests:** 16 engine unit + 7 integration (dashboard composition + labelling,
  forecast bundle, bottlenecks, executive summary, CSV export, RBAC:
  worker-excluded / viewer-view-not-export). Verification run: **169 pass** (94
  rabbit unit + 75 integration incl. Aviculture-finance/reports + BSF-reports
  regression); ruff clean; app boots.

### Milestone 8 — Growth Planner — 🚧 CONTRACTS (recorded before coding)

Verified: the Growth Planner is a **platform-level, cross-module** capability
(`growth_planner_service`, migration 065 tables `growth_plan/goal/milestone/
plan_revision`). Modules do NOT build their own planner — they register a metric
provider via `register_metric_provider(module, fn)` that returns the *actual* for a
`metric_key` from recorded facts (unknown key → `None` → the engine reports
`unknown`, never invented). BSF is the exact template.

- **CON-M8-1 — Reuse the platform Growth Planner; no module planner, no migration.**
  Register a `rabbit` metric provider (`rabbit_growth_provider`) reading recorded
  facts only. No new engine/table — the planner engine + versioning are reused.
- **CON-M8-2 — Endpoints reuse platform schemas** (`app.schemas.growth`) and the
  `growth_planner_service` orchestration; gated `RABBIT_GROWTH_VIEW` /
  `RABBIT_GROWTH_EDIT`. Route prefix `/rabbit/growth` (distinct from M4's
  `/rabbits/{id}/growth` weight-analysis path).
- **Metric keys (recorded actuals):** `herd_size` (active rabbits), `breeding_does`
  (active does), `monthly_kits` / `total_kits` (live kits from litters),
  `monthly_litters`, `monthly_revenue` / `total_revenue` (recorded sale facts).

### Milestone 8 — Growth Planner — ✅ DONE (local, unpushed)

- **Spec sections:** Part 1 §11/§14, Part 5 §13, Part 6 §9-12, Part 7 §10.
- **No migration, no module planner, no new engine** — reuses the platform
  `growth_planner_service` + migration-065 tables + the planner engine/versioning.
- **`rabbit_growth_provider.py`**: registers a `rabbit` metric provider returning
  actuals from recorded facts (herd_size, breeding_does, monthly/total kits,
  monthly litters, monthly/total revenue); unknown key → `None` → planner reports
  `unknown`.
- **Endpoints** `rabbit_growth_planner.py` = **7 routes** under `/rabbit/growth`
  (86 rabbit routes total), reusing `app.schemas.growth`; `RABBIT_GROWTH_VIEW` /
  `RABBIT_GROWTH_EDIT`.
- **Tests:** 7 integration (planned-vs-actual from recorded facts, unknown-key →
  unknown, revision versioning, RBAC). 12 pass with BSF-growth regression; ruff
  clean; app boots. No change to the platform planner.

### Milestone 9 — ARIA — 🚧 CONTRACTS (recorded before coding)

Verified: ARIA reuses the platform AI router `ai_provider.complete` (offline-
grounded) + `ai_settings_service` (enablement, usage log). BSF/Aviculture are the
template. Frozen decisions apply (see [[greena-frozen-decisions]]): **AR-01**
(LLM sees only a bounded context snapshot, never the DB), **AR-04** (≤150 words),
**§4.4** (no disease diagnosis), **PD-07/08** (read-only Q&A).

- **CON-M9-1 — Reuse the platform AI router; no parallel AI.** ARIA reuses
  `ai_provider` + `ai_settings_service`. AI permissions reuse the platform
  `AI_QUERY` (ask) / `AI_INSIGHT_VIEW` (context) — no rabbit-specific AI perms
  (same as avi/bsf). The poultry `aria_router` / frozen system prompt (AR-05) are
  untouched.
- **CON-M9-2 — Deterministic-first.** Factual questions are answered directly from
  recorded facts / deterministic engine outputs (the M7 dashboard + growth
  progress) with **no LLM**; only open explanation routes to the provider, always
  with a grounded offline fallback. `compile_context` is the AR-01 bounded snapshot
  (composes existing engines, recomputes nothing). Every answer carries an honesty
  `fact_type` and cites `sources`.
- **CON-M9-3 — §4.4 + read-only.** ARIA never diagnoses (mortality/health answers
  are patterns with a disclaimer) and never mutates a plan or record.

### Milestone 9 — ARIA — ✅ DONE (local, unpushed)

- **Spec sections:** Part 6 §4-8 (ARIA context, conversations, educational, what-if
  framing), §16-17 (honesty framework, recommendation format).
- **No migration.** Reuses the platform AI router (`ai_provider.complete`,
  offline-grounded) + `ai_settings_service`; no parallel AI, no rabbit AI perms.
- **`rabbit_aria_service.py`**: `compile_context` (AR-01 bounded snapshot composing
  the M7 dashboard + growth progress; recomputes nothing), deterministic-first
  `_factual_answer` (herd/does/bucks, litters, revenue, profit, mortality[pattern
  +disclaimer], housing, bottleneck, forecast, growth) with NO LLM; open questions
  route to `ai_provider` with a grounded offline fallback and usage logging.
  Honesty `fact_type` + `sources` on every answer; ≤150-word prompt (AR-04).
- **Endpoints** `rabbit_aria.py` = **2 routes** (`/aria/ask` `AI_QUERY`,
  `/aria/context` `AI_INSIGHT_VIEW`); 88 rabbit routes total. Poultry `aria_router`
  + frozen system prompt (AR-05) untouched.
- **Tests:** 5 integration (deterministic herd answer, mortality-as-pattern,
  context snapshot, RBAC: worker no AI_QUERY, viewer context-not-ask). 11 pass with
  BSF-ARIA/mission regression; full rabbit suite 164 pass; ruff clean; app boots.

### Milestone 10 — Mission Control — 🚧 CONTRACTS (recorded before coding)

Verified: Mission Control *orchestrates*, owns no domain logic. Each module ships a
PURE `*_intelligence.build_briefing(dashboard, forecast, growth, bottlenecks)` that
reads already-computed deterministic outputs into severity-ranked `Insight`s citing
`Evidence`; `mission_control_data.<module>_briefing` gathers the inputs; the mission
endpoint returns the shared `InsightOut`/`InsightEvidenceOut` schemas. BSF/avi template.

- **CON-M10-1 — Reuse Mission Control; recompute nothing.** `rabbit_intelligence`
  reads the M7 executive dashboard (which already composes the engines) + growth
  progress + bottlenecks; no figure is recomputed. Same Evidence/Insight/Briefing
  shape as bsf/avi so Mission Control consumes every module identically.
- **CON-M10-2 — Orchestration in `mission_control_data.rabbit_briefing`**; endpoint
  `GET /mission/rabbit/briefing` (`AI_INSIGHT_VIEW`) reusing `InsightOut`/
  `InsightEvidenceOut`; new `RabbitBriefingOut` (same shape). No new engine math,
  no migration. Health insights are patterns with a disclaimer (§4.4); growth
  insights never mutate the plan.

### Milestone 10 — Mission Control — ✅ DONE (local, unpushed) — BACKEND COMPLETE

- **Spec sections:** Part 6 §13-15 (Mission Control), Part 7 §11 (bottleneck
  prioritisation), Part 9 §14 (Mission Control verification).
- **No migration.** PURE `rabbit_intelligence.build_briefing` (Evidence/Insight/
  Briefing, same shape as bsf/avi) reads the M7 dashboard + growth + bottlenecks
  into severity-ranked insights (risk/reproduction/health/finance/housing/growth);
  recomputes nothing. Orchestration `mission_control_data.rabbit_briefing`.
  Endpoint `GET /mission/rabbit/briefing` (`AI_INSIGHT_VIEW`) with new
  `RabbitBriefingOut` reusing `InsightOut`/`InsightEvidenceOut`.
- **Tests:** 3 engine unit + 3 integration (structure, viewer-read, worker-403).
  16 pass with Aviculture-mission + BSF-ARIA/mission regression; ruff clean; boots.

**★ RABBIT BACKEND COMPLETE (M1–M10):** migrations 066–070, 11 pure/domain engines
(+ reused platform pedigree/growth-planner/AI/mission engines), 89 API routes,
~285 rabbit tests + regression green. Remaining: M11 Frontend, M12 docs/audit.

### Milestone 11 — Frontend — 🚧 IN PROGRESS (increment 1 done, local, unpushed)

- **Spec sections:** Part 5 (UX/workspaces), Part 9 §7-10 (accessibility/responsive/
  theme). Built on the existing Greena frontend architecture; BSF screens as template.
- **Increment 1 (this commit) — executive/registry/intelligence slice:**
  - **API modules** (presentation-only, no recomputation): `src/api/rabbit.ts`
    (registry/catalog/housing + honesty `Figure` type + enum vocab), `rabbitReports.ts`
    (dashboard/forecast/bottlenecks/summary/CSV), `rabbitAria.ts`, `rabbitMission.ts`.
  - **Screens** `src/screens/rabbit/*`: `RabbitSubnav`, `RabbitDirectoryScreen`
    (list/filter/register modal), `RabbitProfileScreen` (identity + timeline),
    `RabbitDashboardScreen` (population/reproduction/finance tiles + forecast),
    `RabbitReportsScreen` (forecast cards + bottlenecks + CSV export),
    `RabbitAriaScreen` (deterministic-first Q&A), `RabbitMissionScreen` (briefing).
  - Reuses shared `FactBadge`/`LabelledValue`, `Button`/`Skeleton`/`Modal`,
    `useWorkspace`, TanStack Query, axios `apiClient`. Honesty labels rendered via
    `FactBadge` everywhere; forecasts shown with method/assumptions/confidence.
  - Routes + lazy imports in `src/routes/index.tsx`; no client-side RBAC (backend
    403 + error states). No backend logic duplicated.
- **Verification:** `npm run type-check` clean; `npm run build` succeeds; browser-
  verified end-to-end (login demo@greenafarms.co → Directory empty state → register
  "Clover" → Profile → Dashboard live recorded facts → Mission briefing "operations
  on track"); zero console errors. Backend run with local PG (:5433) override.
- **Increment 2 (M11 COMPLETE) — workspace screens:**
  - **API modules:** `rabbitBreeding.ts` (cycles/litters/pedigree/compatibility/
    genetics), `rabbitHealth.ts` (health/vaccinations/mortality/summary),
    `rabbitHousing.ts` (hierarchy/cages/occupancy/summary), `rabbitGrowth.ts`
    (weights/growth analysis/feed/FCR), `rabbitGrowthPlanner.ts` (thin client over
    the PLATFORM planner, module='rabbit'); `moveRabbit` added to `rabbit.ts`.
  - **Screens** `src/screens/rabbit/*`: `RabbitBreedingScreen` (tabs: breedings
    lifecycle, litters+weaning, compatibility checker, reproduction/genetics),
    `RabbitHealthScreen` (summary + vaccinations + mortality + record modals),
    `RabbitHousingScreen` (capacity roll-up + overcrowding + cages + add/move),
    `RabbitGrowthScreen` (per-rabbit weight history + growth analysis + feed/FCR +
    record), `RabbitGrowthPlannerScreen` (plans + planned-vs-actual progress).
  - Subnav extended to all 10 sections; routes lazy-wired. Reuses shared
    `FactBadge`/`LabelledValue`/`Button`/`Skeleton`/`Modal`; all calculations from
    the backend; honesty labels rendered everywhere (verified UNKNOWN shows, not 0).
  - **Verification:** `type-check` clean; `build` succeeds (built in 27s); browser-
    verified every screen (login → Breeding/Health/Housing/Growth/Planner render;
    Growth loads live "RB-00001 · Clover" with UNKNOWN honesty labels); **zero
    console errors**. Backend unchanged this increment.

**★ M11 FRONTEND COMPLETE:** 12 rabbit screens + 8 api modules; type-check + build
green; browser-verified end-to-end. Remaining: M12 docs/handoffs/audit.

## Deviations / decisions

- **DEC-1:** The `rabbit` species profile already existed (Migration 007 seeded it
  as an inactive "Future module"). Milestone 1 **activates** it in-place rather
  than inserting a new row — avoids a `species_key` unique-constraint violation
  and keeps the row owned by its originating migration.
