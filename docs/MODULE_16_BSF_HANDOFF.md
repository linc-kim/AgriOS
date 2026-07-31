# Module 16 — Black Soldier Fly (BSF): Backend Handoff Package

**Canonical technical reference.** Read this to understand, extend, or maintain the
Module 16 backend without rereading the specification or the build history. Living
per-milestone detail and the verified integration contracts are in
[`MODULE_16_BSF_LEDGER.md`](MODULE_16_BSF_LEDGER.md); this document is the map.

- **Status:** Backend complete (Milestones A–H). Frontend + Automation part remain.
- **Branch:** `phase-2-auth` (local commits `a799f10 … 8c59897`, **unpushed**).
- **DB revision:** `065` (head). **Not deployed.**

---

## 1. Overview & core principles

BSF is **batch-centric**: the aggregate root is the **Production Batch**, not an
individual insect. Four non-negotiable principles run through every layer:

1. **Deterministic-first** — all calculations live in **pure engines** (no I/O). The
   same inputs always produce the same output.
2. **Honesty framework** — every figure is labelled `recorded` · `calculated` ·
   `forecast` · `estimate` · `unknown`/`unavailable`. Nothing is fabricated.
3. **Reuse-first** — Finance, Inventory, Files, Audit, Auth/RBAC, Notifications, the
   AI router and Mission Control are **reused, never duplicated**.
4. **Advisors never decide** — ARIA/Mission Control explain and recommend; only
   explicit user actions mutate data. The engines + Growth Planner are the source of
   truth.

---

## 2. Architecture diagram

```mermaid
flowchart TD
    subgraph API["API layer — /farms/{farm_id}/bsf/*  (FastAPI, RBAC-guarded)"]
        A1[bsf.py batches/units/colonies/species]
        A2[bsf_feeding.py]
        A3[bsf_environment.py]
        A4[bsf_harvest.py]
        A5[bsf_health.py]
        A6[bsf_finance.py]
        A7[bsf_reports.py]
        A8[bsf_growth.py]
        A9[bsf_aria.py]
        A10[mission.py → /mission/bsf/briefing]
    end

    subgraph SVC["Service layer — orchestration, DB writes, audit"]
        S1[bsf_service / bsf_batch_service]
        S2[bsf_feedstock_service]
        S3[bsf_environment_service]
        S4[bsf_harvest_service]
        S5[bsf_mortality_service]
        S6[bsf_finance_service]
        S7[bsf_analytics_service]
        S8[bsf_reporting_service]
        S9[growth_planner_service + bsf_growth_provider]
        S10[bsf_aria_service]
        S11[mission_control_data.bsf_briefing]
    end

    subgraph ENG["Pure deterministic engines — independent, calculations only, no I/O"]
        E1[lifecycle]
        E2[production]
        E3[feed_conversion]
        E4[environment]
        E5[harvest]
        E6[frass]
        E7[health]
        E8[sustainability]
        E9[finance]
        E10[forecast]
        E11[bottleneck]
        E12[score]
        E13[growth_planner_engine]
        E14[bsf_intelligence]
    end

    subgraph PLAT["Reused platform capabilities"]
        P1[(Finance ledger)]
        P2[(Inventory movements)]
        P3[(Audit / Files / RBAC)]
        P4[(AI router + ai_settings)]
        P5[(Growth Planner* platform tables)]
    end

    API --> SVC --> ENG
    S6 --> P1
    S4 --> P2
    SVC --> P3
    S10 --> P4
    S9 --> P5
    S8 --> E10 & E11 & E12
    S11 --> E14
    S10 --> S8
    S11 --> S8 & S9
```

`*` Growth Planner is a **new platform capability** created by this module (§6).

---

## 3. Migration timeline (061–065)

| Rev | Migration | Adds | Tables |
|-----|-----------|------|--------|
| **061** | `bsf_foundation` | Registers `species_profiles` (`species_key='bsf'`); domain backbone | `bsf_species`, `bsf_production_unit`, `bsf_colony`, `bsf_batch`, `bsf_lifecycle_event`, `bsf_batch_event`, `bsf_batch_media`, `bsf_batch_document` |
| **062** | `bsf_feeding_environment` | Inputs & monitoring | `bsf_feedstock_lot`, `bsf_feeding_event`, `bsf_environmental_reading` |
| **063** | `bsf_harvest_frass` | Production output | `bsf_harvest_event`, `bsf_frass_production` |
| **064** | `bsf_mortality` | Loss tracking | `bsf_mortality_event` |
| **065** | `growth_planner` | **Platform** cross-module planner | `growth_plan`, `growth_goal`, `growth_milestone`, `growth_plan_revision` |

