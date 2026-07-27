/**
 * Aviculture Breeding API (Module 15, Part 4).
 *
 * Pairs, breeding programmes, pedigrees, relatedness and compatibility. Every
 * genetic figure is computed by the pure pedigree engine and arrives
 * honesty-labelled (calculated / forecast / recorded / unknown). The UI shows
 * the label so a probability never masquerades as a guarantee.
 */
import apiClient from "./client";
import type { Labelled } from "./aviaries";

type APISuccess<T> = { data: T };
type APIList<T> = { data: T[]; meta: { total: number; pages: number } };

const base = (farmId: string) => `/farms/${farmId}/aviculture`;

export interface Compatibility {
  compatible: boolean;
  blocking: boolean;
  risk_level: string;
  relationship_coefficient: Labelled<number>;
  offspring_inbreeding: Labelled<number>;
  warnings: { label: string; code: string; detail: string }[];
  confidence: string;
  limitations: string[];
}

export interface Pair {
  id: string;
  farm_id: string;
  male_bird_id: string | null;
  female_bird_id: string | null;
  name: string | null;
  purpose: string | null;
  formation_type: string;
  formed_on: string | null;
  status: string;
  dissolved_on: string | null;
  program_id: string | null;
  male_name: string | null;
  female_name: string | null;
  compatibility?: Compatibility | null;
}

export interface Program {
  id: string;
  name: string;
  species_id: string | null;
  objective: string | null;
  strategy: string;
  target_traits: string[];
  status: string;
  pair_count: number;
}

export interface Pedigree {
  bird_id: string;
  ancestry: PedigreeNode;
  inbreeding_coefficient: Labelled<number>;
  founders: string[];
  generations: number;
}

export interface PedigreeNode {
  unknown?: boolean;
  id?: string;
  generation?: number;
  has_more?: boolean;
  sire?: PedigreeNode;
  dam?: PedigreeNode;
}

export interface Offspring { bird_id: string; offspring: { id: string; internal_ref: string; name: string | null; status: string }[]; performance: Record<string, Labelled>; }

export async function listPairs(farmId: string, params: Record<string, unknown> = {}): Promise<{ pairs: Pair[]; total: number }> {
  const { data } = await apiClient.get<APIList<Pair>>(`${base(farmId)}/pairs`, { params });
  return { pairs: data.data, total: data.meta.total };
}
export async function createPair(farmId: string, body: { male_bird_id?: string; female_bird_id?: string; name?: string; program_id?: string }): Promise<Pair> {
  const { data } = await apiClient.post<APISuccess<Pair>>(`${base(farmId)}/pairs`, body);
  return data.data;
}
export async function getPair(farmId: string, id: string): Promise<Pair> {
  const { data } = await apiClient.get<APISuccess<Pair>>(`${base(farmId)}/pairs/${id}`);
  return data.data;
}
export async function dissolvePair(farmId: string, id: string, reason?: string): Promise<Pair> {
  const { data } = await apiClient.post<APISuccess<Pair>>(`${base(farmId)}/pairs/${id}/dissolve`, { reason });
  return data.data;
}
export async function checkCompatibility(farmId: string, male_bird_id: string, female_bird_id: string): Promise<Compatibility> {
  const { data } = await apiClient.post<APISuccess<Compatibility>>(`${base(farmId)}/compatibility`, { male_bird_id, female_bird_id });
  return data.data;
}
export async function getPedigree(farmId: string, birdId: string): Promise<Pedigree> {
  const { data } = await apiClient.get<APISuccess<Pedigree>>(`${base(farmId)}/birds/${birdId}/pedigree`);
  return data.data;
}
export async function getOffspring(farmId: string, birdId: string): Promise<Offspring> {
  const { data } = await apiClient.get<APISuccess<Offspring>>(`${base(farmId)}/birds/${birdId}/offspring`);
  return data.data;
}
export async function setParents(farmId: string, birdId: string, body: { sire_id?: string | null; dam_id?: string | null }): Promise<unknown> {
  const { data } = await apiClient.post<APISuccess<unknown>>(`${base(farmId)}/birds/${birdId}/parents`, body);
  return data.data;
}
export async function listPrograms(farmId: string): Promise<Program[]> {
  const { data } = await apiClient.get<APISuccess<Program[]>>(`${base(farmId)}/breeding-programs`);
  return data.data;
}
export async function createProgram(farmId: string, body: { name: string; strategy: string; objective?: string; target_traits?: string[] }): Promise<Program> {
  const { data } = await apiClient.post<APISuccess<Program>>(`${base(farmId)}/breeding-programs`, body);
  return data.data;
}
