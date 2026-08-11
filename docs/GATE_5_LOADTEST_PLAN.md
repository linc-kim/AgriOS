# GATE 5 — Phase 2/4 Load-Test Plan & Assets

**Status:** assets built; **not executed** (needs a staging environment stood up). No optimizations. Not committed until approved.
**Date:** 2026-08-11

## 1. Tooling decision & justification (required before introduction)

**Chosen: [k6](https://k6.io) (Grafana k6).** Not added as a repo/language dependency — k6 is a **single self-contained binary** the operator installs (`winget install k6` / `brew install k6` / apt); the scenarios are plain JavaScript run by that binary. Nothing is imported into the Python app.

Why k6 over the alternatives:
- **Why not the pytest/httpx in-process harness (Phase 1):** it is single-process, no network, and has no concurrency/ramp/think-time model — it cannot generate 1,000 concurrent virtual users or measure real HTTP latency percentiles.
- **Why k6 over Locust:** k6's Go engine sustains thousands of VUs at far lower generator-side CPU than Locust's Python (a laptop generator otherwise becomes the bottleneck and pollutes results), and k6 has first-class `thresholds` that map directly onto the Gate 5 success criteria (fail the run if P95/error-rate exceed targets). Locust is a fine fallback if the team prefers Python.

**Honest caveat (carried from Phase 1):** absolute latency depends on the environment. On a laptop/local-docker staging the numbers are generator- and hardware-bound. What *is* meaningful even locally: **connection-pool exhaustion, deadlocks, cross-tenant leakage under concurrency, error-rate under load, and graceful-degradation vs cascading-failure** — several Gate 5 criteria are about those, not just latency.

## 2. Staging environment (mirror prod, isolated)

Two supported ways to stand up an isolated staging that uses the **same components as production** (Postgres, the FastAPI app, config, AI where appropriate) with **separate credentials/resources**:

**(A) Local/CI docker stack — `infrastructure/staging/docker-compose.yml`** (provided): Postgres 16 + the backend image (built from `backend/Dockerfile`, uvicorn, multiple workers). Reads `infrastructure/staging/.env.staging` (copy from `.env.staging.example`, fill isolated secrets). Fast to iterate; hardware-bound.

**(B) Cloud staging (closest to prod, owner-provisioned):** a **separate** Railway service + a **separate** Supabase project (never prod creds/data), same config keys. Recommended for the numbers that must resemble production. **Owner action** — I cannot create accounts or enter cloud credentials.

Either way: **no production deployment, no real user data.**

## 3. Seed data — `loadtest/seed_staging.py`

Seeds an isolated staging DB with a configurable population (default: 1 org, N users each owning a farm, plus per-farm flocks/logs/finance rows so reads are realistic and the N+1 re-check is valid at volume). It writes `loadtest/data/tokens.json` — `[{email, password, farm_id, token}]` — consumed by the k6 scripts. Run:

```bash
DATABASE_URL=<staging> python loadtest/seed_staging.py --users 1000 --data-scale medium
```

## 4. Scenarios — `loadtest/k6/`

All read `BASE_URL` and `loadtest/data/tokens.json` (via env). Thresholds encode the Gate 5 criteria and **fail the run** when breached.

| Script | Models | Key settings |
|---|---|---|
| `mixed_workload.js` | realistic mixed traffic across all modules (dashboards, lists, finance, health, AI chat, a write) weighted like real farmer use | ramp 0→1000 VUs, sustain 15–30 min |
| `login_storm.js` | many simultaneous `POST /auth/login` | high arrival rate, short duration |
| `burst.js` | sudden spike then drop | arrival-rate spike |
| `soak.js` | steady moderate load for 12–24 h | leak/pool watch |

**Thresholds (non-AI requests):** `http_req_duration{kind:noai} p(95)<500ms, p(99)<1000ms`; `http_req_failed rate<0.005`; AI endpoints are tagged `kind:ai` and excluded from the latency SLO (provider-bound), but still counted for error rate.

## 5. What to collect (Phase 2/4 measurements)

Per run, capture and attach to the results report:
- k6 summary: P50/P95/P99 per endpoint tag, error rate, RPS, VU count.
- **DB:** connection-pool utilization (`pg_stat_activity` count vs `DB_POOL_SIZE+DB_MAX_OVERFLOW`), deadlocks (`pg_stat_database.deadlocks`), slow queries (`pg_stat_statements`), locks.
- **App:** CPU/memory (container stats), `X-Process-Time` header, the `/metrics` registry, `GET /admin/ai/health` (key/usage), AI response-cache hit ratio.
- **Correctness under load:** a probe asserting **zero cross-tenant leakage** (reuse the isolation sweep against live data) and no 5xx spikes; recovery after load stops.

## 6. Reliability (Phase 4) procedures

- **Graceful degradation:** push past capacity; confirm the app sheds/queues non-critical work (AI enrichment, exports) while auth/record-entry/payments stay responsive, rather than cascading 5xx.
- **DB restart recovery:** restart the staging Postgres mid-load; confirm the pool reconnects and requests recover.
- **AI provider failure:** point Gemini/Claude keys at a failing endpoint; confirm the Provider Manager fails over then degrades to offline (already unit-proven; validate under load).
- **Leak detection:** the soak run watches RSS and `pg_stat_activity` for monotonic growth.

## 7. Success criteria (Gate 5) — mapped to thresholds

| Criterion | Where measured |
|---|---|
| 1,000 concurrent users, no crashes | mixed_workload sustained stage |
| Zero cross-tenant leakage | isolation probe under load |
| No pool exhaustion | `pg_stat_activity` vs pool ceiling |
| No deadlocks | `pg_stat_database.deadlocks` == 0 |
| Error rate < 0.5% | k6 `http_req_failed` threshold |
| 95% non-AI < 500 ms | k6 `p(95)` threshold (staging-relative) |
| 99% non-AI < 1 s | k6 `p(99)` threshold (staging-relative) |
| Graceful degradation | Phase 4 overload procedure |

## 8. Sequence from here

1. **Owner:** stand up staging (A local-docker for iteration, and/or B cloud for prod-like numbers).
2. Seed via `seed_staging.py`.
3. Run scenarios, collect §5 evidence → `docs/GATE_5_LOADTEST_RESULTS.md`.
4. **Only then**, Phase 3 optimizes the measured bottlenecks (candidates: `ai:dashboard` 70q, `finance:analytics` 39q, `finance:overview` 20q, ~8q auth floor) with **before/after** evidence.

No optimization is performed until staging measurements justify it.