All migrations round-trip (down/up verified). 14 `bsf_*` tables + 4 platform
`growth_*` tables. Every table inherits `AGRIOSBase` (UUID PK, soft-delete, JSONB
`metadata`, audit timestamps).

---

## 4. Dependency graph (major components)

```mermaid
flowchart LR
    Batch[bsf_batch_service] --> LE[lifecycle_engine] & PE[production_engine]
    Feed[bsf_feedstock_service] --> FCE[feed_conversion_engine]
    Env[bsf_environment_service] --> EE[environment_engine]
    Harv[bsf_harvest_service] --> HE[harvest_engine] & FE[frass_engine]
    Harv --> INV[(inventory_service)]
    Mort[bsf_mortality_service] --> HealthE[health_engine]
    Fin[bsf_finance_service] --> FinE[finance_engine] --> FinL[(finance_service)]
    Ana[bsf_analytics_service] --> SusE[sustainability_engine]

    Report[bsf_reporting_service] --> PE & FCE & HealthE & FinE & SusE
    Report --> ForE[forecast_engine] & BotE[bottleneck_engine] & ScoreE[score_engine]
    Report --> Fin & Ana & GP

    GP[growth_planner_service] --> GPE[growth_planner_engine]
    GP --> Provider[bsf_growth_provider] --> Harv
    ScoreE -.growth score.-> GP

    Aria[bsf_aria_service] --> Report & GP
    Mission[mission_control_data.bsf_briefing] --> Report & GP --> Intel[bsf_intelligence]
```

**Read the arrows as "depends on / reads from."** Key rule: services depend on
engines (never the reverse); the reporting service **composes** other services'
outputs and never recomputes; ARIA/Mission read the reporting service + Growth
Planner but write nothing.

---

## 5. API inventory (58 endpoints, all `/farms/{farm_id}/bsf/*` unless noted)

| Group | Count | Endpoints | Permission |
|-------|------:|-----------|------------|
| **Catalog + infra** | 10 | `species` (GET/POST), `production-units` (GET/POST/GET-one/PATCH), `colonies` (GET/POST/GET-one/PATCH) | `BSF_CATALOG_*` / `BSF_UNIT_*` / `BSF_COLONY_*` |
| **Batches (core)** | 11 | `batches` CRUD + `/advance` `/move` `/split` `/merge` `/terminate` `/lifecycle` `/timeline` | `BSF_BATCH_*` |
| **Feeding** | 8 | `feedstock-lots` (CRUD), `batches/{id}/feedings` (POST/GET), `batches/{id}/feed-conversion` | `BSF_FEED_*` |
| **Environment** | 3 | `environment/readings` (GET/POST), `environment/units/{id}/assessment` | `BSF_ENVIRONMENT_*` |
| **Harvest** | 5 | `batches/{id}/harvests` (POST/GET), `harvest-readiness`, `batches/{id}/frass` (POST/GET) | `BSF_HARVEST_*` |
| **Health** | 3 | `batches/{id}/mortality` (POST/GET), `batches/{id}/health` | `BSF_BATCH_*` |
| **Finance** | 3 | `feedstock-lots/{id}/post-expense`, `finance/expenses`, `finance/summary`, `analytics/sustainability` | `BSF_FEED_RECORD` / `BSF_FINANCE_VIEW` / `BSF_REPORT_VIEW` |
| **Reports** | 4 | `reports/dashboard`, `reports/forecast`, `reports/bottlenecks`, `reports/production.csv` | `BSF_REPORT_VIEW` / `BSF_REPORT_EXPORT` |
| **Growth** | 8 | `growth/plans` (list/create/detail/patch/archive), `.../milestones/{id}`, `.../revisions`, `.../compare` | `BSF_GROWTH_VIEW/EDIT` |
| **ARIA** | 2 | `aria/ask`, `aria/context` | `AI_QUERY` / `AI_INSIGHT_VIEW` |
| **Mission Control** | 1 | `GET /farms/{id}/mission/bsf/briefing` | `AI_INSIGHT_VIEW` |

RBAC (`app/core/permissions.py`): 23 `BSF_*` permissions. Owner/manager = full;
worker = operational (no delete/finance/reports/growth-views); vet/viewer = read;
ARIA/Mission reuse platform `AI_QUERY`/`AI_INSIGHT_VIEW`.

