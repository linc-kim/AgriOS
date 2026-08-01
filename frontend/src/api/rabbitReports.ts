/**
 * Rabbit Reports API (Module 17) — executive dashboard, forecast, bottlenecks,
 * executive summary and CSV export. Presentation-only; every figure is the
 * backend's, honesty-labelled. Nothing is recomputed here.
 */
import apiClient from "./client";
import type { Figure } from "./rabbit";

type APISuccess<T> = { data: T; success: true };

const base = (farmId: string) => `/farms/${farmId}/rabbit/reports`;

export interface ForecastBlock {
  forecast?: Figure;
  current?: Figure;
  daily_rate?: Figure;
  net_daily_change?: Figure;
  method?: string;
  assumptions?: string[];
  confidence?: string;
  limitations?: string[];
  horizon_days?: number;
}

export interface ForecastBundle {
  herd_size: ForecastBlock;
  kits_produced: ForecastBlock;
  feed_requirement_kg: ForecastBlock;
  revenue: ForecastBlock;
  housing_capacity: Record<string, Figure>;
  window_days: number;
}

export interface Bottleneck {
  constraint: string;
  severity: string;
  evidence: string;
  impact: string;
  recommended_action: string;
  confidence: string;
}

export interface Dashboard {
  recorded_facts: { population: Record<string, Figure> };
  reproduction: Record<string, Figure>;
  health: Record<string, unknown>;
  finance: { pnl: Record<string, Figure>; unit_economics: Record<string, Figure> };
  housing: Record<string, unknown>;
  forecast: ForecastBundle;
  bottlenecks: Bottleneck[];
}

export async function getDashboard(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Dashboard>>(`${base(farmId)}/dashboard`);
  return data.data;
}

export async function getForecast(farmId: string, horizon = 90, window = 90) {
  const { data } = await apiClient.get<APISuccess<ForecastBundle>>(
    `${base(farmId)}/forecast`, { params: { horizon_days: horizon, window_days: window } });
  return data.data;
}

export async function getBottlenecks(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Bottleneck[]>>(`${base(farmId)}/bottlenecks`);
  return data.data;
}

export async function getExecutiveSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, unknown>>>(`${base(farmId)}/executive-summary`);
  return data.data;
}

export async function exportHerdCsv(farmId: string): Promise<Blob> {
  const { data } = await apiClient.get(`${base(farmId)}/herd.csv`, { responseType: "blob" });
  return data as Blob;
}
