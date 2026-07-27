/**
 * Aviculture Aviary API (Module 15, Part 3).
 *
 * Facility management: aviaries, zones, fixtures, environmental readings,
 * cleaning/maintenance tasks, timeline and a farm-wide infrastructure summary.
 * Occupancy and environment figures arrive honesty-labelled from the pure
 * aviary engine — the UI renders the label, never re-derives the number.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T };
type APIList<T> = { data: T[]; meta: { total: number; pages: number } };

const base = (farmId: string) => `/farms/${farmId}/aviculture/aviaries`;

export interface Labelled<T = unknown> {
  label: string;
  value: T;
  detail?: string;
}

export interface Occupancy {
  occupied: Labelled<number>;
  capacity: Labelled<number | null>;
  available: Labelled<number | null>;
  utilization_pct: Labelled<number | null>;
  over_capacity: boolean;
}

export interface Aviary {
  id: string;
  farm_id: string;
  name: string;
  code: string | null;
  aviary_type: string;
  building: string | null;
  purpose: string;
  biosecurity_level: string;
  capacity: number | null;
  dimensions: Record<string, unknown>;
  environment: Record<string, unknown>;
  status: string;
  notes: string | null;
  occupancy?: Occupancy | null;
}

export interface AviaryDetail extends Aviary {
  environment_summary: {
    reading_count: number;
    latest: Record<string, unknown>;
    averages: Record<string, Labelled>;
    findings: { label: string; metric: string; detail: string }[];
  } | null;
  cleaning: Record<string, Labelled> | null;
  housing_assessment: { label: string; findings: { metric: string; detail: string }[]; detail: string } | null;
  zone_count: number;
  fixture_count: number;
}

export interface Zone { id: string; aviary_id: string; name: string; zone_type: string; capacity: number | null; notes: string | null; }
export interface Fixture { id: string; aviary_id: string; zone_id: string | null; fixture_type: string; label: string | null; quantity: number; status: string; details: Record<string, unknown>; }
export interface EnvReading { id: string; aviary_id: string; recorded_at: string; temperature_c: string | null; humidity_pct: string | null; light_hours: string | null; air_quality: string | null; notes: string | null; }
export interface AviaryTask { id: string; aviary_id: string; task_type: string; title: string; status: string; scheduled_for: string | null; completed_on: string | null; recurrence: string; notes: string | null; }
export interface AviaryEvent { id: string; aviary_id: string; event_type: string; occurred_on: string; title: string; description: string | null; }
export interface InfrastructureSummary { aviary_count: number; total_capacity: Labelled; total_occupied: Labelled; available: Labelled; by_purpose: Record<string, number>; quarantine_aviaries: number; }

export async function listAviaries(farmId: string, params: Record<string, unknown> = {}): Promise<{ aviaries: Aviary[]; total: number; pages: number }> {
  const { data } = await apiClient.get<APIList<Aviary>>(base(farmId), { params });
  return { aviaries: data.data, total: data.meta.total, pages: data.meta.pages };
}
export async function getInfrastructure(farmId: string): Promise<InfrastructureSummary> {
  const { data } = await apiClient.get<APISuccess<InfrastructureSummary>>(`${base(farmId)}/summary`);
  return data.data;
}
export async function createAviary(farmId: string, body: Partial<Aviary>): Promise<Aviary> {
  const { data } = await apiClient.post<APISuccess<Aviary>>(base(farmId), body);
  return data.data;
}
export async function getAviary(farmId: string, id: string): Promise<AviaryDetail> {
  const { data } = await apiClient.get<APISuccess<AviaryDetail>>(`${base(farmId)}/${id}`);
  return data.data;
}
export async function deactivateAviary(farmId: string, id: string): Promise<Aviary> {
  const { data } = await apiClient.post<APISuccess<Aviary>>(`${base(farmId)}/${id}/deactivate`, {});
  return data.data;
}
export async function listZones(farmId: string, id: string): Promise<Zone[]> {
  const { data } = await apiClient.get<APISuccess<Zone[]>>(`${base(farmId)}/${id}/zones`);
  return data.data;
}
export async function addZone(farmId: string, id: string, body: { name: string; zone_type: string; capacity?: number }): Promise<Zone> {
  const { data } = await apiClient.post<APISuccess<Zone>>(`${base(farmId)}/${id}/zones`, body);
  return data.data;
}
export async function listFixtures(farmId: string, id: string): Promise<Fixture[]> {
  const { data } = await apiClient.get<APISuccess<Fixture[]>>(`${base(farmId)}/${id}/fixtures`);
  return data.data;
}
export async function addFixture(farmId: string, id: string, body: { fixture_type: string; label?: string; quantity?: number }): Promise<Fixture> {
  const { data } = await apiClient.post<APISuccess<Fixture>>(`${base(farmId)}/${id}/fixtures`, body);
  return data.data;
}
export async function listReadings(farmId: string, id: string): Promise<EnvReading[]> {
  const { data } = await apiClient.get<APISuccess<EnvReading[]>>(`${base(farmId)}/${id}/environment`);
  return data.data;
}
export async function addReading(farmId: string, id: string, body: { temperature_c?: string; humidity_pct?: string; light_hours?: string }): Promise<EnvReading> {
  const { data } = await apiClient.post<APISuccess<EnvReading>>(`${base(farmId)}/${id}/environment`, body);
  return data.data;
}
export async function listTasks(farmId: string, id: string): Promise<AviaryTask[]> {
  const { data } = await apiClient.get<APISuccess<AviaryTask[]>>(`${base(farmId)}/${id}/tasks`);
  return data.data;
}
export async function addTask(farmId: string, id: string, body: { task_type: string; title: string; scheduled_for?: string; recurrence?: string }): Promise<AviaryTask> {
  const { data } = await apiClient.post<APISuccess<AviaryTask>>(`${base(farmId)}/${id}/tasks`, body);
  return data.data;
}
export async function completeTask(farmId: string, id: string, taskId: string): Promise<AviaryTask> {
  const { data } = await apiClient.post<APISuccess<AviaryTask>>(`${base(farmId)}/${id}/tasks/${taskId}/complete`, {});
  return data.data;
}
export async function getAviaryTimeline(farmId: string, id: string): Promise<AviaryEvent[]> {
  const { data } = await apiClient.get<APISuccess<AviaryEvent[]>>(`${base(farmId)}/${id}/timeline`);
  return data.data;
}