---

## 6. Reusable platform capabilities created

1. **Growth Planner (canonical, cross-module).** Tables `growth_*` (farm-scoped +
   `module` discriminator), `growth_planner_engine` (pure), `growth_planner_service`
   with a **metric-provider registry** (`register_metric_provider(module, fn)`) and
   immutable revision history (mirrors `MissionRevision`). Any module gets versioned
   goals, milestones, planned-vs-actual and realism checks by registering a provider.
2. **The engine/service/provider template** — 14 pure honesty-labelled engines cleanly
   separated from DB services; the reference pattern for future modules.
3. **`BsfBriefingOut` + the `/mission/{module}/briefing` shape** — Mission Control now
   consumes any module's briefing identically (`InsightOut`/`InsightEvidenceOut`).

---

## 7. Integration contracts (summary — full text in the ledger)

| System | Contract (verified against platform code before coding) |
|--------|----------|
| **Finance** | Costs post to the **shared `expenses` ledger** via `finance_service.record_category_expense(flock_id=None)`, tagged `Expense.metadata_["module"]="bsf"`. P&L is **computed** (revenue = recorded `bsf_harvest_event.revenue_amount`; cost = tag-filtered ledger). **Revenue is a recorded fact, never a `revenue_records` row** (frozen flock-scoped ledger). Feedstock cost posts **once** (idempotent via `lot.metadata_["expense_id"]`). No BSF finance table. |
| **Inventory** | Harvest/frass output optionally enters via `inventory_service.record_movement` with `movement_type="adjustment"` (inbound, **never `stock_in`** → no purchase-expense double-count). BSF stores only a soft `inventory_movement_id`. No BSF stock table. |
| **Growth Planner** | Platform-owned tables/engine/service. Modules own their provider + guarded API. Every mutation snapshots a revision; ARIA/Mission **read** progress and **never mutate** plans. |
| **ARIA** | Reuses `ai_provider` (offline-grounded) + `ai_settings_service`. Deterministic-first: factual Qs answered with no LLM; bounded context (LLM never sees the DB). Read-only. Every answer carries `sources[]` + a `fact_type`. |
| **Mission Control** | `mission_control_data.bsf_briefing` **orchestrates** (owns no business logic): gathers dashboard + forecast + growth progress + bottlenecks → pure `bsf_intelligence.build_briefing`. Every Insight cites `evidence[]`; nothing recomputed. |

---

## 8. Extension guide — adding a new agricultural module (Rabbits, Dairy, Crops…)

Follow the BSF template; each step maps to a milestone:

1. **Schema** — `NNN_<module>_foundation` migration + `app/models/<module>.py`
   (`AGRIOSBase`, `farm_id`-scoped, `*_VALUES` enum tuples). Register in
   `species_profiles`.
2. **RBAC** — add `<MODULE>_*` permissions in `app/core/permissions.py`, graded like
   `_BSF_VIEW`/`_BSF_FULL`; reuse platform `AI_QUERY`/`AI_INSIGHT_VIEW`.
3. **Pure engines** — one module per calculation concern; every output
   `{label,value,detail}`; missing inputs → `unknown`.
