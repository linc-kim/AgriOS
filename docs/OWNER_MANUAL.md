# Greena Owner Manual

For the platform owner / founder. What Greena is as a business you operate, the
levers you control, and the decisions only you can make.

## 1. What you own
- **Product**: Greena, the Agricultural Operating System — a multi-tenant SaaS where farmers run their operations (records, health, finance, AI) across livestock modules.
- **Infrastructure accounts**: GitHub (`linc-kim/AgriOS`), Render (backend), Vercel (frontend), Supabase (database), Paystack (payments), Gemini/Claude (AI). You are the billing and recovery owner of each.
- **The commercial model**: plans, trial, referrals — see [ADMINISTRATOR_MANUAL.md](ADMINISTRATOR_MANUAL.md) for exact limits.

## 2. The money model (source of truth: `subscription_plans`)
- **Free** (KES 0): 1 farm, 100 ARIA queries/mo, 90-day history — the on-ramp.
- **Starter** 999 · **Professional** 1 499 · **Farm Pro** 2 499 · **Enterprise** custom.
- **Trial**: every new org gets a **21-day Professional trial** automatically.
- **Referral growth loop**: each org has a shareable code; a referred org's first Starter payment is **KES 599**, and the referrer earns **KES 100** credit on activation (once, DB-guaranteed). This is your viral acquisition lever.
- Renewals are always full price; the discount is first-payment only.

## 3. What only you can decide/do
1. **Provision paid tiers** when scaling past beta — Render Standard+ and paid Supabase. The free tier is measured at ~8–10 rps (fine for pilot, not for 250+ concurrent). See [OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md) §5.
2. **Enable database backups** — the top reliability gap today (free Supabase has none). See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).
3. **Rotate exposed credentials** (Paystack live key, Render, Northflank tokens shared during setup).
4. **Go-live payment confirmation** — complete one Paystack test-card checkout to confirm activation end-to-end, then switch to live keys in the Render dashboard yourself (never in chat).
5. **Pricing / plan changes** — edit `subscription_plans` (prices intentionally end in 99; changing them is a business decision).
6. **Custom domain** — when purchased, cut over Vercel + Render domains and re-run smoke tests (deferred by design).

## 4. Health of the business — what to watch
- **Conversion funnel**: signup → org (trial starts) → paid. Trial expiry sweep runs 01:00 daily.
- **Referral performance**: codes shared, discounts redeemed, rewards paid.
- **Reliability**: `/health` uptime, error rate (Sentry), Render memory, Supabase connections.
- **Unit economics**: infra cost (Render + Supabase + AI usage) vs. subscription revenue. AI has per-query cost — plan ARIA limits per tier are your cost control.

## 5. Governance
- Keep `super_admin` to the smallest possible set; enable 2FA everywhere.
- Review `audit_logs` for admin grants/revokes.
- Treat production data as farmers' livelihoods — no risky ops without a backup.

## 6. Your first-week checklist (post-launch)
1. Confirm a completed test payment activates a subscription and credits a referrer.
2. Rotate all exposed keys; switch Paystack to live in the dashboard.
3. Enable Supabase backups.
4. Set a Sentry error-rate alert and an external `/health` pinger.
5. Decide the paid Render/Supabase tier before opening to real traffic at scale.
6. Read the [Encyclopedia](GREENA_ENCYCLOPEDIA.md) end to end — it is written so you understand Greena better than anyone.
