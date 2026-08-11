# Alerting Matrix

Vendor-neutral alert definitions for Greena. **Every trigger below is based on a signal
the platform actually exposes today** (see "Signal sources"); alerts for telemetry that
does not yet exist are listed separately in §"Not yet alertable". Wire these into whatever
tool the operator uses (Sentry alerts, Railway/Supabase alerts, an uptime checker).
Indexed from `RUNBOOK_INDEX.md`.

## Signal sources (what exists today)

| Source | Exposes |
|---|---|
| `GET /health` (unauth) | `200 {status:ok, db:connected}` / `503 {db:error}` |
| `GET /production/metrics` (Prometheus) | request counts + status, latency (avg/buckets), exceptions by type, **domain events**: `backup_created/failed`, `restore_failed`, `import_failed`, `export_created/failed`, `rate_limited` |
| `GET /production/status` | `status: healthy/degraded/unhealthy`, metrics summary, entity counts, `active_users_24h`, diagnostics |
| `GET /production/diagnostics` | checks: `database`, `schema`, `migrations`, `environment` (critical), `disk`, `background_jobs` (warning), `ai_providers`, `integrations` (info) |
| `GET /admin/ai/health` (admin) | per-key state (available/rate_limited/quota_exhausted/failed), usage |
| Sentry (prod) | unhandled exceptions / error events |
| Railway (infra) | CPU, memory, restarts |
| Supabase (DB) | connection count, deadlocks, storage |

**Escalation roles** (⚠️CONFIRM contacts before launch): **L1** on-call engineer → **L2** engineering lead → **L3** founder/operations.

## Matrix

| # | Alert | Class | Trigger (real signal) | Impact | Response | Escalation | Resolution verification |
|---|---|---|---|---|---|---|---|
| 1 | **API down** | **Critical** | uptime check on `/health` non-200 for 2 consecutive checks, OR `db:error` | Platform unavailable | **15 min** | L1→L2 at 30 min | `/health` 200 green 10 min; smoke login |
| 2 | **Database check failing** | **Critical** | `/production/diagnostics` `database`/`schema`/`migrations` = fail | Data layer broken/mismatched | 15 min | L1→L2 | all critical checks pass; row spot-check |
| 3 | **Config/secret invalid (boot refused)** | **Critical** | app fails to start; `environment` diagnostic fail | Deploy can't serve | 15 min | L1→L2 | app boots; `/health` 200 (DR §2.6) |
| 4 | **Failed deployment** | **Critical** | Railway health check fails post-deploy / restart loop | New version can't serve | 15 min | L1→L2 | rollback green (DR §2.7) |
| 5 | **Error-rate spike** | **High** | 5xx share of requests (from `/production/metrics`) > 2% over 5 min, OR Sentry error spike | Users hitting failures | 30 min | L1→L2 at 1 h | 5xx back < 0.5%; Sentry quiet |
| 6 | **Backup failed** | **High** | `backup_failed` event increments / `restore_failed` event | Recovery point missed | 1 h | L1→L2 | next backup `success`; DR §2.1 |
| 7 | **Background jobs failing** | **High** | `/production/diagnostics` `background_jobs` = fail (warning check) | Reminders/scheduled work not running | 1 h | L1→L2 | check passes; a job runs (DR §2.5) |
| 8 | **Disk pressure** | **High** | `disk` diagnostic = fail | Risk of write failures | 1 h | L1→L2 | `disk` check passes |
| 9 | **Resource saturation** | **High** | Railway CPU or memory sustained > 85% for 10 min, or memory climbing monotonically | Latency/degradation, possible OOM | 1 h | L1→L2 | resources back in band |
| 10 | **DB connections near cap** | **High** | Supabase active connections > 80% of the pool ceiling | Pool exhaustion risk | 1 h | L1→L2 | connections < 80% |
| 11 | **Deadlocks** | **High** | Supabase `deadlocks` counter increasing | Failed writes | 1 h | L1→L2 | deadlocks stop |
| 12 | **Latency degraded** | **Medium** | `/production/metrics` avg latency (or Sentry p95) above the endpoint's norm over 15 min | Slow UX | 4 h | L1 | latency back to norm |
| 13 | **Import/export failures** | **Medium** | `import_failed` / `export_failed` events rising | Data in/out broken for some users | 4 h | L1 | events stop; a job succeeds |
| 14 | **Auth rate-limit spike** | **Medium** | `rate_limited` event rate elevated | Possible brute-force/abuse (or misconfig) | 4 h | L1→L2 if sustained | source identified; rate normal |
| 15 | **All AI keys unavailable** | **Medium** | `/admin/ai/health` shows every key `quota_exhausted/failed` | ARIA on offline path (no data impact — degrades gracefully) | 4 h | L1 | a key `available`; ARIA answers |
| 16 | **AI provider check (info)** | **Informational** | `ai_providers` diagnostic = fail | ARIA degraded, platform fine | next business day | none | `ai_providers` info returns |
| 17 | **Integrations check (info)** | **Informational** | `integrations` diagnostic = fail | non-critical integration down | next business day | none | integration restored |

## Not yet alertable (no telemetry today — do not invent)

These appear in the Gate 5 metrics wishlist but are **not exposed** as signals yet, so **no
alert is defined** for them until the metric exists:
- **Cache hit/miss ratio** — the AI response cache reports only entry count in `/admin/ai/health`, not hit/miss.
- **Queue depth** — there is no external queue (the scheduler is in-process); only `BackgroundJob` row status exists.
- **Retry counts**, **per-worker utilization** — not currently emitted.

Add these to the metrics registry (or the load-test instrumentation) before defining alerts on them.
