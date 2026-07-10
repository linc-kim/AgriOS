/**
 * Greena — Screen FL-01: Flock List
 * Lists all flocks for the current farm.
 * Tab 2 entry point. Active flocks first, then recently closed.
 * Farm owner / manager see "New Flock" button.
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Plus, ChevronRight, Feather } from "lucide-react";
import { listFlocks } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import { useAuthStore } from "@/stores/authStore";
import type { Flock } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-brand-100 text-brand-700",
  sold: "bg-blue-100 text-blue-700",
  closed: "bg-gray-100 text-gray-600",
  culled: "bg-red-100 text-red-700",
};

export default function FlockListScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const { data: flocks = [], isLoading } = useQuery({
    queryKey: queryKeys.flocks(farmId!),
    queryFn: () => listFlocks(farmId!, { limit: 50 }),
    enabled: !!farmId,
  });

  // Permission check: farm_owner and farm_manager can create flocks
  const canCreate = user?.user_roles?.some(
    (r) => r.farm_id === farmId && ["farm_owner", "farm_manager"].includes(r.role.name)
  ) ?? false;

  const activeFlocks = flocks.filter((f) => f.status === "active");
  const closedFlocks = flocks.filter((f) => f.status !== "active");

  function daysAlive(flock: Flock): number {
    const start = new Date(flock.placement_date);
    const end = flock.close_date ? new Date(flock.close_date) : new Date();
    return Math.floor((end.getTime() - start.getTime()) / 86_400_000);
  }

  function FlockCard({ flock }: { flock: Flock }) {
    return (
      <button
        onClick={() => navigate(`/farms/${farmId}/flocks/${flock.id}`)}
        className="w-full bg-white rounded-2xl shadow-sm border border-gray-100 px-4 py-4 flex items-center gap-3 text-left active:scale-[0.98] transition-transform"
      >
        {/* Icon */}
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
          flock.status === "active" ? "bg-brand-50" : "bg-gray-50"
        }`}>
          <Feather className={`w-5 h-5 ${
            flock.status === "active" ? "text-brand-600" : "text-gray-400"
          }`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-semibold text-gray-900 truncate text-sm">
              {flock.name}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[flock.status]}`}>
              {t(`flock.status.${flock.status}`)}
            </span>
          </div>
          {flock.breed && (
            <div className="text-xs text-gray-500 truncate">{flock.breed}</div>
          )}
          <div className="text-xs text-gray-400 mt-0.5">
            {t("flock.list.initial_count", { count: flock.initial_count })}
            {" · "}
            {t("flock.list.days_alive", { count: daysAlive(flock) })}
          </div>
        </div>

        <ChevronRight className="w-4 h-4 text-gray-300 shrink-0" />
      </button>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 pt-12 pb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">
          {t("flock.list.title")}
        </h1>
        {canCreate && (
          <button
            onClick={() => navigate(`/farms/${farmId}/flocks/new`)}
            className="
              min-h-[40px] px-4 rounded-xl bg-brand-600 text-white
              text-sm font-semibold flex items-center gap-1.5
              active:scale-[0.97] transition-transform
            "
          >
            <Plus className="w-4 h-4" />
            {t("flock.list.new_flock")}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 px-4 py-4">
        {isLoading && (
          <div className="flex justify-center pt-16">
            <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!isLoading && flocks.length === 0 && (
          <div className="text-center pt-20 px-8">
            <div className="w-20 h-20 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-4">
              <Feather className="w-9 h-9 text-brand-400" />
            </div>
            <h2 className="text-lg font-bold text-gray-800 mb-2">
              {t("flock.list.empty_title")}
            </h2>
            <p className="text-sm text-gray-500 leading-relaxed mb-6">
              {t("flock.list.empty_body")}
            </p>
            {canCreate && (
              <button
                onClick={() => navigate(`/farms/${farmId}/flocks/new`)}
                className="
                  min-h-[48px] px-8 rounded-xl bg-brand-600 text-white
                  font-semibold text-base
                "
              >
                {t("flock.list.start_first_flock")}
              </button>
            )}
          </div>
        )}

        {/* Active Flocks */}
        {activeFlocks.length > 0 && (
          <div className="mb-4">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-1">
              {t("flock.list.section_active")} ({activeFlocks.length})
            </div>
            <div className="flex flex-col gap-2">
              {activeFlocks.map((f) => (
                <FlockCard key={f.id} flock={f} />
              ))}
            </div>
          </div>
        )}

        {/* Closed Flocks */}
        {closedFlocks.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-1">
              {t("flock.list.section_closed")} ({closedFlocks.length})
            </div>
            <div className="flex flex-col gap-2">
              {closedFlocks.map((f) => (
                <FlockCard key={f.id} flock={f} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
