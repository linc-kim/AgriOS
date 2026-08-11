# GATE 5 — Phase 1 Performance Baseline

**Status:** baseline measurement only. **No optimizations made** (Phase 3 is evidence-gated and comes after approval). **Awaiting approval.** Not committed.
**Date:** 2026-08-11 · **Branch:** `phase-2-auth` (local)

## 1. Method & environment (read this before the numbers)

- **How:** the app is exercised **in-process** through the ASGI test harness (`httpx.ASGITransport`), with a SQLAlchemy `before_cursor_execute` listener counting the **number of SQL statements per request** (`tests/performance/test_perf_baseline.py`). 16 representative farm-scoped GET endpoints across all launch modules, 5 iterations each, median reported.
- **The trustworthy signal is the QUERY COUNT.** It is environment-independent — the number of round trips an endpoint makes does not change with hardware — so it is honest evidence of round-trip/N+1 cost and is directly actionable.
- **The `ms` column is LOCAL DEV ONLY** — in-process (no network), single worker, tiny seeded dataset, on a developer laptop. It is a *relative* comparison between endpoints, **not** production latency, and must not be read as the Gate 5 P50/P95/P99 targets. Those require Phase 2 (below).
- **Environment constraint (declared, not worked around):** production is Railway + Supabase; both are unreachable here, and this gate is **no-deploy**. A production-representative **1,000-concurrent-user load test and 12–24h soak (Phases 2 & 4)** cannot produce honest evidence on a single local machine with an embedded Postgres — a laptop and a local single-node PG do not represent production hardware, and an on-box load generator competes with the app. Reporting "1,000 users passed" from here would be fabricated. §5 documents how to run Phases 2 & 4 correctly.

## 2. Measured baseline (query count + local latency)

| endpoint | http | queries (median) | local ms (median) |
|---|---|---|---|
| **ai:dashboard** | 200 | **70** | 513 |
| **finance:analytics** | 200 | **39** | 297 |
| **finance:overview** | 200 | **20** | 175 |
| core:production-dashboard | 200 | 14 | 130 |
| health:summary | 200 | 13 | 128 |
| core:farm | 200 | 11 | 106 |
| finance:transactions | 200 | 9 | 94 |
| aviculture:birds | 200 | 9 | 92 |
| bsf:batches | 200 | 9 | 92 |
| core:flocks | 200 | 8 | 84 |
| health:alerts | 200 | 8 | 83 |
| aria:insights | 200 | 8 | 80 |
| automation:reminders | 200 | 8 | 83 |
| rabbit:breeds | 200 | 8 | 90 |
| operations:routines | 200 | 8 | 85 |
| data:exports | 200 | 8 | 88 |

## 3. Findings (evidence-backed)

**F1 — Fixed per-request auth/farm-access floor ≈ 8 queries.** Every farm-scoped request pays a constant ~8 statements before doing its own work: `get_current_user` (user + roles) + `require_farm_access` (farm + active membership + role + plan). Most list endpoints sit at exactly 8–9, i.e. the floor + 1 data query — those are **healthy** (no per-row N+1). Because this cost is paid on *every* authenticated request, shaving it benefits the whole platform.

**F2 — `ai:dashboard` = 70 queries — top round-trip suspect.** `ai_platform_service.get_dashboard` composes many independent analytics (feed forecast, finance analytics, inventory reorder, mortality prediction, disease risk, egg forecast…), each running several sequential aggregation queries. It is **not** a per-row N+1 but a **serial fan-out** of many independent reads.

**F3 — `finance:analytics` (39) and `finance:overview` (20)** — same shape: several sequential aggregations/period loops composed into one response.

**F4 — No classic per-row N+1 detected on the sampled list endpoints** — collection endpoints stay at the floor as row count grows within the seeded set (query count did not scale with the returned list). This should be re-confirmed on a **larger dataset** (see §4) because the seed is tiny.

## 4. Metrics NOT honestly measurable here (require a production-like environment)

| Requested metric | Why not now | How to get it |
|---|---|---|
| API P50/P95/P99 (real) | in-process, no network, laptop ≠ prod | Phase 2 load test against staging |
| AI request latency | no provider keys locally (offline path only) | staging with a real Gemini key; measure via `ai_usage_log.duration_ms` |
| Connection-pool utilization | only meaningful under concurrency/prod worker count | Phase 2; expose pool metrics |
| CPU / memory | laptop ≠ Railway container limits | Phase 2/4 on staging |
| Cache hit/miss ratio | AI response cache is off by default; no app data cache yet | enable + measure under Phase 2 |
| Background-job throughput | single embedded scheduler, tiny data | staging with realistic job volume |
| N+1 under realistic volume | seed dataset is tiny | seed a large dataset (thousands of animals/logs) and re-run this profiler |

## 5. Phase 2 & Phase 4 execution plan (tooling justified, not introduced yet)

To run these honestly, **owner action is required** to provision a target:
1. **A staging environment** that mirrors production (Railway backend + a Supabase/Postgres instance with a production-sized seed). No changes to prod.
2. **A load tool — recommend [k6](https://k6.io) or [Locust](https://locust.io).** *Why needed:* generating 1,000 concurrent virtual users with realistic think-time, ramp, burst, and mixed workloads is not something the pytest/httpx in-process harness can do (it's single-process, no network, no concurrency model). k6 (Go, single binary, scriptable scenarios) or Locust (Python, familiar) both model concurrency, ramp/soak, and percentile reporting. **Neither is added to the repo yet** — pending approval and a staging target, since installing/running them locally against a laptop would only measure the laptop.
3. **Scenarios** to script: login storm, sustained mixed 1,000-user workload (15–30 min), burst, concurrent uploads, concurrent AI, concurrent finance ops, then a 12–24h soak with memory/connection-leak watch.

## 6. Proposed Phase-3 optimizations (candidates only — NOT implemented)

Each references the finding that justifies it; none will be built until measurements justify and you approve:
- **F2/F3:** parallelize the independent aggregation queries in `get_dashboard` / finance analytics with `asyncio.gather` (they're independent reads), and/or serve the dashboard from the existing response cache with a short TTL. Candidate — measure the query-count/latency delta before/after.
- **F1:** consider a per-request cache of the auth principal + farm membership so the ~8-query floor drops (benefits every endpoint). Candidate — verify with the profiler.
- **F4:** re-run this profiler against a large seeded dataset to confirm no hidden N+1 before optimizing.

## 7. Statement of integrity

No application code was changed in Phase 1 — only an additive measurement harness (`tests/performance/test_perf_baseline.py`) and this report. The 1909-passing regression baseline is therefore unaffected. No 1,000-user, latency-percentile, soak, or resource numbers are claimed, because they cannot be honestly produced in this environment.
