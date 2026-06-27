/**
 * AGRIOS — Screen FM-06: Add Farm Section (Unit)
 * Shared for both create and edit (edit pre-fills from route state).
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFarmUnit, updateFarmUnit } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import type { FarmUnit, FarmUnitCreateInput, FarmUnitUpdateInput } from "@/types";

export default function AddUnitScreen() {
  const { farmId, unitId } = useParams<{ farmId: string; unitId?: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const isEditing = !!unitId && unitId !== "new";
  const existingUnit = location.state?.unit as FarmUnit | undefined;

  const [name, setName] = useState(existingUnit?.name ?? "");
  const [description, setDescription] = useState(existingUnit?.description ?? "");

  const createMutation = useMutation({
    mutationFn: (input: FarmUnitCreateInput) => createFarmUnit(farmId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farmSummary(farmId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.farm(farmId!) });
      navigate(-1);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (input: FarmUnitUpdateInput) =>
      updateFarmUnit(farmId!, unitId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farmSummary(farmId!) });
      navigate(-1);
    },
  });

  const isLoading = createMutation.isPending || updateMutation.isPending;
  const serverError = (createMutation.error || updateMutation.error) as Error | null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;

    const input = {
      name: trimmed,
      description: description.trim() || undefined,
    };

    if (isEditing) {
      updateMutation.mutate(input);
    } else {
      createMutation.mutate(input);
    }
  }

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-12 pb-4 border-b border-gray-100">
        <button
          onClick={() => navigate(-1)}
          className="min-h-[48px] min-w-[48px] flex items-center justify-center text-gray-600"
        >
          ←
        </button>
        <h1 className="text-lg font-bold text-gray-900">
          {isEditing ? t("farm.unit.edit_title") : t("farm.unit.add_title")}
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-6 gap-5">

        {/* Unit name */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("farm.unit.name_label")} *
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("farm.unit.name_placeholder")}
            className="
              w-full min-h-[48px] px-4 rounded-xl border border-gray-300
              text-base focus:outline-none focus:ring-2 focus:ring-brand-600
            "
            disabled={isLoading}
            autoFocus
            maxLength={255}
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("farm.unit.description_label")}
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="
              w-full px-4 py-3 rounded-xl border border-gray-300
              text-base focus:outline-none focus:ring-2 focus:ring-brand-600
              resize-none
            "
            disabled={isLoading}
            maxLength={500}
          />
        </div>

        {serverError && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">{serverError.message}</p>
          </div>
        )}

        <div className="flex-1" />

        <button
          type="submit"
          disabled={isLoading || !name.trim()}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {isLoading ? t("common.loading") : t("farm.unit.save")}
        </button>
      </form>
    </div>
  );
}
