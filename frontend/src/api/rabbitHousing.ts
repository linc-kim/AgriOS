/**
 * Rabbit Housing API (Module 17) — the 5-level hierarchy + occupancy/capacity.
 * Occupancy is derived by the backend (never stored); the client only renders it.
 */
import apiClient from "./client";
import type { Figure } from "./rabbit";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/rabbit/housing`;

export const CAGE_TYPES = [
  "cage", "colony_pen", "hutch", "grow_out", "quarantine", "isolation", "nest", "other",
] as const;

export interface HousingUnit {
  id: string; farm_id: string; name: string; code: string | null; status: string; notes: string | null;
  rabbitry_id?: string; building_id?: string; room_id?: string; row_id?: string | null;
}
export interface Cage extends HousingUnit {
  cage_type: string; capacity: number | null; dimensions: Record<string, unknown>; maintenance_status: string | null;
}
export interface CageDetail extends Cage {
  occupancy: Record<string, Figure & { over_capacity?: boolean }>;
}

export async function listRabbitries(farmId: string) {
  const { data } = await apiClient.get<APISuccess<HousingUnit[]>>(`${base(farmId)}/rabbitries`);
  return data.data;
}
export async function createRabbitry(farmId: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<HousingUnit>>(`${base(farmId)}/rabbitries`, body);
  return data.data;
}
export async function listCages(farmId: string, params: Record<string, unknown> = {}) {
  const { data } = await apiClient.get<APISuccess<Cage[]>>(`${base(farmId)}/cages`, { params });
  return data.data;
}
export async function createCage(farmId: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<Cage>>(`${base(farmId)}/cages`, body);
  return data.data;
}
export async function getCage(farmId: string, id: string) {
  const { data } = await apiClient.get<APISuccess<CageDetail>>(`${base(farmId)}/cages/${id}`);
  return data.data;
}
export async function getHousingSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<{
    counts: Record<string, number>;
    capacity: Record<string, Figure>;
    overcrowded_cages: Array<{ cage_id: string; name: string; capacity: number | null; occupied: number }>;
  }>>(`${base(farmId)}/summary`);
  return data.data;
}
