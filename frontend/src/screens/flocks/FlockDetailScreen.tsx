/**
 * AGRIOS — Screen FL-02: Flock Detail
 * Shows flock info + operational metrics (FCR, survival rate, mortality).
 * Entry point for daily log, weighin, production, and feed actions.
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ClipboardList,
  Scale,
  Egg,
  ShoppingCart,
  XCircle,
} from "lucide-react";
import { getFlock } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import { useAuthStore } from "@/stores/authStore";
import type { FlockDetail } from "@/types";

const STATUS_BADGE: Record<string, string> = {
  active: "bg-brand-100 text-brand-700",
  sold: "bg-blue-100 text-blue-700",
  closed: "bg-gray-100 text-gray-600",
  culled: "bg-red-100 text-red-700",
};

function MetricCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className={`rounded-xl p-4 ${accent ? "bg-brand-600" : "bg-white border border-gray-100"}`}>
      <div className={`text-xs font-medium mb-1 ${accent ? "text-brand-100" : "text-gray-500"}`}>
        {label}
      </div>
      <div className={`text-2xl font-bold ${accent ? "text-white" : "text-gray-900"}`}>
        {value}
      </div>
      {sub && (
        <div className={`text-xs mt-0.5 ${accent ? "text-brand-200" : "text-gray-400"}`}>
          {sub}
        </div>
      )}
    </div>
  );
}

export default function FlockDetailScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const { data: flock, isLoading, error } = useQuery<FlockDetail>({
    queryKey: queryKeys.flock(farmId!, flockId!),
    queryFn: () => getFlock(farmId!, flockId!),
    enabled: !!farmId && !!flockId,
  });

  const canOperate = user?.user_roles?.some(
    (r) =>
      r.farm_id === farmId &&
      ["farm_owner", "farm_manager", "farm_worker"].includes(r.role.name),
  ) ?? false;

  const canManage = user?.user_roles?.some(
    (r) =>
      r.farm_id === farmId &&
      ["farm_owner", "farm_manager"].includes(r.role.name),
  ) ?? false;

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !flock) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-6">
        <p className="text-gray-500 mb-4">{t("common.load_error")}</p>
        <button onClick={() => navigate(-1)} className="text-brand-600 font-semibold">
          {t("common.go_back")}
        </button>
      </div>
    );
  }

  const m = flock.metrics;
  const isActive = flock.status === "active";

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 pt-12 pb-4">
        <div className="flex items-center gap-3 mb-3">
          <button
            onClick={() => navigate(-1)}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center text-gray-600"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-gray-900 truncate">{flock.name}</h1>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${STATUS_BADGE[flock.status]}`}>
                {t(`flock.status.${flock.status}`)}
              </span>
            </div>
            {flock.breed && (
              <p className="text-sm text-gray-500 mt-0.5">{flock.breed}</p>
            )}
          </div>
        </div>

        {/* Placement info */}
        <div className="grid grid-cols-3 gap-2 mt-3">
          <div className="text-center">
            <div className="text-lg font-bold text-gray-900">{flock.initial_count.toLocaleString()}</div>
            <div className="text-xs text-gray-400">{t("flock.detail.initial")}</div>
          </div>
          <div className="text-center border-x border-gray-100">
            <div className="text-lg font-bold text-gray-900">{m.current_count.toLocaleString()}</div>
            <div className="text-xs text-gray-400">{t("flock.detail.current")}</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-gray-900">{m.days_alive}</div>
            <div className="text-xs text-gray-400">{t("flock.detail.days")}</div>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="px-4 py-4 grid grid-cols-2 gap-3">
        <MetricCard
          label={t("flock.metrics.survival_rate")}
          value={`${m.survival_rate.toFixed(1)}%`}
          sub={t("flock.metrics.mortality_sub", { count: m.total_mortality })}
          accent
        />
        <MetricCard
          label={t("flock.metrics.fcr")}
          value={m.fcr ? Number(m.fcr).toFixed(3) : "—"}
          sub={t("flock.metrics.fcr_sub")}
        />
        <MetricCard
          label={t("flock.metrics.avg_weight")}
          value={m.latest_avg_weight_kg ? `${Number(m.latest_avg_weight_kg).toFixed(3)} kg` : "—"}
          sub={t("flock.metrics.biomass_sub", {
            kg: m.total_biomass_kg ? Number(m.total_biomass_kg).toFixed(0) : "—",
          })}
        />
        <MetricCard
          label={t("flock.metrics.total_feed")}
          value={`${Number(m.total_feed_kg).toFixed(1)} kg`}
          sub={t("flock.metrics.feed_sub")}
        />
        {m.total_eggs_collected !== null && (
          <MetricCard
            label={t("flock.metrics.eggs")}
            value={m.total_eggs_collected.toLocaleString()}
            sub={
              m.hen_day_production !== null
                ? t("flock.metrics.hdp_sub", { pct: m.hen_day_production.toFixed(1) })
                : undefined
            }
          />
        )}
      </div>

      {/* Actions */}
      {isActive && canOperate && (
        <div className="px-4 pb-2">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-1">
            {t("flock.detail.actions")}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => navigate(`/farms/${farmId}/flocks/${flockId}/log`)}
              className="
                bg-white rounded-xl border border-gray-100 shadow-sm
                flex items-center gap-3 px-4 py-3
                active:scale-[0.97] transition-transform
              "
            >
              <div className="w-9 h-9 rounded-lg bg-brand-50 flex items-center justify-center">
                <ClipboardList className="w-4 h-4 text-brand-600" />
              </div>
              <span className="text-sm font-semibold text-gray-800">
                {t("flock.detail.action_log")}
              </span>
            </button>

            <button
              onClick={() => navigate(`/farms/${farmId}/flocks/${flockId}/weighin`)}
              className="
                bg-white rounded-xl border border-gray-100 shadow-sm
                flex items-center gap-3 px-4 py-3
                active:scale-[0.97] transition-transform
              "
            >
              <div className="w-9 h-9 rounded-lg bg-navy-50 flex items-center justify-center">
                <Scale className="w-4 h-4 text-navy-600" />
              </div>
              <span className="text-sm font-semibold text-gray-800">
                {t("flock.detail.action_weighin")}
              </span>
            </button>

            <button
              onClick={() => navigate(`/farms/${farmId}/flocks/${flockId}/production`)}
              className="
                bg-white rounded-xl border border-gray-100 shadow-sm
                flex items-center gap-3 px-4 py-3
                active:scale-[0.97] transition-transform
              "
            >
              <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                <Egg className="w-4 h-4 text-amber-600" />
              </div>
              <span className="text-sm font-semibold text-gray-800">
                {t("flock.detail.action_production")}
              </span>
            </button>

            <button
              onClick={() => navigate(`/farms/${farmId}/feed-purchases/new`, {
                state: { flockId },
              })}
              className="
                bg-white rounded-xl border border-gray-100 shadow-sm
                flex items-center gap-3 px-4 py-3
                active:scale-[0.97] transition-transform
              "
            >
              <div className="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center">
                <ShoppingCart className="w-4 h-4 text-green-600" />
              </div>
              <span className="text-sm font-semibold text-gray-800">
                {t("flock.detail.action_feed")}
              </span>
            </button>
          </div>
        </div>
      )}

      {/* History Links */}
      <div className="px-4 py-3 flex flex-col gap-2">
        <button
          onClick={() => navigate(`/farms/${farmId}/flocks/${flockId}/logs`)}
          className="w-full bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-3 flex items-center justify-between"
        >
          <span className="text-sm font-semibold text-gray-700">{t("flock.detail.view_log_history")}</span>
          <span className="text-brand-600 text-sm">→</span>
        </button>
      </div>

      {/* Close Flock */}
      {isActive && canManage && (
        <div className="px-4 pb-8 mt-auto">
          <button
            onClick={() => navigate(`/farms/${farmId}/flocks/${flockId}/close`)}
            className="
              w-full min-h-[48px] rounded-xl border border-red-200 text-red-600
              font-semibold text-sm flex items-center justify-center gap-2
              active:scale-[0.97] transition-transform
            "
          >
            <XCircle className="w-4 h-4" />
            {t("flock.detail.close_flock")}
          </button>
        </div>
      )}
    </div>
  );
}
