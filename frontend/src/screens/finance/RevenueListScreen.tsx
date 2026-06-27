/**
 * FI-04 — Revenue List
 * /farms/:farmId/revenue
 *
 * Shows paginated revenue history. Filter by type and date.
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { listRevenue } from "@/api/finance";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { RevenueSummaryItem, RevenueType } from "@/types";

const REVENUE_TYPES: { value: RevenueType | ""; label: string; icon: string }[] = [
  { value: "", label: "All", icon: "📊" },
  { value: "eggs", label: "Eggs", icon: "🥚" },
  { value: "birds", label: "Birds", icon: "🐔" },
  { value: "manure", label: "Manure", icon: "🌿" },
  { value: "other", label: "Other", icon: "💰" },
];

function fmtKES(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "KES 0";
  return `KES ${num.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function RevenueRow({ item }: { item: RevenueSummaryItem }) {
  const typeConfig: Record<string, { icon: string; color: string }> = {
    eggs: { icon: "🥚", color: "bg-yellow-50" },
    birds: { icon: "🐔", color: "bg-orange-50" },
    manure: { icon: "🌿", color: "bg-green-50" },
    other: { icon: "💰", color: "bg-blue-50" },
  };
  const { icon, color } = typeConfig[item.revenue_type] ?? { icon: "💰", color: "bg-gray-50" };

  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-50 last:border-0 px-4">
      <div className="flex items-center gap-3">
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-sm flex-shrink-0 ${color}`}>
          {icon}
        </div>
        <div>
          <p className="text-sm font-medium text-gray-900 capitalize">{item.revenue_type}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {item.quantity ? `${item.quantity} ${item.unit ?? ""}` : ""}
            {item.buyer_name ? ` · ${item.buyer_name}` : ""}
            {" · "}{item.revenue_date}
          </p>
        </div>
      </div>
      <p className="text-sm font-semibold text-brand-600 flex-shrink-0 ml-2">
        +{fmtKES(item.amount)}
      </p>
    </div>
  );
}

export default function RevenueListScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<RevenueType | "">("");

  const { data, isLoading, isError } = useQuery({
    queryKey: [...queryKeys.revenue(farmId!), { page, typeFilter }],
    queryFn: () =>
      listRevenue(farmId!, {
        page,
        page_size: 20,
        revenue_type: typeFilter || undefined,
      }),
    enabled: !!farmId,
  });

  const totalPages = data ? Math.ceil(data.total / 20) : 0;

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate(-1)} className="text-gray-500">←</button>
            <div>
              <h1 className="text-lg font-bold text-gray-900">{t("finance.revenue.title")}</h1>
              {data && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {t("finance.revenue.total_label")} {fmtKES(data.total_kes)}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => navigate(`/farms/${farmId}/revenue/new`)}
            className="bg-brand-600 text-white text-sm font-semibold px-4 py-2 rounded-xl"
          >
            + {t("finance.revenue.add")}
          </button>
        </div>

        {/* Type filter chips */}
        <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
          {REVENUE_TYPES.map((rt) => (
            <button
              key={rt.value}
              onClick={() => { setTypeFilter(rt.value); setPage(1); }}
              className={`flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                typeFilter === rt.value
                  ? "bg-brand-600 text-white border-brand-600"
                  : "bg-gray-50 text-gray-600 border-gray-200"
              }`}
            >
              {rt.icon} {rt.label}
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
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <p className="text-sm text-gray-500">{t("common.load_error")}</p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center px-6">
          <span className="text-5xl mb-4">📈</span>
          <p className="text-gray-800 font-semibold">{t("finance.revenue.empty_title")}</p>
          <p className="text-gray-400 text-sm mt-1">{t("finance.revenue.empty_body")}</p>
          <button
            onClick={() => navigate(`/farms/${farmId}/revenue/new`)}
            className="mt-4 bg-brand-600 text-white rounded-xl px-6 py-3 text-sm font-semibold"
          >
            {t("finance.revenue.log_first")}
          </button>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          {/* Summary bar */}
          <div className="bg-white mx-4 mt-4 rounded-xl p-3 flex items-center justify-between shadow-sm border border-gray-100">
            <p className="text-xs text-gray-500">
              {t("finance.revenue.showing_count", { count: data.total })}
            </p>
            <p className="text-sm font-bold text-brand-600">{fmtKES(data.total_kes)}</p>
          </div>

          <div className="bg-white mx-4 mt-3 rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            {data.items.map((item) => (
              <RevenueRow key={item.id} item={item} />
            ))}
          </div>

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
