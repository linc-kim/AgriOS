/**
 * Greena — Reporting & BI API Client (Module 7).
 */
import apiClient from "./client";
import type { APISuccess, Report, SavedReport } from "@/types";

const base = (farmId: string) => `/farms/${farmId}/reporting`;

export interface ReportParams {
  report_type: string;
  period_type?: string;
  start?: string;
  end?: string;
}

export async function generateReport(farmId: string, params: ReportParams): Promise<Report> {
  const { data } = await apiClient.get<APISuccess<Report>>(`${base(farmId)}/generate`, { params });
  return data.data;
}

export async function getRoleDashboard(farmId: string, role: string): Promise<Report> {
  const { data } = await apiClient.get<APISuccess<Report>>(`${base(farmId)}/dashboards/${role}`);
  return data.data;
}

export async function getComparison(farmId: string, comparisonType: string, flockA?: string, flockB?: string): Promise<Report> {
  const { data } = await apiClient.get<APISuccess<Report>>(`${base(farmId)}/comparisons`, {
    params: { comparison_type: comparisonType, flock_a: flockA, flock_b: flockB },
  });
  return data.data;
}

export async function downloadReportCsv(farmId: string, params: ReportParams): Promise<Blob> {
  const res = await apiClient.get(`${base(farmId)}/generate/csv`, { params, responseType: "blob" });
  return res.data as Blob;
}

export async function listSavedReports(farmId: string): Promise<SavedReport[]> {
  const { data } = await apiClient.get<APISuccess<SavedReport[]>>(`${base(farmId)}/saved`);
  return data.data;
}

export async function createSavedReport(farmId: string, input: { name: string; report_type: string; config?: Record<string, any>; is_pinned?: boolean }): Promise<SavedReport> {
  const { data } = await apiClient.post<APISuccess<SavedReport>>(`${base(farmId)}/saved`, input);
  return data.data;
}

export async function updateSavedReport(farmId: string, id: string, input: { name?: string; config?: Record<string, any>; is_pinned?: boolean }): Promise<SavedReport> {
  const { data } = await apiClient.patch<APISuccess<SavedReport>>(`${base(farmId)}/saved/${id}`, input);
  return data.data;
}

export async function deleteSavedReport(farmId: string, id: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/saved/${id}`);
}