4. **Services** — orchestrate DB + audit; delegate all maths to engines; reuse
   Finance/Inventory per the contracts above (don't reinvent).
5. **API** — `app/api/v1/endpoints/<module>*.py`, `SuccessResponse`/`ListResponse`
   envelopes, `require_farm_access` + `require_permission`; register in the v1 router.
6. **Growth Planner** — write `<module>_growth_provider.py` mapping metric keys to
   recorded facts and call `growth_planner_service.register_metric_provider(...)`.
   You inherit goals/milestones/versioning/progress for free.
7. **ARIA** — a `<module>_aria_service` with `compile_context` (bounded) +
   `_factual_answer` + `ask` (reuse `ai_provider`).
8. **Mission Control** — a pure `<module>_intelligence.build_briefing` + a
   `mission_control_data.<module>_briefing` + a `/mission/<module>/briefing` route
   reusing `InsightOut`.
9. **Tests** — engine unit tests (pure, fast) + integration tests (HTTP, RBAC 403s,
   farm isolation) per layer.

**Rule of thumb:** if a calculation isn't in a pure engine, or a shared-system write
isn't going through an existing platform service, stop — it's drifting from the
architecture.

---

## 9. Known limitations & intentional deferrals

| Item | Why | Where it lands |
|------|-----|----------------|
| **Frontend** (all `src/screens/bsf/*`) | Backend-first delivery | Next phase |
| **Automation** (auto-tasks, env/feedstock/harvest **alert emission**) | Detection is deterministic now; emission centralised to stay idempotent (`metadata.module='bsf'`, dedup keys) — mirrors Aviculture | Dedicated Automation part |
| **Browser / a11y / load-perf audit** (Spec Part 9) | Needs the frontend | With frontend |
| **Bulk import + async background jobs** (Part 9 §5–6) | Not yet required | Follow-up |
| **Cross-module Mission Control roll-up** | Each module exposes its own briefing today | Additive future step |
| **Farm-wide capacity-utilisation** = `unknown` on dashboard | No aggregate unit-capacity roll-up | Follow-up (honest gap, not fabricated) |
| **Species starter-seed catalog** | Starts empty; UI creates inline | Optional seed (as Aviculture) |
| **Growth score** needs a primary plan | By design — `unavailable` without one | — |

Pre-existing, not introduced here: unused `from uuid import UUID` in
`permissions.py` (left per scope-linters convention); repo `npm run lint` broken
(ESLint v9 config) — frontend gate is `tsc` + `vite build`.

---

## 10. Verification summary

- **Tests:** 155 Module-16 test functions — **94 unit + 61 integration**, all passing.
  Unit = pure-engine determinism + honesty labels + RBAC grading; integration = HTTP
  against a real Postgres, asserting RBAC 403s, farm isolation, and the integration
  contracts (e.g. inventory `adjustment` not `stock_in`; P&L confirmed-vs-calculated;
  plan version history; ARIA read-only).
- **Regressions:** mission + aviculture suite **117 passed** after shared-file edits
  (`mission_control_data`, `mission.py`, `schemas/mission.py`); inventory & finance
  regressions green.
- **Migrations:** 061–065 apply and round-trip; DB at head `065`.
- **Lint:** `ruff` clean across all module files.
- **App boot:** imports cleanly, 58 `/bsf` routes + `/mission/bsf/briefing` register,
  BSF growth metric-provider registers at startup.

Run the module suite:
```bash
cd backend && DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/agrios" DATABASE_SSL=false TESTING=1 ./.venv/Scripts/python.exe -m pytest tests -k "bsf or growth" -q
```

---

## 11. Implementation statistics

| Metric | Value |
|--------|------:|
| Milestones (A–H) | 8 |
| Migrations (061–065) | 5 |
| Tables (14 `bsf_*` + 4 `growth_*`) | 18 |
| Pure deterministic engines | 14 |
| Services (incl. provider) | 12 |
| API endpoint modules | 9 (+`mission.py`) |
| API endpoints (BSF-related) | 58 |
| RBAC permissions (`BSF_*`) | 23 |
| Source LOC (services/models/schemas/endpoints) | ~6,600 |
| Migration LOC | ~730 |
| Test LOC | ~1,900 |
| Test functions (94 unit + 61 integration) | 155 |

### Component index (files)

- **Engines (pure):** `bsf_lifecycle_engine`, `bsf_production_engine`,
  `bsf_feed_conversion_engine`, `bsf_environment_engine`, `bsf_harvest_engine`,
  `bsf_frass_engine`, `bsf_health_engine`, `bsf_sustainability_engine`,
  `bsf_finance_engine`, `bsf_forecast_engine`, `bsf_bottleneck_engine`,
  `bsf_score_engine`, `growth_planner_engine`, `bsf_intelligence`.
- **Services:** `bsf_service`, `bsf_batch_service`, `bsf_feedstock_service`,
  `bsf_environment_service`, `bsf_harvest_service`, `bsf_mortality_service`,
  `bsf_finance_service`, `bsf_analytics_service`, `bsf_reporting_service`,
  `bsf_aria_service`, `growth_planner_service`, `bsf_growth_provider`.
- **Models:** `app/models/bsf.py`, `app/models/growth.py`.
- **Endpoints:** `bsf.py`, `bsf_feeding.py`, `bsf_environment.py`, `bsf_harvest.py`,
  `bsf_health.py`, `bsf_finance.py`, `bsf_reports.py`, `bsf_growth.py`, `bsf_aria.py`,
  + `mission.py` (briefing route).
- **Tests:** `tests/unit/test_bsf_*.py`, `tests/unit/test_growth_planner_engine.py`,
  `tests/integration/test_bsf_*.py`.
