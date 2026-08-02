# Modules 18 & 19 — Small Ruminant (Goat + Sheep) — Implementation Ledger

Canonical, per-milestone record of the **unified Small Ruminant subsystem** — Goat
(Module 18) and Sheep (Module 19) built **once** on a shared `sr_*` schema with a
`species` discriminator, not as two parallel applications.

- **Spec:** `MODULE_18_GOAT_MANAGEMENT_SYSTEM_onlinenotepad.io.txt` (Goat Docs 1–11;
  Sheep Module 19 from the same file) — the business contract.
- **Branch:** `phase-2-auth`. Commits are **local only** — never pushed/deployed
  without explicit per-action approval.
- **Aggregate root:** the individual animal (`sr_animal`). Closest template was
  Module 17 Rabbit; latest conventions from Modules 15/16.

## Core architecture

```
Platform (Auth/RBAC · Org/Farm · Finance ledger · Inventory · Reminders · Files ·
          Audit · Growth Planner · ARIA/ai_provider · Mission Control · Pedigree)   ← REUSED
        |
Small Ruminant foundation  (sr_* schema + small_ruminant_* services/engines)
        |
   ┌────┴────┐
  Goat       Sheep    ← species='goat'|'sheep' on every animal-scoped sr_ row;
 (dairy)    (wool)       app/services/small_ruminant_species_config.py drives every
                         difference (gestation, sex vocab, kid/lamb, capabilities).
```

**Build-once principle.** There is exactly one breeding engine, one health engine,
one finance engine, etc. Everything that differs between a goat and a sheep is
**data** in `small_ruminant_species_config` (pure), never forked code. Two
`species_profiles` rows (`goat` …0008, `sheep` …0009) surface two launcher
workspaces over the shared implementation.

## Reuse-first inventory (no parallel systems)

