/**
 * AGRIOS — Screen FL-06: Daily Log History
 * Shows chronological list of daily logs for a flock.
 * Corrected logs are flagged with a badge.
 * Requires OPS_LOG_VIEW (all roles).
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { listDailyLogs } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import type { DailyLog } from "@/types";

function LogRow({ log }: { log: DailyLog }) {
  const { t } = useTranslation();
  const formatted = new Date(log.log_date).toLocaleDateString("en-KE", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-4">
      {/* Date + corrected badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-gray-800">{formatted}</span>
        {log.is_corrected && (
          <span className="text-xs bg-amber-100 text-amber-700 font-medium px-2 py-0.5 rounded-full flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            {t("flock.log_history.corrected")}
          </span>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2">
        <div className="text-center">
          <div className="text-base font-bold text-red-600">{log.mortality_count}</div>
          <div className="text-xs text-gray-400">{t("flock.log_history.mortality")}</div>
        </div>
        <div className="text-center border-x border-gray-100">
          <div className="text-base font-bold text-gray-800">
            {Number(log.feed_consumed_kg).toFixed(1)} <span className="text-xs font-normal text-gray-400">kg</span>
          </div>
          <div className="text-xs text-gray-400">{t("flock.log_history.feed")}</div>
        </div>
        <div className="text-center">
          <div className="text-base font-bold text-gray-800">
            {log.morning_count?.toLocaleString() ?? "—"}
          </div>
          <div className="text-xs text-gray-400">{t("flock.log_history.count")}</div>
        </div>
      </div>

      {/* Optional mortality cause */}
      {log.mortality_count > 0 && log.mortality_cause && (
        <div className="mt-2 text-xs text-gray-500 italic">
          {t("flock.log_history.cause")}: {log.mortality_cause}
        </div>
      )}

      {/* Temperature */}
      {(log.house_temp_am || log.house_temp_pm) && (
        <div className="mt-2 text-xs text-gray-400">
          🌡 {log.house_temp_am ? `${log.house_temp_am}°C AM` : ""}{" "}
          {log.house_temp_pm ? `· ${log.house_temp_pm}°C PM` : ""}
        </div>
      )}

      {/* Notes */}
      {log.notes && (
        <div className="mt-2 text-xs text-gray-500 leading-relaxed line-clamp-2">
          {log.notes}
        </div>
      )}
    </div>
  );
}

export default function DailyLogHistoryScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: logs = [], isLoading } = useQuery({
    queryKey: queryKeys.flockLogs(farmId!, flockId!),
    queryFn: () => listDailyLogs(farmId!, flockId!, { limit: 90 }),
    enabled: !!farmId && !!flockId,
  });

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 pt-12 pb-4 flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="min-h-[48px] min-w-[48px] flex items-center justify-center text-gray-600"
        >
          ←
        </button>
        <h1 className="text-lg font-bold text-gray-900">
          {t("flock.log_history.title")}
        </h1>
      </div>

      {/* Content */}
      <div className="flex-1 px-4 py-4 flex flex-col gap-2">
        {isLoading && (
          <div className="flex justify-center pt-12">
            <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!isLoading && logs.length === 0 && (
          <div className="text-center pt-16 px-8">
            <p className="text-gray-500 text-sm">{t("flock.log_history.empty")}</p>
          </div>
        )}

        {logs.map((log) => (
          <LogRow key={log.id} log={log} />
        ))}

        {logs.length > 0 && (
          <p className="text-center text-xs text-gray-400 py-2">
            {t("flock.log_history.showing", { count: logs.length })}
          </p>
        )}
      </div>
    </div>
  );
}
