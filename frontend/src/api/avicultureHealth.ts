/**
 * Aviculture Health API (Module 15, Part 6).
 *
 * Individual-bird health records, quarantine, disease events and analytics.
 * Analytics arrive honesty-labelled from the pure health engine. Diagnostic
 * records carry a veterinary-guidance disclaimer — ARIA explains, never diagnoses.
 *
 * Distinct from the platform's flock ``health.ts`` (Module 1) — different domain.
 */
import apiClient from "./client";
import type { Labelled } from "./aviaries";

type APISuccess<T> = { data: T };

const base = (farmId: string) => `/farms/${farmId}/aviculture`;

export interface HealthRecord {
  id: string; bird_id: string; record_type: string; recorded_on: string; title: string | null;
  summary: string | null; weight_grams: string | null; body_condition: string | null;
  status: string; severity: string | null; next_due_on: string | null; details: Record<string, unknown>;
}

export interface Quarantine {
  id: string; farm_id: string; bird_id: string; aviary_id: string | null; reason: string | null;
  started_on: string; expected_end_on: string | null; ended_on: string | null; status: string; outcome: string | null;
}

export interface DiseaseEvent {
  id: string; farm_id: string; disease_name: string; status: string; started_on: string;
  resolved_on: string | null; affected_count: number; is_notifiable: boolean; notes: string | null;
}

export interface WeightTrend {
  bird_id: string;
  trend: {
    count: Labelled<number>; latest: Labelled<number | null>; first?: Labelled<number | null>;
    change_grams: Labelled<number | null>; direction: Labelled<string | null>;
    series?: { date: string; grams: number }[];
  };
}

export interface HealthSummary {
  records_total: Labelled; records_by_type: Record<string, number>; active_birds: Labelled;
  mortality_rate_pct: Labelled; vaccination_coverage_pct: Labelled;
  active_quarantines: Labelled; active_disease_events: Labelled;
  preventive_due: { due_count: Labelled; overdue_count: Labelled };
}

export async function listHealthRecords(farmId: string, birdId: string): Promise<HealthRecord[]> {
  const { data } = await apiClient.get<APISuccess<HealthRecord[]>>(`${base(farmId)}/birds/${birdId}/health`);
  return data.data;
}
export async function addHealthRecord(farmId: string, birdId: string, body: {
  record_type: string; recorded_on?: string; title?: string; summary?: string; weight_grams?: string;
  severity?: string; next_due_on?: string; details?: Record<string, unknown>;
}): Promise<HealthRecord> {
  const { data } = await apiClient.post<APISuccess<HealthRecord>>(`${base(farmId)}/birds/${birdId}/health`, body);
  return data.data;
}
export async function getWeightTrend(farmId: string, birdId: string): Promise<WeightTrend> {
  const { data } = await apiClient.get<APISuccess<WeightTrend>>(`${base(farmId)}/birds/${birdId}/weight-trend`);
  return data.data;
}
export async function startQuarantine(farmId: string, birdId: string, body: { reason?: string; started_on?: string; expected_end_on?: string }): Promise<Quarantine> {
  const { data } = await apiClient.post<APISuccess<Quarantine>>(`${base(farmId)}/birds/${birdId}/quarantine`, body);
  return data.data;
}
export async function listBirdQuarantine(farmId: string, birdId: string): Promise<Quarantine[]> {
  const { data } = await apiClient.get<APISuccess<Quarantine[]>>(`${base(farmId)}/birds/${birdId}/quarantine`);
  return data.data;
}
export async function listQuarantine(farmId: string, activeOnly = false): Promise<Quarantine[]> {
  const { data } = await apiClient.get<APISuccess<Quarantine[]>>(`${base(farmId)}/quarantine`, { params: { active_only: activeOnly } });
  return data.data;
}
export async function releaseQuarantine(farmId: string, quarantineId: string, outcome?: string): Promise<Quarantine> {
  const { data } = await apiClient.post<APISuccess<Quarantine>>(`${base(farmId)}/quarantine/${quarantineId}/release`, { outcome });
  return data.data;
}
export async function listDiseaseEvents(farmId: string): Promise<DiseaseEvent[]> {
  const { data } = await apiClient.get<APISuccess<DiseaseEvent[]>>(`${base(farmId)}/disease-events`);
  return data.data;
}
export async function createDiseaseEvent(farmId: string, body: { disease_name: string; status?: string; affected_count?: number; is_notifiable?: boolean }): Promise<DiseaseEvent> {
  const { data } = await apiClient.post<APISuccess<DiseaseEvent>>(`${base(farmId)}/disease-events`, body);
  return data.data;
}
export async function updateDiseaseEvent(farmId: string, eventId: string, body: { status?: string; affected_count?: number }): Promise<DiseaseEvent> {
  const { data } = await apiClient.patch<APISuccess<DiseaseEvent>>(`${base(farmId)}/disease-events/${eventId}`, body);
  return data.data;
}
export async function getHealthSummary(farmId: string): Promise<HealthSummary> {
  const { data } = await apiClient.get<APISuccess<HealthSummary>>(`${base(farmId)}/health/summary`);
  return data.data;
}
