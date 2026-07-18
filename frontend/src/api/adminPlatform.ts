/**
 * Greena — Admin Platform API Client (Module 10).
 */
import apiClient from "./client";
import type { APISuccess } from "@/types";
import type {
  AdminAskResponse, AdminDashboardData, AdminFarmRow, AdminOrgDetail, AdminOrgRow,
  AdminAuditRow, AdminPage, AdminUserRow, BackgroundJobStats, FeatureFlagRow,
  PlatformAnalytics, SystemConfigData, SystemHealthData,
} from "@/types/admin";

const base = "/admin/platform";

export async function getAdminDashboard(): Promise<AdminDashboardData> {
  const { data } = await apiClient.get<APISuccess<AdminDashboardData>>(`${base}/dashboard`);
  return data.data;
}
export async function getPlatformAnalytics(): Promise<PlatformAnalytics> {
  const { data } = await apiClient.get<APISuccess<PlatformAnalytics>>(`${base}/analytics`);
  return data.data;
}
export async function getSystemHealth(): Promise<SystemHealthData> {
  const { data } = await apiClient.get<APISuccess<SystemHealthData>>(`${base}/health`);
  return data.data;
}

// Organizations
export async function listOrganizations(params?: { q?: string; status?: string; page?: number }): Promise<AdminPage<AdminOrgRow>> {
  const { data } = await apiClient.get<APISuccess<AdminPage<AdminOrgRow>>>(`${base}/organizations`, { params });
  return data.data;
}
export async function getOrgDetail(id: string): Promise<AdminOrgDetail> {
  const { data } = await apiClient.get<APISuccess<AdminOrgDetail>>(`${base}/organizations/${id}`);
  return data.data;
}
export async function suspendOrg(id: string, reason?: string) {
  await apiClient.post(`${base}/organizations/${id}/suspend`, { reason });
}
export async function reactivateOrg(id: string) {
  await apiClient.post(`${base}/organizations/${id}/reactivate`, {});
}
export async function deleteOrg(id: string) {
  await apiClient.delete(`${base}/organizations/${id}`);
}

// Users
export async function listAdminUsers(params?: { q?: string; page?: number }): Promise<AdminPage<AdminUserRow>> {
  const { data } = await apiClient.get<APISuccess<AdminPage<AdminUserRow>>>(`${base}/users`, { params });
  return data.data;
}
export async function changeUserRole(id: string, role: string) {
  await apiClient.post(`${base}/users/${id}/role`, { role });
}
export async function disableUser(id: string, reason?: string) {
  await apiClient.post(`${base}/users/${id}/disable`, { reason });
}
export async function reactivateUser(id: string) {
  await apiClient.post(`${base}/users/${id}/reactivate`, {});
}
export async function forceLogout(id: string) {
  const { data } = await apiClient.post<APISuccess<{ sessions_revoked: number }>>(`${base}/users/${id}/force-logout`, {});
  return data.data;
}
export async function resetPassword(id: string) {
  await apiClient.post(`${base}/users/${id}/reset-password`, {});
}

// Farms
export async function listAdminFarms(params?: { q?: string; page?: number }): Promise<AdminPage<AdminFarmRow>> {
  const { data } = await apiClient.get<APISuccess<AdminPage<AdminFarmRow>>>(`${base}/farms`, { params });
  return data.data;
}
export async function archiveFarm(id: string, reason?: string) {
  await apiClient.post(`${base}/farms/${id}/archive`, { reason });
}
export async function restoreFarm(id: string) {
  await apiClient.post(`${base}/farms/${id}/restore`, {});
}

// Audit
export async function listAudit(params?: { q?: string; resource_type?: string; page?: number }): Promise<AdminPage<AdminAuditRow>> {
  const { data } = await apiClient.get<APISuccess<AdminPage<AdminAuditRow>>>(`${base}/audit`, { params });
  return data.data;
}
export async function downloadAuditCsv(): Promise<Blob> {
  const res = await apiClient.get(`${base}/audit/csv`, { responseType: "blob" });
  return res.data as Blob;
}

// Feature flags
export async function listFeatureFlags(): Promise<FeatureFlagRow[]> {
  const { data } = await apiClient.get<APISuccess<FeatureFlagRow[]>>(`${base}/feature-flags`);
  return data.data;
}
export async function setFeatureFlag(input: { flag_key: string; is_enabled: boolean; organization_id?: string | null }): Promise<FeatureFlagRow> {
  const { data } = await apiClient.post<APISuccess<FeatureFlagRow>>(`${base}/feature-flags`, input);
  return data.data;
}

// System config
export async function getSystemConfig(): Promise<SystemConfigData> {
  const { data } = await apiClient.get<APISuccess<SystemConfigData>>(`${base}/system-config`);
  return data.data;
}
export async function updateSystemConfig(input: Partial<SystemConfigData>): Promise<SystemConfigData> {
  const { data } = await apiClient.patch<APISuccess<SystemConfigData>>(`${base}/system-config`, input);
  return data.data;
}

// Jobs
export async function getJobs(): Promise<BackgroundJobStats> {
  const { data } = await apiClient.get<APISuccess<BackgroundJobStats>>(`${base}/jobs`);
  return data.data;
}
export async function runJob(name: string) {
  const { data } = await apiClient.post(`${base}/jobs/run`, { name });
  return data.data;
}

// Admin AI
export async function adminAsk(question: string): Promise<AdminAskResponse> {
  const { data } = await apiClient.post<APISuccess<AdminAskResponse>>(`${base}/ai/ask`, { question });
  return data.data;
}
