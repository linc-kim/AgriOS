/**
 * Black Soldier Fly API (Module 16) — core: species, production units, colonies
 * and the batch-centric production backbone.
 *
 * Presentation-only client: it consumes the stable backend endpoints and never
 * recomputes calculations, validations, forecasts or business rules. Every
 * computed figure arrives honesty-labelled ({label,value,detail}) from a
 * deterministic engine and is rendered as-is.
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

const base = (farmId: string) => `/farms/${farmId}/bsf`;

// ── Enumerated UI vocabularies (mirror the backend *_VALUES) ─────────────────

export const LIFECYCLE_STAGES = [
  "egg", "hatchling", "feeding_larvae", "mature_larvae", "prepupae", "pupae", "adult",
] as const;
export const BATCH_STATUSES = [
  "active", "harvested", "completed", "split", "merged", "terminated", "archived",
] as const;
export const BATCH_TYPES = ["production", "breeding", "egg", "nursery", "mixed"] as const;
export const UNIT_TYPES = [
  "bin", "tray", "rack", "cage", "chamber", "container", "shelf", "incubator",
  "drying_unit", "nursery", "love_cage", "other",
] as const;
export const COLONY_SOURCES = ["bred", "purchased", "donated", "transferred", "wild", "unknown"] as const;

export const STAGE_LABELS: Record<string, string> = {
  egg: "Egg", hatchling: "Hatchling", feeding_larvae: "Feeding larvae",
  mature_larvae: "Mature larvae", prepupae: "Prepupae", pupae: "Pupae", adult: "Adult",
  unknown: "Unknown",
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Species {
  id: string;
  organization_id: string | null;
  common_name: string;
  scientific_name: string | null;
  strain: string | null;
  production_type: string;
  profile: Record<string, unknown>;
  is_system: boolean;
}

export interface ProductionUnit {
  id: string;
  farm_id: string;
  name: string;
  code: string | null;
  unit_type: string;
  facility: string | null;
  production_area: string | null;
  capacity_grams: string | null;
  status: string;
  environment_profile: Record<string, unknown>;
  maintenance_status: string | null;
  notes: string | null;
}

export interface Colony {
  id: string;
  farm_id: string;
  species_id: string | null;
  production_unit_id: string | null;
  name: string;
  code: string | null;
  source: string;
  established_on: string | null;
  population_estimate: number | null;
  status: string;
  retired_on: string | null;
  notes: string | null;
}

export interface Batch {
  id: string;
  created_at: string;
  updated_at: string;
  farm_id: string;
  species_id: string | null;
  source_colony_id: string | null;
  parent_batch_id: string | null;
  production_unit_id: string | null;
  batch_number: string;
  name: string | null;
  batch_type: string;
  lifecycle_stage: string;
  stage_started_on: string | null;
  status: string;
  started_on: string | null;
  completed_on: string | null;
  population_estimate: number | null;
  biomass_estimate_g: string | null;
  tags: string[];
  notes: string | null;
}

export interface BatchDetail extends Batch {
  metrics: Record<string, Figure>;
  pacing: Record<string, Figure>;
}

export interface LifecycleEvent {
  id: string;
  batch_id: string;
  previous_stage: string | null;
  new_stage: string;
  occurred_on: string;
  population_estimate: number | null;
  biomass_estimate_g: string | null;
  survival_rate_pct: string | null;
  source: string;
  observations: string | null;
}

export interface BatchEvent {
  id: string;
  batch_id: string;
  event_type: string;
  summary: string | null;
  details: Record<string, unknown>;
  related_batch_id: string | null;
  created_at: string;
}

export interface BatchFilters {
  status?: string;
  lifecycle_stage?: string;
  production_unit_id?: string;
  page?: number;
  limit?: number;
}

export interface BatchCreateInput {
  batch_number?: string;
  name?: string | null;
  batch_type?: string;
  species_id?: string | null;
  source_colony_id?: string | null;
  production_unit_id?: string | null;
  lifecycle_stage?: string;
  started_on?: string | null;
  population_estimate?: number | null;
  biomass_estimate_g?: number | null;
  tags?: string[];
  notes?: string | null;
}

// ── Species ─────────────────────────────────────────────────────────────────

export async function listSpecies(farmId: string): Promise<Species[]> {
  const { data } = await apiClient.get<APISuccess<Species[]>>(`${base(farmId)}/species`);
  return data.data;
}
export async function createSpecies(
  farmId: string,
  body: { common_name: string; scientific_name?: string; strain?: string; production_type?: string; profile?: Record<string, unknown> },
): Promise<Species> {
  const { data } = await apiClient.post<APISuccess<Species>>(`${base(farmId)}/species`, body);
  return data.data;
}

// ── Production units ──────────────────────────────────────────────────────────

export async function listUnits(farmId: string, status?: string): Promise<ProductionUnit[]> {
  const { data } = await apiClient.get<APISuccess<ProductionUnit[]>>(`${base(farmId)}/production-units`, {
    params: status ? { status } : {},
  });
  return data.data;
}
export async function createUnit(
  farmId: string,
  body: { name: string; unit_type: string; code?: string; capacity_grams?: number | null; facility?: string; production_area?: string; notes?: string },
): Promise<ProductionUnit> {
  const { data } = await apiClient.post<APISuccess<ProductionUnit>>(`${base(farmId)}/production-units`, body);
  return data.data;
}

// ── Colonies ──────────────────────────────────────────────────────────────────

export async function listColonies(farmId: string, status?: string): Promise<Colony[]> {
  const { data } = await apiClient.get<APISuccess<Colony[]>>(`${base(farmId)}/colonies`, {
    params: status ? { status } : {},
  });
  return data.data;
}
export async function createColony(
  farmId: string,
  body: { name: string; species_id?: string | null; production_unit_id?: string | null; source?: string; population_estimate?: number | null; notes?: string },
): Promise<Colony> {
  const { data } = await apiClient.post<APISuccess<Colony>>(`${base(farmId)}/colonies`, body);
  return data.data;
}

// ── Batches ───────────────────────────────────────────────────────────────────

export interface BatchListResult { batches: Batch[]; total: number; page: number; pages: number }

export async function listBatches(farmId: string, filters: BatchFilters = {}): Promise<BatchListResult> {
  const { data } = await apiClient.get<APIList<Batch>>(`${base(farmId)}/batches`, { params: filters });
  return { batches: data.data, total: data.meta.total, page: data.meta.page, pages: data.meta.pages };
}
export async function getBatch(farmId: string, batchId: string): Promise<BatchDetail> {
  const { data } = await apiClient.get<APISuccess<BatchDetail>>(`${base(farmId)}/batches/${batchId}`);
  return data.data;
}
export async function createBatch(farmId: string, body: BatchCreateInput): Promise<Batch> {
  const { data } = await apiClient.post<APISuccess<Batch>>(`${base(farmId)}/batches`, body);
  return data.data;
}
export async function updateBatch(farmId: string, batchId: string, body: Partial<BatchCreateInput>): Promise<Batch> {
  const { data } = await apiClient.patch<APISuccess<Batch>>(`${base(farmId)}/batches/${batchId}`, body);
  return data.data;
}
export async function advanceBatch(
  farmId: string, batchId: string,
  body: { to_stage: string; occurred_on?: string; population_estimate?: number | null; biomass_estimate_g?: number | null; survival_rate_pct?: number | null; observations?: string; allow_premature?: boolean },
): Promise<BatchDetail> {
  const { data } = await apiClient.post<APISuccess<BatchDetail>>(`${base(farmId)}/batches/${batchId}/advance`, body);
  return data.data;
}
export async function moveBatch(farmId: string, batchId: string, body: { production_unit_id: string | null; note?: string }): Promise<Batch> {
  const { data } = await apiClient.post<APISuccess<Batch>>(`${base(farmId)}/batches/${batchId}/move`, body);
  return data.data;
}
export async function splitBatch(
  farmId: string, batchId: string,
  body: { parts: Array<{ name?: string; population_estimate: number; production_unit_id?: string | null }>; reason?: string },
): Promise<Batch[]> {
  const { data } = await apiClient.post<APISuccess<Batch[]>>(`${base(farmId)}/batches/${batchId}/split`, body);
  return data.data;
}
export async function mergeBatches(
  farmId: string,
  body: { source_batch_ids: string[]; name?: string; production_unit_id?: string | null; reason?: string },
): Promise<Batch> {
  const { data } = await apiClient.post<APISuccess<Batch>>(`${base(farmId)}/batches/merge`, body);
  return data.data;
}
export async function terminateBatch(farmId: string, batchId: string, body: { reason?: string } = {}): Promise<Batch> {
  const { data } = await apiClient.post<APISuccess<Batch>>(`${base(farmId)}/batches/${batchId}/terminate`, body);
  return data.data;
}
export async function listLifecycle(farmId: string, batchId: string): Promise<LifecycleEvent[]> {
  const { data } = await apiClient.get<APISuccess<LifecycleEvent[]>>(`${base(farmId)}/batches/${batchId}/lifecycle`);
  return data.data;
}
export async function listTimeline(farmId: string, batchId: string): Promise<BatchEvent[]> {
  const { data } = await apiClient.get<APISuccess<BatchEvent[]>>(`${base(farmId)}/batches/${batchId}/timeline`);
  return data.data;
}
