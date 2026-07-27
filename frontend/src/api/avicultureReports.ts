/**
 * Aviculture Reports & Finance API (Module 15, Parts 7-8).
 *
 * The dashboard composes the existing engines (aviary/incubation/health/finance);
 * the population forecast and collection valuation are computed and honesty-
 * labelled. Operational costs reuse the shared Finance ledger — no aviculture
 * expense table. Every figure carries the label its source engine assigned.
 */
import apiClient from "./client";
import type { Labelled } from "./aviaries";

type APISuccess<T> = { data: T };

const base = (farmId: string) => `/farms/${farmId}/aviculture`;

export interface Dashboard {
  collection: {
    total: Labelled<number>;
    by_species: Record<string, number>;
    by_status: Record<string, number>;
    by_sex: Record<string, number>;
    by_lifecycle_stage: Record<string, number>;
  };
  infrastructure: { aviary_count: number; total_occupied: Labelled; available: Labelled; quarantine_aviaries: number };
  breeding: { active_pairs: number; active_programs: number };
  incubation: { active_batches: number; statistics: Record<string, Labelled> };
  health: Record<string, Labelled | Record<string, unknown>>;
  finance: FinanceSummary;
}

export interface FinanceSummary {
  sale_income: Labelled<number>;
  purchase_costs: Labelled<number>;
  operational_expenses: Labelled<number>;
  net: Labelled<number>;
  collection_value: Labelled<number | null> | null;
}

export interface CollectionValuation {
  total_value: Labelled<number | null>;
  birds_valued: Labelled<number>;
  birds_unvalued: Labelled<number>;
  by_basis: Record<string, number>;
}

export interface Forecast {
  current: Labelled<number>;
  births_in_window?: Labelled<number>;
  deaths_in_window?: Labelled<number>;
  net_daily_change?: Labelled<number>;
  forecast: Labelled<number | null>;
  method?: string;
  assumptions?: string[];
  confidence?: string;
  limitations?: string[];
  horizon_days?: number;
}

export interface Valuation {
  id: string; bird_id: string | null; valued_on: string; amount: string; currency: string; method: string; source: string | null;
}

export async function getDashboard(farmId: string): Promise<Dashboard> {
  const { data } = await apiClient.get<APISuccess<Dashboard>>(`${base(farmId)}/reports/dashboard`);
  return data.data;
}
export async function getForecast(farmId: string, horizonDays = 90): Promise<Forecast> {
  const { data } = await apiClient.get<APISuccess<Forecast>>(`${base(farmId)}/reports/forecast`, { params: { horizon_days: horizonDays } });
  return data.data;
}
export async function getFinanceSummary(farmId: string): Promise<FinanceSummary> {
  const { data } = await apiClient.get<APISuccess<FinanceSummary>>(`${base(farmId)}/finance/summary`);
  return data.data;
}
export async function getCollectionValuation(farmId: string): Promise<CollectionValuation> {
  const { data } = await apiClient.get<APISuccess<CollectionValuation>>(`${base(farmId)}/finance/valuation`);
  return data.data;
}
export async function listValuations(farmId: string, birdId?: string): Promise<Valuation[]> {
  const { data } = await apiClient.get<APISuccess<Valuation[]>>(`${base(farmId)}/valuations`, { params: birdId ? { bird_id: birdId } : undefined });
  return data.data;
}
export async function recordValuation(farmId: string, body: { bird_id?: string; amount: string; method: string; source?: string }): Promise<Valuation> {
  const { data } = await apiClient.post<APISuccess<Valuation>>(`${base(farmId)}/valuations`, body);
  return data.data;
}
export async function postExpense(farmId: string, body: { bird_id?: string; amount: string; category_slug: string; description: string }): Promise<{ expense_id: string }> {
  const { data } = await apiClient.post<APISuccess<{ expense_id: string }>>(`${base(farmId)}/expenses`, body);
  return data.data;
}
/** Fetch the collection CSV as an authenticated Blob (the caller triggers download). */
export async function downloadCollectionCsv(farmId: string): Promise<Blob> {
  const res = await apiClient.get(`${base(farmId)}/reports/collection.csv`, { responseType: "blob" });
  return res.data as Blob;
}
