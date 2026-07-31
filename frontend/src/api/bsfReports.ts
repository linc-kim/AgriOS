/**
 * BSF Reports & Analytics API (Module 16) — the composed executive dashboard,
 * forecasts, bottlenecks and CSV export.
 *
 * Read-only presentation of the backend reporting service, which itself composes
 * the deterministic engines. The frontend renders the honesty-labelled figures
 * as-is and never recomputes them.
 */
import apiClient from "./client";
import type { Figure } from "./bsf";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/bsf/reports`;

export interface Bottleneck {
  constraint: string;
  severity: "critical" | "high" | "medium" | "low";
  evidence: string;
  impact: string;
  recommended_action: string;
  confidence: string;
}

export interface ForecastBlock {
  forecast: Figure;
  daily_rate?: Figure;
  current?: Figure;
  method: string;
  assumptions: string[];
  confidence: string;
  limitations: string[];
  horizon_days: number;
}

export interface ForecastBundle {
  window_days: number;
  horizon_days: number;
  harvest_kg: ForecastBlock;
  feed_requirement_kg: ForecastBlock;
  revenue: ForecastBlock;
}

export interface Dashboard {
  recorded_facts: Record<string, Figure>;
  analytics: {
    production: Record<string, Figure>;
    health: Record<string, Figure>;
    finance: Record<string, Figure>;
    sustainability: Record<string, Figure>;
  };
  scores: Record<string, Figure>;
  forecast: ForecastBundle;
  bottlenecks: Bottleneck[];
  top_bottleneck: Bottleneck | null;
}

export async function getDashboard(farmId: string): Promise<Dashboard> {
  const { data } = await apiClient.get<APISuccess<Dashboard>>(`${base(farmId)}/dashboard`);
  return data.data;
}

export async function getForecast(farmId: string, horizonDays = 90, windowDays = 90): Promise<ForecastBundle> {
  const { data } = await apiClient.get<APISuccess<ForecastBundle>>(`${base(farmId)}/forecast`, {
    params: { horizon_days: horizonDays, window_days: windowDays },
  });
  return data.data;
}

export async function getBottlenecks(farmId: string): Promise<Bottleneck[]> {
  const { data } = await apiClient.get<APISuccess<Bottleneck[]>>(`${base(farmId)}/bottlenecks`);
  return data.data;
}

/** Authenticated CSV download (blob) — never a plain <a href>, which would 401. */
export async function exportProductionCsv(farmId: string): Promise<Blob> {
  const { data } = await apiClient.get(`${base(farmId)}/production.csv`, { responseType: "blob" });
  return data as Blob;
}
