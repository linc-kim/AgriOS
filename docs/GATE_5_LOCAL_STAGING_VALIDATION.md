# GATE 5 — Local Staging Validation (asset functional check)

**Purpose:** validate that the load-testing assets *function correctly*. **These are NOT performance results** — this environment is a developer laptop with an embedded Postgres; no number here is production evidence (that is the cloud-staging phase).
**Status:** validated within tooling limits. Awaiting approval. Not committed.
**Date:** 2026-08-11

## Environment reality

**Docker and k6 are not installed on this machine** (verified: `docker`/`k6` not found; no Docker Desktop). So the *containerized* stack and the *k6* binary cannot be executed here. Rather than fabricate those runs, the same validations were performed with equivalent tools already present:
- **uvicorn** (standalone real HTTP server) — substitute for the Docker container.
- **httpx** (Python, real HTTP + concurrency) — substitute for low-volume k6.

## Checklist results

| Step-1 item | Result | How |
|---|---|---|
| Container startup | ⚠️ **substituted** | Docker absent → started the app as a standalone `uvicorn` server on `127.0.0.1:8000`; it booted and served. Container-in-Docker itself unverified here. |
| DB migration verification | ✅ PASS | `alembic upgrade head` applied all 86 migrations (→086) to a fresh local `agrios` DB. |
| Health checks | ✅ PASS | `GET /health` → `200 {status: ok, db: connected}` on the live server. |
| Authentication verification | ✅ PASS | `POST /auth/login` (seeded email/password) → `200` with a valid `access_token` (~960 ms — Argon2 cost). |
| Seeder verification | ✅ PASS | `seed_staging.py --users 20` seeded org/users/farms and wrote `tokens.json`; re-runnable (unique per run). |
| Smoke tests | ✅ PASS | Authed `GET /farms/{id}` with a seeded token → `200`. |
| Low-volume k6 execution | ⚠️ **substituted** | k6 absent → 50 concurrent authed `GET .../production-dashboard` via httpx → **50/50 = 200**, no errors/crashes. Functional only; the ~4.9 s wall for 50-concurrent on one worker on a laptop is **not** latency evidence. |

## What this proves (and what it does not)

**Proves:** the app boots as a real server, migrations apply cleanly, `/health` reflects DB state, email/password auth issues tokens, the seeder produces working tokens the scenarios consume, and the authenticated read surface serves concurrent requests without errors. **The load-testing assets are wired correctly against a running target.**

**Does not prove (needs the cloud-staging phase + Docker/k6):** any latency percentile, throughput, pool utilization, CPU/memory, cache-ratio, soak/leak, or 1,000-user behaviour. Those remain unmeasured and unclaimed.

## Remaining to run the containerized + k6 validation

On a machine with Docker + k6:
```bash
cp infrastructure/staging/.env.staging.example infrastructure/staging/.env.staging   # fill isolated secrets
docker compose -f infrastructure/staging/docker-compose.yml up --build                # container startup + migrations
DATABASE_URL=<staging> python loadtest/seed_staging.py --users 1000 --yes
BASE_URL=http://localhost:8000 k6 run loadtest/k6/mixed_workload.js                    # low VUs first, functional
```
Then proceed to cloud staging for the actual Phase-2/4 measurements.
