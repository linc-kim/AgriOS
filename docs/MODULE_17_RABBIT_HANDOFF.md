# Module 17 — Rabbit Management System — Canonical Handoff

> Companion to the implementation ledger: [`MODULE_17_RABBIT_LEDGER.md`](./MODULE_17_RABBIT_LEDGER.md)
> (per-milestone decisions, contracts and deviations). This document is the
> architectural reference for maintaining and extending the module.

**Status:** Backend M1–M10 complete · Frontend M11 complete · M12 documentation.
**Branch:** `phase-2-auth` — local commits only, **not pushed / not deployed**.
**DB head:** migration `070`.

---

## 1. Architecture

Rabbit Management is a first-class Greena platform module, not a standalone app. It
follows the canonical layered architecture and never bypasses a layer:

```
Frontend (React/Vite)  →  API routers (thin)  →  Services (orchestration)
      →  Deterministic engines (pure calculations)  →  Shared platform services  →  Database
```

- **Aggregate root:** the individual **rabbit** (`rabbit` table) — the closest
  template is Module 15 Aviculture (`avi_*`); latest conventions from Module 16 BSF.
- **Deterministic-first:** every calculation, score, forecast and validation lives
  in a pure engine. Services orchestrate DB reads/writes and call engines. Routers
  are thin. The frontend renders results and never recomputes business values.
- **Honesty framework:** every user-visible value carries an origin label —
  `recorded` · `calculated` · `forecast` · `estimated` · `unknown`/`unavailable`.
  Missing data is reported honestly, never fabricated.
- **Org/farm isolation:** farm-scoped rows carry `farm_id`; isolation flows through
  `farms.organization_id`. Catalog rows (`rabbit_breed`) carry a nullable
  `organization_id` (NULL = global).

## 2. Migrations (`backend/alembic/versions/`)

| # | File | Adds |
|---|---|---|
| 066 | `066_rabbit_foundation.py` | breed & bloodline catalog; 5-level housing (rabbitry→building→room→row→cage); `rabbit` aggregate root; `rabbit_event`/`_media`/`_document`. Activates the pre-seeded `species_profiles` rabbit row. |
| 067 | `067_rabbit_breeding.py` | `rabbit_breeding`, `rabbit_litter`; adds `rabbit.litter_id` (kit→birth-litter). |
| 068 | `068_rabbit_growth_feed.py` | `rabbit_weight` (immutable), `rabbit_feed_record` (soft Inventory refs). |
| 069 | `069_rabbit_health.py` | `rabbit_health_record`, `rabbit_vaccination` (soft `reminder_id`), `rabbit_mortality`. |
| 070 | `070_rabbit_sales.py` | `rabbit_sale` (revenue as a recorded fact). |

All migrations round-trip (upgrade/downgrade) and keep a linear history; no
destructive schema changes. Historical records are soft-deleted only.

## 3. Models (`backend/app/models/rabbit.py`) — 19 classes

`RabbitBreed`, `RabbitBloodline`, `RabbitRabbitry`, `RabbitBuilding`, `RabbitRoom`,
`RabbitRow`, `RabbitCage`, `Rabbit`, `RabbitEvent`, `RabbitMedia`, `RabbitDocument`,
`RabbitBreeding`, `RabbitLitter`, `RabbitWeight`, `RabbitFeedRecord`,
`RabbitHealthRecord`, `RabbitVaccination`, `RabbitMortality`, `RabbitSale`.

All inherit `AGRIOSBase` (UUID PK, timestamps, `deleted_at` soft-delete, JSONB
`metadata`). Enumerated fields are strings validated at the schema/service layer via
`*_VALUES` tuples (no DB enums) — matching the avi/bsf convention. Pedigree links
are `rabbit.sire_id`/`dam_id` self-FKs (unknown ancestry stays NULL).

## 4. Deterministic engines (pure — `backend/app/services/`)

