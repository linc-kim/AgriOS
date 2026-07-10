/**
 * Greena — Health Module API Client
 * Covers Sprint 4 health endpoints:
 *   - Vaccination records (CRUD per flock)
 *   - Vaccination schedule (upcoming/overdue, farm-wide)
 *   - Disease alerts (farmer read + admin CRUD)
 */

import apiClient from "./client";
import type {
  ActiveAlertSummary,
  APISuccess,
  DiseaseAlert,
  UpcomingVaccinationsResponse,
  VaccinationRecord,
  VaccinationRecordCreateInput,
  VaccinationRecordUpdateInput,
} from "@/types";

// ── Vaccination Records ───────────────────────────────────────────────────────

export async function logVaccination(
  farmId: string,
  flockId: string,
  input: VaccinationRecordCreateInput,
): Promise<VaccinationRecord> {
  const { data } = await apiClient.post<APISuccess<VaccinationRecord>>(
    `/farms/${farmId}/flocks/${flockId}/vaccinations`,
    input,
  );
  return data.data;
}

export async function listVaccinations(
  farmId: string,
  flockId: string,
  params?: { limit?: number; offset?: number },
): Promise<VaccinationRecord[]> {
  const { data } = await apiClient.get<APISuccess<VaccinationRecord[]>>(
    `/farms/${farmId}/flocks/${flockId}/vaccinations`,
    { params },
  );
  return data.data;
}

export async function getVaccination(
  farmId: string,
  flockId: string,
  recordId: string,
): Promise<VaccinationRecord> {
  const { data } = await apiClient.get<APISuccess<VaccinationRecord>>(
    `/farms/${farmId}/flocks/${flockId}/vaccinations/${recordId}`,
  );
  return data.data;
}

export async function updateVaccination(
  farmId: string,
  flockId: string,
  recordId: string,
  input: VaccinationRecordUpdateInput,
): Promise<VaccinationRecord> {
  const { data } = await apiClient.patch<APISuccess<VaccinationRecord>>(
    `/farms/${farmId}/flocks/${flockId}/vaccinations/${recordId}`,
    input,
  );
  return data.data;
}

export async function deleteVaccination(
  farmId: string,
  flockId: string,
  recordId: string,
): Promise<void> {
  await apiClient.delete(
    `/farms/${farmId}/flocks/${flockId}/vaccinations/${recordId}`,
  );
}

// ── Vaccination Schedule (farm-wide) ─────────────────────────────────────────

export async function getVaccinationSchedule(
  farmId: string,
): Promise<UpcomingVaccinationsResponse> {
  const { data } = await apiClient.get<APISuccess<UpcomingVaccinationsResponse>>(
    `/farms/${farmId}/health/schedule`,
  );
  return data.data;
}

// ── Disease Alerts ────────────────────────────────────────────────────────────

export async function getFarmAlerts(
  farmId: string,
  params?: { limit?: number; offset?: number },
): Promise<DiseaseAlert[]> {
  const { data } = await apiClient.get<APISuccess<DiseaseAlert[]>>(
    `/farms/${farmId}/health/alerts`,
    { params },
  );
  return data.data;
}

export async function getActiveAlertBanner(
  farmId: string,
): Promise<ActiveAlertSummary[]> {
  const { data } = await apiClient.get<APISuccess<ActiveAlertSummary[]>>(
    `/farms/${farmId}/health/alerts/active`,
  );
  return data.data;
}
