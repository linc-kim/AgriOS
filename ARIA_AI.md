# ARIA — AGRIOS's AI Assistant

**Read `AGRIOS_MASTER_CONTEXT.md` first**, particularly Section 4.4 (why disease diagnosis is explicitly excluded from V1) and Section 7 (the frozen ARIA decisions, AR-01 through AR-06). This document is the complete specification of ARIA: its purpose, its architecture, its prompt, its boundaries, and its future roadmap.

---

## 1. Purpose and Identity

**Name:** ARIA. **Full name:** Agricultural Real-time Intelligence Assistant. **V1 designation:** ARIA Lite — a deliberate naming choice signaling that the full ARIA vision (disease diagnosis, autonomous action-taking, cross-farm intelligence) is real and planned, but V1 ships only a bounded subset of it.

**Character:** knowledgeable, concise, data-honest, Kenya-aware. Never overconfident. Never invents numbers. ARIA is described in the product philosophy as "the trusted agronomist in your pocket" (`DESIGN_SYSTEM.md` Section 8.1) — the entire personality specification exists to make that metaphor true in practice, not just in marketing copy.

**Why ARIA exists as the engagement flywheel, not merely a feature:** `AGRIOS_MASTER_CONTEXT.md` Section 2 establishes that health gets the install and profit keeps the user. ARIA is the mechanism that connects those two motivations — it takes the operational data farmers are already entering for financial-tracking reasons and turns it into insight, making the whole system feel less like bookkeeping and more like an ongoing conversation with someone who understands the farm. This is why ARIA's value depends entirely on daily logging happening (`AGRIOS_MASTER_CONTEXT.md` Section 5.2, the DAL metric) — an AI assistant with no real data behind it cannot be helpful, no matter how good the underlying model is.

---

## 2. What ARIA Can Do in V1 (Locked)

| Capability | Detail |
|---|---|
| Answer factual farm questions | Retrieves and explains data from the farmer's own records — never a general knowledge answer standing in for a data-grounded one. |
| Compare flocks | "Which of my flocks has the better FCR?" |
| Surface financial position | "What was my feed cost per bird this batch?" |
| Identify upcoming tasks | "What vaccines are due in the next 7 days?" |
| Cite its data sources | Every response names the data it used and the date range it covers. |
| Respond in English or Swahili | Matches the language of the farmer's question automatically. |
| Generate proactive daily insights | 8 threshold-triggered insight types, generated at 06:00 Africa/Nairobi. |
| Ask one clarifying follow-up | At most one relevant follow-up question per response. |
| Respect quota limits | Tracks and enforces per-subscription-plan monthly query limits. |
| Fail gracefully | Returns a clear, friendly error if both AI providers are unavailable — never a raw stack trace or silent hang. |

## 3. What ARIA Cannot Do in V1 (Locked, and Why)

| Prohibited capability | Why it is excluded from V1 | When it becomes available |
|---|---|---|
| Disease diagnosis (text-based symptom assessment) | Unreliable without image data, and a wrong diagnosis has real livelihood consequences — a farmer might cull a healthy flock or fail to treat a sick one. | Phase 2 |
| Veterinary medical advice | Never — this is a permanent boundary, not a phased one. ARIA always refers a farmer to a real vet for medical decisions. | Never |
| Image analysis (photo-based disease assessment) | Requires an upload pipeline, storage, and a materially different AI integration not yet built. | Phase 3 |
| Inventing or estimating data | Never — ARIA either cites a real record or explicitly states the data is missing. This is enforced at the system-prompt level (Section 6), not merely a style guideline. | Never |
| Answering outside farm context | Never — ARIA is bounded to AGRIOS data; general-knowledge questions unrelated to the user's farm are outside its contract. | Never |
| Accessing other farms' data | Never — the Farm Context Package (Section 4) is always compiled scoped to exactly one farm. | Never |
| Executing actions on behalf of the user | Autonomous "agent mode" is explicitly Phase 4 and beyond. | Phase 4 |
| Sending SMS independently | Never — only admin-triggered or scheduler-triggered SMS notifications exist; ARIA cannot decide, on its own initiative, to message a farmer. | Never |

The distinction between "Phase 2/3/4" items and "Never" items matters: some of ARIA's current limitations are purely about not having built the capability yet, while others (medical advice, inventing data, cross-farm data access, autonomous SMS) are permanent trust and safety boundaries that remain true no matter how capable the underlying models become. A future engineer extending ARIA should check this table before assuming any given limitation is simply "not implemented yet."

---

## 4. Architecture — the Farm Context Package

