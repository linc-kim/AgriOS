# GATE 4 — AI, Infrastructure & Observability — Report (Increment 1 of Gate 4)

**Scope of this increment:** the **AI Provider Manager** keystone — multi-key Gemini rotation, failover, health tracking, extensible provider registry, and centralized routing of the shared AI façade. Remaining Gate 4 items are mapped in §"Focus-area status" and proposed as follow-up increments.
**Status:** implemented + verified. **Awaiting owner approval. NOT committed, NOT pushed.**
**Date:** 2026-08-11 · **Branch:** `phase-2-auth` (local)

## Objectives completed (this increment)
1. **AI Provider Manager** (`app/services/ai_provider_manager.py`) — one service every completion flows through. Registry of providers; each provider owns its keys.
2. **Gemini multi-key round-robin** — `GeminiProvider` rotates across N keys; the cursor advances on each success.
3. **Automatic failover + health states** — per-key state machine `AVAILABLE / RATE_LIMITED / QUOTA_EXHAUSTED / FAILED` with cooldowns (429→60s, quota→1h, transient→120s). On 429/quota/5xx/timeout it fails over to the next key, then the next provider (Claude), then a grounded **offline** completion. HTTP status → error-kind classification (`_classify_status`).
4. **Extensible registry** — `manager.register(provider)`; adding a key or a new provider (OpenAI, etc.) is registration, not an ARIA rewrite. `manager.health()` exposes per-provider/per-key status for observability.
5. **Centralized façade** — `ai_provider.complete()` now delegates to the manager (unchanged public `AIResult` contract; offline behavior preserved). `summarize()` rides on `complete()`.
6. **Multi-key config** — `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEYS` (csv), surfaced via `settings.gemini_api_keys` (deduped, order-preserving). Documented in `.env.example` (names only).
7. **Confidence/explainability metadata** — `Completion.confidence` (offline path marked `"offline"`); groundwork for surfacing through callers.
8. **Configurable routing policy** (owner request) — key selection is no longer hardcoded: `AI_KEY_ROUTING = round_robin | primary | least_failures` (`RoutingPolicy` enum; unknown value falls back to round-robin with a warning). `round_robin` spreads load, `primary` sticks to the lowest-index usable key, `least_failures` prefers the healthiest key.
9. **Per-key health + usage metrics** (owner request) — each key tracks `state`, `requests`, `successes`, `failures`, `cooldown_remaining`, `prompt_tokens`, `completion_tokens`, `last_used_at` (`key_health()`); Claude tracks the same. `manager.usage()` aggregates counters across all keys/providers; `manager.health()` also reports the active policy.
10. **Legacy entry points preserved + offline/test behavior intact** (owner request) — `aria_service._call_gemini/_call_claude` and their monkeypatches are untouched; empty keys → offline exactly as before.

## Focus-area status (all Gate 4 items)
| Area | Status |
|---|---|
| Gemini key rotation (round-robin) | ✅ Done |
| Failover on quota/transient errors | ✅ Done |
| Centralized AI client abstraction | ◑ Partial — the shared `ai_provider` façade now routes through the manager; the **legacy `aria_service._call_gemini` core-chat path is not yet migrated** (its 6 `test_aria_flow` monkeypatches must move to the manager). Proposed as increment 2. |
| Prompt-injection defenses | ◑ Existing — `redact_secrets`, bounded farm-only context, never-diagnose (`ai_provider.py`, Security std §22). A dedicated injection test-suite is proposed. |
| Conversation/context limits + cost controls | ✅ Existing — `AI_CONTEXT_MAX_TOKENS=8000`, `AI_RESPONSE_MAX_WORDS=150`, per-farm `monthly_budget_usd`, immutable `ai_usage_log` (no change needed). |
| AI request/response caching (where safe) | ☐ Deferred — needs a tenant-scoped, freshness-aware design; proposed increment. |
| Confidence & explainability metadata | ◑ Started — manager emits `confidence`; surfacing to API responses proposed. |
| PostHog (flags/analytics/error tracking) | ☐ Not enabled — no `POSTHOG_*` config; needs a key + owner go-ahead ("if enabled"). Sentry already covers error tracking (prod-gated). |
| Routing policy | ✅ Configurable (`AI_KEY_ROUTING`: round_robin / primary / least_failures) — no longer hardcoded. |
| Logging / metrics / observability | ◑ Improved — per-key `state/requests/successes/failures/cooldown/tokens/last_used` via `key_health()`, `manager.usage()` aggregate, `manager.health()` (+ active policy), failover logging (key **index** only). Wiring an AI-health *endpoint* still proposed. |

