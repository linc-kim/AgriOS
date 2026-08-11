# k6 load-test scenarios (Gate 5)

Prereqs: install the **k6** binary (`winget install k6` / `brew install k6` / apt), stand up staging (see `docs/GATE_5_LOADTEST_PLAN.md`), seed it (`loadtest/seed_staging.py`), then:

```bash
BASE_URL=http://localhost:8000 TOKENS=../data/tokens.json k6 run <scenario>.js
```

| Scenario | Purpose |
|---|---|
| `mixed_workload.js` | realistic mixed traffic, ramp → 1,000 VUs, sustained 20 min |
| `login_storm.js` | authentication surge (429 from the auth limiter is expected, not a failure) |
| `burst.js` | sudden spike → recovery |
| `soak.js` | 12–24 h steady load (leak/pool watch) |
| `ai_heavy.js` | AI-concentrated traffic (chat/dashboard/insights) — provider throughput, cache, rotation |
| `dashboard_storm.js` | dashboard refresh storm — the heaviest reads (baseline: ai:dashboard 70q) |
| `reports_export.js` | concurrent CSV/report exports |
| `uploads_imports.js` | multipart CSV imports (dry-run) — upload guard + parse path |

## Scenarios that need extra setup (documented, not yet scripted end-to-end)

- **Payment workflow** — DEFERRED: Paystack is not integrated (owner decision, Gate-4 §6). Add a `payment.js` when Paystack lands, driving init + webhook-verify with idempotency.
- **Background-job saturation** — jobs are scheduler-driven, not directly HTTP-triggerable. Approaches: (a) drive job-*creating* endpoints (automation reminder generation, export creation) at high rate and watch queue depth / job latency; (b) temporarily lower the scheduler interval in staging. Measure via the metrics registry + `pg_stat_activity`.
- **Mixed farm sizes (small/medium/enterprise)** — extend `seed_staging.py` with a `--data-scale` that seeds farms with small / medium / enterprise data volumes (e.g., 50 / 1,000 / 20,000 animals + proportional logs), tag tokens with `size`, and weight `mixed_workload.js` so N+1 behaviour is exercised at each scale (the Phase-1 N+1 re-check needs this volume).
- **Image (multimodal) uploads** — need a real PNG fixture + a staging Gemini key; excluded here to avoid a binary in the repo.

## Metrics to capture per run (attach to the results report)

P50/P95/P99 (per `name`/`kind` tag), RPS, error rate — from k6. DB query counts (`pg_stat_statements`), pool utilization (`pg_stat_activity` vs `DB_POOL_SIZE+DB_MAX_OVERFLOW`), deadlocks, cache hit/miss (`GET /admin/ai/health`), CPU/mem/worker utilization (container stats), queue depth, retry counts — from the DB + app + host.