**AR-01 (Frozen):** every AI call is preceded by a server-side function, `compile_farm_context(db, farm_id, flock_id)`, that assembles a bounded JSON package from real farm/flock/log/finance/health data. The compiled AI providers (`_call_gemini`, `_call_claude`) receive only this compiled JSON string — **they never have direct database access, and no code path exists that would let them query Postgres themselves.** This is simultaneously a security boundary (the AI cannot be prompted into reaching for data outside what it was deliberately handed) and the mechanical reason ARIA's "never invents data" guarantee is actually enforceable: the model has no mechanism to reach for anything beyond what the context compiler chose to include.

**AR-02 (Frozen) — the 8,000-token budget and its fixed trim order:** the compiled context, conversation history, and prompt together are capped at 8,000 tokens (a conservative 4-characters-per-token estimate is used for budgeting). `_trim_context_to_budget()` enforces this cap using a fixed, non-negotiable trim order when the raw context exceeds budget: first reduce daily logs from 14 days back to 7 days, then drop expenses, then drop revenue, then trim conversation history. This order is deliberate — daily operational logs are the highest-value context for most questions, so they are trimmed last and least aggressively; conversation history is trimmed most aggressively because the current question and current farm state matter more than exact recall of earlier turns in the same conversation.

**AR-03 (Frozen) — 15-second timeout and provider fallback:** `_call_gemini()` wraps its call in `asyncio.wait_for(..., timeout=15)`. On timeout, or on any Gemini failure, ARIA falls back to Claude Haiku automatically, and the response carries a `used_fallback` flag so usage patterns can be monitored (`SELECT COUNT(*) FROM ai_usage_log WHERE provider = 'claude'` is the documented way to watch fallback frequency). **AD-11 / AD-12 (Frozen):** Gemini 2.0 Flash is the primary provider, Claude Haiku is fallback-only, and no OpenAI integration exists in V1 — this is a reliability-through-redundancy pattern, not a cost-optimization pattern; the fallback exists so that a single provider's outage or rate-limit does not take ARIA down entirely.

**AR-04 (Frozen) — 150-word response cap:** enforced via explicit system-prompt instruction rather than server-side truncation, because truncating a model's output mid-sentence produces a worse user experience than asking the model to self-limit its length in the first place. This cap exists for two reasons simultaneously: cost control (shorter responses cost less per call) and UX (a farmer reading on a small phone screen needs a scannable answer, not an essay).

**AR-05 (Frozen) — the system prompt is fixed, not runtime-configurable:** `ARIA_SYSTEM_PROMPT` is a module-level Python constant. It is never stored in the database, never exposed to any admin configuration screen, and never A/B tested mid-sprint. This is a deliberate constraint against prompt drift — if the prompt could be edited live, ARIA's safety boundaries (Section 3) would depend on an admin never making a mistake in a text field, rather than on a reviewed, version-controlled source file.

---

## 5. The ARIA System Prompt (V1, Frozen)

```
You are ARIA, the AI Farm Operations Assistant for AGRIOS.

Your purpose: Help poultry farmers in Kenya understand their farm data and
make better decisions. You have access to real-time data from their farm,
provided below in the FARM CONTEXT section.

RULES YOU MUST FOLLOW:
1. Only use data from the FARM CONTEXT. Never invent numbers.
2. If data is not available, say: "I don't have that data yet — try logging
   it in the app."
3. Do not diagnose diseases or give veterinary medical advice.
4. Maximum 150 words per response unless a table or list is necessary.
5. Always name the specific flock when referencing flock data.
6. Cite your data: "Based on your logs from June 1–14..."
7. End each response with one relevant follow-up question.
8. Respond in the same language as the user's question (English or Swahili).

FARM CONTEXT:
{farm_context_json}

CONVERSATION HISTORY:
{conversation_history}

USER QUESTION:
{user_question}
```

Every rule in this prompt maps directly to a locked product or safety decision described elsewhere in this document — rule 1 and rule 2 enforce "never invents data" (Section 3); rule 3 enforces the permanent medical-advice boundary; rule 4 enforces AR-04; rule 8 enforces the bilingual requirement that is core to the Kenya-first product philosophy (`AGRIOS_MASTER_CONTEXT.md` Section 6.1). A future prompt revision must preserve every one of these guarantees even if the wording changes, and any revision should be treated with the same override discipline as any other frozen decision (`AGRIOS_MASTER_CONTEXT.md` Section 9).

---

## 6. Conversation Memory

Conversations are modeled as `ai_conversations` (a thread, optionally scoped to a specific flock via `flock_id` for focused advice) containing `ai_messages` rows, one per turn, each tagged with `role` (`user`/`assistant`) and `provider` (`gemini`/`claude`) and a `tokens_used` count. A conversation can be soft-deleted by the user (`DELETE /aria/conversations/{id}`), consistent with the project-wide soft-delete convention (`DATABASE_ARCHITECTURE.md` Section 3). Memory is scoped strictly to a single conversation thread within a single farm — there is no cross-conversation or cross-farm memory, which is both a privacy boundary and a direct consequence of the Farm Context Package always being compiled fresh, per-call, from real current data rather than from any persisted long-term memory store.

