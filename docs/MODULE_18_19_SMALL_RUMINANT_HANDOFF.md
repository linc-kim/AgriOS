# Modules 18 & 19 — Small Ruminant (Goat + Sheep) — Architectural Handoff

The canonical architecture reference for the unified Small Ruminant subsystem. See
[`MODULE_18_19_SMALL_RUMINANT_LEDGER.md`](./MODULE_18_19_SMALL_RUMINANT_LEDGER.md)
for the per-milestone record and reuse contracts.

## 1. The one idea

Goat and Sheep are **one subsystem**, not two apps. A single `sr_*` schema and a
single set of `small_ruminant_*` services/engines serve both species, distinguished
by a `species` column ('goat' | 'sheep'). Everything that differs is **data** in the
pure `small_ruminant_species_config` module — never forked code. This is the
extensible foundation for future mammalian-livestock modules: add a species to the
config + a `species_profiles` row and the whole stack works for it.

## 2. Layering

- **Pure engines** (`app/services/small_ruminant_*_engine.py`, `_genetics`,
  `_species_config`, `_intelligence`): no I/O, deterministic, honesty-labelled. All
  business math lives here. Trivially unit-testable.
- **Services** (`small_ruminant_service`, `_housing_service`, `_breeding_service`,
  `_growth_service`, `_feed_service`, `_health_service`, `_dairy_service`,
  `_wool_service`, `_finance_service`, `_reporting_service`, `_aria_service`,
  `_growth_provider`): own DB writes + audit + timeline + platform reuse. No math.
- **Endpoints** (`app/api/v1/endpoints/sr_*.py`): auth/RBAC/farm-isolation guards +
  a `require_species` 404 guard; thin — they call services and shape responses.
- **Frontend** (`src/screens/smallRuminant/*`, `src/api/smallRuminant.ts`):
  presentation only; every computed figure arrives honesty-labelled and is rendered
  as-is. Two launchers (`/goat`, `/sheep`) render the same components with a
  `species` prop.

## 3. Data model (Migrations 072–078)

Animal-and-genetics tables carry `species`; physical infrastructure is species-neutral.

- **Catalog:** `sr_breed` (species-scoped, org-nullable), `sr_bloodline`.
- **Grouping (species-scoped):** `sr_herd` → `sr_group` (dynamic membership).
- **Housing (species-neutral):** `sr_pen`, `sr_pasture` — occupancy DERIVED, never stored.
- **Aggregate root:** `sr_animal` (identity, classification, biology, lifecycle,
  pedigree self-FKs `sire_id`/`dam_id`, location FKs, `birth_id`). Refs `GT-#####`/`SH-#####`.
- **History/attachments:** `sr_event` (append-only), `sr_media`, `sr_document`.
- **Breeding:** `sr_breeding` (service→pregnancy-check→birth), `sr_birth` (kidding/lambing).
- **Growth/feed:** `sr_weight` (kg, immutable), `sr_feed_record` (soft Inventory refs).
- **Health:** `sr_health_record`, `sr_vaccination`, `sr_deworming` (FAMACHA),
  `sr_hoof_care` (lameness), `sr_mortality` (immutable, one/animal).
- **Dairy (goat):** `sr_lactation`, `sr_milk_record` (litres).
- **Wool (sheep):** `sr_shearing`, `sr_fleece` (greasy kg, micron, staple, grade).
- **Sales:** `sr_sale` (revenue fact; animal + product sales).

## 4. Species config (the extension point)

`small_ruminant_species_config.py` exposes per-species: `collective_noun`
(herd/flock), `offspring_term` (kid/lamb), `birth_event` (kidding/lambing),
`male_term`/`female_term` (buck-doe / ram-ewe), `sex_values`,
`default_gestation_days` (150/147, breed-overridable via `sr_breed.profile
['gestation_days']`), and capability flags `produces_milk`/`produces_wool`. Helpers:
`is_valid_sex`, `biological_role`, `gestation_days`, `has_capability`. **Breeding
eligibility uses the intact `male_term`/`female_term`, so a wether (castrated male)
is never a valid sire** even though its biological role is male.

## 5. API surface (98 routes, prefix `/farms/{farm_id}/sr/{species}`)
`…/animals` (+ move/archive/restore/transfer/sell/death/cull/timeline/media/documents),
`…/breeds` · `…/bloodlines`, `…/housing/{herds,groups,pens,pastures,summary}`,
`…/breeding` (+ service/pregnancy-check/birth/wean/summary/pedigree/compatibility/
performance), `…/animals/{id}/weights` · `…/animals/{id}/growth` · `…/feed`,
`…/health/*`, `…/dairy/*` (goat), `…/wool/*` (sheep), `…/finance/{sales,expenses,summary}`,
`…/reports/{dashboard,forecast,bottlenecks,registry.csv}`, `…/growth/plans`,
`…/aria/{ask,context}`, plus `/farms/{id}/mission/small-ruminant/{species}/briefing`.

## 6. RBAC
31 `SR_*` permissions (one shared set for both species) layered on the 6 roles:
owner/manager/enterprise full; worker operational (create/edit/breeding/health/
weight/feed/dairy/wool/automation) but not archive/transact/housing/catalog/sales or
strategic finance/report/growth views; vet clinical write (`SR_HEALTH_LOG`); viewer
read-only. ARIA/Mission reuse platform `AI_QUERY`/`AI_INSIGHT_VIEW`. Cost posting
reuses platform `FINANCE_RECORD`.

## 7. Extending
- **New species** (e.g. camel): add a config entry + a `species_profiles` row; the
  shared schema/services/engines/frontend work immediately. Add species-specific
  capability tables only if a new production type is needed.
- **New health/production entity:** add a table + a pure engine block + service
  method; the reporting/ARIA/mission layers compose it automatically once surfaced
  in the dashboard.

## 8. Known limitations / deferred
Offline sync (schema sync-ready, no engine), embryo transfer (enum-ready workflow),
external lab/SCC integrations (fields present). Frontend covers the core workspace
(directory/profile/dashboard/production/reports/ARIA/mission); breeding/health/
growth data-entry screens can reuse the same shared component pattern next.

**Status:** feature-complete M1–M12, local `phase-2-auth`, **unpushed, not deployed.**
