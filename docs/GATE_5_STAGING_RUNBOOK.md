# GATE 5 — Cloud Staging Runbook (Phase 2/3/4 execution)

Everything needed so that, once a staging environment exists, the **only** remaining
work is running the prepared scenarios and analyzing the evidence. No optimization is
implemented until measurements justify it and the owner approves.

> Discipline (unchanged): local commits only, no push, no production deployment,
> evidence-first, stop for approval before any optimization.

---

## 1. Infrastructure prerequisites

| Component | Purpose | Notes |
|---|---|---|
| Backend host | run the API (same as prod: Railway, or a container host) | ≥ prod-equivalent CPU/RAM; multiple uvicorn workers |
| PostgreSQL 16 | system of record | **separate** instance/project from prod; note its `max_connections` |
| (optional) Redis | only if a shared cache/queue is later introduced | not required for launch scope |
| Load generator host | runs k6 | **separate from the app host** (a co-located generator steals CPU and pollutes results) |
| k6 | load tool | install the binary on the generator host |
| Observability | container CPU/mem stats; DB stats access | enable `pg_stat_statements` on the staging DB |

**Isolation rules:** never reuse production credentials, keys, or data. Staging uses its own secrets and a disposable dataset.

---

## 2. Staging deployment

**Path A — local docker (fast iteration, hardware-bound):**
```bash
cp infrastructure/staging/.env.staging.example infrastructure/staging/.env.staging   # fill §3
docker compose -f infrastructure/staging/docker-compose.yml up --build -d
docker compose -f infrastructure/staging/docker-compose.yml logs -f api               # watch startup + migrations
```

**Path B — cloud staging (prod-like numbers, recommended for Phase 2/4):**
1. Provision a **separate** backend service mirroring prod (same image from `backend/Dockerfile`, same worker count, same instance size).
2. Provision a **separate** Postgres (Supabase project or managed PG), record its connection string + `max_connections`.
3. Set the environment variables from §3 in the service (isolated secrets).
4. Deploy; the container runs `alembic upgrade head` then uvicorn (see the compose `command`; replicate in the service start command).

---

## 3. Environment variable checklist

| Var | Required | Staging value |
|---|---|---|
| `ENVIRONMENT` | ✅ | `staging` |
| `SECRET_KEY` | ✅ | fresh random (never prod) |
| `JWT_SECRET` | ✅ | fresh random (never prod) |
| `DATABASE_URL` | ✅ | staging Postgres (asyncpg) |
| `DATABASE_SSL` | ✅ | `true` for managed PG; `false` for in-cluster docker |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | ✅ | start at prod values; **compute** `(pool+overflow)×workers×instances + 1 ≤ DB max_connections` |
| `ALLOWED_ORIGINS` | ✅ | staging frontend origin |
| `GEMINI_API_KEY` / `_2` | ⛔/opt | **staging** Gemini key(s) only, or empty to load-test the offline path |
| `AI_KEY_ROUTING` | opt | `round_robin` |
| `AI_RESPONSE_CACHE_TTL_SECONDS` | opt | set > 0 to measure cache hit ratio under load |
| `CLAUDE_API_KEY` | opt | staging key or empty |
| `AT_*`, `EMAIL_PROVIDER` | opt | dormant (`sandbox` / `console`) |
| `SENTRY_DSN` | opt | staging project or empty |

**Pool sizing is the #1 thing to get right** before a 1,000-user run — under-sizing hides real capacity, over-sizing exhausts Postgres. Record the computed ceiling in the results report.

---

## 4. Database initialization

```bash
# Against the staging DATABASE_URL (from backend/):
alembic upgrade head          # builds schema + seeds roles/plans/categories/species
# Confirm:
#   psql> select count(*) from alembic_version;  -- head applied
#   psql> select count(*) from roles;            -- 8
```
Docker path A runs this automatically on `up`.

---

## 5. Seeder execution

```bash
DATABASE_URL=<staging> python loadtest/seed_staging.py --users 1000 --yes
# writes loadtest/data/tokens.json  (gitignored; contains access tokens — do not commit)
```
- Start with `--users 1000` for the target test; use fewer for smoke.
- For **mixed farm sizes**, extend the seeder with `--data-scale` (small/medium/enterprise) before the N+1-at-volume runs (see `loadtest/k6/README.md`).
- Re-runnable (unique emails per run); each run regenerates `tokens.json`.

