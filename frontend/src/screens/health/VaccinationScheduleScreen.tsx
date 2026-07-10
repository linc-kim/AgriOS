/**
 * Greena — Screen H-02: Vaccination Schedule
 * Full upcoming + overdue vaccination list across all active flocks.
 * Groups by: Overdue → Due Today → This Week → Upcoming (next 30 days).
 *
 * Requires HEALTH_VACCINATION_VIEW (all roles).
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { getVaccinationSchedule } from "@/api/health";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { VaccinationScheduleItem } from "@/types";

interface SectionProps {
  title: string;
  count: number;
  items: VaccinationScheduleItem[];
  accent: "red" | "amber" | "brand" | "gray";
  farmId: string;
  canLog: boolean;
  onLogVaccination: (flockId: string) => void;
}

function ScheduleSection({
  title,
  count,
  items,
  accent,
  canLog,
  onLogVaccination,
}: SectionProps) {
  const accentStyles = {
    red: {
      header: "bg-red-50 border-red-100",
      label: "text-red-700",
      dot: "bg-red-500",
      badge: "bg-red-100 text-red-700",
    },
    amber: {
      header: "bg-amber-50 border-amber-100",
      label: "text-amber-700",
      dot: "bg-amber-500",
      badge: "bg-amber-100 text-amber-700",
    },
    brand: {
      header: "bg-brand-50 border-brand-100",
      label: "text-brand-700",
      dot: "bg-brand-500",
      badge: "bg-brand-100 text-brand-700",
    },
    gray: {
      header: "bg-gray-50 border-gray-100",
      label: "text-gray-600",
      dot: "bg-gray-400",
      badge: "bg-gray-100 text-gray-600",
    },
  }[accent];

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className={`flex items-center justify-between px-4 py-3 border-b ${accentStyles.header}`}>
        <p className={`text-xs font-bold uppercase tracking-wide ${accentStyles.label}`}>
          {title}
        </p>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${accentStyles.badge}`}>
          {count}
        </span>
      </div>
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center gap-3 px-4 py-3.5 border-b border-gray-50 last:border-0"
        >
          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${accentStyles.dot}`} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 truncate">
              {item.next_vaccine_name || item.vaccine_name}
            </p>
            <p className="text-xs text-gray-500 truncate">{item.flock_name}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {new Date(item.next_due_date).toLocaleDateString()}
              {item.is_overdue && (
                <span className="ml-1 text-red-600 font-medium">
                  · {Math.abs(item.days_until_due)}d overdue
                </span>
              )}
            </p>
          </div>
          {canLog && (
            <button
              onClick={() => onLogVaccination(item.flock_id)}
              className="min-h-[40px] px-3 text-xs font-semibold text-brand-600 border border-brand-200 rounded-xl bg-brand-50 active:scale-95 transition-transform flex-shrink-0"
            >
              Log
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

export default function VaccinationScheduleScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: schedule, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.healthSchedule(farmId!),
    queryFn: () => getVaccinationSchedule(farmId!),
    enabled: !!farmId,
  });

  // TODO: derive canLog from user role (farm_owner, farm_manager, vet_consultant)
  const canLog = true;

  function handleLogVaccination(flockId: string) {
    navigate(`/farms/${farmId}/flocks/${flockId}/vaccinations/new`);
  }

  const totalUpcoming =
    (schedule?.overdue.length ?? 0) +
    (schedule?.due_today.length ?? 0) +
    (schedule?.due_this_week.length ?? 0) +
    (schedule?.upcoming.length ?? 0);

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
            {t("health.schedule.title")}
          </h1>
          <p className="text-xs text-gray-400">
            {t("health.schedule.next_30_days")}
          </p>
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
          <button
            onClick={() => refetch()}
            className="text-sm font-semibold text-brand-600"
          >
            {t("common.retry")}
          </button>
        </div>
      )}

      {schedule && (
        <div className="px-4 py-5 space-y-4">
          {totalUpcoming === 0 && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-4 py-10 text-center">
              <p className="text-3xl mb-3">✅</p>
              <p className="text-base font-bold text-gray-800">
                {t("health.schedule.all_clear")}
              </p>
              <p className="text-sm text-gray-400 mt-1">
                {t("health.schedule.all_clear_sub")}
              </p>
            </div>
          )}

          {schedule.overdue.length > 0 && (
            <ScheduleSection
              title={t("health.schedule.overdue")}
              count={schedule.overdue.length}
              items={schedule.overdue}
              accent="red"
              farmId={farmId!}
              canLog={canLog}
              onLogVaccination={handleLogVaccination}
            />
          )}

          {schedule.due_today.length > 0 && (
            <ScheduleSection
              title={t("health.schedule.due_today")}
              count={schedule.due_today.length}
              items={schedule.due_today}
              accent="amber"
              farmId={farmId!}
              canLog={canLog}
              onLogVaccination={handleLogVaccination}
            />
          )}

          {schedule.due_this_week.length > 0 && (
            <ScheduleSection
              title={t("health.schedule.this_week")}
              count={schedule.due_this_week.length}
              items={schedule.due_this_week}
              accent="brand"
              farmId={farmId!}
              canLog={canLog}
              onLogVaccination={handleLogVaccination}
            />
          )}

          {schedule.upcoming.length > 0 && (
            <ScheduleSection
              title={t("health.schedule.upcoming")}
              count={schedule.upcoming.length}
              items={schedule.upcoming}
              accent="gray"
              farmId={farmId!}
              canLog={canLog}
              onLogVaccination={handleLogVaccination}
            />
          )}
        </div>
      )}
    </div>
  );
}
