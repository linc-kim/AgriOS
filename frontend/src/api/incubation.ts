/**
 * Aviculture Incubation API (Module 15, Part 5).
 *
 * Eggs, clutches, incubation batches, candling and hatching. Schedule, progress
 * and hatch statistics arrive honesty-labelled from the pure incubation engine.
 * A hatched egg produces a real chick bird linked to its pair.
 */
import apiClient from "./client";
import type { Labelled } from "./aviaries";

type APISuccess<T> = { data: T };
type APIList<T> = { data: T[]; meta: { total: number; pages: number } };

const base = (farmId: string) => `/farms/${farmId}/aviculture`;

export interface Egg {
  id: string; identifier: string; status: string; fertility_status: string;
  clutch_id: string | null; batch_id: string | null; pair_id: string | null; species_id: string | null;
  laid_on: string | null; quality: string; source: string; set_on: string | null; hatched_bird_id: string | null;
  weight_grams: string | null; notes: string | null;
}

export interface Batch {
  id: string; farm_id: string; species_id: string | null; name: string; method: string;
  incubator_label: string | null; set_on: string | null; incubation_days: number | null;
  target_temperature_c: string | null; target_humidity_pct: string | null;
  expected_lockdown_on: string | null; expected_hatch_on: string | null; status: string;
  egg_count: number; progress?: Record<string, Labelled> | null;
}

export interface BatchDetail extends Batch {
  schedule: Record<string, Labelled> | null;
  statistics: Record<string, Labelled> | null;
}

export interface Candling { id: string; egg_id: string; candled_on: string; day_number: number | null; result: string; notes: string | null; }
export interface Hatch { id: string; egg_id: string; outcome: string; assisted: boolean; chick_bird_id: string | null; failure_reason: string | null; hatched_on: string | null; }
export interface IncLog { id: string; batch_id: string; log_date: string; temperature_c: string | null; humidity_pct: string | null; turns_count: number | null; }

export async function listBatches(farmId: string): Promise<Batch[]> {
  const { data } = await apiClient.get<APISuccess<Batch[]>>(`${base(farmId)}/incubation-batches`);
  return data.data;
}
export async function createBatch(farmId: string, body: { name: string; method: string; species_id?: string; set_on?: string; incubation_days?: number }): Promise<Batch> {
  const { data } = await apiClient.post<APISuccess<Batch>>(`${base(farmId)}/incubation-batches`, body);
  return data.data;
}
export async function getBatch(farmId: string, id: string): Promise<BatchDetail> {
  const { data } = await apiClient.get<APISuccess<BatchDetail>>(`${base(farmId)}/incubation-batches/${id}`);
  return data.data;
}
export async function setEggs(farmId: string, batchId: string, egg_ids: string[], set_on?: string): Promise<{ eggs_set: number }> {
  const { data } = await apiClient.post<APISuccess<{ eggs_set: number }>>(`${base(farmId)}/incubation-batches/${batchId}/set-eggs`, { egg_ids, set_on });
  return data.data;
}
export async function listEggs(farmId: string, params: Record<string, unknown> = {}): Promise<Egg[]> {
  const { data } = await apiClient.get<APIList<Egg>>(`${base(farmId)}/eggs`, { params });
  return data.data;
}
export async function createEgg(farmId: string, body: { species_id?: string; pair_id?: string; clutch_id?: string; quality?: string; source?: string }): Promise<Egg> {
  const { data } = await apiClient.post<APISuccess<Egg>>(`${base(farmId)}/eggs`, body);
  return data.data;
}
export async function candleEgg(farmId: string, eggId: string, body: { result: string; candled_on?: string; notes?: string }): Promise<Candling> {
  const { data } = await apiClient.post<APISuccess<Candling>>(`${base(farmId)}/eggs/${eggId}/candling`, body);
  return data.data;
}
export async function hatchEgg(farmId: string, eggId: string, body: { outcome: string; hatched_on?: string; assisted?: boolean; create_chick?: boolean; chick_name?: string; failure_reason?: string }): Promise<Hatch> {
  const { data } = await apiClient.post<APISuccess<Hatch>>(`${base(farmId)}/eggs/${eggId}/hatch`, body);
  return data.data;
}
export async function listBatchLogs(farmId: string, batchId: string): Promise<IncLog[]> {
  const { data } = await apiClient.get<APISuccess<IncLog[]>>(`${base(farmId)}/incubation-batches/${batchId}/logs`);
  return data.data;
}
export async function addBatchLog(farmId: string, batchId: string, body: { temperature_c?: string; humidity_pct?: string; turns_count?: number }): Promise<IncLog> {
  const { data } = await apiClient.post<APISuccess<IncLog>>(`${base(farmId)}/incubation-batches/${batchId}/logs`, body);
  return data.data;
}
