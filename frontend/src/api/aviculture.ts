/**
 * Aviculture API (Module 15).
 *
 * Collection management for individual ornamental & specialty birds. Every bird
 * carries a complete, permanent digital identity: identity fields, a data-driven
 * species/breed/mutation taxonomy, an append-only ownership chain, and an
 * immutable life-history timeline. Ownership events (transfer/sale/purchase/death)
 * are recorded as collection facts; financial posting is a later, reused concern.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };
type APIList<T> = { data: T[]; success: true; meta: { total: number; page: number; limit: number; pages: number } };

const base = (farmId: string) => `/farms/${farmId}/aviculture`;

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Species {
  id: string;
  organization_id: string | null;
  common_name: string;
  scientific_name: string | null;
  species_group: string;
  conservation_status: string | null;
  profile: Record<string, unknown>;
  is_system: boolean;
}

export interface Breed {
  id: string;
  species_id: string;
  name: string;
  is_system: boolean;
}

export interface Mutation {
  id: string;
  species_id: string | null;
  name: string;
  inheritance: string;
  is_system: boolean;
}

export interface Ownership {
  id: string;
  bird_id: string;
  owner_type: string;
  owner_name: string;
  owner_contact: Record<string, unknown>;
  acquisition: string;
  from_date: string | null;
  to_date: string | null;
  is_current: boolean;
  notes: string | null;
}

export interface BirdMutation {
  id: string;
  mutation_id: string;
  zygosity: string;
  mutation_name: string | null;
  inheritance: string | null;
}

export interface Bird {
  id: string;
  farm_id: string;
  species_id: string;
  breed_id: string | null;
  aviary_id: string | null;
  internal_ref: string;
  name: string | null;
  ring_number: string | null;
  band_number: string | null;
  microchip: string | null;
  colour_description: string | null;
  sex: string;
  sex_method: string;
  dna_status: string;
  hatch_date: string | null;
  hatch_date_estimated: boolean;
  sire_id: string | null;
  dam_id: string | null;
  lifecycle_stage: string;
  status: string;
  acquisition_type: string;
  acquired_on: string | null;
  tags: string[];
  notes: string | null;
  species_name: string | null;
  breed_name: string | null;
  aviary_name: string | null;
}

export interface BirdDetail extends Bird {
  mutations: BirdMutation[];
  current_owner: Ownership | null;
}

export interface BirdEvent {
  id: string;
  bird_id: string;
  event_type: string;
  occurred_on: string;
  title: string;
  description: string | null;
  data: Record<string, unknown>;
  actor_id: string | null;
  created_at: string;
}

export interface Media {
  id: string;
  media_type: string;
  url: string | null;
  filename: string | null;
  caption: string | null;
  is_primary: boolean;
  taken_on: string | null;
}

export interface BirdDocument {
  id: string;
  document_type: string;
  title: string | null;
  url: string | null;
  issued_on: string | null;
  expires_on: string | null;
  is_restricted: boolean;
}

export interface BirdListResult {
  birds: Bird[];
  total: number;
  pages: number;
}

export interface BirdFilters {
  status?: string;
  species_id?: string;
  sex?: string;
  lifecycle_stage?: string;
  search?: string;
  tag?: string;
  include_archived?: boolean;
  limit?: number;
  offset?: number;
}

// ── Catalog ───────────────────────────────────────────────────────────────────

export async function listSpecies(farmId: string): Promise<Species[]> {
  const { data } = await apiClient.get<APISuccess<Species[]>>(`${base(farmId)}/species`);
  return data.data;
}

export async function createSpecies(
  farmId: string,
  body: { common_name: string; species_group: string; scientific_name?: string; conservation_status?: string },
): Promise<Species> {
  const { data } = await apiClient.post<APISuccess<Species>>(`${base(farmId)}/species`, body);
  return data.data;
}

export async function listBreeds(farmId: string, speciesId?: string): Promise<Breed[]> {
  const { data } = await apiClient.get<APISuccess<Breed[]>>(`${base(farmId)}/breeds`, {
    params: speciesId ? { species_id: speciesId } : undefined,
  });
  return data.data;
}

export async function listMutations(farmId: string, speciesId?: string): Promise<Mutation[]> {
  const { data } = await apiClient.get<APISuccess<Mutation[]>>(`${base(farmId)}/mutations`, {
    params: speciesId ? { species_id: speciesId } : undefined,
  });
  return data.data;
}

// ── Birds ─────────────────────────────────────────────────────────────────────

export async function listBirds(farmId: string, filters: BirdFilters = {}): Promise<BirdListResult> {
  const { data } = await apiClient.get<APIList<Bird>>(`${base(farmId)}/birds`, { params: filters });
  return { birds: data.data, total: data.meta.total, pages: data.meta.pages };
}

export async function getBird(farmId: string, birdId: string): Promise<BirdDetail> {
  const { data } = await apiClient.get<APISuccess<BirdDetail>>(`${base(farmId)}/birds/${birdId}`);
  return data.data;
}

export interface BirdCreateInput {
  species_id: string;
  breed_id?: string | null;
  name?: string;
  ring_number?: string;
  microchip?: string;
  sex?: string;
  sex_method?: string;
  dna_status?: string;
  colour_description?: string;
  hatch_date?: string | null;
  lifecycle_stage?: string;
  acquisition_type?: string;
  tags?: string[];
  notes?: string;
}

export async function createBird(farmId: string, body: BirdCreateInput): Promise<Bird> {
  const { data } = await apiClient.post<APISuccess<Bird>>(`${base(farmId)}/birds`, body);
  return data.data;
}

export async function updateBird(farmId: string, birdId: string, body: Partial<BirdCreateInput>): Promise<Bird> {
  const { data } = await apiClient.patch<APISuccess<Bird>>(`${base(farmId)}/birds/${birdId}`, body);
  return data.data;
}

export async function archiveBird(farmId: string, birdId: string, reason?: string): Promise<Bird> {
  const { data } = await apiClient.post<APISuccess<Bird>>(`${base(farmId)}/birds/${birdId}/archive`, { reason });
  return data.data;
}

export async function restoreBird(farmId: string, birdId: string): Promise<Bird> {
  const { data } = await apiClient.post<APISuccess<Bird>>(`${base(farmId)}/birds/${birdId}/restore`, {});
  return data.data;
}

export async function transferBird(
  farmId: string, birdId: string,
  body: { to_owner_name: string; to_owner_type?: string; destination?: string; occurred_on?: string; notes?: string },
): Promise<Bird> {
  const { data } = await apiClient.post<APISuccess<Bird>>(`${base(farmId)}/birds/${birdId}/transfer`, body);
  return data.data;
}

export async function sellBird(
  farmId: string, birdId: string,
  body: { buyer_name: string; price?: string; currency?: string; occurred_on?: string; notes?: string },
): Promise<Bird> {
  const { data } = await apiClient.post<APISuccess<Bird>>(`${base(farmId)}/birds/${birdId}/sell`, body);
  return data.data;
}

export async function recordDeath(
  farmId: string, birdId: string, body: { cause?: string; occurred_on?: string; notes?: string },
): Promise<Bird> {
  const { data } = await apiClient.post<APISuccess<Bird>>(`${base(farmId)}/birds/${birdId}/death`, body);
  return data.data;
}

export async function getTimeline(farmId: string, birdId: string): Promise<BirdEvent[]> {
  const { data } = await apiClient.get<APISuccess<BirdEvent[]>>(`${base(farmId)}/birds/${birdId}/timeline`);
  return data.data;
}

export async function getOwnership(farmId: string, birdId: string): Promise<Ownership[]> {
  const { data } = await apiClient.get<APISuccess<Ownership[]>>(`${base(farmId)}/birds/${birdId}/ownership`);
  return data.data;
}

export async function getMedia(farmId: string, birdId: string): Promise<Media[]> {
  const { data } = await apiClient.get<APISuccess<Media[]>>(`${base(farmId)}/birds/${birdId}/media`);
  return data.data;
}

export async function addMedia(
  farmId: string, birdId: string,
  body: { media_type: string; url: string; caption?: string; is_primary?: boolean },
): Promise<Media> {
  const { data } = await apiClient.post<APISuccess<Media>>(`${base(farmId)}/birds/${birdId}/media`, body);
  return data.data;
}

export async function getDocuments(farmId: string, birdId: string): Promise<BirdDocument[]> {
  const { data } = await apiClient.get<APISuccess<BirdDocument[]>>(`${base(farmId)}/birds/${birdId}/documents`);
  return data.data;
}

export async function addDocument(
  farmId: string, birdId: string,
  body: { document_type: string; url: string; title?: string; issued_on?: string; expires_on?: string },
): Promise<BirdDocument> {
  const { data } = await apiClient.post<APISuccess<BirdDocument>>(`${base(farmId)}/birds/${birdId}/documents`, body);
  return data.data;
}
