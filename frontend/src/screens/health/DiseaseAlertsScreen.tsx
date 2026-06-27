/**
 * AGRIOS — Screen H-05: Disease Alerts
 * Lists all disease alerts relevant to this farm (county + species matched).
 * Shows severity badge, status, brief guidance, and full description on tap.
 *
 * Requires HEALTH_ALERT_VIEW (all roles).
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { getFarmAlerts } from "@/api/health";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { DiseaseAlert } from "@/types";

function SeverityBadge({ severity }: { severity: string }) {
  const styles = {
    critical: "bg-red-100 text-red-700",
    warning:  "bg-amber-100 text-amber-700",
    info:     "bg-blue-100 text-blue-700",
  }[severity] ?? "bg-gray-100 text-gray-600";

  return (
    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${styles}`}>
      {severity}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles = {
    active:      "bg-green-100 text-green-700",
    deactivated: "bg-gray-100 text-gray-500",
    draft:       "bg-gray-100 text-gray-500",
  }[status] ?? "bg-gray-100 text-gray-500";

  return (
    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${styles}`}>
      {status}
    </span>
  );
}

function AlertCard({
  alert,
  onExpand,
  isExpanded,
}: {
  alert: DiseaseAlert;
  onExpand: () => void;
  isExpanded: boolean;
}) {
  const { t } = useTranslation();

  const borderColor = {
    critical: "border-l-red-500",
    warning:  "border-l-amber-500",
    info:     "border-l-blue-500",
  }[alert.severity] ?? "border-l-gray-300";

  return (
    <div
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden border-l-4 ${borderColor}`}
    >
      <button
        onClick={onExpand}
        className="w-full text-left px-4 py-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <SeverityBadge severity={alert.severity} />
              <StatusBadge status={alert.status} />
              {alert.county && (
                <span className="text-[10px] font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                  {alert.county}
                </span>
              )}
            </div>
            <p className="text-sm font-bold text-gray-900 mt-1 leading-snug">
              {alert.title}
            </p>
            <p className="text-xs text-gray-500 mt-0.5">{alert.disease_name}</p>
          </div>
          <span className={`text-gray-400 transition-transform flex-shrink-0 mt-1 ${isExpanded ? "rotate-90" : ""}`}>
            ›
          </span>
        </div>

        {alert.published_at && (
          <p className="text-xs text-gray-400 mt-2">
            {t("health.alerts.published")}: {new Date(alert.published_at).toLocaleDateString()}
          </p>
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-50">
          <div className="pt-3 space-y-3">
            {alert.brief_guidance && (
              <div className="rounded-xl bg-gray-50 border border-gray-100 px-3 py-3">
                <p className="text-xs font-bold text-gray-600 uppercase tracking-wide mb-1">
                  {t("health.alerts.guidance")}
                </p>
                <p className="text-sm text-gray-700 leading-relaxed">{alert.brief_guidance}</p>
              </div>
            )}
            <div>
              <p className="text-xs font-bold text-gray-600 uppercase tracking-wide mb-1">
                {t("health.alerts.description")}
              </p>
              <p className="text-sm text-gray-600 leading-relaxed">{alert.description}</p>
            </div>
            {alert.expires_at && (
              <p className="text-xs text-gray-400">
                {t("health.alerts.expires")}: {new Date(alert.expires_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DiseaseAlertsScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: alerts = [], isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.farmAlerts(farmId!),
    queryFn: () => getFarmAlerts(farmId!, { limit: 50 }),
    enabled: !!farmId,
  });

  const activeAlerts = alerts.filter((a: DiseaseAlert) => a.status === "active");
  const inactiveAlerts = alerts.filter((a: DiseaseAlert) => a.status !== "active");

  function toggleExpand(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-12 pb-4 border-b border-gray-100 bg-white">
        <button
          onClick={() => navigate(-1)}
          className="min-h-[48px] min-w-[48px] flex items-center justify-center text-gray-600"
        >
          ←
        </button>
        <div className="flex-1">
          <h1 className="text-lg font-bold text-gray-900">
            {t("health.alerts.title")}
          </h1>
          {activeAlerts.length > 0 && (
            <p className="text-xs text-red-600 font-medium mt-0.5">
              {t("health.alerts.active_count", { count: activeAlerts.length })}
            </p>
          )}
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      )}

      {isError && (
        <div className="px-4 py-8 text-center">
          <p className="text-sm text-red-600 mb-3">{t("common.load_error")}</p>
          <button onClick={() => refetch()} className="text-sm font-semibold text-brand-600">
            {t("common.retry")}
          </button>
        </div>
      )}

      {!isLoading && !isError && alerts.length === 0 && (
        <div className="px-4 py-16 text-center">
          <p className="text-3xl mb-4">✅</p>
          <p className="text-base font-bold text-gray-800">
            {t("health.alerts.empty_title")}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            {t("health.alerts.empty_body")}
          </p>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="px-4 py-5 space-y-4">

          {/* Active alerts */}
          {activeAlerts.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wide px-1">
                {t("health.alerts.section_active")}
              </p>
              {activeAlerts.map((alert: DiseaseAlert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  isExpanded={expandedId === alert.id}
                  onExpand={() => toggleExpand(alert.id)}
                />
              ))}
            </div>
          )}

          {/* Past/deactivated alerts */}
          {inactiveAlerts.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wide px-1">
                {t("health.alerts.section_past")}
              </p>
              {inactiveAlerts.map((alert: DiseaseAlert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  isExpanded={expandedId === alert.id}
                  onExpand={() => toggleExpand(alert.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
