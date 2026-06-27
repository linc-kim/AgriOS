/**
 * A-01 — Admin Overview Screen
 * /admin
 * Platform KPIs: users, farms, AI cost, active alerts.
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { adminAPI } from "@/api/admin";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { PlatformStats } from "@/types";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function AdminOverviewScreen() {
  const { t } = useTranslation();

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.adminStats(),
    queryFn: adminAPI.getStats,
    staleTime: 1000 * 60 * 5, // 5 min
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8 text-center text-gray-500 text-sm">{t("common.error_loading")}</div>
    );
  }

  const s: PlatformStats = data;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.overview.title")}</h1>
      <p className="text-sm text-gray-400 mb-8">{t("admin.overview.subtitle")}</p>

      {/* User + Farm row */}
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">
        {t("admin.overview.section_platform")}
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label={t("admin.overview.total_users")} value={s.total_users.toLocaleString()} sub={t("admin.overview.active_30d", { n: s.active_users_30d })} />
        <StatCard label={t("admin.overview.total_farms")} value={s.total_farms.toLocaleString()} sub={t("admin.overview.active_30d", { n: s.active_farms_30d })} />
        <StatCard label={t("admin.overview.total_flocks")} value={s.total_flocks.toLocaleString()} sub={t("admin.overview.active_count", { n: s.active_flocks })} />
        <StatCard label={t("admin.overview.active_alerts")} value={s.total_disease_alerts_active} />
      </div>

      {/* AI + Market row */}
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">
        {t("admin.overview.section_ai")}
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label={t("admin.overview.ai_queries_30d")} value={s.total_ai_queries_30d.toLocaleString()} />
        <StatCard label={t("admin.overview.ai_cost_30d")} value={`$${s.total_ai_cost_usd_30d.toFixed(4)}`} />
        <StatCard label={t("admin.overview.notifications_30d")} value={s.total_notifications_sent_30d.toLocaleString()} />
        <StatCard label={t("admin.overview.market_prices")} value={s.total_market_prices.toLocaleString()} />
      </div>
    </div>
  );
}
