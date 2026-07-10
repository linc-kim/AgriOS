/**
 * Greena — Screen FM-07: Add Production House
 * Create or edit a production house inside a farm unit.
 * Enforces: capacity > 0, house_type from the allowed enum.
 */

import { useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createProductionHouse, updateProductionHouse } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import type {
  HouseType,
  ProductionHouse,
  ProductionHouseCreateInput,
  ProductionHouseUpdateInput,
} from "@/types";

const HOUSE_TYPES: HouseType[] = ["broiler", "layer", "breeder", "pullet", "multi"];

export default function AddHouseScreen() {
  const { farmId, unitId, houseId } = useParams<{
    farmId: string;
    unitId: string;
    houseId?: string;
  }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const isEditing = !!houseId && houseId !== "new";
  const existing = location.state?.house as ProductionHouse | undefined;

  const [name, setName] = useState(existing?.name ?? "");
  const [capacity, setCapacity] = useState(
    existing?.capacity ? String(existing.capacity) : ""
  );
  const [houseType, setHouseType] = useState<HouseType>(
    existing?.house_type ?? "broiler"
  );
  const [capacityError, setCapacityError] = useState("");

  const createMutation = useMutation({
    mutationFn: (input: ProductionHouseCreateInput) =>
      createProductionHouse(farmId!, unitId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farmSummary(farmId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.farm(farmId!) });
      navigate(-1);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (input: ProductionHouseUpdateInput) =>
      updateProductionHouse(farmId!, unitId!, houseId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farmSummary(farmId!) });
      navigate(-1);
    },
  });

  const isLoading = createMutation.isPending || updateMutation.isPending;
  const serverError = (createMutation.error || updateMutation.error) as Error | null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cap = parseInt(capacity, 10);
    if (!capacity || isNaN(cap) || cap <= 0 || cap > 100_000) {
      setCapacityError("Capacity must be between 1 and 100,000");
      return;
    }
    setCapacityError("");
    const input = {
      name: name.trim(),
      capacity: cap,
      house_type: houseType,
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
          {isEditing ? t("farm.house.edit_title") : t("farm.house.add_title")}
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-6 gap-5">

        {/* House name */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("farm.house.name_label")} *
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("farm.house.name_placeholder")}
            className="
              w-full min-h-[48px] px-4 rounded-xl border border-gray-300
              text-base focus:outline-none focus:ring-2 focus:ring-brand-600
            "
            disabled={isLoading}
            autoFocus
            maxLength={255}
          />
        </div>

        {/* Capacity */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("farm.house.capacity_label")} *
          </label>
          <input
            type="number"
            inputMode="numeric"
            value={capacity}
            onChange={(e) => {
              setCapacity(e.target.value);
              if (capacityError) setCapacityError("");
            }}
            placeholder={t("farm.house.capacity_placeholder")}
            min={1}
            max={100000}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${capacityError ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
            disabled={isLoading}
          />
          {capacityError && (
            <p className="mt-1.5 text-sm text-red-600">{capacityError}</p>
          )}
        </div>

        {/* House type */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            {t("farm.house.type_label")} *
          </label>
          <div className="grid grid-cols-2 gap-2">
            {HOUSE_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setHouseType(type)}
                disabled={isLoading}
                className={`
                  min-h-[48px] rounded-xl border text-sm font-medium
                  transition-colors
                  ${houseType === type
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-600"}
                `}
              >
                {t(`farm.house.types.${type}` as any)}
              </button>
            ))}
          </div>
        </div>

        {serverError && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">{serverError.message}</p>
          </div>
        )}

        <div className="flex-1" />

        <button
          type="submit"
          disabled={isLoading || !name.trim() || !capacity}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {isLoading ? t("common.loading") : t("farm.house.save")}
        </button>
      </form>
    </div>
  );
}
