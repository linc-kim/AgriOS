/**
 * A-07 — Admin AI Usage Screen
 * /admin/ai-usage
 * AI usage dashboard — queries, cost, fallback rate, daily breakdown.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { adminAPI } from "@/api/admin";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";

const PERIOD_OPTIONS = [7, 14, 30, 60, 90];

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function AdminAIUsageScreen() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState(30);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.adminAIUsage(period),
    queryFn: () => adminAPI.getAIUsage(period),
  });

  const formatCost = (usd: number) => `$${usd.toFixed(4)}`;
  const formatTokens = (n: number) =>
    n >= 1_000_000 ? `${(n / 1_000_000).toFixed(2)}M` : n >= 1_000 ? `${(n / 1_000).toFixed(1)}K` : String(n);

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.ai.title")}</h1>
          <p className="text-sm text-gray-400">{t("admin.ai.subtitle")}</p>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {PERIOD_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                period === d ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : data ? (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard
              label={t("admin.ai.stat_queries")}
              value={data.total_queries.toLocaleString()}
              sub={`${t("admin.ai.unique_users")}: ${data.unique_users}`}
            />
            <StatCard
              label={t("admin.ai.stat_tokens")}
              value={formatTokens(data.total_tokens)}
            />
            <StatCard
              label={t("admin.ai.stat_cost")}
              value={formatCost(data.total_cost_usd)}
              sub={t("admin.ai.period_label", { days: period })}
            />
            <StatCard
              label={t("admin.ai.stat_fallback")}
              value={`${data.fallback_rate_pct.toFixed(1)}%`}
              sub={t("admin.ai.fallback_sub")}
            />
          </div>

          {/* Daily breakdown table */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-50">
              <h2 className="text-sm font-semibold text-gray-900">{t("admin.ai.daily_breakdown")}</h2>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 text-xs uppercase tracking-wide">
                  <th className="text-left px-5 py-3">{t("admin.ai.col_date")}</th>
                  <th className="text-right px-4 py-3">{t("admin.ai.col_queries")}</th>
                  <th className="text-right px-4 py-3">{t("admin.ai.col_tokens")}</th>
                  <th className="text-right px-4 py-3">{t("admin.ai.col_cost")}</th>
                  <th className="text-right px-4 py-3">{t("admin.ai.col_users")}</th>
                </tr>
              </thead>
              <tbody>
                {data.daily_breakdown.length === 0 ? (
                  <tr><td colSpan={5} className="text-center py-10 text-gray-400">{t("admin.ai.no_data")}</td></tr>
                ) : (
                  data.daily_breakdown.map((row) => (
                    <tr key={row.date} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-5 py-3 font-medium text-gray-700">{row.date}</td>
                      <td className="px-4 py-3 text-right text-gray-900">{row.query_count.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-gray-600">{formatTokens(row.total_tokens)}</td>
                      <td className="px-4 py-3 text-right font-medium text-brand-700">{formatCost(row.cost_usd)}</td>
                      <td className="px-4 py-3 text-right text-gray-600">{row.unique_users}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
