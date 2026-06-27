/**
 * FI-07 — Financial Summary / Category Breakdown
 * /farms/:farmId/finance/summary
 *
 * Expense category breakdown with percentage bars.
 * Allows date-range filtering.
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getCategoryBreakdown } from "@/api/finance";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { ExpenseCategoryBreakdown } from "@/types";

function fmtKES(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "KES 0";
  return `KES ${num.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function CategoryRow({ item }: { item: ExpenseCategoryBreakdown }) {
  const pct = item.pct_of_total ? parseFloat(item.pct_of_total) : 0;

  return (
    <div className="py-3 border-b border-gray-50 last:border-0">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-sm"
            style={{
              backgroundColor: item.category_color ? `${item.category_color}20` : "#f3f4f6",
            }}
          >
            {item.category_icon ?? "📦"}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-800">{item.category_name}</p>
            <p className="text-xs text-gray-400">{item.transaction_count} transactions</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-gray-900">{fmtKES(item.total_kes)}</p>
          {pct > 0 && (
            <p className="text-xs text-gray-400">{pct.toFixed(1)}%</p>
          )}
        </div>
      </div>
      {/* Percentage bar */}
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div
          className="h-1.5 rounded-full transition-all"
          style={{
            width: `${Math.min(pct, 100)}%`,
            backgroundColor: item.category_color ?? "#16a34a",
          }}
        />
      </div>
    </div>
  );
}

// Quick date presets
const PRESETS = [
  { label: "All time", value: "" },
  { label: "This month", getValue: () => {
    const now = new Date();
    const from = new Date(now.getFullYear(), now.getMonth(), 1);
    return {
      date_from: from.toISOString().split("T")[0],
      date_to: now.toISOString().split("T")[0],
    };
  }},
  { label: "Last 30 days", getValue: () => {
    const now = new Date();
    const from = new Date(now);
    from.setDate(from.getDate() - 30);
    return {
      date_from: from.toISOString().split("T")[0],
      date_to: now.toISOString().split("T")[0],
    };
  }},
  { label: "Last 90 days", getValue: () => {
    const now = new Date();
    const from = new Date(now);
    from.setDate(from.getDate() - 90);
    return {
      date_from: from.toISOString().split("T")[0],
      date_to: now.toISOString().split("T")[0],
    };
  }},
];

export default function FinancialSummaryScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [presetIdx, setPresetIdx] = useState(0);

  const preset = PRESETS[presetIdx];
  const dateParams =
    presetIdx === 0
      ? {}
      : (PRESETS[presetIdx] as { getValue: () => { date_from: string; date_to: string } }).getValue();

  const { data, isLoading, isError } = useQuery({
    queryKey: [...queryKeys.categoryBreakdown(farmId!), presetIdx],
    queryFn: () => getCategoryBreakdown(farmId!, dateParams),
    enabled: !!farmId,
  });

  const grandTotal = data?.reduce(
    (sum, item) => sum + parseFloat(item.total_kes),
    0
  ) ?? 0;

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-500">←</button>
          <h1 className="text-lg font-bold text-gray-900">{t("finance.summary.title")}</h1>
        </div>

        {/* Date presets */}
        <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
          {PRESETS.map((p, idx) => (
            <button
              key={p.label}
              onClick={() => setPresetIdx(idx)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                presetIdx === idx
                  ? "bg-brand-600 text-white border-brand-600"
                  : "bg-gray-50 text-gray-600 border-gray-200"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      )}

      {isError && (
        <div className="flex items-center justify-center py-20">
          <p className="text-sm text-gray-500">{t("common.load_error")}</p>
        </div>
      )}

      {data && data.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center px-6">
          <span className="text-5xl mb-4">📊</span>
          <p className="text-gray-800 font-semibold">{t("finance.summary.empty_title")}</p>
          <p className="text-gray-400 text-sm mt-1">{t("finance.summary.empty_body")}</p>
        </div>
      )}

      {data && data.length > 0 && (
        <>
          {/* Total */}
          <div className="bg-white mx-4 mt-4 rounded-xl p-4 shadow-sm border border-gray-100">
            <p className="text-xs text-gray-400">{t("finance.summary.total_expenses")}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{fmtKES(grandTotal)}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {data.reduce((sum, i) => sum + i.transaction_count, 0)} {t("finance.summary.transactions")}
            </p>
          </div>

          {/* Category breakdown */}
          <div className="bg-white mx-4 mt-3 rounded-2xl shadow-sm border border-gray-100 px-4">
            {data.map((item) => (
              <CategoryRow key={item.category_id} item={item} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
