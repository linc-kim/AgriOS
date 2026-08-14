/**
 * Greena — commercial policy (single frontend source of truth).
 *
 * The BACKEND is authoritative: `trial_service.TRIAL_DAYS` defines the trial
 * length and the authenticated trial-status API returns `trial_days` live.
 * This module is the ONE place the frontend mirrors that policy for static copy
 * (marketing pages, tooltips) so no surface hardcodes its own number. Dynamic,
 * signed-in surfaces should prefer the live `trial_days` / `days_remaining` from
 * the API; fall back to these constants when the value isn't loaded yet.
 *
 * If the backend policy changes, update this one file (and ideally read the live
 * value where a fetch is already happening).
 */

/** Trial length in days. Mirrors backend `trial_service.TRIAL_DAYS`. */
export const TRIAL_DAYS = 14;

/** Customer-facing name of the plan the trial grants (DB display for `pro`). */
export const PREMIUM_PLAN_LABEL = "Premium";

/** Premium monthly price in KES. Mirrors the seeded `pro` plan price. */
export const PREMIUM_PRICE_KES = 1499;

/** "14-day Premium trial" — the canonical phrase for the trial. */
export const trialLabel = (): string => `${TRIAL_DAYS}-day ${PREMIUM_PLAN_LABEL} trial`;

/** "KES 1,499/month" — the canonical Premium price phrase. */
export const premiumPriceLabel = (): string =>
  `KES ${PREMIUM_PRICE_KES.toLocaleString()}/month`;