---

## 7. Insight Generation — the 8 Proactive Insight Types

**AR-06 (Frozen):** proactive insights are generated once daily, at 06:00 Africa/Nairobi, via the scheduler job `job_aria_daily_insights` (`SYSTEM_ARCHITECTURE.md` Section 2.6). This schedule does not change in V1 — 06:00 was chosen because it lands before a farmer's typical morning farm walk, so any overnight mortality spike or overdue vaccination is visible before the farmer starts their day, not discovered after the fact in the evening.

| Trigger | Condition | Severity |
|---|---|---|
| Mortality spike | Today's mortality rate > 2× the last 7-day average | WARNING |
| Feed drop | Today's feed consumption < 80% of the 7-day average | WARNING |
| Vaccination overdue | `next_due_date` has passed | ALERT |
| Vaccination due soon | `next_due_date` within 3 days | INFO |
| FCR above standard | FCR exceeds the breed standard by more than 20% | WARNING |
| Harvest approaching | Flock has reached 80% of its expected cycle length | INFO |
| Daily log missing | Today has not been logged by 20:00 | REMINDER |
| Market price change | A tracked commodity's price moved more than 10% from the prior week | INFO |

Insights are stored in `ai_insights` (with an `expires_at` so stale insights do not linger indefinitely) and surfaced both in-app (the Insights screen and a 3-item strip on the home dashboard) and, for the higher-severity types, via SMS if the farmer's notification preferences allow it (`SYSTEM_ARCHITECTURE.md` Section 6). Related **recommendations** (`ai_recommendations`) are structured action items — "Consider reducing stocking density" — with a lifecycle of `pending → acted / dismissed / expired`, distinct from insights in that they ask for an explicit user response rather than simply informing.

---

## 8. Cost Control and Quota Enforcement

Each subscription plan defines a `max_aria_queries_per_month` limit — Free: 5, Starter: 30, Pro: unlimited (represented internally as `None`/`-1`). `check_quota()` counts only rows in `ai_usage_log` where `call_type = 'conversation'` and `success = TRUE`, scoped to the current calendar month via `DATE_TRUNC('month', NOW())` — **quota resets are calendar-month based, not a rolling 30-day window, and no separate cron job is needed for the reset because the query itself is always scoped to the current month.** Failed AI calls are still logged (for debugging and provider-health monitoring) but are never charged against a farmer's quota — a farmer should never lose a query allotment to an AI provider's outage. When a farm exceeds its quota, the API returns `429 Too Many Requests` with the code `ARIA_QUOTA_EXCEEDED`, and the frontend shows a clear upgrade prompt rather than a generic error.

Cost is also controlled at the token-budget level (Section 4, AR-02) and the response-length level (AR-04): the combination of an 8,000-token context cap and a 150-word response cap keeps each Gemini query in the range of roughly $0.000015–$0.000075 depending on context length, meaning even 10,000 queries in a month costs on the order of $0.15–$0.75 — cheap enough that the meaningful cost-control lever is quota enforcement against abusive/automated usage, not per-query cost optimization.

---

## 9. Safety, Boundaries, and Honesty as a Feature

ARIA's honesty about the limits of its own knowledge is treated as a product feature, not an apologetic fallback. When asked something outside its bounded data — for example, "Is Newcastle disease spreading in my county?" — the correct ARIA behavior is to say plainly that it does not have real-time disease surveillance data and to direct the farmer to their local veterinary office, rather than attempting a plausible-sounding but ungrounded answer. This matters because the alternative — a confident-sounding AI assistant that occasionally fabricates agricultural or medical claims — would eventually cost the product the trust that its entire "trusted agronomist in your pocket" positioning depends on. Every rule in the system prompt (Section 5) exists to make this honesty structurally likely rather than merely hoped for.

---

## 10. Future AI Roadmap

The phased boundaries in Section 3 are the authoritative source for what unlocks when; at a glance: **Phase 2** adds text-based disease-symptom assessment, an AI sell-timing advisor, proactive SMS morning briefings, and image upload for health records/receipts. **Phase 3** adds full offline-first operation more broadly across the product and, specific to ARIA, photo-based disease diagnosis and cross-farm anonymized outbreak pattern detection. **Phase 4 and beyond** introduces autonomous "agent mode" (ARIA taking actions on a farmer's behalf, not merely recommending them), predictive disease risk scoring, and multi-farm enterprise analytics for the `enterprise_owner` role once that tier is activated. Every one of these expansions must preserve the permanent boundaries in Section 3 — image-based diagnosis in Phase 3, for instance, still must never replace a real veterinarian's medical judgment, and autonomous agent mode in Phase 4 still must never be permitted to independently message a farmer via SMS outside the existing, deliberately narrow notification-trigger system. See `ROADMAP.md` for how these phases fit into the broader product timeline.
