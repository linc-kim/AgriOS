/**
 * AGRIOS — Screen H-04: Vaccination History
 * Full vaccination record list for a single flock.
 * Shows: vaccine name, dose number, date, route, next due date.
 * Allows viewing record detail and logging new vaccination.
 *
 * Requires HEALTH_VACCINATION_VIEW (all roles).
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { listVaccinations } from "@/api/health";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { VaccinationRecord } from "@/types";

function routeLabel(route: string | null): string {
  if (!route) return "";
  const map: Record<string, string> = {
    drinking_water: "Drinking Water",
    spray: "Spray",
    eye_drop: "Eye Drop",
    injection: "Injection",
    wing_stab: "Wing Stab",
    oral: "Oral",
  };
  return map[route] ?? route;
}

export default function VaccinationHistoryScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: records = [], isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.flockVaccinations(farmId!, flockId!),
    queryFn: () => listVaccinations(farmId!, flockId!, { limit: 100 }),
    enabled: !!farmId && !!flockId,
  });

  // TODO: derive canLog from user role
  const canLog = true;

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
            {t("health.history.title")}
          </h1>
          {records.length > 0 && (
            <p className="text-xs text-gray-400">
              {t("health.history.showing", { count: records.length })}
            </p>
          )}
        </div>
        {canLog && (
          <button
            onClick={() => navigate(`/farms/${farmId}/flocks/${flockId}/vaccinations/new`)}
            className="min-h-[44px] px-4 text-sm font-semibold text-white bg-brand-600 rounded-xl active:scale-95 transition-transform"
          >
            + {t("health.history.log_new")}
          </button>
        )}
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

      {!isLoading && !isError && records.length === 0 && (
        <div className="px-4 py-16 text-center">
          <p className="text-3xl mb-4">💉</p>
          <p className="text-base font-bold text-gray-800">
            {t("health.history.empty_title")}
          </p>
          <p className="text-sm text-gray-400 mt-1 mb-6">
            {t("health.history.empty_body")}
          </p>
          {canLog && (
            <button
              onClick={() => navigate(`/farms/${farmId}/flocks/${flockId}/vaccinations/new`)}
              className="min-h-[48px] px-6 bg-brand-600 text-white rounded-xl font-semibold text-sm"
            >
              {t("health.history.log_first")}
            </button>
          )}
        </div>
      )}

      {records.length > 0 && (
        <div className="px-4 py-4 space-y-3">
          {records.map((record: VaccinationRecord) => (
            <div
              key={record.id}
              className="bg-white rounded-2xl border border-gray-100 shadow-sm px-4 py-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-sm font-bold text-gray-900 truncate">
                      {record.vaccine_name}
                    </p>
                    <span className="flex-shrink-0 text-xs font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                      {t("health.history.dose")} {record.dose_number}
                    </span>
                  </div>
                  {record.vaccine_brand && (
                    <p className="text-xs text-gray-500 mb-1">{record.vaccine_brand}</p>
                  )}
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500">
                    <span>📅 {new Date(record.administered_date).toLocaleDateString()}</span>
                    {record.flock_age_days !== null && (
                      <span>🐔 {t("health.history.day")} {record.flock_age_days}</span>
                    )}
                    {record.route && (
                      <span>💧 {routeLabel(record.route)}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Next dose */}
              {record.next_due_date && (
                <div className={`
                  mt-3 pt-3 border-t border-gray-50 flex items-center gap-2
                `}>
                  <div className={`
                    w-2 h-2 rounded-full flex-shrink-0
                    ${record.is_overdue ? "bg-red-500" : record.is_due_soon ? "bg-amber-500" : "bg-brand-400"}
                  `} />
                  <div className="flex-1">
                    <p className={`text-xs font-semibold ${
                      record.is_overdue ? "text-red-600" : record.is_due_soon ? "text-amber-600" : "text-gray-600"
                    }`}>
                      {record.next_vaccine_name || t("health.history.next_dose")} ·{" "}
                      {new Date(record.next_due_date).toLocaleDateString()}
                      {record.is_overdue && ` (${t("health.schedule.overdue")})`}
                      {record.is_due_soon && !record.is_overdue && ` (${t("health.schedule.due_soon")})`}
                    </p>
                  </div>
                </div>
              )}

              {/* Notes */}
              {record.notes && (
                <p className="mt-2 text-xs text-gray-400 line-clamp-2">{record.notes}</p>
              )}

              {/* Batch number */}
              {record.batch_number && (
                <p className="mt-1 text-xs text-gray-400">
                  {t("health.history.batch")}: {record.batch_number}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
