/**
 * Greena — Market Prices API Client (Sprint 7)
 * Wraps /api/v1/market endpoints.
 * Platform-wide (not farm-scoped) per DB-04 exception documented in DB-09.
 */

import { apiClient } from "./client";
import type {
  APISuccess,
  MarketPrice,
  MarketPriceCreate,
  MarketPriceListResponse,
  CommodityListResponse,
} from "@/types";

export interface MarketPriceParams {
  commodity?: string;
  county?: string;
  as_of_date?: string;   // ISO date YYYY-MM-DD
}

export interface MarketPriceHistoryParams {
  commodity: string;     // required
  county?: string;
  limit?: number;
  offset?: number;
}

export const marketAPI = {
  /**
   * Get the latest price per commodity (optionally filtered by county/date).
   */
  listLatestPrices: async (
    params?: MarketPriceParams,
  ): Promise<MarketPriceListResponse> => {
    const res = await apiClient.get<APISuccess<MarketPriceListResponse>>(
      "/market/prices",
      { params },
    );
    return res.data.data;
  },

  /**
   * Get price history for a specific commodity.
   */
  listPriceHistory: async (
    params: MarketPriceHistoryParams,
  ): Promise<MarketPriceListResponse> => {
    const res = await apiClient.get<APISuccess<MarketPriceListResponse>>(
      "/market/prices/history",
      { params },
    );
    return res.data.data;
  },

  /**
   * Get all known commodity names.
   */
  listCommodities: async (): Promise<CommodityListResponse> => {
    const res = await apiClient.get<APISuccess<CommodityListResponse>>(
      "/market/commodities",
    );
    return res.data.data;
  },

  /**
   * Admin only: publish a new market price entry.
   * DB-09 (Frozen): corrections are new rows, not edits.
   */
  createPrice: async (payload: MarketPriceCreate): Promise<MarketPrice> => {
    const res = await apiClient.post<APISuccess<MarketPrice>>(
      "/market/prices",
      payload,
    );
    return res.data.data;
  },
};
