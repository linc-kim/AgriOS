/**
 * FI-01 — Finance Dashboard
 * Entry point from Finance tab (/farms/:farmId/finance)
 *
 * Zones:
 *   1. P&L Summary card (revenue / expenses / profit)
 *   2. Cost breakdown bar (feed / DOC / vet / labour / other)
 *   3. Flock P&L cards (from pre-computed snapshots — DB-07 Frozen)
 *   4. Recent transactions (last 5 expenses + revenue)
 *   5. Quick action buttons
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getFinanceDashboard } from "@/api/finance";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { FlockPnLCard, ExpenseSummaryItem, RevenueSummaryItem } from "@/types";
import apiClient from "@/api/client";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtKES(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "KES 0";
  return `KES ${num.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function profitColor(isProfit: boolean): string {
  return isProfit ? "text-brand-600" : "text-red-600";
}

function marginBadge(pct: string | null, isProfit: boolean): string {
  if (!pct) return "";
  const p = parseFloat(pct);
  return isProfit
    ? `+${p.toFixed(1)}% margin`
    : `${p.toFixed(1)}% margin`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PnLCard({
  revenue,
  expenses,
  profit,
  marginPct,
  isProfit,
}: {
  revenue: string;
  expenses: string;
  profit: string;
  marginPct: string | null;
  isProfit: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <p className="text-xs text-gray-500 mb-3">{t("finance.dashboard.period_label", "All flocks")}</p>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <p className="text-xs text-gray-400">{t("finance.dashboard.revenue")}</p>
          <p className="text-sm font-semibold text-gray-900 mt-0.5">{fmtKES(revenue)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">{t("finance.dashboard.expenses")}</p>
          <p className="text-sm font-semibold text-gray-900 mt-0.5">{fmtKES(expenses)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">{t("finance.dashboard.profit")}</p>
          <p className={`text-sm font-bold mt-0.5 ${profitColor(isProfit)}`}>
            {fmtKES(profit)}
          </p>
        </div>
      </div>
      {marginPct && (
        <div className="mt-3 pt-3 border-t border-gray-50">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            isProfit
              ? "bg-brand-50 text-brand-700"
              : "bg-red-50 text-red-700"
          }`}>
            {marginBadge(marginPct, isProfit)}
          </span>
        </div>
      )}
    </div>
  );
}

function CostBar({
  feed,
  doc,
  vet,
  labour,
  other,
  total,
}: {
  feed: string; doc: string; vet: string; labour: string; other: string; total: string;
}) {
  const { t } = useTranslation();
  const tot = parseFloat(total) || 1;

  const segments = [
    { key: "feed", label: t("finance.categories.feed"), value: parseFloat(feed) || 0, color: "bg-green-500" },
    { key: "doc", label: t("finance.categories.doc"), value: parseFloat(doc) || 0, color: "bg-yellow-400" },
    { key: "vet", label: t("finance.categories.vet"), value: parseFloat(vet) || 0, color: "bg-blue-500" },
    { key: "labour", label: t("finance.categories.labour"), value: parseFloat(labour) || 0, color: "bg-purple-500" },
    { key: "other", label: t("finance.categories.other"), value: parseFloat(other) || 0, color: "bg-gray-300" },
  ].filter((s) => s.value > 0);

  if (segments.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <p className="text-xs font-medium text-gray-500 mb-3">{t("finance.dashboard.cost_breakdown")}</p>
      {/* Stacked bar */}
      <div className="flex rounded-full overflow-hidden h-3 bg-gray-100 mb-3">
        {segments.map((s) => (
          <div
            key={s.key}
            className={`${s.color} transition-all`}
            style={{ width: `${(s.value / tot) * 100}%` }}
          />
        ))}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {segments.map((s) => (
          <div key={s.key} className="flex items-center gap-1">
            <div className={`w-2 h-2 rounded-full ${s.color}`} />
            <span className="text-xs text-gray-500">
              {s.label} {((s.value / tot) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FlockCard({ card, farmId }: { card: FlockPnLCard; farmId: string }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const grossProfit = parseFloat(card.gross_profit_kes);
  const isProfit = card.is_profitable;

  return (
    <button
      onClick={() => navigate(`/farms/${farmId}/flocks/${card.flock_id}/finance`)}
      className="w-full text-left bg-white rounded-xl p-4 border border-gray-100 shadow-sm active:scale-95 transition-transform"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-gray-900 truncate max-w-[160px]">
            {card.flock_name}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            {card.flock_status === "active"
              ? t("finance.flock.day_n", { n: card.days_alive ?? "—" })
              : t(`flock.status.${card.flock_status}`, card.flock_status)}
          </p>
        </div>
        <div className="text-right">
          <p className={`text-sm font-bold ${profitColor(isProfit)}`}>
            {grossProfit >= 0 ? "+" : ""}{fmtKES(card.gross_profit_kes)}
          </p>
          {card.gross_margin_pct && (
            <p className="text-xs text-gray-400 mt-0.5">
              {parseFloat(card.gross_margin_pct).toFixed(1)}%
            </p>
          )}
        </div>
      </div>
      <div className="flex gap-3 mt-3 pt-3 border-t border-gray-50">
        <div>
          <p className="text-xs text-gray-400">{t("finance.dashboard.revenue")}</p>
          <p className="text-xs font-medium text-gray-700">{fmtKES(card.total_revenue_kes)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">{t("finance.dashboard.expenses")}</p>
          <p className="text-xs font-medium text-gray-700">{fmtKES(card.total_expenses_kes)}</p>
        </div>
      </div>
    </button>
  );
}

function RecentExpenseRow({ item }: { item: ExpenseSummaryItem }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2.5">
        <span className="text-base">{item.category_icon ?? "📦"}</span>
        <div>
          <p className="text-sm text-gray-800 font-medium truncate max-w-[160px]">
            {item.description}
          </p>
          <p className="text-xs text-gray-400">{item.category_name} · {item.expense_date}</p>
        </div>
      </div>
      <p className="text-sm font-semibold text-red-600">
        -{fmtKES(item.amount)}
      </p>
    </div>
  );
}

function RecentRevenueRow({ item }: { item: RevenueSummaryItem }) {
  const typeIcon: Record<string, string> = {
    eggs: "🥚",
    birds: "🐔",
    manure: "🌿",
    other: "💰",
  };

  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2.5">
        <span className="text-base">{typeIcon[item.revenue_type] ?? "💰"}</span>
        <div>
          <p className="text-sm text-gray-800 font-medium capitalize">
            {item.revenue_type} {item.quantity ? `· ${item.quantity} ${item.unit ?? ""}` : ""}
          </p>
          <p className="text-xs text-gray-400">{item.buyer_name ? `${item.buyer_name} · ` : ""}{item.revenue_date}</p>
        </div>
      </div>
      <p className="text-sm font-semibold text-brand-600">
        +{fmtKES(item.amount)}
      </p>
    </div>
  );
}

// ── Export Data Card ──────────────────────────────────────────────────────────

function ExportDataCard({ farmId }: { farmId: string }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState<"pdf" | "excel" | "csv" | null>(null);

  async function triggerDownload(format: "pdf" | "excel" | "csv") {
    setLoading(format);
    try {
      const mimeTypes: Record<string, string> = {
        pdf: "application/pdf",
        excel: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        csv: "text/csv",
      };
      const extensions: Record<string, string> = {
        pdf: "pdf",
        excel: "xlsx",
        csv: "csv",
      };

      // Use apiClient so the Axios interceptor injects the JWT automatically
      const response = await apiClient.get(
        `/farms/${farmId}/export/${format}`,
        { responseType: "blob" },
      );

      const blob = new Blob([response.data], { type: mimeTypes[format] });
      const url = URL.createObjectURL(blob);
      const ts = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const a = document.createElement("a");
      a.href = url;
      a.download = `Greena_Report_${ts}.${extensions[format]}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export error", err);
    } finally {
      setLoading(null);
    }
  }

  const buttons: { key: "pdf" | "excel" | "csv"; icon: string; label: string; color: string }[] = [
    { key: "pdf",   icon: "📄", label: "PDF",   color: "bg-red-50 text-red-700 border-red-100" },
    { key: "excel", icon: "📊", label: "Excel", color: "bg-green-50 text-green-700 border-green-100" },
    { key: "csv",   icon: "📋", label: "CSV",   color: "bg-blue-50 text-blue-700 border-blue-100" },
  ];

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">⬇️</span>
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {t("finance.export.title", "Download Your Data")}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            {t("finance.export.subtitle", "Your data belongs to you — take it anywhere")}
          </p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {buttons.map(({ key, icon, label, color }) => (
          <button
            key={key}
            onClick={() => triggerDownload(key)}
            disabled={loading !== null}
            className={`flex flex-col items-center justify-center gap-1 py-2.5 rounded-xl border text-xs font-semibold
              ${color} active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {loading === key ? (
              <span className="animate-spin text-base">⏳</span>
            ) : (
              <span className="text-base">{icon}</span>
            )}
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function FinanceDashboardScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.financeDashboard(farmId!),
    queryFn: () => getFinanceDashboard(farmId!),
    enabled: !!farmId,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6 gap-3">
        <p className="text-gray-500 text-sm">{t("common.load_error")}</p>
        <button
          onClick={() => navigate(-1)}
          className="text-brand-600 text-sm font-medium"
        >
          {t("common.go_back")}
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-5 border-b border-gray-100">
        <h1 className="text-xl font-bold text-gray-900">{t("finance.dashboard.title")}</h1>
        <p className="text-sm text-gray-400 mt-0.5">{t("finance.dashboard.subtitle")}</p>
      </div>

      <div className="px-4 py-4 space-y-3">
        {/* Zone 1 — P&L Summary */}
        <PnLCard
          revenue={data.total_revenue_kes}
          expenses={data.total_expenses_kes}
          profit={data.gross_profit_kes}
          marginPct={data.gross_margin_pct}
          isProfit={data.is_profitable}
        />

        {/* Zone 2 — Cost Breakdown Bar */}
        {parseFloat(data.total_expenses_kes) > 0 && (
          <CostBar
            feed={data.feed_cost_kes}
            doc={data.doc_cost_kes}
            vet={data.vet_health_cost_kes}
            labour={data.labour_cost_kes}
            other={data.other_cost_kes}
            total={data.total_expenses_kes}
          />
        )}

        {/* Zone 3 — Quick Actions */}
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => navigate(`/farms/${farmId}/expenses/new`)}
            className="bg-red-50 rounded-xl p-3.5 text-left active:scale-95 transition-transform"
          >
            <span className="text-xl">📉</span>
            <p className="text-sm font-semibold text-gray-800 mt-1">{t("finance.dashboard.action_expense")}</p>
            <p className="text-xs text-gray-400">{t("finance.dashboard.action_expense_sub")}</p>
          </button>
          <button
            onClick={() => navigate(`/farms/${farmId}/revenue/new`)}
            className="bg-brand-50 rounded-xl p-3.5 text-left active:scale-95 transition-transform"
          >
            <span className="text-xl">📈</span>
            <p className="text-sm font-semibold text-gray-800 mt-1">{t("finance.dashboard.action_revenue")}</p>
            <p className="text-xs text-gray-400">{t("finance.dashboard.action_revenue_sub")}</p>
          </button>
          <button
            onClick={() => navigate(`/farms/${farmId}/expenses`)}
            className="bg-white border border-gray-100 rounded-xl p-3.5 text-left active:scale-95 transition-transform"
          >
            <span className="text-xl">🧾</span>
            <p className="text-sm font-semibold text-gray-800 mt-1">{t("finance.dashboard.action_expenses")}</p>
            <p className="text-xs text-gray-400">{t("finance.dashboard.action_expenses_sub")}</p>
          </button>
          <button
            onClick={() => navigate(`/farms/${farmId}/finance/calculators`)}
            className="bg-white border border-gray-100 rounded-xl p-3.5 text-left active:scale-95 transition-transform"
          >
            <span className="text-xl">🧮</span>
            <p className="text-sm font-semibold text-gray-800 mt-1">{t("finance.dashboard.action_calculators")}</p>
            <p className="text-xs text-gray-400">{t("finance.dashboard.action_calculators_sub")}</p>
          </button>
        </div>

        {/* Zone 4 — Flock P&L Cards */}
        {data.flock_cards.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-gray-700">{t("finance.dashboard.flock_pl")}</p>
            </div>
            <div className="space-y-2">
              {data.flock_cards.map((card) => (
                <FlockCard key={card.flock_id} card={card} farmId={farmId!} />
              ))}
            </div>
          </div>
        )}

        {/* Zone 5 — Export Data */}
        <ExportDataCard farmId={farmId!} />

        {/* Zone 6 — Recent Transactions */}
        {(data.recent_expenses.length > 0 || data.recent_revenue.length > 0) && (
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-gray-700">{t("finance.dashboard.recent_transactions")}</p>
              <button
                onClick={() => navigate(`/farms/${farmId}/expenses`)}
                className="text-xs text-brand-600 font-medium"
              >
                {t("common.view_all")}
              </button>
            </div>
            {data.recent_revenue.slice(0, 3).map((r) => (
              <RecentRevenueRow key={r.id} item={r} />
            ))}
            {data.recent_expenses.slice(0, 3).map((e) => (
              <RecentExpenseRow key={e.id} item={e} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {data.flock_cards.length === 0 &&
          data.recent_expenses.length === 0 &&
          data.recent_revenue.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <span className="text-5xl mb-4">💰</span>
            <p className="text-gray-800 font-semibold">{t("finance.dashboard.empty_title")}</p>
            <p className="text-gray-400 text-sm mt-1 max-w-xs">{t("finance.dashboard.empty_body")}</p>
            <button
              onClick={() => navigate(`/farms/${farmId}/expenses/new`)}
              className="mt-4 bg-brand-600 text-white rounded-xl px-6 py-3 text-sm font-semibold"
            >
              {t("finance.dashboard.log_first_expense")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
