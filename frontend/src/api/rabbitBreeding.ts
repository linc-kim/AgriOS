/**
 * Rabbit Breeding API (Module 17) — breeding cycles, litters, pedigree & genetics.
 *
 * Presentation-only: the backend owns eligibility, gestation, litter performance,
 * Wright's inbreeding and all genetics. Every computed figure arrives honesty-
 * labelled and is rendered as-is.
 */
import apiClient from "./client";
import type { Figure } from "./rabbit";

type APISuccess<T> = { data: T; success: true };
type APIList<T> = { data: T[]; success: true; meta: { total: number; page: number; limit: number; pages: number } };

const base = (farmId: string) => `/farms/${farmId}/rabbit`;

export const BREEDING_STATUSES = [
  "planned", "serviced", "pregnant", "not_pregnant", "kindled", "failed", "closed", "cancelled",
] as const;

export interface Breeding {
  id: string;
  farm_id: string;
  doe_id: string | null;
  buck_id: string | null;
  method: string;
  service_date: string | null;
  planned_kindling_date: string | null;
  pregnancy_checked_on: string | null;
  pregnancy_result: string;
  nest_box_prepared_on: string | null;
  actual_kindling_date: string | null;
  status: string;
  outcome: string | null;
  notes: string | null;
}

export interface Litter {
  id: string;
  farm_id: string;
  breeding_id: string | null;
  doe_id: string | null;
  buck_id: string | null;
  litter_code: string;
  kindling_date: string;
  total_kits: number;
  live_kits: number;
  stillbirths: number;
  fostered_in: number;
  fostered_out: number;
  weaned_kits: number;
  mortality: number;
  avg_birth_weight_g: string | null;
  weaning_date: string | null;
  status: string;
  notes: string | null;
}

export interface LitterDetail extends Litter {
  performance: Record<string, Figure>;
}

export interface Compatibility {
  compatible: boolean;
  blocking: boolean;
  risk_level: string;
  relationship_coefficient: Figure;
  offspring_inbreeding: Figure;
  warnings: Array<{ label: string; code: string; detail: string }>;
  confidence: string;
  limitations: string[];
}

export interface PedigreeTree {
  rabbit_id: string;
  ancestry: Record<string, unknown>;
  inbreeding_coefficient: Figure;
  founders: string[];
}

// ── Breeding cycle ─────────────────────────────────────────────────────────────

export async function listBreedings(farmId: string, params: Record<string, unknown> = {}) {
  const { data } = await apiClient.get<APIList<Breeding>>(`${base(farmId)}/breedings`, { params });
  return data;
}
export async function createBreeding(farmId: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<Breeding>>(`${base(farmId)}/breedings`, body);
  return data.data;
}
export async function pregnancyCheck(farmId: string, id: string, result: string) {
  const { data } = await apiClient.post<APISuccess<Breeding>>(`${base(farmId)}/breedings/${id}/pregnancy-check`, { result });
  return data.data;
}
export async function prepareKindling(farmId: string, id: string) {
  const { data } = await apiClient.post<APISuccess<Breeding>>(`${base(farmId)}/breedings/${id}/prepare-kindling`, {});
  return data.data;
}
export async function recordKindling(farmId: string, id: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<Litter>>(`${base(farmId)}/breedings/${id}/kindling`, body);
  return data.data;
}
export async function closeBreeding(farmId: string, id: string) {
  const { data } = await apiClient.post<APISuccess<Breeding>>(`${base(farmId)}/breedings/${id}/close`, {});
  return data.data;
}

// ── Litters ──────────────────────────────────────────────────────────────────

export async function listLitters(farmId: string, params: Record<string, unknown> = {}) {
  const { data } = await apiClient.get<APIList<Litter>>(`${base(farmId)}/litters`, { params });
  return data;
}
export async function getLitter(farmId: string, id: string) {
  const { data } = await apiClient.get<APISuccess<LitterDetail>>(`${base(farmId)}/litters/${id}`);
  return data.data;
}
export async function recordWeaning(farmId: string, id: string, weaned_kits: number) {
  const { data } = await apiClient.post<APISuccess<Litter>>(`${base(farmId)}/litters/${id}/weaning`, { weaned_kits });
  return data.data;
}

// ── Pedigree & genetics ─────────────────────────────────────────────────────────

export async function getPedigree(farmId: string, rabbitId: string) {
  const { data } = await apiClient.get<APISuccess<PedigreeTree>>(`${base(farmId)}/rabbits/${rabbitId}/pedigree`);
  return data.data;
}
export async function checkCompatibility(farmId: string, buck_id: string, doe_id: string) {
  const { data } = await apiClient.post<APISuccess<Compatibility>>(`${base(farmId)}/breeding/compatibility`, { buck_id, doe_id });
  return data.data;
}
export async function getReproductionSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, Figure>>>(`${base(farmId)}/breeding/reproduction-summary`);
  return data.data;
}
export async function getGenetics(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, unknown>>>(`${base(farmId)}/breeding/genetics`);
  return data.data;
}
