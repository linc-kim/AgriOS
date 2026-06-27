/**
 * FI-06 — Flock P&L Screen
 * /farms/:farmId/flocks/:flockId/finance
 *
 * Shows the pre-computed P&L snapshot for a specific flock.
 * DB-07 Frozen: reads from financial_snapshots, never real-time aggregates.
 *
 * Sections:
 *   1. P&L summary (revenue / expenses / profit / margin)
 *   2. Revenue breakdown by type
 *   3. Expense breakdown by category group
 *   4. Per-bird metrics (cost, revenue, break-even)
 *   5. FCR + feed stats
 *   6. Quick actions (log expense / log revenue)
 */

import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getFlockSnapshot, refreshFlockSnapshot } from "@/api/finance";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { FinancialSnapshot } from "@/types";

function fmtKES(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "—";
  return `KES ${num.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function fmtNum(value: string | number | null | undefined, dp = 2): string {
  if (value === null || value === undefined) return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "—";
  return num.toFixed(dp);
}

function MetricRow({
  label,
  value,
  valueClass = "text-gray-900",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-sm font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide px-4 pt-4 pb-1">
      {title}
    </p>
  );
}

function SnapshotAge({ snapshotAt }: { snapshotAt: string }) {
  const now = new Date();
  const snap = new Date(snapshotAt);
  const diffMins = Math.round((now.getTime() - snap.getTime()) / 60000);

  if (diffMins < 2) return <span className="text-green-600">just now</span>;
  if (diffMins < 60) return <span className="text-gray-400">{diffMins}m ago</span>;
  const diffHrs = Math.round(diffMins / 60);
  if (diffHrs < 24) return <span className="text-gray-400">{diffHrs}h ago</span>;
  return <span className="text-gray-400">{snap.toLocaleDateString()}</span>;
}

export default function FlockPnLScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: snapshot, isLoading, isError } = useQuery({
    queryKey: queryKeys.flockSnapshot(farmId!, flockId!),
    queryFn: () => getFlockSnapshot(farmId!, flockId!),
    enabled: !!farmId && !!flockId,
    staleTime: 1000 * 30, // 30 seconds — snapshot data changes only after mutations
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshFlockSnapshot(farmId!, flockId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.flockSnapshot(farmId!, flockId!) });
      qc.invalidateQueries({ queryKey: queryKeys.financeDashboard(farmId!) });
    },
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !snapshot) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6 gap-3">
        <p className="text-gray-500 text-sm">{t("common.load_error")}</p>
        <button onClick={() => navigate(-1)} className="text-brand-600 text-sm font-medium">
          {t("common.go_back")}
        </button>
      </div>
    );
  }

  const s = snapshot;
  const profitKES = parseFloat(s.gross_profit_kes);
  const isProfitable = s.is_profitable;

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate(-1)} className="text-gray-500">←</button>
            <div>
              <h1 className="text-lg font-bold text-gray-900">{t("finance.flock_pl.title")}</h1>
              <p className="text-xs text-gray-400 mt-0.5">
                {t("finance.flock_pl.snapshot_age")} <SnapshotAge snapshotAt={s.updated_at} />
                {" · "}
                <button
                  onClick={() => refreshMutation.mutate()}
                  disabled={refreshMutation.isPending}
                  className="text-brand-600 font-medium"
                >
                  {refreshMutation.isPending ? t("common.loading") : t("finance.flock_pl.refresh")}
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* P&L Hero */}
      <div className={`mx-4 mt-4 rounded-2xl p-5 ${isProfitable ? "bg-brand-600" : "bg-red-600"}`}>
        <p className="text-xs text-white/70 mb-1">{t("finance.flock_pl.gross_profit")}</p>
        <p className="text-3xl font-bold text-white">
          {profitKES >= 0 ? "+" : ""}{fmtKES(s.gross_profit_kes)}
        </p>
        {s.gross_margin_pct && (
          <p className="text-sm text-white/80 mt-1">
            {parseFloat(s.gross_margin_pct).toFixed(1)}% margin
          </p>
        )}
        <div className="flex gap-4 mt-4 pt-4 border-t border-white/20">
          <div>
            <p className="text-xs text-white/60">{t("finance.dashboard.revenue")}</p>
            <p className="text-sm font-semibold text-white">{fmtKES(s.total_revenue_kes)}</p>
          </div>
          <div>
            <p className="text-xs text-white/60">{t("finance.dashboard.expenses")}</p>
            <p className="text-sm font-semibold text-white">{fmtKES(s.total_expenses_kes)}</p>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3 px-4 mt-3">
        <button
          onClick={() => navigate(`/farms/${farmId}/expenses/new?flockId=${flockId}`)}
          className="bg-red-50 border border-red-100 rounded-xl p-3 text-left active:scale-95 transition-transform"
        >
          <p className="text-sm font-semibold text-red-700">📉 {t("finance.flock_pl.log_expense")}</p>
        </button>
        <button
          onClick={() => navigate(`/farms/${farmId}/revenue/new?flockId=${flockId}`)}
          className="bg-brand-50 border border-brand-100 rounded-xl p-3 text-left active:scale-95 transition-transform"
        >
          <p className="text-sm font-semibold text-brand-700">📈 {t("finance.flock_pl.log_revenue")}</p>
        </button>
      </div>

      {/* Revenue breakdown */}
      <SectionHeader title={t("finance.flock_pl.revenue_breakdown")} />
      <div className="bg-white mx-4 rounded-2xl shadow-sm border border-gray-100 px-4">
        <MetricRow label="🥚 Eggs" value={fmtKES(s.revenue_eggs_kes)} />
        <MetricRow label="🐔 Birds" value={fmtKES(s.revenue_birds_kes)} />
        <MetricRow label="🌿 Manure" value={fmtKES(s.revenue_manure_kes)} />
        <MetricRow label="💰 Other" value={fmtKES(s.revenue_other_kes)} />
      </div>

      {/* Expense breakdown */}
      <SectionHeader title={t("finance.flock_pl.expense_breakdown")} />
      <div className="bg-white mx-4 rounded-2xl shadow-sm border border-gray-100 px-4">
        <MetricRow label={`🌾 ${t("finance.categories.feed")}`} value={fmtKES(s.feed_cost_kes)}
          valueClass={s.feed_cost_pct ? `text-gray-900` : "text-gray-900"} />
        {s.feed_cost_pct && (
          <div className="pb-1 -mt-1">
            <div className="w-full bg-gray-100 rounded-full h-1.5">
              <div
                className="bg-green-500 h-1.5 rounded-full"
                style={{ width: `${Math.min(parseFloat(s.feed_cost_pct), 100)}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              {parseFloat(s.feed_cost_pct).toFixed(1)}% {t("finance.flock_pl.of_expenses")}
            </p>
          </div>
        )}
        <MetricRow label={`🐥 ${t("finance.categories.doc")}`} value={fmtKES(s.doc_cost_kes)} />
        <MetricRow label={`🩺 ${t("finance.categories.vet")}`} value={fmtKES(s.vet_health_cost_kes)} />
        <MetricRow label={`👷 ${t("finance.categories.labour")}`} value={fmtKES(s.labour_cost_kes)} />
        <MetricRow label={`📦 ${t("finance.categories.other")}`} value={fmtKES(s.other_cost_kes)} />
      </div>

      {/* Per-bird metrics */}
      <SectionHeader title={t("finance.flock_pl.per_bird_metrics")} />
      <div className="bg-white mx-4 rounded-2xl shadow-sm border border-gray-100 px-4">
        <MetricRow
          label={t("finance.flock_pl.cost_per_bird")}
          value={fmtKES(s.cost_per_bird_kes)}
        />
        <MetricRow
          label={t("finance.flock_pl.revenue_per_bird")}
          value={fmtKES(s.revenue_per_bird_kes)}
        />
        <MetricRow
          label={t("finance.flock_pl.break_even_per_bird")}
          value={fmtKES(s.break_even_price_kes)}
          valueClass={
            s.break_even_price_kes && s.revenue_per_bird_kes
              ? parseFloat(s.revenue_per_bird_kes) >= parseFloat(s.break_even_price_kes)
                ? "text-brand-600"
                : "text-red-600"
              : "text-gray-900"
          }
        />
        {s.birds_sold_snapshot != null && (
          <MetricRow
            label={t("finance.flock_pl.birds_sold")}
            value={s.birds_sold_snapshot.toLocaleString()}
          />
        )}
      </div>

      {/* FCR */}
      {(s.fcr_computed || s.total_feed_kg) && (
        <>
          <SectionHeader title={t("finance.flock_pl.fcr_feed")} />
          <div className="bg-white mx-4 rounded-2xl shadow-sm border border-gray-100 px-4">
            <MetricRow
              label={t("finance.flock_pl.total_feed_kg")}
              value={`${fmtNum(s.total_feed_kg, 0)} kg`}
            />
            {s.fcr_computed && (
              <MetricRow
                label={t("finance.flock_pl.fcr")}
                value={fmtNum(s.fcr_computed, 3)}
                valueClass={
                  parseFloat(s.fcr_computed) < 2.1
                    ? "text-brand-600"
                    : parseFloat(s.fcr_computed) < 2.5
                    ? "text-amber-600"
                    : "text-red-600"
                }
              />
            )}
          </div>
        </>
      )}

      {/* Calculators link */}
      <div className="px-4 mt-4">
        <button
          onClick={() => navigate(`/farms/${farmId}/finance/calculators`)}
          className="w-full bg-white border border-gray-100 rounded-2xl p-4 text-left shadow-sm active:scale-95 transition-transform"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-gray-800">🧮 {t("finance.calculators.title")}</p>
              <p className="text-xs text-gray-400 mt-0.5">{t("finance.calculators.subtitle")}</p>
            </div>
            <span className="text-gray-300">→</span>
          </div>
        </button>
      </div>
    </div>
  );
}
