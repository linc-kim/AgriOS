/**
 * Greena — Admin API Client (Sprint 8)
 * Wraps /api/v1/admin/* endpoints.
 * All calls require super_admin or platform_admin role.
 */

import { apiClient } from "./client";
import type {
  APISuccess,
  AdminAIUsageResponse,
  AdminFarmListResponse,
  AdminFarmPlanInput,
  AdminUserDetail,
  AdminUserListResponse,
  AdminUserQuotaInput,
  AdminUserSuspendInput,
  PlatformStats,
  SubscriptionPlanSummary,
} from "@/types";

export interface AdminUserListParams {
  search?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}

export interface AdminFarmListParams {
  search?: string;
  plan_name?: string;
  limit?: number;
  offset?: number;
}

export const adminAPI = {
  // A-01 — Platform stats
  getStats: async (): Promise<PlatformStats> => {
    const res = await apiClient.get<APISuccess<PlatformStats>>("/admin/stats");
    return res.data.data;
  },

  // A-02 — User management
  listUsers: async (params?: AdminUserListParams): Promise<AdminUserListResponse> => {
    const res = await apiClient.get<APISuccess<AdminUserListResponse>>("/admin/users", { params });
    return res.data.data;
  },

  getUser: async (userId: string): Promise<AdminUserDetail> => {
    const res = await apiClient.get<APISuccess<AdminUserDetail>>(`/admin/users/${userId}`);
    return res.data.data;
  },

  suspendUser: async (userId: string, body: AdminUserSuspendInput): Promise<void> => {
    await apiClient.patch(`/admin/users/${userId}/suspend`, body);
  },

  restoreUser: async (userId: string): Promise<void> => {
    await apiClient.patch(`/admin/users/${userId}/restore`);
  },

  overrideQuota: async (userId: string, body: AdminUserQuotaInput): Promise<void> => {
    await apiClient.patch(`/admin/users/${userId}/quota`, body);
  },

  // A-03/A-04 — Farm management
  listFarms: async (params?: AdminFarmListParams): Promise<AdminFarmListResponse> => {
    const res = await apiClient.get<APISuccess<AdminFarmListResponse>>("/admin/farms", { params });
    return res.data.data;
  },

  overrideFarmPlan: async (farmId: string, body: AdminFarmPlanInput): Promise<void> => {
    await apiClient.patch(`/admin/farms/${farmId}/plan`, body);
  },

  listPlans: async (): Promise<SubscriptionPlanSummary[]> => {
    const res = await apiClient.get<APISuccess<SubscriptionPlanSummary[]>>("/admin/plans");
    return res.data.data;
  },

  // A-07 — AI usage
  getAIUsage: async (period_days = 30): Promise<AdminAIUsageResponse> => {
    const res = await apiClient.get<APISuccess<AdminAIUsageResponse>>("/admin/ai/usage", {
      params: { period_days },
    });
    return res.data.data;
  },
};