| Engine | Responsibility |
|---|---|
| `rabbit_housing_engine` | occupancy/availability/utilization, overcrowding, hierarchy roll-up |
| `rabbit_breeding_engine` | eligibility, gestation forecast/progress, litter performance, doe/buck productivity, reproduction summary, breeding-value ranking |
| `rabbit_genetics` | rabbit-domain wrapper over the **reused** `pedigree_engine` (Wright's F, relatedness, ancestry, cycle safety) — buck/doe semantics + risk banding |
| `rabbit_growth_engine` | ADG, growth series, breed-curve expected weight, deviation, percentile |
| `rabbit_feed_engine` | feed conversion ratio, feed summary/cost |
| `rabbit_health_engine` | mortality rate/by-cause/trend, recovery rate, condition frequency, vaccination compliance — **patterns, never a diagnosis (§4.4)** |
| `rabbit_finance_engine` | P&L (revenue/feed/operating cost, gross, margin, ROI), unit economics (cost/profit per rabbit/litter/doe/kg, feed/vet %) |
| `rabbit_forecast_engine` | herd (`project_stock`), kits/feed/revenue (`project_flow`), housing capacity — `forecast`-labelled |
| `rabbit_bottleneck_engine` | severity-ranked operational constraints with evidence/impact/action |
| `rabbit_intelligence` | Mission Control briefing builder (Evidence/Insight/Briefing), reads engine outputs — recomputes nothing |

**Reused platform engines (not reimplemented):** `pedigree_engine` (Wright's
genetics), `growth_planner_engine` (goal progress/versioning), the AI router
(`ai_provider`), the Mission Control shapes.

## 5. Services (orchestration — `backend/app/services/`)

`rabbit_service` (registry, catalog, lifecycle, movement, attachments),
`rabbit_housing_service` (5-level CRUD + occupancy/summary),
`rabbit_breeding_service` (cycle, litters, foster/weaning, pedigree, compatibility,
performance, genetics), `rabbit_growth_service` (weights + growth analysis),
`rabbit_feed_service` (feeding + FCR, Inventory reuse), `rabbit_health_service`
(health/vaccination/mortality, Reminder reuse), `rabbit_finance_service` (sales +
P&L, Finance reuse), `rabbit_reporting_service` (dashboard/forecast/bottlenecks/
summary/CSV — composes the others), `rabbit_growth_provider` (Growth Planner metric
provider), `rabbit_aria_service` (deterministic-first ARIA). Mission Control
orchestration lives in `mission_control_data.rabbit_briefing`.

## 6. API endpoints — 89 operations under `/farms/{farm_id}/rabbit`

Modules (`backend/app/api/v1/endpoints/`): `rabbit.py` (registry + catalog +
timeline + attachments), `rabbit_housing.py`, `rabbit_breeding.py`, `rabbit_growth.py`
(weights + feed), `rabbit_health.py`, `rabbit_finance.py`, `rabbit_reports.py`,
`rabbit_growth_planner.py`, `rabbit_aria.py`; plus `GET /farms/{farm_id}/mission/
rabbit/briefing`. Every route enforces `require_farm_access` + a `RABBIT_*` (or
reused platform) permission. See §8 for the API inventory.

## 7. Frontend structure (`frontend/src/`)

- **API clients** (`api/`): `rabbit.ts`, `rabbitBreeding.ts`, `rabbitHealth.ts`,
  `rabbitHousing.ts`, `rabbitGrowth.ts`, `rabbitReports.ts`, `rabbitGrowthPlanner.ts`,
  `rabbitAria.ts`, `rabbitMission.ts` — presentation-only, typed, no recomputation.
- **Screens** (`screens/rabbit/`, 12): `RabbitSubnav`, `RabbitDirectoryScreen`,
  `RabbitProfileScreen`, `RabbitDashboardScreen`, `RabbitBreedingScreen`,
  `RabbitHealthScreen`, `RabbitHousingScreen`, `RabbitGrowthScreen`,
  `RabbitGrowthPlannerScreen`, `RabbitReportsScreen`, `RabbitAriaScreen`,
  `RabbitMissionScreen`. Lazy-routed in `routes/index.tsx` under `/rabbit/*`.
- **Shared components reused:** `FactBadge`/`LabelledValue` (honesty rendering),
  `Button`/`Skeleton`/`Modal`, `useWorkspace`, TanStack Query, axios `apiClient`.
- No client-side RBAC (rely on backend 403 + error states); no business logic.

## 8. API inventory (by group)

- **Registry:** `POST/GET /rabbits`, `GET/PATCH /rabbits/{id}`, `/rabbits/{id}/move`,
  `/archive`, `/restore`, `/transfer`, `/sell`, `/death`, `/timeline`, `/media`,
  `/documents`.
- **Catalog:** `GET/POST /breeds`, `PATCH /breeds/{id}`, `GET/POST /bloodlines`,
  `PATCH /bloodlines/{id}`.
- **Housing:** `/housing/rabbitries|buildings|rooms|rows|cages` (GET/POST/PATCH),
  `GET /housing/cages/{id}` (occupancy), `GET /housing/summary`.
- **Breeding:** `POST/GET /breedings`, `GET /breedings/{id}`, `/service`,
  `/pregnancy-check`, `/prepare-kindling`, `/kindling`, `/close`; `GET /litters`,
  `GET /litters/{id}`, `/foster`, `/weaning`; `GET /rabbits/{id}/pedigree`,
  `GET /rabbits/{id}/breeding-performance`, `POST /breeding/compatibility`,
  `GET /breeding/reproduction-summary`, `GET /breeding/genetics`.
- **Growth/Feed:** `POST/GET /rabbits/{id}/weights`, `GET /rabbits/{id}/growth`,
  `POST/GET /feed`, `GET /feed/summary`.
- **Health:** `POST/GET /rabbits/{id}/health`, `POST/GET /rabbits/{id}/vaccinations`,
  `GET /vaccinations`, `POST /rabbits/{id}/mortality`, `GET /mortality`,
  `GET /health/summary`.
- **Sales/Finance:** `POST/GET /sales`, `POST /finance/expenses`, `GET /finance/summary`.
- **Reports:** `GET /reports/dashboard|forecast|bottlenecks|executive-summary|herd.csv`.
- **Growth Planner:** `/growth/plans` (GET/POST), `/growth/plans/{id}` (GET/PATCH),
  `/archive`, `/milestones/{id}`, `/revisions`, `/compare`.
- **ARIA:** `POST /aria/ask`, `GET /aria/context`.
- **Mission Control:** `GET /mission/rabbit/briefing`.

## 9. Integration contracts (reuse-first — never duplicated)

| Platform capability | Contract |
|---|---|
| **Inventory** | Feed consumption posts a `consumption` movement via `inventory_service.record_movement` (decrement, **no new expense** — feed expensed once at `stock_in`). `rabbit_feed_record` holds soft refs (`inventory_item_id`/`inventory_movement_id`, no FK). |
| **Finance** | Operating costs post to the SHARED `expenses` ledger via `finance_service.record_category_expense(flock_id=None)`, tagged `metadata.module='rabbit'`. **Sale revenue is a recorded fact** on `rabbit_sale` — never posted to the flock-scoped `revenue_records` (frozen DB-07). P&L feed cost = recorded consumption allocation (no double-count). |
| **Reminders/Notifications** | Vaccination/follow-up due dates create a platform `Reminder` (`metadata.module='rabbit'`, idempotent `dedup_key`); the scheduler fires it into Notifications. No rabbit reminder/notification table; `reminder_id` soft ref on `rabbit_vaccination`. |
| **Growth Planner** | Reuses `growth_planner_service` (migration 065). `rabbit_growth_provider` registers a `rabbit` metric provider returning actuals from recorded facts; unknown key → `None` → `unknown`. No module planner. |
| **Pedigree engine** | `rabbit_genetics` reuses `pedigree_engine` (Wright's F/relatedness/cycle) — buck/doe wrapper only, no duplicate math. |
| **ARIA / AI router** | `rabbit_aria_service` reuses `ai_provider.complete` + `ai_settings_service`; deterministic-first; AR-01 bounded context; §4.4 no diagnosis; reuses platform `AI_QUERY`/`AI_INSIGHT_VIEW`. |
| **Mission Control** | `rabbit_intelligence.build_briefing` reads engine outputs; `mission_control_data.rabbit_briefing` orchestrates; reuses `InsightOut`/`InsightEvidenceOut`. |
| **Audit / Timeline / Files** | `audit_service`, `rabbit_event` timeline, `rabbit_media`/`rabbit_document` referencing the platform file store. |

## 10. Reusable platform capabilities relied upon

Auth/JWT, RBAC (`app/core/permissions.py`), Organizations/Farms, `species_profiles`
extensibility engine, Finance ledger, Inventory, Reminders/Notifications, Audit log,
Files/Media, Growth Planner, Pedigree engine, AI router (ARIA), Mission Control,
shared frontend components (`FactBadge`, `Button`, `Skeleton`, `Modal`, `useWorkspace`).

## 11. RBAC

27 `RABBIT_*` permissions (`rabbit:resource:action`) graded across the 8 roles in
`app/core/permissions.py` (`_RABBIT_VIEW`/`_RABBIT_FULL`): owner/manager/enterprise
full; worker operational (create/edit/breeding/health/weight/feed/automation) but
not archive/transact/catalog/housing-manage/sales/growth-edit nor strategic
finance/report/growth/sales **views**; vet read + `RABBIT_HEALTH_LOG`; viewer
read-only. ARIA/Mission reuse platform `AI_QUERY`/`AI_INSIGHT_VIEW`; cost posting
reuses platform `FINANCE_RECORD`.

## 12. Extension guide

- **New breed/bloodline attributes:** extend `rabbit_breed.profile` JSONB (e.g.
  `gestation_days`, `growth_curve`) — engines read them data-driven; no schema change.
- **New deterministic metric:** add a pure function to the relevant engine, surface
  it through the owning service, expose via a thin route. Never compute in a router
  or the frontend.
- **New Growth-Planner goal metric:** add a `metric_key` branch to
  `rabbit_growth_provider.provide` (must read recorded facts only).
- **New ARIA factual answer:** add a branch to `rabbit_aria_service._factual_answer`
  and a field to `compile_context` — keep it deterministic and cite `sources`.
- **New frontend screen:** add an `api/rabbit*.ts` client + a `screens/rabbit/*`
  screen, a `RabbitSubnav` link, and a lazy route. Reuse `FactBadge`/`LabelledValue`.
- **IoT/RFID/auto-weighing (future):** the schema already carries `rfid`, immutable
  weight history and environmental-ready housing — ingest as recorded facts; engines
  need no redesign.

## 13. Known limitations

- **Frontend RBAC** is backend-enforced only (403 + error states); no per-control
  hiding. Consistent with avi/bsf.
- **ARIA online mode** requires a configured provider; otherwise it returns grounded
  offline/deterministic answers (by design).
- **Global breed starter-seed** is not shipped — the breed catalog starts empty; the
  UI creates breeds inline (breed-driven gestation/growth-curve read as `unknown`
  until a breed profile is populated).
- **Growth-Planner revision diff** UI is minimal (progress + goals shown; the
  `/compare` endpoint exists but has no dedicated screen yet).
- **Automation** (auto-generated rabbit tasks/workflows beyond vaccination reminders)
  is not a separate part — folded into Health/Reminders reuse.
- `npm run lint` is broken repo-wide (ESLint v9 vs legacy config) — the frontend
  gate is `tsc --noEmit` + `vite build`.

## 14. Implementation statistics

- **Migrations:** 5 (066–070). **Models:** 19. **Pure engines:** 10 (+2 reused).
- **Services:** 10 (incl. the Growth-Planner provider). **Endpoint modules:** 9
  (+ Mission briefing). **API operations:** 89 across 69 paths.
- **Backend tests:** 170 (97 unit + 73 integration). **Frontend:** 12 screens +
  9 API modules. **RBAC:** 27 `RABBIT_*` permissions.

## 15. Verification summary

- **Migrations:** apply + downgrade round-trip on the dev and test DBs; single head 070.
- **Backend:** 170 rabbit tests pass; regression green for Aviculture, BSF, Mission,
  Finance, Inventory and Reminders (shared platform code unaffected); `ruff` clean on
  all changed files; app boots (89 rabbit operations registered).
- **Frontend:** `npm run type-check` clean; `npm run build` succeeds; every screen
  browser-verified end-to-end (login → register → profile → dashboard/breeding/
  health/housing/growth/planner/reports/ARIA/mission) with **zero console errors**;
  honesty labels render correctly (e.g. `UNKNOWN` shown, never a fabricated 0).
- **Honesty framework:** every calculated value traces to recorded facts; every
  projection is `forecast`-labelled; ARIA/Mission are read-only and never diagnose.

---

_Per-milestone contracts, decisions and deviations: see the ledger →_
[`MODULE_17_RABBIT_LEDGER.md`](./MODULE_17_RABBIT_LEDGER.md).