| Platform capability | How the Small Ruminant subsystem reuses it |
|---|---|
| Auth / RBAC | `app/core/permissions.py` — 31 `SR_*` perms, ONE shared set for both species on the 6 roles |
| Organizations / Farms | `farm_id` + `farms.organization_id`; catalog `organization_id` nullable (NULL = global) |
| species_profiles engine | Inserts `goat`/`sheep` rows (Migration 072), the aviculture/bsf pattern |
| Pedigree / genetics | `pedigree_engine.py` (Wright's F) reused via a thin `small_ruminant_genetics` wrapper |
| Inventory | Feed consumption via `inventory_service.record_movement` (decrement, cost snapshot, no re-expense) |
| Finance | Costs via `finance_service.record_category_expense(flock_id=None)`, tagged `metadata.module=<species>`; revenue is a recorded fact on `sr_sale` (DB-07) |
| Reminders / Notifications | Vaccination/deworming/hoof/health follow-ups via platform `Reminder` (`metadata.module=<species>`) |
| Growth Planner | `growth_planner_service.register_metric_provider` (goat + sheep providers) |
| ARIA | `ai_provider` + `ai_settings_service`, deterministic-first; platform `AI_QUERY`/`AI_INSIGHT_VIEW` perms |
| Mission Control | pure `small_ruminant_intelligence.build_briefing`; `mission_control_data.small_ruminant_briefing` |
| Files / Audit / Timeline | `sr_media`/`sr_document` reference the file store; `sr_event` + `audit_service` |

## Frozen decisions preserved (see `AGRIOS_MASTER_CONTEXT.md`, `ARIA_AI.md`)
- **AR-01** — ARIA sees only a bounded context snapshot (`compile_context`), never the DB.
- **§4.4** — the health engine reports *patterns* with a "not a veterinary diagnosis"
  disclaimer; it never diagnoses. FAMACHA / lameness / diagnosis are recorded inputs only.
- **DB-07** — `revenue_records` is flock-scoped; sr sale revenue stays a recorded fact on `sr_sale`.
- **DB-03** — `species_profiles` is the extensibility engine; goat/sheep rows inserted there.

## Milestones (all ✅ DONE, local `phase-2-auth`, UNPUSHED)

| # | Milestone | Migration | Commit | Key deliverables |
|---|-----------|-----------|--------|------------------|
| M1 | Foundation | 072 | 0787ca0 | `sr_breed/bloodline/herd/group/pen/pasture/animal/event/media/document`; goat+sheep species rows; `species_config`; 28 unit tests |
| M2 | Registry & Housing | — | c67dbf2 | pure housing engine; `small_ruminant_service` (register GT-/SH-, move/archive/transfer/sell/death/cull) + housing service; 38 routes; 12 integration |
| M3 | Breeding / Pedigree / Birth | 073 | 701b834 | `sr_breeding`+`sr_birth`+`animal.birth_id`; breeding engine (gestation from config, **wether never a valid sire**); genetics reuses `pedigree_engine` (full-sib F=0.25); offspring auto-create; 9 unit + 6 integration |
| M4 | Growth / Weight / Feed | 074 | 8aaaffd | `sr_weight` (kg, immutable) + `sr_feed_record`; growth + feed engines; **feed reuses Inventory**; 5 unit + 4 integration |
| M5 | Health / Vax / Deworming / Hoof / Mortality | 075 | a7c18a0 | 5 tables; health engine (patterns + §4.4); **reuses platform Reminder engine**; 4 unit + 6 integration |
| M6 | Goat dairy (milk / lactation) | 076 | 3e97bad | `sr_lactation`+`sr_milk_record`; lactation engine (305-day forecast, dry-off advisory); gated by `produces_milk`; 4 unit + 2 integration |
| M7 | Sheep wool (shearing / fleece) | 077 | 80d6175 | `sr_shearing`+`sr_fleece`; wool engine (micron grade / clean weight / value); gated by `produces_wool` (**goats rejected 422**); 4 unit + 3 integration |
| M8 | Sales & Finance | 078 | aa3b962 | `sr_sale` (revenue fact, DB-07); finance engine (P&L / unit economics); **reuses shared Finance ledger**; 3 unit + 3 integration |
| M9 | Analytics / Reporting / Forecast | — | 3f51ecb | forecast + bottleneck engines; reporting service **composes** M2–M8 summaries + population + CSV; 6 unit + 4 integration |
| M10 | Growth Planner + ARIA + Mission Control | — | 2425998 | goat+sheep growth providers; deterministic-first ARIA (AR-01/§4.4); `intelligence.build_briefing` + mission wiring; 7 integration |
| M11 | Frontend — Goat & Sheep workspaces | — | bd3cb95 | one shared `src/screens/smallRuminant/*` set + `src/api/smallRuminant.ts`; two launchers `/goat` `/sheep`; browser-verified |
| M12 | Documentation & readiness | — | (this) | this ledger + handoff; memory finalized; readiness audit |

## Statistics
- **7 migrations** (072–078, head 078), **26 models**, **15 pure deterministic engines**
  (+ reused pedigree/growth-planner/AI/mission engines), **~18 services**, **98 API
  routes** under `/farms/{id}/sr/{species}` (+ `/mission/small-ruminant/{species}/briefing`),
  **31 `SR_*` permissions**.
- **109 Small Ruminant tests** (unit + integration) pass; platform regression green
  (aviculture / bsf / rabbit / finance / inventory / reminders / mission).
- **Frontend:** 8 shared screens + 1 API module + config; two launcher workspaces;
  `vite build` clean; browser-verified end-to-end (0 console errors).

## Deterministic engines (pure, honesty-labelled)
`species_config` · `housing_engine` · `breeding_engine` · `genetics` (wraps pedigree) ·
`growth_engine` · `feed_engine` · `health_engine` · `lactation_engine` (goat) ·
`wool_engine` (sheep) · `finance_engine` · `forecast_engine` · `bottleneck_engine` ·
`intelligence` (mission) · plus the reporting/aria composition services.

## Honesty framework
Every user-visible value carries a label (recorded / calculated / forecast / estimate /
recommendation / unknown / unavailable). Zero denominators → `unknown`, never a
fabricated number. Browser check confirmed UNKNOWN renders for birth rate (not a fake 0)
and FORECAST for projections.

## Production-readiness checklist
- ✅ Database migrations round-trip (downgrade→upgrade verified for every migration).
- ✅ All deterministic engines have dedicated unit tests; reproducible outputs.
- ✅ API auth / RBAC / farm-isolation / species-isolation / validation / audit logging.
- ✅ Integration tests over HTTP for every milestone (109 pass) + platform regression green.
- ✅ Frontend `vite build` clean; browser-verified both workspaces; zero console errors.
- ✅ Honesty framework enforced; §4.4/AR-01/DB-07/DB-03 preserved.
- ✅ Reuse-first — no platform capability duplicated.
- ⏳ **Not pushed, not deployed** — awaiting explicit deployment approval.
- ⏳ Deferred (flagged, not built): offline sync engine (schema is sync-ready),
  embryo-transfer workflow (enum-ready), external lab/SCC integrations (fields present).

## Running / tests (dev)
Embedded Postgres :5433 (`backend/.pgdata`; restart after reboot via
`pg_ctl.exe -D .pgdata -o "-p 5433" -l pg.log start`). Run with
`DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/agrios
TEST_DATABASE_URL=...agrios_test DATABASE_SSL=false` using `backend/.venv`. Frontend
gate = `vite build` (repo ESLint v9 is broken; pre-existing `tsc` errors live in
unrelated rabbit screens). Browser: backend uvicorn :8000, `greena-web` :5173, login
`demo@greenafarms.co` / `Demo1234!`; in-SPA nav (`history.pushState` + `PopStateEvent`)
— a full-page navigate drops the in-memory token (known, not a bug).
