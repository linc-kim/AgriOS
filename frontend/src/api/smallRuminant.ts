/**
 * Small Ruminant API (Modules 18 Goat + 19 Sheep) — one presentation-only client
 * for both species. Every call is parameterised by `species` ('goat' | 'sheep')
 * and hits the shared backend under `/farms/{farmId}/sr/{species}`. The client
 * never recomputes anything: computed figures arrive honesty-labelled
 * ({label,value,detail}) from the deterministic engines and are rendered as-is.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };
type APIList<T> = {
  data: T[];
  success: true;
  meta: { total: number; page: number; limit: number; pages: number };
};

export type Species = "goat" | "sheep";

/** A value produced by a deterministic engine, carrying its honesty label. */
export interface Figure {
  label: string;
  value: unknown;
  detail?: string;
}

const base = (farmId: string, species: Species) => `/farms/${farmId}/sr/${species}`;

// ── Types ───────────────────────────────────────────────────────────────────

export interface Animal {
  id: string;
  species: string;
  farm_id: string;
  internal_ref: string;
  name: string | null;
  ear_tag: string | null;
  sex: string;
  purpose: string;
  horn_status: string;
  lifecycle_stage: string;
  status: string;
  reproductive_status: string;
  date_of_birth: string | null;
  current_weight_kg: string | null;
  sire_id: string | null;
  dam_id: string | null;
  breed_name?: string | null;
  herd_name?: string | null;
  group_name?: string | null;
  pen_name?: string | null;
  pasture_name?: string | null;
}

export interface AnimalDetail extends Animal {
  sire_ref?: string | null;
  dam_ref?: string | null;
}

export interface AnimalEvent {
  id: string;
  animal_id: string;
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
  purpose?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

// ── Registry ──────────────────────────────────────────────────────────────────

export async function listAnimals(farmId: string, species: Species, params: ListParams = {}) {
  const { data } = await apiClient.get<APIList<Animal>>(`${base(farmId, species)}/animals`, { params });
  return data;
}

export async function getAnimal(farmId: string, species: Species, animalId: string) {
  const { data } = await apiClient.get<APISuccess<AnimalDetail>>(`${base(farmId, species)}/animals/${animalId}`);
  return data.data;
}

export async function registerAnimal(farmId: string, species: Species, body: Partial<Animal>) {
  const { data } = await apiClient.post<APISuccess<Animal>>(`${base(farmId, species)}/animals`, body);
  return data.data;
}

export async function getTimeline(farmId: string, species: Species, animalId: string) {
  const { data } = await apiClient.get<APISuccess<AnimalEvent[]>>(
    `${base(farmId, species)}/animals/${animalId}/timeline`);
  return data.data;
}

// ── Composed analytics / intelligence ─────────────────────────────────────────

export async function getDashboard(farmId: string, species: Species) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId, species)}/reports/dashboard`);
  return data.data;
}

export async function getBottlenecks(farmId: string, species: Species) {
  const { data } = await apiClient.get<APISuccess<any[]>>(`${base(farmId, species)}/reports/bottlenecks`);
  return data.data;
}

export function registryCsvUrl(farmId: string, species: Species) {
  return `${apiClient.defaults.baseURL ?? ""}${base(farmId, species)}/reports/registry.csv`;
}

export async function askAria(farmId: string, species: Species, question: string) {
  const { data } = await apiClient.post<APISuccess<AriaAnswer>>(`${base(farmId, species)}/aria/ask`, { question });
  return data.data;
}

export async function getMissionBriefing(farmId: string, species: Species) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(
    `/farms/${farmId}/mission/small-ruminant/${species}/briefing`);
  return data.data;
}

export async function getFinanceSummary(farmId: string, species: Species) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId, species)}/finance/summary`);
  return data.data;
}

// ── Species-specific production ───────────────────────────────────────────────

export async function getDairySummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId, "goat")}/dairy/summary`);
  return data.data;
}

export async function listLactations(farmId: string) {
  const { data } = await apiClient.get<APISuccess<any[]>>(`${base(farmId, "goat")}/dairy/lactations`);
  return data.data;
}

export async function getWoolSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, any>>>(`${base(farmId, "sheep")}/wool/summary`);
  return data.data;
}

export async function listShearings(farmId: string) {
  const { data } = await apiClient.get<APISuccess<any[]>>(`${base(farmId, "sheep")}/wool/shearings`);
  return data.data;
}
