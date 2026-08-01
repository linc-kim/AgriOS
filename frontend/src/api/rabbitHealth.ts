/**
 * Rabbit Health API (Module 17) — health records, vaccinations (which reuse the
 * platform Reminder engine) and mortality. Presentation-only; the backend owns
 * all analytics and never diagnoses (patterns only).
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/rabbit`;

export const HEALTH_EVENT_TYPES = [
  "observation", "exam", "illness", "injury", "treatment", "medication",
  "deworming", "surgery", "vet_visit", "recovery", "quarantine", "note",
] as const;
export const HEALTH_SEVERITIES = ["info", "mild", "moderate", "severe", "critical"] as const;
export const MORTALITY_CAUSES = [
  "disease", "injury", "predation", "environmental", "congenital", "digestive",
  "respiratory", "heat_stress", "starvation", "unknown", "other",
] as const;

export interface HealthRecord {
  id: string; rabbit_id: string; event_type: string; title: string | null;
  status: string; severity: string; symptoms: string | null; diagnosis: string | null;
  treatment: string | null; medication: string | null; veterinarian: string | null;
  recovery_status: string | null; occurred_on: string; next_due_on: string | null; notes: string | null;
}
export interface Vaccination {
  id: string; rabbit_id: string; vaccine: string; batch_number: string | null;
  administered_on: string; next_due_on: string | null; administrator: string | null;
  reminder_id: string | null; notes: string | null;
}
export interface Mortality {
  id: string; rabbit_id: string; occurred_on: string; age_days: number | null;
  cause: string; suspected_cause: string | null; postmortem_notes: string | null;
}

export async function listHealth(farmId: string, rabbitId: string) {
  const { data } = await apiClient.get<APISuccess<HealthRecord[]>>(`${base(farmId)}/rabbits/${rabbitId}/health`);
  return data.data;
}
export async function recordHealth(farmId: string, rabbitId: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<HealthRecord>>(`${base(farmId)}/rabbits/${rabbitId}/health`, body);
  return data.data;
}
export async function listRabbitVaccinations(farmId: string, rabbitId: string) {
  const { data } = await apiClient.get<APISuccess<Vaccination[]>>(`${base(farmId)}/rabbits/${rabbitId}/vaccinations`);
  return data.data;
}
export async function recordVaccination(farmId: string, rabbitId: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<Vaccination>>(`${base(farmId)}/rabbits/${rabbitId}/vaccinations`, body);
  return data.data;
}
export async function listVaccinations(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Vaccination[]>>(`${base(farmId)}/vaccinations`);
  return data.data;
}
export async function recordMortality(farmId: string, rabbitId: string, body: Record<string, unknown>) {
  const { data } = await apiClient.post<APISuccess<Mortality>>(`${base(farmId)}/rabbits/${rabbitId}/mortality`, body);
  return data.data;
}
export async function listMortality(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Mortality[]>>(`${base(farmId)}/mortality`);
  return data.data;
}
export async function getHealthSummary(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, unknown>>>(`${base(farmId)}/health/summary`);
  return data.data;
}
