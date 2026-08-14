# Greena Roadmap & Business Documentation

The business model, its mechanics in the system, and where the product goes next.
Grounded in the real commercial schema and code seams.

## 1. Business model
Greena is **multi-tenant subscription SaaS** for farming businesses in Kenya
(KES, Africa/Nairobi, 47-county validation), sold per organization.

### Plans (source of truth: `subscription_plans`)
| Plan | KES/mo | Positioning |
|---|---|---|
| Free | 0 | On-ramp: 1 farm, 100 ARIA/mo, 90-day history |
| Starter | 999 | Small operation: 3 farms, 2 000 ARIA, unlimited history |
| Professional | 1 499 | Growing: 10 farms, 10 000 ARIA |
| Farm Pro | 2 499 | Multi-farm: 50 farms, 50 000 ARIA |
| Enterprise | custom | Unlimited; sales-led |

Prices intentionally end in **99**. Limits (farms, houses, flocks, team, ARIA, history) are the upgrade levers.

### Growth engine — trial + referral
- **21-day Professional trial** on every new org (experience full value first).
- **Referral loop**: each org has a shareable code. A referred org's **first Starter payment is KES 599** (vs 999); the **referrer earns KES 100** credit on that activation, **once** (DB-guaranteed). Must be entered within **48h** of org creation; immutable once set. Renewals are always full price.
- This makes farmers the acquisition channel and lowers CAC.

### Unit economics (levers to watch)
- **Revenue**: active subscriptions × plan price.
- **Cost**: Render + Supabase (fixed-ish per tier) + **AI usage** (variable — ARIA per-query cost, capped by plan limits) + Paystack fees (per transaction).
- **Margin control**: ARIA monthly limits per tier are the primary variable-cost guard; the response cache (`AI_RESPONSE_CACHE_TTL_SECONDS`) cuts AI cost further.

## 2. How the business logic lives in the system
- **Entitlement**: an org's `subscriptions` row drives what its farms can do; farms inherit it. Expiry sweep (01:00) downgrades lapsed orgs.
- **Activation sources**: `paystack` (paid), `admin` (comp), `lifetime` (never expires), `trial`.
- **Money correctness**: Paystack re-verify on webhook, idempotent activation, DB-unique referral rewards, full audit trail.
- **Seams already present for future monetisation**: a `market` permission and notification system exist as hooks for marketplace/market-price features.

## 3. Product roadmap
Near-term (operational readiness — mostly owner-gated):
- Paid Render + Supabase tiers → real scale (measured free ceiling ~8–10 rps) + **database backups** (top reliability gap).
- Complete the live paid-payment validation; switch Paystack to live keys.
- Custom domain cutover (Vercel + Render), then re-run smoke tests.

Product (feature — currently frozen per directive):
- **Fish / Aquaculture** module (the remaining species engine).
- **ARIA** deepening: multimodal, more languages, document intelligence.
- **Mission Control** expansion: CEO advisor, cross-farm strategy.
- **Operations Planner** maturation: richer optimisation.
- **Marketplace / market prices**: leverage the `market` seam + notifications.
- **Mobile-first** field experience for workers.

Platform/reliability:
- Autoscaling + multi-instance (advisory-lock scheduler already supports it).
- Observability: Sentry alerting, uptime pinger, DB connection dashboards.
- Automated backups + tested restore drill (define real RTO/RPO).

## 4. Internal business reference
- **Market**: Kenyan livestock farmers across poultry, small ruminants, swine, rabbit, aviculture, BSF — smallholder to commercial.
- **Value proposition**: one operating system replacing spreadsheets + notebooks + separate accounting + expert calls, with proactive scheduling and farm-aware AI.
- **Moat**: breadth (many species as deep engines), the proactive operational clock, and tenant-safe AI grounded in the farm's own data.
- **Key metrics**: signup→trial→paid conversion, referral redemption rate, retention/renewal, ARIA engagement, infra cost per active org.
- **Risks**: infra cost at scale (AI especially), single-region DB, backup gap until addressed, payment-provider dependence (Paystack).

## 5. Decision log (why the architecture is what it is)
- **Species as separate engines** — real data-model differences; shared cross-cutting engines keep the UX coherent.
- **Deterministic-first AI** — accuracy + cost control; never block on providers.
- **Additive-only migrations** — safe rollbacks.
- **Fail-safe operations** — boot-time validation, 503 health gate, single-leader scheduler.
- **Prices ending in 99 + first-payment-only referral discount** — deliberate commercial choices, encoded in the DB and enforced server-side.
