/**
 * Greena — Finance API Client
 * All functions unwrap from APISuccess<T> envelope.
 * Covers: expense categories, expenses, revenue records,
 *         financial snapshots, dashboard, and calculators.
 */

import { apiClient } from "./client";
import type {
  APISuccess,
  BreakEvenResult,
  Expense,
  ExpenseCategory,
  ExpenseCategoryBreakdown,
  ExpenseCategoryCreateInput,
  ExpenseCreateInput,
  ExpenseListResponse,
  ExpenseUpdateInput,
  FCRCalculatorResult,
  FinanceDashboardResponse,
  FinancialSnapshot,
  FeedNeedsResult,
  ProfitProjectionResult,
  RevenueListResponse,
  RevenueRecord,
  RevenueRecordCreateInput,
  RevenueRecordUpdateInput,
} from "@/types";

// ── Expense Categories ────────────────────────────────────────────────────────

export async function listExpenseCategories(
  farmId: string
): Promise<ExpenseCategory[]> {
  const res = await apiClient.get<APISuccess<ExpenseCategory[]>>(
    `/farms/${farmId}/finance/categories`
  );
  return res.data.data;
}

export async function createExpenseCategory(
  farmId: string,
  body: ExpenseCategoryCreateInput
): Promise<ExpenseCategory> {
  const res = await apiClient.post<APISuccess<ExpenseCategory>>(
    `/farms/${farmId}/finance/categories`,
    body
  );
  return res.data.data;
}

// ── Expenses ──────────────────────────────────────────────────────────────────

export interface ExpenseListParams {
  flock_id?: string;
  category_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function logExpense(
  farmId: string,
  body: ExpenseCreateInput
): Promise<Expense> {
  const res = await apiClient.post<APISuccess<Expense>>(
    `/farms/${farmId}/expenses`,
    body
  );
  return res.data.data;
}

export async function listExpenses(
  farmId: string,
  params?: ExpenseListParams
): Promise<ExpenseListResponse> {
  const res = await apiClient.get<APISuccess<ExpenseListResponse>>(
    `/farms/${farmId}/expenses`,
    { params }
  );
  return res.data.data;
}

export async function getExpense(
  farmId: string,
  expenseId: string
): Promise<Expense> {
  const res = await apiClient.get<APISuccess<Expense>>(
    `/farms/${farmId}/expenses/${expenseId}`
  );
  return res.data.data;
}

export async function updateExpense(
  farmId: string,
  expenseId: string,
  body: ExpenseUpdateInput
): Promise<Expense> {
  const res = await apiClient.patch<APISuccess<Expense>>(
    `/farms/${farmId}/expenses/${expenseId}`,
    body
  );
  return res.data.data;
}

export async function deleteExpense(
  farmId: string,
  expenseId: string
): Promise<void> {
  await apiClient.delete(`/farms/${farmId}/expenses/${expenseId}`);
}

// ── Revenue Records ───────────────────────────────────────────────────────────

export interface RevenueListParams {
  flock_id?: string;
  revenue_type?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function logRevenue(
  farmId: string,
  body: RevenueRecordCreateInput
): Promise<RevenueRecord> {
  const res = await apiClient.post<APISuccess<RevenueRecord>>(
    `/farms/${farmId}/revenue`,
    body
  );
  return res.data.data;
}

export async function listRevenue(
  farmId: string,
  params?: RevenueListParams
): Promise<RevenueListResponse> {
  const res = await apiClient.get<APISuccess<RevenueListResponse>>(
    `/farms/${farmId}/revenue`,
    { params }
  );
  return res.data.data;
}

export async function getRevenueRecord(
  farmId: string,
  recordId: string
): Promise<RevenueRecord> {
  const res = await apiClient.get<APISuccess<RevenueRecord>>(
    `/farms/${farmId}/revenue/${recordId}`
  );
  return res.data.data;
}

export async function updateRevenueRecord(
  farmId: string,
  recordId: string,
  body: RevenueRecordUpdateInput
): Promise<RevenueRecord> {
  const res = await apiClient.patch<APISuccess<RevenueRecord>>(
    `/farms/${farmId}/revenue/${recordId}`,
    body
  );
  return res.data.data;
}

export async function deleteRevenueRecord(
  farmId: string,
  recordId: string
): Promise<void> {
  await apiClient.delete(`/farms/${farmId}/revenue/${recordId}`);
}

// ── Financial Snapshot ────────────────────────────────────────────────────────

export async function getFlockSnapshot(
  farmId: string,
  flockId: string
): Promise<FinancialSnapshot> {
  const res = await apiClient.get<APISuccess<FinancialSnapshot>>(
    `/farms/${farmId}/flocks/${flockId}/finance`
  );
  return res.data.data;
}

export async function refreshFlockSnapshot(
  farmId: string,
  flockId: string
): Promise<FinancialSnapshot> {
  const res = await apiClient.post<APISuccess<FinancialSnapshot>>(
    `/farms/${farmId}/flocks/${flockId}/finance/refresh`
  );
  return res.data.data;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export async function getFinanceDashboard(
  farmId: string
): Promise<FinanceDashboardResponse> {
  const res = await apiClient.get<APISuccess<FinanceDashboardResponse>>(
    `/farms/${farmId}/finance`
  );
  return res.data.data;
}

export async function getCategoryBreakdown(
  farmId: string,
  params?: { flock_id?: string; date_from?: string; date_to?: string }
): Promise<ExpenseCategoryBreakdown[]> {
  const res = await apiClient.get<APISuccess<ExpenseCategoryBreakdown[]>>(
    `/farms/${farmId}/finance/categories/breakdown`,
    { params }
  );
  return res.data.data;
}

// ── Calculators ───────────────────────────────────────────────────────────────

export async function calculateFCR(
  total_feed_kg: number,
  total_live_weight_kg: number
): Promise<FCRCalculatorResult> {
  const res = await apiClient.post<APISuccess<FCRCalculatorResult>>(
    "/calculators/fcr",
    { total_feed_kg, total_live_weight_kg }
  );
  return res.data.data;
}

export async function calculateProfitProjection(body: {
  current_bird_count: number;
  expected_close_weight_kg: number;
  expected_sale_price_per_kg: number;
  total_expenses_so_far_kes: number;
  expected_additional_expenses_kes?: number;
  expected_mortality_pct?: number;
}): Promise<ProfitProjectionResult> {
  const res = await apiClient.post<APISuccess<ProfitProjectionResult>>(
    "/calculators/profit-projection",
    body
  );
  return res.data.data;
}

export async function calculateBreakEven(body: {
  total_expenses_kes: number;
  expected_birds_sold: number;
  expected_avg_weight_kg: number;
}): Promise<BreakEvenResult> {
  const res = await apiClient.post<APISuccess<BreakEvenResult>>(
    "/calculators/break-even",
    body
  );
  return res.data.data;
}

export async function calculateFeedNeeds(body: {
  current_bird_count: number;
  current_avg_weight_kg: number;
  target_weight_kg: number;
  target_fcr?: number;
  days_remaining?: number;
}): Promise<FeedNeedsResult> {
  const res = await apiClient.post<APISuccess<FeedNeedsResult>>(
    "/calculators/feed-needs",
    body
  );
  return res.data.data;
}