---

## 6. k6 execution

Run from the **generator host**, pointing at staging. Smoke each scenario at low VUs first.
```bash
export BASE_URL=https://staging.api.example   TOKENS=../data/tokens.json
cd loadtest/k6
k6 run --summary-export=../results/mixed_$(date +%F_%H%M).json mixed_workload.js
k6 run login_storm.js
k6 run burst.js
k6 run ai_heavy.js
k6 run dashboard_storm.js
k6 run reports_export.js
k6 run uploads_imports.js
k6 run --env SOAK_HOURS=12 soak.js     # Phase 4
```
Order: **smoke → mixed (staged 100→250→500→750→1000) → burst → scenario-specific → soak.** Do not jump to 1,000.

---

## 7. Results collection

For **every** run, capture (into `loadtest/results/` and the report template §Performance Dashboard):
- **k6 summary JSON** (`--summary-export`) → P50/P95/P99 per tag, RPS, error rate, VUs.
- **DB:** `select * from pg_stat_statements order by total_exec_time desc limit 20;` (slow queries + call counts); `select count(*) from pg_stat_activity where datname=current_database();` sampled during load (pool utilization); `select deadlocks,blks_read from pg_stat_database where datname=current_database();`.
- **App:** container CPU/mem (host stats / `docker stats`), worker count, `GET /admin/ai/health` (per-key usage, cache — via `manager.config().cache`), `/metrics` registry.
- **Correctness under load:** run the tenant-isolation probe against live staging data → assert zero cross-tenant leakage; scan logs for 5xx.
- **Recovery:** stop load; confirm pool/connections drain and latency returns to baseline.

---

## 8. Performance analysis

Fill `docs/GATE_5_PERFORMANCE_REPORT_TEMPLATE.md` (copy per run/cycle). It captures all required metrics + top endpoints + optimization candidates + before/after. Keep every cycle's copy to build a performance history.

---

## 9. Bottleneck investigation checklist

When a target is missed, work top-down before touching code:
1. **Which metric failed?** latency p95/p99, error rate, or a resource (CPU/mem/pool)?
2. **Where?** slice k6 by `name` tag → the offending endpoint(s).
3. **Resource-bound?** CPU saturated → compute/serialization; memory climbing → leak/large payloads; pool at ceiling → too few connections or slow queries holding them.
4. **DB-bound?** `pg_stat_statements`: high `total_exec_time` or `calls` → slow query or N+1. Cross-check the Phase-1 profiler query counts.
5. **Serial fan-out?** (e.g. `ai:dashboard` 70q) → many independent awaits run sequentially.
6. **AI-bound?** provider latency (expected) vs missing cache/dedup.
7. **Contention?** deadlocks/lock waits → transaction scope.
Record the identified bottleneck + the evidence line before proposing a fix.

---

## 10. Optimization workflow (Phase 3 — evidence-gated)

For each candidate, **one change at a time**:
1. Record the **before** measurement (query count via the Phase-1 profiler and/or the staging k6/DB numbers).
2. Propose the change referencing that measurement. **Stop for owner approval.**
3. Implement the smallest change; keep it in its own commit.
4. Re-measure (**after**) with the *same* method.
5. Record before/after in the report template; keep only if it measurably helps and breaks nothing (full regression stays green).
6. If no improvement → revert. Never keep an unjustified change.

Current candidates (hypotheses, from Phase 1 — do not optimize until staging-measured):
`ai:dashboard` (70q, serial fan-out), `finance:analytics` (39q), `finance:overview` (20q), auth/farm-access floor (~8q).

---

## 11. Rollback procedure

- **App:** each optimization is its own commit → `git revert <sha>` restores prior behavior; redeploy staging.
- **DB (if an index/migration was added):** every schema change ships as a reversible migration → `alembic downgrade -1`; verify with the query profiler.
- **Config (pool sizes, cache TTL, routing):** env-only → revert the value and restart; no code change.
- **Load itself:** k6 stop is immediate; confirm recovery (§7). Staging is disposable — it can be torn down and re-seeded without touching production.
