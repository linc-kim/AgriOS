/**
 * Greena — Farm API Client
 * All farm management API calls. Matches backend endpoints in farms.py.
 */

import { apiClient } from "./client";
import type {
  APISuccess,
  Farm,
  FarmCreateInput,
  FarmMember,
  FarmMemberInviteInput,
  FarmMemberUpdateInput,
  FarmSummary,
  FarmUnit,
  FarmUnitCreateInput,
  FarmUnitUpdateInput,
  FarmUpdateInput,
  ProductionHouse,
  ProductionHouseCreateInput,
  ProductionHouseUpdateInput,
  SubscriptionPlan,
} from "@/types";

// ── Subscription Plans ────────────────────────────────────────────────────────

export async function getSubscriptionPlans(): Promise<SubscriptionPlan[]> {
  const resp = await apiClient.get<APISuccess<SubscriptionPlan[]>>("/plans");
  return resp.data.data;
}

// ── Farms ─────────────────────────────────────────────────────────────────────

export async function createFarm(input: FarmCreateInput): Promise<Farm> {
  const resp = await apiClient.post<APISuccess<Farm>>("/farms", input);
  return resp.data.data;
}

export async function listFarms(): Promise<FarmSummary[]> {
  const resp = await apiClient.get<APISuccess<FarmSummary[]>>("/farms");
  return resp.data.data;
}

export async function getFarm(farmId: string): Promise<Farm> {
  const resp = await apiClient.get<APISuccess<Farm>>(`/farms/${farmId}`);
  return resp.data.data;
}

export async function updateFarm(farmId: string, input: FarmUpdateInput): Promise<Farm> {
  const resp = await apiClient.patch<APISuccess<Farm>>(`/farms/${farmId}`, input);
  return resp.data.data;
}

// ── Farm Members ──────────────────────────────────────────────────────────────

export async function listFarmMembers(farmId: string): Promise<FarmMember[]> {
  const resp = await apiClient.get<APISuccess<FarmMember[]>>(
    `/farms/${farmId}/members`
  );
  return resp.data.data;
}

export async function inviteFarmMember(
  farmId: string,
  input: FarmMemberInviteInput
): Promise<FarmMember> {
  const resp = await apiClient.post<APISuccess<FarmMember>>(
    `/farms/${farmId}/members/invite`,
    input
  );
  return resp.data.data;
}

export async function updateFarmMember(
  farmId: string,
  memberId: string,
  input: FarmMemberUpdateInput
): Promise<FarmMember> {
  const resp = await apiClient.patch<APISuccess<FarmMember>>(
    `/farms/${farmId}/members/${memberId}`,
    input
  );
  return resp.data.data;
}

export async function removeFarmMember(
  farmId: string,
  memberId: string
): Promise<void> {
  await apiClient.delete(`/farms/${farmId}/members/${memberId}`);
}

// ── Farm Units ────────────────────────────────────────────────────────────────

export async function listFarmUnits(farmId: string): Promise<FarmUnit[]> {
  const resp = await apiClient.get<APISuccess<FarmUnit[]>>(
    `/farms/${farmId}/units`
  );
  return resp.data.data;
}

export async function createFarmUnit(
  farmId: string,
  input: FarmUnitCreateInput
): Promise<FarmUnit> {
  const resp = await apiClient.post<APISuccess<FarmUnit>>(
    `/farms/${farmId}/units`,
    input
  );
  return resp.data.data;
}

export async function updateFarmUnit(
  farmId: string,
  unitId: string,
  input: FarmUnitUpdateInput
): Promise<FarmUnit> {
  const resp = await apiClient.patch<APISuccess<FarmUnit>>(
    `/farms/${farmId}/units/${unitId}`,
    input
  );
  return resp.data.data;
}

export async function deleteFarmUnit(farmId: string, unitId: string): Promise<void> {
  await apiClient.delete(`/farms/${farmId}/units/${unitId}`);
}

// ── Production Houses ─────────────────────────────────────────────────────────

export async function listFarmHouses(farmId: string): Promise<ProductionHouse[]> {
  const resp = await apiClient.get<APISuccess<ProductionHouse[]>>(
    `/farms/${farmId}/houses`
  );
  return resp.data.data;
}

export async function createProductionHouse(
  farmId: string,
  unitId: string,
  input: ProductionHouseCreateInput
): Promise<ProductionHouse> {
  const resp = await apiClient.post<APISuccess<ProductionHouse>>(
    `/farms/${farmId}/units/${unitId}/houses`,
    input
  );
  return resp.data.data;
}

export async function updateProductionHouse(
  farmId: string,
  unitId: string,
  houseId: string,
  input: ProductionHouseUpdateInput
): Promise<ProductionHouse> {
  const resp = await apiClient.patch<APISuccess<ProductionHouse>>(
    `/farms/${farmId}/units/${unitId}/houses/${houseId}`,
    input
  );
  return resp.data.data;
}

export async function deleteProductionHouse(
  farmId: string,
  unitId: string,
  houseId: string
): Promise<void> {
  await apiClient.delete(
    `/farms/${farmId}/units/${unitId}/houses/${houseId}`
  );
}