## Files changed (delta)
- `backend/app/services/ai_provider_manager.py` — **new** (manager, providers, health).
- `backend/app/services/ai_provider.py` — `complete()` delegates to the manager.
- `backend/app/config.py` — `GEMINI_API_KEY_2`, `GEMINI_API_KEYS`, `gemini_api_keys` property, `AI_KEY_ROUTING` policy; also removed a **pre-existing** unused `AnyHttpUrl` import so the now-active CI lints clean on this file.
- `backend/tests/unit/test_ai_provider_manager.py` — **new** (16 tests: routing, rotation, failover, health, offline, configurable policy, per-key + aggregate metrics).
- `.env.example`, `backend/.env.example` — new variable names documented (no secrets).
- `docs/GATE_4_REPORT.md`, `docs/GREENA_STANDARDS_GAP_AUDIT.md`.

## Database migrations
**None.**

## Tests executed
- **Environment:** local embedded Postgres 16.14 `127.0.0.1:5433`; Python 3.12 venv; AI keys empty (offline path); `ENVIRONMENT=development`.
- `pytest tests/unit/test_ai_provider_manager.py + 7 AI integration files` → **109 passed** in 84.2s (confirms the `complete()` rewiring is regression-clean, incl. `test_aria_flow` which patches the untouched legacy path).
- After adding the configurable policy + metrics: `pytest manager + test_aria_flow + test_ai_platform_module` → **39 passed** in 23.1s; `ruff check` on all changed files → **clean**.
- **Full regression:** `pytest -q` → **1881 passed, 0 failed in 323.4s (5m23s)**.
- **Skipped:** none newly skipped.

## Tests passed / failed
**1881 passed, 0 failed, 0 errors.** Baseline before Gate 4 was 1865; new this increment: **+16 unit tests**. No live provider was called (rotation/failover/metrics covered by fakes — no network, no real key used).

## Coverage impact
New manager logic is unit-covered (rotation, failover, health, offline). Façade behavior unchanged and still covered by existing AI integration tests.

## Performance impact
None. The manager adds in-process branching only; the network call is identical to before. Offline path unchanged.

## Security impact
Positive/neutral. Keys remain backend-only and are never logged (failover logs the key **index**, never the value). No new external exposure. **The key shared in chat should be rotated** (treat as exposed — Doc 3 §39) and placed in env by the owner; Claude did not persist it.

## Breaking changes
**None.** `ai_provider.complete()` keeps its signature and `AIResult` shape; existing monkeypatches and offline behavior are preserved.

## Rollback strategy
`git revert` the increment. The manager module is additive; reverting `ai_provider.complete()` restores the prior inline gemini→claude→offline logic. No migrations, no data, no external state.

## Remaining risks / limitations
- Legacy `aria_service._call_gemini` core-chat path still single-key until increment 2 (production rotation applies to the `ai_provider` façade now, not yet to that path).
- AI caching, PostHog, and an AI-health endpoint not yet built.
- Manager singleton reads keys at first build; `reset_manager()` exists for rotation/tests.

## Owner action required (credentials)
Add the second Gemini key yourself (Claude will not persist secrets): set `GEMINI_API_KEY_2=<value>` in `backend/.env.local` (dev) and in Railway (prod). Recommend rotating the key that was shared in chat. Confirm the `AQ.…` value is a Generative Language API key (usual format is `AIza…`).

## Recommendation
**Proceed.** The keystone is in place and verified with zero regressions. Recommend approving increment 1 (commit), then continuing Gate 4 with: (2) migrate the ARIA core path onto the manager, (3) safe tenant-scoped AI response cache, (4) confidence surfacing + AI-health endpoint/metrics, (5) PostHog only if you enable it.
