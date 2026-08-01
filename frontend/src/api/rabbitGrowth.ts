/**
 * Rabbit Growth & Feed API (Module 17) — weight history, growth analysis, feeding
 * (which reuses the platform Inventory module) and feed efficiency. All growth and
 * FCR math is the backend's; the client renders honesty-labelled figures only.
 */
import apiClient from "./client";
import type { Figure } from "./rabbit";

type APISuccess<T> = { data: T; success: true };
type APIList<T> = { data: T[]; success: true; meta: { total: number; page: number; limit: number; pages: number } };
const base = (farmId: string) => `/farms/${farmId}/rabbit`;

export interface Weight {
  id: string; rabbit_id: string; recorded_on: string; weight_g: string; age_days: number | null; notes: string | null;
}
export interface GrowthAnalysis {
  rabbit_id: string;
  internal_ref: string;
  analysis: Record<string, Figure>;
  series: Array<{ recorded_on: string; weight_g: number | null; age_days: number | null; gain_from_prev_g: number | null; adg_from_prev: number | null }>;
  herd_percentile_pct: Figure;
}
export interface FeedRecord {
  id: string; rabbit_id: string | null; cage_id: string | null; inventory_item_id: string | null;
  inventory_movement_id: string | null; feed_type: string | null; quantity_kg: string;
  fed_on: string; cost: string | null; currency: string | null; supplier: string | null; notes: string | null;
}

export async function listWeights(farmId: string, rabbitId: string) {
  const { data } = await apiClient.get<APISuccess<Weight[]>>(`${base(farmId)}/rabbits/${rabbitId}/weights`);
  return data.data;
}
export async function recordWeight(farmId: string, rabbitId: string, body: { recorded_on: string; weight_g: number; notes?: string }) {
  const { data } = await apiClient.post<APISuccess<Weight>>(`${base(farmId)}/rabbits/${rabbitId}/weights`, body);
  return data.data;
}
export async function getGrowthAnalysis(farmId: string, rabbitId: string) {
  const { data } = await apiClient.get<APISuccess<GrowthAnalysis>>(`${base(farmId)}/rabbits/${rabbitId}/growth`);
  return data.data;
}
export async function listFeed(farmId: string, params: Record<string, unknown> = {}) {
  const { data } = await apiClient.get<APIList<FeedRecord>>(`${base(farmId)}/feed`, { params });
  return data;
}
export async function recordFeed(farmId: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<FeedRecord>>(`${base(farmId)}/feed`, body);
  return data.data;
}
export async function getFeedSummary(farmId: string, rabbitId?: string) {
  const { data } = await apiClient.get<APISuccess<{ rabbit_id: string | null; summary: Record<string, Figure> }>>(
    `${base(farmId)}/feed/summary`, { params: rabbitId ? { rabbit_id: rabbitId } : {} });
  return data.data;
}
