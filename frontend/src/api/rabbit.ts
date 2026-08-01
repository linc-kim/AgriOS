/**
 * Rabbit API (Module 17) — registry, catalog & housing summary.
 *
 * Presentation-only client: it consumes the stable backend endpoints and never
 * recomputes calculations, validations or business rules. Every computed figure
 * arrives honesty-labelled ({label,value,detail}) from a deterministic engine
 * and is rendered as-is.
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

const base = (farmId: string) => `/farms/${farmId}/rabbit`;

// ── Enumerated UI vocabularies (mirror the backend *_VALUES) ─────────────────

export const SEXES = ["buck", "doe", "unknown"] as const;
export const PURPOSES = [
  "meat", "breeding", "fiber", "pet", "show", "replacement",
  "genetic_improvement", "educational", "mixed", "unknown",
] as const;
export const LIFECYCLE_STAGES = [
  "kit", "weaner", "grower", "breeding_candidate", "breeding_adult", "retired", "unknown",
] as const;
export const RABBIT_STATUSES = ["active", "sold", "transferred", "deceased", "archived"] as const;

export const STAGE_LABELS: Record<string, string> = {
  kit: "Kit", weaner: "Weaner", grower: "Grower", breeding_candidate: "Breeding candidate",
  breeding_adult: "Breeding adult", retired: "Retired", unknown: "Unknown",
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Rabbit {
  id: string;
  farm_id: string;
  breed_id: string | null;
  bloodline_id: string | null;
  cage_id: string | null;
  litter_id: string | null;
  internal_ref: string;
  name: string | null;
  ear_tag: string | null;
  tattoo: string | null;
  qr_code: string | null;
  rfid: string | null;
  variety: string | null;
  color: string | null;
  sex: string;
  purpose: string;
  purposes: string[];
  date_of_birth: string | null;
  birth_weight_g: string | null;
  current_weight_g: string | null;
  lifecycle_stage: string;
  status: string;
  reproductive_status: string;
  fertility_status: string;
  acquisition_type: string;
  acquired_on: string | null;
  sire_id: string | null;
  dam_id: string | null;
  tags: string[];
  notes: string | null;
  breed_name?: string | null;
  bloodline_name?: string | null;
  cage_name?: string | null;
}

export interface RabbitDetail extends Rabbit {
  sire_ref?: string | null;
  dam_ref?: string | null;
  location_path?: string | null;
}

export interface RabbitEvent {
  id: string;
  rabbit_id: string;
  event_type: string;
  occurred_at: string;
  summary: string | null;
  details: Record<string, unknown>;
}

export interface Breed {
  id: string;
  name: string;
  category: string;
  origin: string | null;
  production_purpose: string | null;
  profile: Record<string, unknown>;
  is_system: boolean;
}

export interface RabbitListParams {
  status?: string;
  sex?: string;
  purpose?: string;
  lifecycle_stage?: string;
  search?: string;
  page?: number;
  limit?: number;
}

// ── Registry ────────────────────────────────────────────────────────────────

export async function listRabbits(farmId: string, params: RabbitListParams = {}) {
  const { data } = await apiClient.get<APIList<Rabbit>>(`${base(farmId)}/rabbits`, { params });
  return data;
}

export async function getRabbit(farmId: string, rabbitId: string) {
  const { data } = await apiClient.get<APISuccess<RabbitDetail>>(`${base(farmId)}/rabbits/${rabbitId}`);
  return data.data;
}

export async function registerRabbit(farmId: string, body: Partial<Rabbit>) {
  const { data } = await apiClient.post<APISuccess<Rabbit>>(`${base(farmId)}/rabbits`, body);
  return data.data;
}

export async function updateRabbit(farmId: string, rabbitId: string, body: Partial<Rabbit>) {
  const { data } = await apiClient.patch<APISuccess<Rabbit>>(`${base(farmId)}/rabbits/${rabbitId}`, body);
  return data.data;
}

export async function getTimeline(farmId: string, rabbitId: string) {
  const { data } = await apiClient.get<APISuccess<RabbitEvent[]>>(`${base(farmId)}/rabbits/${rabbitId}/timeline`);
  return data.data;
}

export async function moveRabbit(farmId: string, rabbitId: string, cageId: string | null, reason?: string) {
  const { data } = await apiClient.post<APISuccess<Rabbit>>(
    `${base(farmId)}/rabbits/${rabbitId}/move`, { cage_id: cageId, reason });
  return data.data;
}

// ── Catalog & housing ─────────────────────────────────────────────────────────

export async function listBreeds(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Breed[]>>(`${base(farmId)}/breeds`);
  return data.data;
}

export async function getHousingSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, unknown>>>(`${base(farmId)}/housing/summary`);
  return data.data;
}
