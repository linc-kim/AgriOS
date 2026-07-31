/**
 * BSF Feedstock & Feeding API (Module 16).
 *
 * Feedstock lots (a first-class resource with remaining-quantity tracking) and
 * immutable feeding events against a batch. Feed-conversion metrics are computed
 * by the backend engine and rendered here honesty-labelled — never recomputed.
 */
import apiClient from "./client";
import type { Figure } from "./bsf";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/bsf`;

export const FEEDSTOCK_CATEGORIES = [
  "fruit_waste", "vegetable_waste", "market_waste", "brewery_waste",
  "food_processing_waste", "agricultural_byproduct", "manure", "organic_waste", "other",
] as const;
export const FEEDSTOCK_QUALITIES = ["excellent", "good", "fair", "poor", "spoiled", "unknown"] as const;
export const FEEDING_METHODS = ["manual", "automated", "top_dressing", "single_dose", "continuous", "other"] as const;

export interface FeedstockLot {
  id: string;
  farm_id: string;
  name: string;
  code: string | null;
  category: string;
  source: string | null;
  supplier: string | null;
  collection_date: string | null;
  delivery_date: string | null;
  weight_kg: string;
  remaining_kg: string;
  moisture_pct: string | null;
  quality: string;
  storage_location: string | null;
  cost: string | null;
  currency: string | null;
  status: string;
  notes: string | null;
}

export interface FeedingEvent {
  id: string;
  batch_id: string;
  feedstock_lot_id: string | null;
  quantity_kg: string;
  feeding_method: string;
  fed_on: string;
  observations: string | null;
}

export async function listFeedstockLots(farmId: string, status?: string): Promise<FeedstockLot[]> {
  const { data } = await apiClient.get<APISuccess<FeedstockLot[]>>(`${base(farmId)}/feedstock-lots`, {
    params: status ? { status } : {},
  });
  return data.data;
}

export async function createFeedstockLot(
  farmId: string,
  body: { name: string; category: string; weight_kg: number; source?: string; supplier?: string; moisture_pct?: number | null; quality?: string; cost?: number | null; currency?: string; storage_location?: string; notes?: string },
): Promise<FeedstockLot> {
  const { data } = await apiClient.post<APISuccess<FeedstockLot>>(`${base(farmId)}/feedstock-lots`, body);
  return data.data;
}

export async function recordFeeding(
  farmId: string, batchId: string,
  body: { feedstock_lot_id?: string | null; quantity_kg: number; feeding_method?: string; fed_on?: string; observations?: string },
): Promise<FeedingEvent> {
  const { data } = await apiClient.post<APISuccess<FeedingEvent>>(`${base(farmId)}/batches/${batchId}/feedings`, body);
  return data.data;
}

export async function listFeedings(farmId: string, batchId: string): Promise<FeedingEvent[]> {
  const { data } = await apiClient.get<APISuccess<FeedingEvent[]>>(`${base(farmId)}/batches/${batchId}/feedings`);
  return data.data;
}

export async function getFeedConversion(farmId: string, batchId: string): Promise<Record<string, Figure>> {
  const { data } = await apiClient.get<APISuccess<Record<string, Figure>>>(`${base(farmId)}/batches/${batchId}/feed-conversion`);
  return data.data;
}

/** Post a lot's recorded cost to the SHARED expenses ledger (once). */
export async function postFeedstockExpense(farmId: string, lotId: string): Promise<{ expense_id: string; amount: string }> {
  const { data } = await apiClient.post<APISuccess<{ expense_id: string; amount: string }>>(
    `${base(farmId)}/feedstock-lots/${lotId}/post-expense`,
  );
  return data.data;
}
