/**
 * ARIA planner API (Module 13 Part 6).
 *
 * Forecasts, capacity, budget, cash flow, calendar and what-if simulations —
 * all deterministic, none of it touching Gemini or Claude.
 *
 * `getPlanning` is read-only by default. Passing `syncCalendar` also writes the
 * calendar into the reminder system, so the dashboard never calls it that way
 * on a refresh: opening a page must not create reminders.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export type Confidence = "high" | "medium" | "low" | "none";

export interface AriaForecastItem {
  key: string;
  label: string;
  value: string;
  unit: string;
  available: boolean;
  confidence: Confidence;
  method: string;
  assumptions: string[];
  evidence: string[];
}

export interface AriaFeedForecast {
  daily_rate_kg: string | null;
  days_remaining: number | null;
  depletion_date: string | null;
  required_7d_kg: string | null;
  required_30d_kg: string | null;
  required_cycle_kg: string | null;
  cycle_days_remaining: number | null;
  confidence: Confidence;
  method: string;
  assumptions: string[];
  evidence: string[];
  notes: string[];
}

export interface AriaHouseCapacity {
  name: string;
  capacity: number;
  birds: number;
  utilisation_pct: number | null;
  state: "empty" | "under" | "healthy" | "crowded" | "over" | "unknown";
  note: string;
}

export interface AriaCapacityPlan {
  total_capacity: number;
  total_birds: number;
  available_space: number;
  utilisation_pct: number | null;
  houses: AriaHouseCapacity[];
  recommendations: string[];
  notes: string[];
}

export interface AriaBudgetLine {
  category: string;
  amount: string;
  basis: string;
}

export interface AriaBudget {
  period: string;
  label: string;
  lines: AriaBudgetLine[];
  total: string;
  method: string;
  assumptions: string[];
  notes: string[];
  available: boolean;
}

export interface AriaCashFlow {
  period_days: number;
  expected_expenses: string | null;
  expected_income: string | null;
  net: string | null;
  upcoming: string[];
  outlook: "surplus" | "shortfall" | "unknown";
  assumptions: string[];
  notes: string[];
}

export interface AriaCalendarEntry {
  on: string;
  kind: "vaccination" | "inspection" | "cleaning" | "inventory" | "recording";
  title: string;
  why: string;
}

export interface AriaScenarioChange {
  label: string;
  current: string;
  projected: string;
  difference: string;
}

export interface AriaScenarioResult {
  scenario: string;
  description: string;
  changes: AriaScenarioChange[];
  implications: string[];
  assumptions: string[];
  available: boolean;
  note: string;
}

export interface AriaPlanningSnapshot {
  feed: AriaFeedForecast;
  production: AriaForecastItem[];
  capacity: AriaCapacityPlan;
  budget: AriaBudget;
  cashflow: AriaCashFlow;
  calendar: AriaCalendarEntry[];
}

export type ScenarioKind =
  | "add_birds"
  | "mortality_change"
  | "feed_price_change"
  | "production_change";

export async function getPlanning(
  farmId: string,
  opts: { horizonDays?: number; syncCalendar?: boolean } = {},
): Promise<AriaPlanningSnapshot> {
  const { data } = await apiClient.get<APISuccess<AriaPlanningSnapshot>>(
    `/farms/${farmId}/aria/planning`,
    {
      params: {
        ...(opts.horizonDays ? { horizon_days: opts.horizonDays } : {}),
        ...(opts.syncCalendar ? { sync_calendar: true } : {}),
      },
    },
  );
  return data.data;
}

export async function getBudget(
  farmId: string,
  period: "weekly" | "monthly" | "cycle",
): Promise<AriaBudget> {
  const { data } = await apiClient.get<APISuccess<AriaBudget>>(
    `/farms/${farmId}/aria/budget`,
    { params: { period } },
  );
  return data.data;
}

/** Pure on the server — a simulation never modifies farm data. */
export async function runSimulation(
  farmId: string,
  scenario: ScenarioKind,
  magnitude: number,
): Promise<AriaScenarioResult> {
  const { data } = await apiClient.post<APISuccess<AriaScenarioResult>>(
    `/farms/${farmId}/aria/simulations`,
    { scenario, magnitude },
  );
  return data.data;
}
