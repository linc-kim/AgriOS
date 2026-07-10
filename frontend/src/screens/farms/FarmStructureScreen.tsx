/**
 * Greena — Screen FM-05: Farm Structure
 * Shows a list of farm units with their houses.
 * Farm owner / manager can add, edit, or delete units.
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listFarmUnits, deleteFarmUnit } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import { Plus, ChevronRight, Trash2 } from "lucide-react";
import type { FarmUnit } from "@/types";

export default function FarmStructureScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: units = [], isLoading } = useQuery({
    queryKey: queryKeys.farmSummary(farmId!),  // reuse summary key for units
    queryFn: () => listFarmUnits(farmId!),
    enabled: !!farmId,
  });

  const deleteMutation = useMutation({
    mutationFn: (unitId: string) => deleteFarmUnit(farmId!, unitId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farmSummary(farmId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.farm(farmId!) });
    },
  });

  function handleDeleteUnit(unit: FarmUnit) {
    if (window.confirm(t("farm.unit.delete_confirm"))) {
      deleteMutation.mutate(unit.id);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 pt-12 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="min-h-[48px] min-w-[48px] flex items-center justify-center text-gray-600"
          >
            ←
          </button>
          <h1 className="text-lg font-bold text-gray-900">
            {t("farm.structure.title")}
          </h1>
        </div>
        <button
          onClick={() => navigate(`/farms/${farmId}/units/new`)}
          className="
            min-h-[40px] px-4 rounded-xl bg-brand-600 text-white
            text-sm font-semibold flex items-center gap-1.5
          "
        >
          <Plus className="w-4 h-4" />
          {t("farm.structure.add_unit")}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 px-4 py-4 flex flex-col gap-3">
        {isLoading && (
          <div className="flex justify-center pt-12">
            <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!isLoading && units.length === 0 && (
          <div className="text-center px-8 pt-16">
            <div className="w-16 h-16 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">🏗️</span>
            </div>
            <p className="text-gray-500 text-sm leading-relaxed">
              {t("farm.structure.units_empty")}
            </p>
            <button
              onClick={() => navigate(`/farms/${farmId}/units/new`)}
              className="mt-4 text-brand-600 font-semibold text-sm"
            >
              {t("farm.structure.add_unit")} →
            </button>
          </div>
        )}

        {units.map((unit) => (
          <div key={unit.id} className="bg-white rounded-xl shadow-sm overflow-hidden">
            {/* Unit row */}
            <div className="flex items-center px-4 py-4 gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-gray-900">{unit.name}</div>
                {unit.description && (
                  <div className="text-xs text-gray-500 mt-0.5 truncate">
                    {unit.description}
                  </div>
                )}
                <div className="text-xs text-gray-400 mt-1">
                  {unit.house_count === 1
                    ? t("farm.structure.houses_count_one", { count: unit.house_count })
                    : t("farm.structure.houses_count_other", { count: unit.house_count })}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {/* Delete unit */}
                <button
                  onClick={() => handleDeleteUnit(unit)}
                  disabled={deleteMutation.isPending}
                  className="
                    min-h-[40px] min-w-[40px] flex items-center justify-center
                    rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50
                    transition-colors
                  "
                  aria-label={t("farm.unit.delete")}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                {/* Add house inside unit */}
                <button
                  onClick={() => navigate(`/farms/${farmId}/units/${unit.id}/houses/new`)}
                  className="
                    min-h-[40px] min-w-[40px] flex items-center justify-center
                    rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50
                    transition-colors
                  "
                  aria-label={t("farm.unit.add_house")}
                >
                  <Plus className="w-4 h-4" />
                </button>
                <ChevronRight className="w-4 h-4 text-gray-300" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
