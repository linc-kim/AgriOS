# GATE 5 — Performance Report (TEMPLATE — copy per run/cycle)

> Copy this file to `docs/perf/GATE_5_RESULTS_<scenario>_<YYYY-MM-DD>.md` and fill it.
> Keep every copy — the series is the platform's performance history.
> **Only numbers collected from the run go here. No estimates, no fabrication.**

## Run metadata

| Field | Value |
|---|---|
| Date / time | |
| Scenario(s) | mixed / login_storm / burst / ai_heavy / dashboard_storm / reports_export / uploads_imports / soak |
| Cycle | baseline / optimization-N |
| Environment | local-docker / cloud-staging |
| App: instances × workers | |
| DB: version, `max_connections` | |
| Pool: `DB_POOL_SIZE` + `DB_MAX_OVERFLOW` → ceiling `(pool+ovf)×workers×instances+1` | |
| Seed: users / data-scale | |
| k6: peak VUs / duration | |
| Commit SHA under test | |

## Performance dashboard (fill from collected evidence)

| Metric | Value | Target | Pass? |
|---|---|---|---|
| Latency P50 (non-AI) | | — | |
| Latency P95 (non-AI) | | < 500 ms | |
| Latency P99 (non-AI) | | < 1000 ms | |
| Requests per second | | — | |
| Error rate | | < 0.5% | |
| DB query count (per key endpoint) | | — | |
| Connection-pool utilization (peak vs ceiling) | | no exhaustion | |
| Cache hit / miss ratio | | — | |
| CPU utilization (peak) | | headroom | |
| Memory utilization (peak / trend) | | stable | |
| Worker utilization | | balanced | |
| AI throughput (req/s, provider) | | — | |
| Queue depth (peak) | | bounded | |
| Retry counts | | low | |
| Deadlocks | | 0 | |
| Cross-tenant leakage | | 0 | |

## Latency by endpoint (from k6 `name`/`kind` tags)

| Endpoint | RPS | P50 | P95 | P99 | error % |
|---|---|---|---|---|---|
| | | | | | |

## Top endpoints (by volume and by time)

| Endpoint | share of traffic | share of total time |
|---|---|---|
| | | |

## Slow queries (`pg_stat_statements`, top 20 by total_exec_time)

| query (normalized) | calls | total ms | mean ms |
|---|---|---|---|
| | | | |

## Success-criteria verdict (Gate 5)

- [ ] 1,000 concurrent users, no crashes
- [ ] Zero cross-tenant leakage
- [ ] No connection-pool exhaustion
- [ ] No deadlocks
- [ ] Error rate < 0.5%
- [ ] 95% non-AI < 500 ms
- [ ] 99% non-AI < 1 s
- [ ] Graceful degradation (not cascading failure)

## Optimization candidates surfaced this run

| # | Endpoint / area | Evidence (metric + value) | Hypothesized cause | Proposed change |
|---|---|---|---|---|
| 1 | ai:dashboard | queries=…, p95=… | serial aggregation fan-out | e.g. `asyncio.gather` / cache |
| 2 | finance:analytics | | | |
| 3 | auth/farm-access floor | ~8 q/request | per-request principal + membership lookups | per-request principal cache |
| … | | | | |

## Before / after (fill on the NEXT cycle after an approved optimization)

| Metric | Before (SHA) | After (SHA) | Δ | Kept? |
|---|---|---|---|---|
| target endpoint p95 | | | | |
| target endpoint query count | | | | |
| error rate | | | | |
| regression suite | 1909 passed | | | |

## Notes / anomalies / follow-ups

-
