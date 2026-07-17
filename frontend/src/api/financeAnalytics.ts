/**
 * Greena — Finance Analytics API Client (Module 5).
 * Farm-level overview, rolling analytics, unified transactions, cash flow,
 * period reports, CSV export, and AI context.
 */

import apiClient from "./client";
import type {
  APISuccess,
  FinanceAnalytics,
  FinanceOverview,
  FinanceReport,
  FinCashflow,
  FinTransactionPage,
} from "@/types";

const base = (farmId: string) => `/farms/${farmId}/finance`;

export async function getFinanceOverview(farmId: string): Promise<FinanceOverview> {
  const { data } = await apiClient.get<APISuccess<FinanceOverview>>(`${base(farmId)}/overview`);
  return data.data;
}

export async function getFinanceAnalytics(farmId: string): Promise<FinanceAnalytics> {
  const { data } = await apiClient.get<APISuccess<FinanceAnalytics>>(`${base(farmId)}/analytics`);
  return data.data;
}

export interface TransactionQuery {
  q?: string;
  kind?: "revenue" | "expense";
  category_id?: string;
  revenue_type?: string;
  flock_id?: string;
  date_from?: string;
  date_to?: string;
  min_amount?: string;
  max_amount?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export async function getFinanceTransactions(
  farmId: string,
  params?: TransactionQuery,
): Promise<FinTransactionPage> {
  const { data } = await apiClient.get<APISuccess<FinTransactionPage>>(`${base(farmId)}/transactions`, {
    params,
  });
  return data.data;
}

export async function getFinanceCashflow(farmId: string, months = 12): Promise<FinCashflow> {
  const { data } = await apiClient.get<APISuccess<FinCashflow>>(`${base(farmId)}/cashflow`, {
    params: { months },
  });
  return data.data;
}

export async function getFinanceReport(
  farmId: string,
  periodType: "monthly" | "quarterly" | "yearly",
  year: number,
  index: number,
): Promise<FinanceReport> {
  const { data } = await apiClient.get<APISuccess<FinanceReport>>(`${base(farmId)}/reports`, {
    params: { period_type: periodType, year, index },
  });
  return data.data;
}

/** Fetch the CSV export as a Blob for download. */
export async function downloadFinanceCsv(farmId: string, params?: { date_from?: string; date_to?: string }): Promise<Blob> {
  const res = await apiClient.get(`${base(farmId)}/reports/csv`, { params, responseType: "blob" });
  return res.data as Blob;
}
