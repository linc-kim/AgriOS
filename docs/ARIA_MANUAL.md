# ARIA Manual — Greena's AI Assistant

ARIA is Greena's built-in farm intelligence. This covers what it does, how it
works, and how to operate it — grounded in the real AI configuration
(`app/config.py`, `app/services/ai_provider_manager.py`, migration 051).

## 1. What ARIA is
A farm-aware assistant that answers questions and generates insights from **your
own farm data**. It is embedded across Greena and reachable wherever you see the
assistant. It is not a generic chatbot — its answers are grounded in your
flocks, health, feed, and finance records.

## 2. How ARIA thinks (deterministic-first)
1. **Deterministic layer first** — for questions Greena can answer directly from your data (counts, statuses, simple calculations), ARIA responds from the database, exactly and cheaply. No AI guesswork on hard facts.
2. **AI provider fallback** — for open-ended questions it calls an LLM with a bounded snapshot of your farm context.
3. **Offline fallback** — if AI providers are unavailable, ARIA still returns a safe, useful response rather than failing. The app never blocks on AI.

## 3. Providers & limits (real config)
- **Providers**: Gemini (primary, supports multiple keys with round-robin rotation + failover) and Claude. Configured via `GEMINI_API_KEY(S)`, `CLAUDE_API_KEY`.
- **Key routing**: `AI_KEY_ROUTING = round_robin` (spreads load; `primary`/`least_failures` available).
- **Timeout**: `AI_CALL_TIMEOUT_SECONDS = 15` — bounded, never hangs.
- **Context budget**: `AI_CONTEXT_MAX_TOKENS = 8000` — the farm-context snapshot is capped; it embeds your data so responses are tenant-safe (a prompt hash includes the farm snapshot, so caching never leaks across farms).
- **Answer length**: `AI_RESPONSE_MAX_WORDS = 150` — concise by design.
- **Response cache**: `AI_RESPONSE_CACHE_TTL_SECONDS` (default 0 = off) — identical prompts can return the cached completion when enabled; the offline fallback is never cached.

## 4. Monthly query limits (per plan)
| Plan | ARIA queries / month |
|---|---|
| Free | 100 |
| Starter | 2 000 |
| Professional | 10 000 |
| Farm Pro | 50 000 |
| Enterprise | unlimited |

Limits are a cost-control lever (each AI call has provider cost) and a fair-use guard. When you hit the cap, deterministic answers still work; open-ended AI resumes next cycle or on upgrade.

## 5. Daily Insights
Every morning at **06:00 (Africa/Nairobi)** ARIA generates per-farm insights from the prior day's data (production trends, health flags, things to watch). These appear on your dashboard without you asking.

## 6. Using ARIA well
- **Be specific**: "egg production for house 2 this week" beats "how are things".
- **Ask for actions**: "what should I feed batch 3 today?" — ARIA uses your feed and growth data.
- **Trust the deterministic answers**: counts and statuses come straight from your records.
- **Documents**: ARIA can work with uploaded documents/settings per farm (migration 051 `ai_settings` + `ai_documents`), where enabled.

## 7. Safety & privacy
- ARIA answers only from **your** organization's data — tenant isolation applies to AI context exactly as it does to the API (cross-farm data never enters your prompt).
- AI keys are backend-only and never reach the browser.
- If a provider misbehaves, rotate its key in Render env and redeploy; ARIA fails over automatically in the meantime.

## 8. Administration
- Set/adjust AI provider keys and model (`GEMINI_MODEL`, `CLAUDE_MODEL`) via Render env.
- Watch AI usage in `ai_usage_log`; watch cost at the provider dashboards.
- Turn on the response cache (`AI_RESPONSE_CACHE_TTL_SECONDS > 0`) to cut cost/latency for repeated prompts.
