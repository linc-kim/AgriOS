/**
 * Swine API (Module 20) — a presentation-only client. Single species, so no
 * discriminator: every call hits `/farms/{farmId}/swine`. The client never
 * recomputes anything — computed figures arrive honesty-labelled ({label,value,detail})
 * from the deterministic engines and are rendered as-is.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };
type APIList<T> = {
  data: T[];
  success: true;
  meta: { total: number; page: number; limit: number; pages: number };
};

/** A value produced by a deterministic engine, carrying its honesty label. */
export interface Figure {
  label: string;
  value: unknown;
  detail?: string;
}

const base = (farmId: string) => `/farms/${farmId}/swine`;

// ── Types ───────────────────────────────────────────────────────────────────

export interface Pig {
  id: string;
  farm_id: string;
  internal_ref: string;
  name: string | null;
  ear_tag: string | null;
  sex: string;
  birth_sex: string;
  purpose: string;
  production_stage: string;
  status: string;
  reproductive_status: string;
  market_status: string;
  date_of_birth: string | null;
  current_weight_kg: string | null;
  sire_id: string | null;
  dam_id: string | null;
  litter_id: string | null;
  breed_name?: string | null;
  herd_name?: string | null;
  group_name?: string | null;
  pen_name?: string | null;
}

export interface PigDetail extends Pig {
  sire_ref?: string | null;
  dam_ref?: string | null;
}

export interface PigEvent {
  id: string;
  pig_id: string;
  event_type: string;
  occurred_at: string | null;
  summary: string | null;
  details: Record<string, unknown>;
}

export interface AriaAnswer {
  provider: string;
  engine: string;
  fact_type: string;
  answer: string;
  sources: string[];
  confidence: string;
  ai_enabled: boolean;
}

export interface ListParams {
  status?: string;
  sex?: string;
  production_stage?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

// ── Registry ──────────────────────────────────────────────────────────────────

export async function listPigs(farmId: string, params: ListParams = {}) {
  const { data } = await apiClient.get<APIList<Pig>>(`${base(farmId)}/pigs`, { params });
  return data;
}

export async function getPig(farmId: string, pigId: string) {
  const { data } = await apiClient.get<APISuccess<PigDetail>>(`${base(farmId)}/pigs/${pigId}`);
  return data.data;
}

export async function registerPig(farmId: string, body: Partial<Pig>) {
  const { data } = await apiClient.post<APISuccess<Pig>>(`${base(farmId)}/pigs`, body);
  return data.data;
}

export async function getTimeline(farmId: string, pigId: string) {
  const { data } = await apiClient.get<APISuccess<PigEvent[]>>(`${base(farmId)}/pigs/${pigId}/timeline`);
  return data.data;
}

export async function getGrowthAnalysis(farmId: string, pigId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(
    `${base(farmId)}/growth/pigs/${pigId}/analysis`);
  return data.data;
}

export async function getReadiness(farmId: string, pigId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(
    `${base(farmId)}/growth/pigs/${pigId}/readiness`);
  return data.data;
}

// ── Composed analytics / domain summaries ─────────────────────────────────────

export async function getFarmDashboard(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId)}/reports/farm`);
  return data.data;
}

export async function getReproductionSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId)}/breeding/summary`);
  return data.data;
}

export async function listBreedings(farmId: string) {
  const { data } = await apiClient.get<APISuccess<any[]>>(`${base(farmId)}/breeding`);
  return data.data;
}

export async function listPregnancies(farmId: string) {
  const { data } = await apiClient.get<APISuccess<any[]>>(`${base(farmId)}/pregnancy`);
  return data.data;
}

export async function getHealthSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId)}/health/summary`);
  return data.data;
}

export async function listDiseaseCases(farmId: string) {
  const { data } = await apiClient.get<APISuccess<any[]>>(`${base(farmId)}/health/disease-cases`);
  return data.data;
}

export async function getHerdGrowth(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId)}/growth/summary`);
  return data.data;
}

export async function getStageComparison(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId)}/growth/stage-comparison`);
  return data.data;
}

export async function getFinanceSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId)}/finance/summary`);
  return data.data;
}

export async function listSales(farmId: string) {
  const { data } = await apiClient.get<APIList<any>>(`${base(farmId)}/finance/sales`);
  return data;
}

export function csvUrl(farmId: string, name: "registry" | "sales" | "mortality") {
  return `${apiClient.defaults.baseURL ?? ""}${base(farmId)}/reports/${name}.csv`;
}

// ── ARIA / Mission Control ────────────────────────────────────────────────────

export async function askAria(farmId: string, question: string) {
  const { data } = await apiClient.post<APISuccess<AriaAnswer>>(`${base(farmId)}/aria/ask`, { question });
  return data.data;
}

export async function getRecommendations(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId)}/aria/recommendations`);
  return data.data;
}

export async function getMissionBriefing(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`/farms/${farmId}/mission/swine/briefing`);
  return data.data;
}
