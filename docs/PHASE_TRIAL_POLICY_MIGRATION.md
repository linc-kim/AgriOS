# Greena — Trial Policy Migration (21 → 14 days) + Premium Messaging

**Date:** 2026-08-14 · **Commits:** `ff037a1` (code), `bd2470b` (plan doc) on `phase-2-auth` (pushed) · **Frontend:** deployed to `agrioskenya.vercel.app`.

## Policy
The Greena free trial is now **14 days** (was 21), granting the **Premium** plan (KES 1,499/month). One authoritative definition per tier; no competing hardcoded values.

## Source of truth
- **Backend authority:** `backend/app/services/trial_service.py` → `TRIAL_DAYS = 14`. Everything server-side derives from it; `get_trial_status` now also returns `trial_days` so the app/ARIA read the policy live.
- **Frontend mirror:** `frontend/src/lib/policy.ts` (`TRIAL_DAYS = 14`, `PREMIUM_PLAN_LABEL`, `PREMIUM_PRICE_KES = 1499`, `trialLabel()`, `premiumPriceLabel()`) — the one place static copy references the policy.

## Files changed
**Backend**
- `services/trial_service.py` — `TRIAL_DAYS 21 → 14`; docstrings; `get_trial_status` returns `trial_days`.
- `schemas/commercial.py` — `TrialStatusOut.trial_days`.
- `schemas/billing.py` — new `PublicPlanOut` (price + limits).
- `api/v1/endpoints/billing.py` — new public `GET /billing/plans/public` (no auth).
- `api/v1/endpoints/organizations.py` — trial-grant comment 21 → 14.
- `alembic/versions/092_rename_pro_plan_to_premium.py` — **new migration**: rename `pro` display "Professional" → "Premium" (data-only, reversible, idempotent).
- `tests/integration/test_billing_trial.py` — stale "21"/"Professional" comments updated (assertions already use the `TRIAL_DAYS` constant, so they follow the policy automatically).

**Frontend**
- `lib/policy.ts` — **new** single source of truth for static copy.
- `lib/pricing.ts` — **new** live-fetch + fallback (fallback `pro` display now "Premium").
- `screens/public/PricingScreen.tsx` — live-fetch catalogue; "14-day Premium trial"; correct prices/limits.
- `screens/billing/ReferralDashboardScreen.tsx` — trial countdown: "You're exploring Greena Premium", days-left, "Continue … for KES 1,499/month" (informative, not aggressive).
- `api/billing.ts` — `TrialStatus.trial_days`.
- `screens/public/TermsScreen.tsx` — header comment "14-day Premium trial".

## Database changes
- **No duration data change** — trial length is computed at creation and stored as a per-org `trial_ends_at` timestamp. Existing trials keep their granted window (no corruption); only new trials get 14 days.
- **Migration 092** renames the `pro` plan's `display_name` to "Premium" (non-destructive UPDATE, guarded on the old value, with a downgrade). Runs on the backend deploy via `alembic upgrade head`.

## Tests updated
- `test_billing_trial.py` — comments only; logic asserts against `TRIAL_DAYS`, so it validates 14 days automatically. (Not run here — the suite needs a non-prod Postgres.)

## Verification
**Repository search (policy requirement):**
- `21-day` / `21 days` / `Professional trial` as a trial duration → **0 remaining** (excluding the unrelated `aria_intelligence.age_days <= 21` and `incubation_days: 21`, which are not the trial and were correctly left untouched).
- Duplicated trial-duration constants → none; one backend constant + one frontend mirror.
- Hardcoded pricing differing from Premium → the old marketing `1,500 / 4,500` is removed; page now shows catalogue values.

**Build/typecheck:** frontend `tsc` clean on changed files; `vite build` passes. Backend `py_compile` OK on all changed files + migration.

| Surface | Environment | Result | Evidence |
|---|---|---|---|
| Pricing page copy "14-day Premium trial" + Premium @ 1,499 | Local dev | **PASS** | rendered text verified |
| Frontend new code deployed | Production CDN (`agrioskenya.vercel.app`) | **PASS** | deployed `PricingScreen` chunk contains `plans/public` + `Premium`; old "billed monthly, cancel whenever" gone. (A still-open browser tab may show stale content until its PWA service worker updates on next load — expected.) |
| Public plans endpoint returns Premium + limits | Production API (Render) | **PENDING / UNVERIFIED** | `GET /billing/plans/public` → **404** ~11 min after push; old backend still serving (`/health` 200). Render deploy has not swapped in the new revision. |
| Migration 092 applied (pro → Premium) | Production DB | **PENDING** | runs with the backend deploy above; not yet applied. |
| New orgs get 14-day trial | Production API | **PENDING** | activates with the backend deploy. |

## Remaining areas requiring manual review / follow-up
- **Backend deploy is not live yet.** The new endpoint 404s ~11 min post-push and the Render dashboard/logs are not accessible from this session (CLI token is credential-blocked), so I can't tell whether it's a slow free-tier Docker build, autoDeploy not firing, or a failed deploy. **Until the backend deploys, there is a window where the frontend says "14-day Premium" (via its accurate fallback) while the API still grants 21-day trials and 404s the public endpoint.** Needs: confirm/trigger the Render deploy from the dashboard, then re-verify the three PENDING rows.
- **Emails:** no trial email templates exist in the repo — nothing to change (not fabricated). If trial emails are added later, they must read `TRIAL_DAYS` / the Premium label.
- **ARIA:** no hardcoded trial length; ARIA answers from live entitlement (`get_trial_status` now includes `trial_days`).
