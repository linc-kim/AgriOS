/**
 * Greena — Feed Management API Client (Phase 3, Module 4).
 * Suppliers, inventory, purchases, consumption, transfers, wastage,
 * dashboard, reorder alerts, analytics, and the AI context payload.
 */

import apiClient from "./client";
import type {
  APISuccess,
  FeedAnalytics,
  FeedConsumptionInput,
  FeedDashboard,
  FeedInventoryItem,
  FeedInventoryItemInput,
  FeedPurchaseModuleInput,
  FeedReorderAlert,
  FeedSupplier,
  FeedSupplierInput,
  FeedTransaction,
  FeedTransferInput,
  FeedWastageInput,
} from "@/types";

const base = (farmId: string) => `/farms/${farmId}/feed`;

// ── Suppliers ─────────────────────────────────────────────────────────────────

export async function listSuppliers(farmId: string, includeInactive = false): Promise<FeedSupplier[]> {
  const { data } = await apiClient.get<APISuccess<FeedSupplier[]>>(`${base(farmId)}/suppliers`, {
    params: { include_inactive: includeInactive },
  });
  return data.data;
}

export async function createSupplier(farmId: string, input: FeedSupplierInput): Promise<FeedSupplier> {
  const { data } = await apiClient.post<APISuccess<FeedSupplier>>(`${base(farmId)}/suppliers`, input);
  return data.data;
}

export async function updateSupplier(
  farmId: string,
  supplierId: string,
  input: Partial<FeedSupplierInput> & { is_active?: boolean },
): Promise<FeedSupplier> {
  const { data } = await apiClient.patch<APISuccess<FeedSupplier>>(
    `${base(farmId)}/suppliers/${supplierId}`,
    input,
  );
  return data.data;
}

export async function deleteSupplier(farmId: string, supplierId: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/suppliers/${supplierId}`);
}

// ── Inventory ─────────────────────────────────────────────────────────────────

export async function listInventory(farmId: string, includeInactive = false): Promise<FeedInventoryItem[]> {
  const { data } = await apiClient.get<APISuccess<FeedInventoryItem[]>>(`${base(farmId)}/inventory`, {
    params: { include_inactive: includeInactive },
  });
  return data.data;
}

export async function createInventoryItem(
  farmId: string,
  input: FeedInventoryItemInput,
): Promise<FeedInventoryItem> {
  const { data } = await apiClient.post<APISuccess<FeedInventoryItem>>(`${base(farmId)}/inventory`, input);
  return data.data;
}

export async function updateInventoryItem(
  farmId: string,
  itemId: string,
  input: Partial<FeedInventoryItemInput> & { is_active?: boolean },
): Promise<FeedInventoryItem> {
  const { data } = await apiClient.patch<APISuccess<FeedInventoryItem>>(
    `${base(farmId)}/inventory/${itemId}`,
    input,
  );
  return data.data;
}

export async function deleteInventoryItem(farmId: string, itemId: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/inventory/${itemId}`);
}

// ── Movements ─────────────────────────────────────────────────────────────────

export async function recordPurchase(farmId: string, input: FeedPurchaseModuleInput) {
  const { data } = await apiClient.post<APISuccess<{ item: FeedInventoryItem; transaction: FeedTransaction }>>(
    `${base(farmId)}/purchases`,
    input,
  );
  return data.data;
}

export async function recordConsumption(farmId: string, input: FeedConsumptionInput) {
  const { data } = await apiClient.post<APISuccess<{ item: FeedInventoryItem; transaction: FeedTransaction }>>(
    `${base(farmId)}/consumption`,
    input,
  );
  return data.data;
}

export async function recordTransfer(farmId: string, input: FeedTransferInput) {
  const { data } = await apiClient.post<APISuccess<{ from_item: FeedInventoryItem; to_item: FeedInventoryItem }>>(
    `${base(farmId)}/transfers`,
    input,
  );
  return data.data;
}

export async function recordWastage(farmId: string, input: FeedWastageInput) {
  const { data } = await apiClient.post<APISuccess<{ item: FeedInventoryItem; transaction: FeedTransaction }>>(
    `${base(farmId)}/wastage`,
    input,
  );
  return data.data;
}

// ── Reporting ─────────────────────────────────────────────────────────────────

export async function listTransactions(
  farmId: string,
  params?: { item_id?: string; flock_id?: string; txn_type?: string; limit?: number; offset?: number },
): Promise<FeedTransaction[]> {
  const { data } = await apiClient.get<APISuccess<FeedTransaction[]>>(`${base(farmId)}/transactions`, {
    params,
  });
  return data.data;
}

export async function getFeedDashboard(farmId: string, windowDays = 30): Promise<FeedDashboard> {
  const { data } = await apiClient.get<APISuccess<FeedDashboard>>(`${base(farmId)}/dashboard`, {
    params: { window_days: windowDays },
  });
  return data.data;
}

export async function getReorderAlerts(farmId: string): Promise<FeedReorderAlert[]> {
  const { data } = await apiClient.get<APISuccess<FeedReorderAlert[]>>(`${base(farmId)}/alerts`);
  return data.data;
}

export async function getFeedAnalytics(farmId: string, windowDays = 90): Promise<FeedAnalytics> {
  const { data } = await apiClient.get<APISuccess<FeedAnalytics>>(`${base(farmId)}/analytics`, {
    params: { window_days: windowDays },
  });
  return data.data;
}

export async function listFlockConsumption(
  farmId: string,
  flockId: string,
  params?: { limit?: number; offset?: number },
): Promise<FeedTransaction[]> {
  const { data } = await apiClient.get<APISuccess<FeedTransaction[]>>(
    `/farms/${farmId}/flocks/${flockId}/feed-consumption`,
    { params },
  );
  return data.data;
}
