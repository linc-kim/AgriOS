/**
 * AGRIOS — Screen H-01: Health Dashboard
 * Farm-wide health overview: overdue/upcoming vaccinations + active disease alerts.
 * Entry point from the Health tab in bottom navigation.
 *
 * Requires HEALTH_VACCINATION_VIEW (all roles).
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { getVaccinationSchedule, getFarmAlerts } from "@/api/health";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { VaccinationScheduleItem, DiseaseAlert } from "@/types";

function severityColor(severity: string): string {
  switch (severity) {
    case "critical": return "bg-red-50 border-red-200 text-red-800";
    case "warning":  return "bg-amber-50 border-amber-200 text-amber-800";
    default:         return "bg-blue-50 border-blue-200 text-blue-800";
  }
}

function severityDot(severity: string): string {
  switch (severity) {
    case "critical": return "bg-red-500";
    case "warning":  return "bg-amber-500";
    default:         return "bg-blue-500";
  }
}

function VaccinationRow({ item }: { item: VaccinationScheduleItem }) {
  const { t } = useTranslation();
  const isOverdue = item.is_overdue;
  const isToday = item.days_until_due === 0;

  return (
    <div className={`flex items-center gap-3 px-4 py-3 border-b border-gray-50 last:border-0`}>
      <div className={`
        w-2 h-2 rounded-full flex-shrink-0 mt-0.5
        ${isOverdue ? "bg-red-500" : isToday ? "bg-amber-500" : "bg-brand-500"}
      `} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate">
          {item.next_vaccine_name || item.vaccine_name}
        </p>
        <p className="text-xs text-gray-500 truncate">{item.flock_name}</p>
      </div>
      <div className="text-right flex-shrink-0">
        {isOverdue ? (
          <span className="text-xs font-bold text-red-600">
            {t("health.schedule.overdue_by", { days: Math.abs(item.days_until_due) })}
          </span>
        ) : isToday ? (
          <span className="text-xs font-bold text-amber-600">
            {t("health.schedule.due_today")}
          </span>
        ) : (
          <span className="text-xs text-gray-500">
            {t("health.schedule.due_in", { days: item.days_until_due })}
          </span>
        )}
        <p className="text-xs text-gray-400">
          {new Date(item.next_due_date).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}

export default function HealthDashboardScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const scheduleQuery = useQuery({
    queryKey: queryKeys.healthSchedule(farmId!),
    queryFn: () => getVaccinationSchedule(farmId!),
    enabled: !!farmId,
  });

  const alertsQuery = useQuery({
    queryKey: queryKeys.farmAlerts(farmId!),
    queryFn: () => getFarmAlerts(farmId!, { limit: 5 }),
    enabled: !!farmId,
  });

  const schedule = scheduleQuery.data;
  const alerts = alertsQuery.data ?? [];

  const urgentCount =
    (schedule?.overdue.length ?? 0) + (schedule?.due_today.length ?? 0);

  const isLoading = scheduleQuery.isLoading || alertsQuery.isLoading;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 pt-12 pb-5">
        <h1 className="text-2xl font-bold text-gray-900">
          {t("health.dashboard.title")}
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {t("health.dashboard.subtitle")}
        </p>
      </div>

      <div className="px-4 py-5 space-y-5">

        {/* Disease Alert Banner — only when active alerts exist */}
        {alerts.filter((a: DiseaseAlert) => a.status === "active").length > 0 && (
          <div>
            {alerts
              .filter((a: DiseaseAlert) => a.status === "active")
              .slice(0, 2)
              .map((alert: DiseaseAlert) => (
                <button
                  key={alert.id}
                  onClick={() => navigate(`/farms/${farmId}/health/alerts`)}
                  className={`
                    w-full text-left rounded-2xl border px-4 py-4 mb-2
                    ${severityColor(alert.severity)}
                  `}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-2.5 h-2.5 rounded-full mt-1 flex-shrink-0 ${severityDot(alert.severity)}`} />
                    <div className="flex-1">
                      <p className="text-xs font-bold uppercase tracking-wide opacity-70 mb-0.5">
                        {t(`health.alert.severity.${alert.severity}`)} · {alert.county ?? t("health.alert.national")}
                      </p>
                      <p className="text-sm font-bold leading-snug">{alert.title}</p>
                      {alert.brief_guidance && (
                        <p className="text-xs opacity-80 mt-1 leading-relaxed line-clamp-2">
                          {alert.brief_guidance}
                        </p>
                      )}
                    </div>
                    <span className="text-lg opacity-60 flex-shrink-0">›</span>
                  </div>
                </button>
              ))}
          </div>
        )}

        {/* Vaccination Urgency Card */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-4 py-4 border-b border-gray-50">
            <div>
              <h2 className="text-base font-bold text-gray-900">
                {t("health.schedule.title")}
              </h2>
              {urgentCount > 0 && (
                <p className="text-xs text-red-600 font-medium mt-0.5">
                  {t("health.schedule.urgent_count", { count: urgentCount })}
                </p>
              )}
            </div>
            <button
              onClick={() => navigate(`/farms/${farmId}/health/schedule`)}
              className="text-sm font-semibold text-brand-600 min-h-[44px] px-2"
            >
              {t("common.view_all")} ›
            </button>
          </div>

          {/* Overdue */}
          {schedule && schedule.overdue.length > 0 && (
            <div>
              <div className="px-4 py-2 bg-red-50">
                <p className="text-xs font-bold text-red-700 uppercase tracking-wide">
                  {t("health.schedule.overdue")} ({schedule.overdue.length})
                </p>
              </div>
              {schedule.overdue.map((item) => (
                <VaccinationRow key={item.id} item={item} />
              ))}
            </div>
          )}

          {/* Due Today */}
          {schedule && schedule.due_today.length > 0 && (
            <div>
              <div className="px-4 py-2 bg-amber-50">
                <p className="text-xs font-bold text-amber-700 uppercase tracking-wide">
                  {t("health.schedule.due_today")} ({schedule.due_today.length})
                </p>
              </div>
              {schedule.due_today.map((item) => (
                <VaccinationRow key={item.id} item={item} />
              ))}
            </div>
          )}

          {/* Due This Week */}
          {schedule && schedule.due_this_week.length > 0 && (
            <div>
              <div className="px-4 py-2 bg-gray-50">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">
                  {t("health.schedule.this_week")} ({schedule.due_this_week.length})
                </p>
              </div>
              {schedule.due_this_week.map((item) => (
                <VaccinationRow key={item.id} item={item} />
              ))}
            </div>
          )}

          {/* Empty state */}
          {schedule &&
            schedule.overdue.length === 0 &&
            schedule.due_today.length === 0 &&
            schedule.due_this_week.length === 0 && (
              <div className="px-4 py-8 text-center">
                <p className="text-2xl mb-2">✅</p>
                <p className="text-sm font-semibold text-gray-700">
                  {t("health.schedule.all_clear")}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {t("health.schedule.all_clear_sub")}
                </p>
              </div>
            )}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => navigate(`/farms/${farmId}/health/schedule`)}
            className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-left active:scale-[0.97] transition-transform"
          >
            <div className="text-2xl mb-2">💉</div>
            <p className="text-sm font-bold text-gray-900">
              {t("health.dashboard.action_schedule")}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {t("health.dashboard.action_schedule_sub")}
            </p>
          </button>
          <button
            onClick={() => navigate(`/farms/${farmId}/health/alerts`)}
            className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-left active:scale-[0.97] transition-transform"
          >
            <div className="text-2xl mb-2">⚠️</div>
            <p className="text-sm font-bold text-gray-900">
              {t("health.dashboard.action_alerts")}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {t("health.dashboard.action_alerts_sub")}
            </p>
          </button>
        </div>
      </div>
    </div>
  );
}
