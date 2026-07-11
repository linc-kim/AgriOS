/**
 * Greena — Flock API Client
 * Covers all Sprint 3 flock, daily log, production, weighin, and feed purchase endpoints.
 */

import apiClient from "./client";
import type {
  APISuccess,
  DailyLog,
  DailyLogSubmitInput,
  FarmProductionDashboard,
  FeedPurchase,
  FeedPurchaseInput,
  Flock,
  FlockCloseInput,
  FlockCreateInput,
  FlockDetail,
  FlockUpdateInput,
  ProductionRecord,
  ProductionRecordInput,
  WeighinInput,
  WeighinRecord,
} from "@/types";

// ── Flocks ────────────────────────────────────────────────────────────────────

export async function createFlock(
  farmId: string,
  input: FlockCreateInput,
): Promise<Flock> {
  const { data } = await apiClient.post<APISuccess<Flock>>(
    `/farms/${farmId}/flocks`,
    input,
  );
  return data.data;
}

export async function listFlocks(
  farmId: string,
  params?: { status?: string; limit?: number; offset?: number },
): Promise<Flock[]> {
  const { data } = await apiClient.get<APISuccess<Flock[]>>(
    `/farms/${farmId}/flocks`,
    { params },
  );
  return data.data;
}

export async function getFlock(farmId: string, flockId: string): Promise<FlockDetail> {
  const { data } = await apiClient.get<APISuccess<FlockDetail>>(
    `/farms/${farmId}/flocks/${flockId}`,
  );
  return data.data;
}

export async function updateFlock(
  farmId: string,
  flockId: string,
  input: FlockUpdateInput,
): Promise<Flock> {
  const { data } = await apiClient.patch<APISuccess<Flock>>(
    `/farms/${farmId}/flocks/${flockId}`,
    input,
  );
  return data.data;
}

export async function archiveFlock(farmId: string, flockId: string): Promise<Flock> {
  const { data } = await apiClient.post<APISuccess<Flock>>(
    `/farms/${farmId}/flocks/${flockId}/archive`,
  );
  return data.data;
}

export async function closeFlock(
  farmId: string,
  flockId: string,
  input: FlockCloseInput,
): Promise<Flock> {
  const { data } = await apiClient.post<APISuccess<Flock>>(
    `/farms/${farmId}/flocks/${flockId}/close`,
    input,
  );
  return data.data;
}

export async function getProductionDashboard(
  farmId: string,
): Promise<FarmProductionDashboard> {
  const { data } = await apiClient.get<APISuccess<FarmProductionDashboard>>(
    `/farms/${farmId}/production-dashboard`,
  );
  return data.data;
}

// ── Daily Logs ────────────────────────────────────────────────────────────────

export async function submitDailyLog(
  farmId: string,
  flockId: string,
  input: DailyLogSubmitInput,
): Promise<DailyLog> {
  const { data } = await apiClient.post<APISuccess<DailyLog>>(
    `/farms/${farmId}/flocks/${flockId}/logs`,
    input,
  );
  return data.data;
}

export async function listDailyLogs(
  farmId: string,
  flockId: string,
  params?: { limit?: number; offset?: number },
): Promise<DailyLog[]> {
  const { data } = await apiClient.get<APISuccess<DailyLog[]>>(
    `/farms/${farmId}/flocks/${flockId}/logs`,
    { params },
  );
  return data.data;
}

export async function getDailyLog(
  farmId: string,
  flockId: string,
  logDate: string,
): Promise<DailyLog> {
  const { data } = await apiClient.get<APISuccess<DailyLog>>(
    `/farms/${farmId}/flocks/${flockId}/logs/${logDate}`,
  );
  return data.data;
}

export async function correctDailyLog(
  farmId: string,
  flockId: string,
  logDate: string,
  input: Partial<DailyLogSubmitInput> & { correction_reason: string },
): Promise<DailyLog> {
  const { data } = await apiClient.patch<APISuccess<DailyLog>>(
    `/farms/${farmId}/flocks/${flockId}/logs/${logDate}`,
    input,
  );
  return data.data;
}

// ── Production Records ────────────────────────────────────────────────────────

export async function submitProductionRecord(
  farmId: string,
  flockId: string,
  input: ProductionRecordInput,
): Promise<ProductionRecord> {
  const { data } = await apiClient.post<APISuccess<ProductionRecord>>(
    `/farms/${farmId}/flocks/${flockId}/production`,
    input,
  );
  return data.data;
}

export async function listProductionRecords(
  farmId: string,
  flockId: string,
  params?: { limit?: number; offset?: number },
): Promise<ProductionRecord[]> {
  const { data } = await apiClient.get<APISuccess<ProductionRecord[]>>(
    `/farms/${farmId}/flocks/${flockId}/production`,
    { params },
  );
  return data.data;
}

// ── Weigh-Ins ─────────────────────────────────────────────────────────────────

export async function submitWeighin(
  farmId: string,
  flockId: string,
  input: WeighinInput,
): Promise<WeighinRecord> {
  const { data } = await apiClient.post<APISuccess<WeighinRecord>>(
    `/farms/${farmId}/flocks/${flockId}/weighins`,
    input,
  );
  return data.data;
}

export async function listWeighins(
  farmId: string,
  flockId: string,
  params?: { limit?: number; offset?: number },
): Promise<WeighinRecord[]> {
  const { data } = await apiClient.get<APISuccess<WeighinRecord[]>>(
    `/farms/${farmId}/flocks/${flockId}/weighins`,
    { params },
  );
  return data.data;
}

// ── Feed Purchases ────────────────────────────────────────────────────────────

export async function createFeedPurchase(
  farmId: string,
  input: FeedPurchaseInput,
): Promise<FeedPurchase> {
  const { data } = await apiClient.post<APISuccess<FeedPurchase>>(
    `/farms/${farmId}/feed-purchases`,
    input,
  );
  return data.data;
}

export async function listFeedPurchases(
  farmId: string,
  params?: { flock_id?: string; limit?: number; offset?: number },
): Promise<FeedPurchase[]> {
  const { data } = await apiClient.get<APISuccess<FeedPurchase[]>>(
    `/farms/${farmId}/feed-purchases`,
    { params },
  );
  return data.data;
}
