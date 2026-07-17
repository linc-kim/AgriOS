/**
 * Greena — Inventory & Asset Management API Client (Module 6).
 */
import apiClient from "./client";
import type {
  APISuccess,
  Asset,
  AssetInput,
  AssetMaintenance,
  InventoryAlert,
  InventoryAnalytics,
  InventoryDashboard,
  InventoryItem,
  InventoryItemInput,
  InventoryMovement,
  InventoryMovementInput,
  InventorySupplier,
  MaintenanceInput,
} from "@/types";

const base = (farmId: string) => `/farms/${farmId}/inventory`;

// Suppliers
export async function listInvSuppliers(farmId: string, includeInactive = false): Promise<InventorySupplier[]> {
  const { data } = await apiClient.get<APISuccess<InventorySupplier[]>>(`${base(farmId)}/suppliers`, { params: { include_inactive: includeInactive } });
  return data.data;
}
export async function createInvSupplier(farmId: string, input: Partial<InventorySupplier> & { name: string }): Promise<InventorySupplier> {
  const { data } = await apiClient.post<APISuccess<InventorySupplier>>(`${base(farmId)}/suppliers`, input);
  return data.data;
}
export async function updateInvSupplier(farmId: string, id: string, input: Record<string, unknown>): Promise<InventorySupplier> {
  const { data } = await apiClient.patch<APISuccess<InventorySupplier>>(`${base(farmId)}/suppliers/${id}`, input);
  return data.data;
}
export async function deleteInvSupplier(farmId: string, id: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/suppliers/${id}`);
}

// Items
export async function listInvItems(farmId: string, params?: { include_inactive?: boolean; category?: string }): Promise<InventoryItem[]> {
  const { data } = await apiClient.get<APISuccess<InventoryItem[]>>(`${base(farmId)}/items`, { params });
  return data.data;
}
export async function createInvItem(farmId: string, input: InventoryItemInput): Promise<InventoryItem> {
  const { data } = await apiClient.post<APISuccess<InventoryItem>>(`${base(farmId)}/items`, input);
  return data.data;
}
export async function updateInvItem(farmId: string, id: string, input: Partial<InventoryItemInput> & { is_active?: boolean }): Promise<InventoryItem> {
  const { data } = await apiClient.patch<APISuccess<InventoryItem>>(`${base(farmId)}/items/${id}`, input);
  return data.data;
}
export async function deleteInvItem(farmId: string, id: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/items/${id}`);
}

// Movements
export async function recordInvMovement(farmId: string, input: InventoryMovementInput) {
  const { data } = await apiClient.post<APISuccess<{ item: InventoryItem; movement: InventoryMovement }>>(`${base(farmId)}/movements`, input);
  return data.data;
}
export async function listInvMovements(farmId: string, params?: { item_id?: string; movement_type?: string; limit?: number }): Promise<InventoryMovement[]> {
  const { data } = await apiClient.get<APISuccess<InventoryMovement[]>>(`${base(farmId)}/movements`, { params });
  return data.data;
}

// Assets
export async function listAssets(farmId: string, params?: { asset_type?: string }): Promise<Asset[]> {
  const { data } = await apiClient.get<APISuccess<Asset[]>>(`${base(farmId)}/assets`, { params });
  return data.data;
}
export async function createAsset(farmId: string, input: AssetInput): Promise<Asset> {
  const { data } = await apiClient.post<APISuccess<Asset>>(`${base(farmId)}/assets`, input);
  return data.data;
}
export async function updateAsset(farmId: string, id: string, input: Record<string, unknown>): Promise<Asset> {
  const { data } = await apiClient.patch<APISuccess<Asset>>(`${base(farmId)}/assets/${id}`, input);
  return data.data;
}
export async function deleteAsset(farmId: string, id: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/assets/${id}`);
}

// Maintenance
export async function listMaintenance(farmId: string, params?: { asset_id?: string; status?: string }): Promise<AssetMaintenance[]> {
  const { data } = await apiClient.get<APISuccess<AssetMaintenance[]>>(`${base(farmId)}/maintenance`, { params });
  return data.data;
}
export async function createMaintenance(farmId: string, input: MaintenanceInput): Promise<AssetMaintenance> {
  const { data } = await apiClient.post<APISuccess<AssetMaintenance>>(`${base(farmId)}/maintenance`, input);
  return data.data;
}
export async function updateMaintenance(farmId: string, id: string, input: Record<string, unknown>): Promise<AssetMaintenance> {
  const { data } = await apiClient.patch<APISuccess<AssetMaintenance>>(`${base(farmId)}/maintenance/${id}`, input);
  return data.data;
}

// Reporting
export async function getInvDashboard(farmId: string, windowDays = 30): Promise<InventoryDashboard> {
  const { data } = await apiClient.get<APISuccess<InventoryDashboard>>(`${base(farmId)}/dashboard`, { params: { window_days: windowDays } });
  return data.data;
}
export async function getInvAlerts(farmId: string): Promise<InventoryAlert[]> {
  const { data } = await apiClient.get<APISuccess<InventoryAlert[]>>(`${base(farmId)}/alerts`);
  return data.data;
}
export async function getInvAnalytics(farmId: string, windowDays = 90): Promise<InventoryAnalytics> {
  const { data } = await apiClient.get<APISuccess<InventoryAnalytics>>(`${base(farmId)}/analytics`, { params: { window_days: windowDays } });
  return data.data;
}
