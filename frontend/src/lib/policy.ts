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

import { apiClient } from "@/api/client";

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

// ── Live commercial policy (backend is authoritative) ─────────────────────────

export interface CommercialPolicy {
  trial_days: number;
  plan_name: string;
  monthly_price: number;
  currency: string;
  billing_period: string;
}

/** The constants above as a policy object — the offline/cold-start fallback. */
export const FALLBACK_POLICY: CommercialPolicy = {
  trial_days: TRIAL_DAYS,
  plan_name: PREMIUM_PLAN_LABEL,
  monthly_price: PREMIUM_PRICE_KES,
  currency: "KES",
  billing_period: "month",
};

/**
 * Read the authoritative commercial policy from the backend. Frontends should
 * prefer this over the constants; the constants are the fallback when the API
 * isn't reachable yet.
 */
export async function fetchCommercialPolicy(): Promise<CommercialPolicy> {
  try {
    const res = await apiClient.get<{ data: CommercialPolicy }>("/billing/policy", {
      timeout: 60000,
    });
    return res.data?.data ?? FALLBACK_POLICY;
  } catch {
    return FALLBACK_POLICY;
  }
}

/** "{n}-day {Plan} trial" from a live policy. */
export const policyTrialLabel = (p: CommercialPolicy): string =>
  `${p.trial_days}-day ${p.plan_name} trial`;

/** "KES 1,499/month" from a live policy. */
export const policyPriceLabel = (p: CommercialPolicy): string =>
  `${p.currency} ${p.monthly_price.toLocaleString()}/${p.billing_period}`;
