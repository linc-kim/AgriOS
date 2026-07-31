/**
 * BSF Harvest & Frass API (Module 16).
 *
 * Records harvests (larvae/prepupae/…) and frass collection against a batch.
 * Revenue is a recorded fact; harvested/frass output optionally flows into the
 * platform Inventory module via an inbound adjustment (handled server-side).
 * Harvest readiness and yield are computed by the backend engine.
 */
import apiClient from "./client";
import type { Figure } from "./bsf";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/bsf`;

export const HARVEST_TYPES = ["larvae", "prepupae", "pupae", "adult", "frass", "mixed"] as const;
export const QUALITY_GRADES = ["premium", "standard", "low", "reject", "ungraded"] as const;
export const HARVEST_DESTINATIONS = ["inventory", "sale", "feed", "processing", "disposal", "other"] as const;

export interface HarvestEvent {
  id: string;
  farm_id: string;
  batch_id: string;
  harvest_type: string;
  is_complete: boolean;
  harvested_on: string;
  quantity_kg: string;
  population_estimate: number | null;
  quality_grade: string;
  destination: string;
  revenue_amount: string | null;
  unit_price: string | null;
  currency: string | null;
  buyer_name: string | null;
  inventory_item_id: string | null;
  inventory_movement_id: string | null;
  observations: string | null;
}

export interface FrassProduction {
  id: string;
  farm_id: string;
  batch_id: string;
  collected_on: string;
  weight_kg: string;
  moisture_pct: string | null;
  quality: string;
  storage_location: string | null;
  inventory_item_id: string | null;
  inventory_movement_id: string | null;
  notes: string | null;
}

export interface HarvestReadiness {
  batch_id: string;
  lifecycle_stage: string;
  readiness: Figure;
  total_harvested_kg: Figure;
}

export async function getHarvestReadiness(farmId: string, batchId: string): Promise<HarvestReadiness> {
  const { data } = await apiClient.get<APISuccess<HarvestReadiness>>(`${base(farmId)}/batches/${batchId}/harvest-readiness`);
  return data.data;
}

export async function listHarvests(farmId: string, batchId: string): Promise<HarvestEvent[]> {
  const { data } = await apiClient.get<APISuccess<HarvestEvent[]>>(`${base(farmId)}/batches/${batchId}/harvests`);
  return data.data;
}

export async function recordHarvest(
  farmId: string, batchId: string,
  body: {
    harvest_type: string; quantity_kg: number; is_complete?: boolean; quality_grade?: string;
    destination?: string; revenue_amount?: number | null; currency?: string; buyer_name?: string;
    inventory_item_id?: string | null; observations?: string;
  },
): Promise<HarvestEvent> {
  const { data } = await apiClient.post<APISuccess<HarvestEvent>>(`${base(farmId)}/batches/${batchId}/harvests`, body);
  return data.data;
}

export async function listFrass(farmId: string, batchId: string): Promise<FrassProduction[]> {
  const { data } = await apiClient.get<APISuccess<FrassProduction[]>>(`${base(farmId)}/batches/${batchId}/frass`);
  return data.data;
}

export async function recordFrass(
  farmId: string, batchId: string,
  body: { weight_kg: number; moisture_pct?: number | null; quality?: string; storage_location?: string; inventory_item_id?: string | null; notes?: string },
): Promise<FrassProduction> {
  const { data } = await apiClient.post<APISuccess<FrassProduction>>(`${base(farmId)}/batches/${batchId}/frass`, body);
  return data.data;
}
