/**
 * FI-02 — Expense List
 * /farms/:farmId/expenses
 *
 * Shows paginated expense history with totals.
 * Filter by flock, category, date range.
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { listExpenses } from "@/api/finance";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { ExpenseSummaryItem } from "@/types";

function fmtKES(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "KES 0";
  return `KES ${num.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const PAYMENT_LABELS: Record<string, string> = {
  cash: "Cash",
  mpesa: "M-Pesa",
  bank_transfer: "Bank",
  credit: "Credit",
};

function ExpenseRow({ item }: { item: ExpenseSummaryItem }) {
  const dotColor = item.category_color ?? "#6b7280";

  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-50 last:border-0 px-4">
      <div className="flex items-center gap-3">
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center text-sm flex-shrink-0"
          style={{ backgroundColor: `${dotColor}18` }}
        >
          <span>{item.category_icon ?? "📦"}</span>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-900 truncate max-w-[180px]">
            {item.description}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            {item.category_name}
            {item.payment_method ? ` · ${PAYMENT_LABELS[item.payment_method] ?? item.payment_method}` : ""}
            {" · "}{item.expense_date}
          </p>
        </div>
      </div>
      <p className="text-sm font-semibold text-red-600 flex-shrink-0 ml-2">
        -{fmtKES(item.amount)}
      </p>
    </div>
  );
}

export default function ExpenseListScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: [...queryKeys.expenses(farmId!), { page }],
    queryFn: () => listExpenses(farmId!, { page, page_size: 20 }),
    enabled: !!farmId,
  });

  const totalPages = data ? Math.ceil(data.total / 20) : 0;

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="text-gray-500 hover:text-gray-700"
            >
              ←
            </button>
            <div>
              <h1 className="text-lg font-bold text-gray-900">{t("finance.expenses.title")}</h1>
              {data && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {t("finance.expenses.total_label")} {fmtKES(data.total_kes)}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => navigate(`/farms/${farmId}/expenses/new`)}
            className="bg-brand-600 text-white text-sm font-semibold px-4 py-2 rounded-xl"
          >
            + {t("finance.expenses.add")}
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <p className="text-sm text-gray-500">{t("common.load_error")}</p>
          <button onClick={() => navigate(-1)} className="text-brand-600 text-sm font-medium">
            {t("common.go_back")}
          </button>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center px-6">
          <span className="text-5xl mb-4">🧾</span>
          <p className="text-gray-800 font-semibold">{t("finance.expenses.empty_title")}</p>
          <p className="text-gray-400 text-sm mt-1">{t("finance.expenses.empty_body")}</p>
          <button
            onClick={() => navigate(`/farms/${farmId}/expenses/new`)}
            className="mt-4 bg-brand-600 text-white rounded-xl px-6 py-3 text-sm font-semibold"
          >
            {t("finance.expenses.log_first")}
          </button>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          {/* Total summary bar */}
          <div className="bg-white mx-4 mt-4 rounded-xl p-3 flex items-center justify-between shadow-sm border border-gray-100">
            <p className="text-xs text-gray-500">
              {t("finance.expenses.showing_count", { count: data.total })}
            </p>
            <p className="text-sm font-bold text-red-600">{fmtKES(data.total_kes)}</p>
          </div>

          {/* List */}
          <div className="bg-white mx-4 mt-3 rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            {data.items.map((item) => (
              <ExpenseRow key={item.id} item={item} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-4 pb-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="text-sm text-brand-600 font-medium disabled:text-gray-300"
              >
                ← {t("common.prev")}
              </button>
              <span className="text-xs text-gray-400">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="text-sm text-brand-600 font-medium disabled:text-gray-300"
              >
                {t("common.next")} →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
