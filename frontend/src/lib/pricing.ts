/**
 * Greena — pricing source of truth for public surfaces.
 *
 * The marketing pricing page reads the SAME catalogue the checkout charges from,
 * via the public, unauthenticated `GET /billing/plans/public`. That endpoint
 * derives everything from the `subscription_plans` table, so the website can no
 * longer drift from what a farmer is actually billed.
 *
 * A static fallback mirrors the seeded catalogue so the page always shows
 * correct numbers even if the API is briefly unreachable (e.g. a free-tier
 * backend cold start). Live data replaces it as soon as the fetch resolves.
 */
import { apiClient } from "@/api/client";

export interface PublicPlan {
  name: string;
  display_name: string;
  price_kes: number;
  is_self_serve: boolean;
  max_farms: number;
  max_houses_per_farm: number;
  max_active_flocks: number;
  max_aria_queries_per_month: number;
  history_days: number;
  max_team_members: number;
}

/**
 * Mirrors the seeded catalogue (migration 088). Kept only as an offline/cold-
 * start fallback — the live fetch is authoritative. `-1` = unlimited; `0` = free;
 * a `price_kes` of `-1` marks a custom/contact-sales plan.
 */
export const FALLBACK_PLANS: PublicPlan[] = [
  { name: "free", display_name: "Free", price_kes: 0, is_self_serve: false, max_farms: 1, max_houses_per_farm: 2, max_active_flocks: 500, max_aria_queries_per_month: 100, history_days: 90, max_team_members: 1 },
  { name: "starter", display_name: "Starter", price_kes: 999, is_self_serve: true, max_farms: 3, max_houses_per_farm: 20, max_active_flocks: 10000, max_aria_queries_per_month: 2000, history_days: -1, max_team_members: 10 },
  { name: "pro", display_name: "Premium", price_kes: 1499, is_self_serve: true, max_farms: 10, max_houses_per_farm: 75, max_active_flocks: 50000, max_aria_queries_per_month: 10000, history_days: -1, max_team_members: 30 },
  { name: "farm_pro", display_name: "Farm Pro", price_kes: 2499, is_self_serve: true, max_farms: 50, max_houses_per_farm: 250, max_active_flocks: 250000, max_aria_queries_per_month: 50000, history_days: -1, max_team_members: 150 },
  { name: "enterprise", display_name: "Enterprise", price_kes: -1, is_self_serve: false, max_farms: -1, max_houses_per_farm: -1, max_active_flocks: -1, max_aria_queries_per_month: -1, history_days: -1, max_team_members: -1 },
];

/** The plan highlighted as the recommended default on the pricing page. */
export const RECOMMENDED_PLAN = "pro";

export async function fetchPublicPlans(): Promise<PublicPlan[]> {
  const res = await apiClient.get<{ data: PublicPlan[] }>("/billing/plans/public", {
    // A free-tier backend can cold-start slowly; allow longer than the default.
    timeout: 60000,
  });
  const plans = res.data?.data;
  return Array.isArray(plans) && plans.length > 0 ? plans : FALLBACK_PLANS;
}

// ── Display helpers ───────────────────────────────────────────────────────────

/** "Unlimited" for -1, otherwise a grouped number. */
export function limit(n: number): string {
  return n === -1 ? "Unlimited" : n.toLocaleString();
}

/** History window: -1 = full. */
export function historyLabel(days: number): string {
  return days === -1 ? "Full history" : `${days} days of history`;
}

/** "1 farm" / "3 farms", handling the unlimited (-1) case. */
export function countLabel(n: number, singular: string, plural = `${singular}s`): string {
  if (n === -1) return `Unlimited ${plural}`;
  return `${n.toLocaleString()} ${n === 1 ? singular : plural}`;
}

export type PriceDisplay =
  | { kind: "free" }
  | { kind: "custom" }
  | { kind: "amount"; amount: string };

export function priceDisplay(price_kes: number): PriceDisplay {
  if (price_kes === 0) return { kind: "free" };
  if (price_kes < 0) return { kind: "custom" };
  return { kind: "amount", amount: price_kes.toLocaleString() };
}
