/**
 * AGRIOS — Screen FL-03: Create Flock
 * Opens a new flock in a chosen production house.
 * House dropdown shows only unoccupied houses.
 * Requires FLOCK_CREATE (farm_owner, farm_manager).
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFlock, listFlocks } from "@/api/flocks";
import { listFarmUnits } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import type { FlockCreateInput, ProductionHouse, FarmUnit } from "@/types";

const COMMON_BREEDS = [
  "Ross 308",
  "Cobb 500",
  "ISA Brown",
  "Lohmann Brown",
  "Kienyeji",
  "KARI Improved Kienyeji",
  "Other",
];

export default function CreateFlockScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Form state
  const [houseId, setHouseId] = useState("");
  const [name, setName] = useState("");
  const [breed, setBreed] = useState("");
  const [customBreed, setCustomBreed] = useState("");
  const [batchNumber, setBatchNumber] = useState("");
  const [initialCount, setInitialCount] = useState("");
  const [placementDate, setPlacementDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [expectedCycleDays, setExpectedCycleDays] = useState("42");
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Load farm units with their houses to show house picker
  const { data: units = [] } = useQuery<FarmUnit[]>({
    queryKey: queryKeys.farmUnits(farmId!),
    queryFn: () => listFarmUnits(farmId!),
    enabled: !!farmId,
  });

  // Build flat list of unoccupied houses from units
  // NOTE: FarmUnit has 'houses' relation — included in the response
  const availableHouses: Array<ProductionHouse & { unitName: string }> = (
    units as Array<FarmUnit & { houses?: ProductionHouse[] }>
  ).flatMap((u) =>
    (u.houses ?? [])
      .filter((h) => !h.is_occupied)
      .map((h) => ({ ...h, unitName: u.name })),
  );

  const mutation = useMutation({
    mutationFn: (input: FlockCreateInput) => createFlock(farmId!, input),
    onSuccess: (flock) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.flocks(farmId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.farmHouses(farmId!) });
      navigate(`/farms/${farmId}/flocks/${flock.id}`, { replace: true });
    },
  });

  function validate(): boolean {
    const newErrors: Record<string, string> = {};
    if (!houseId) newErrors.houseId = t("flock.create.house_required");
    if (!name.trim() || name.trim().length < 2)
      newErrors.name = t("flock.create.name_required");
    const count = parseInt(initialCount, 10);
    if (!initialCount || isNaN(count) || count < 1)
      newErrors.initialCount = t("flock.create.count_required");
    if (!placementDate) newErrors.placementDate = t("flock.create.date_required");
    const days = parseInt(expectedCycleDays, 10);
    if (!expectedCycleDays || isNaN(days) || days < 1)
      newErrors.expectedCycleDays = t("flock.create.cycle_required");
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const resolvedBreed = breed === "Other" ? customBreed.trim() : breed;

    mutation.mutate({
      house_id: houseId,
      name: name.trim(),
      breed: resolvedBreed || undefined,
      batch_number: batchNumber.trim() || undefined,
      initial_count: parseInt(initialCount, 10),
      placement_date: placementDate,
      expected_cycle_days: parseInt(expectedCycleDays, 10),
      species_key: "poultry",
    });
  }

  const today = new Date().toISOString().split("T")[0];

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
          {t("flock.create.title")}
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-5 gap-5 overflow-y-auto">

        {/* House Picker */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.create.house_label")} *
          </label>
          {availableHouses.length === 0 ? (
            <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3">
              <p className="text-sm text-amber-700">{t("flock.create.no_houses")}</p>
            </div>
          ) : (
            <select
              value={houseId}
              onChange={(e) => setHouseId(e.target.value)}
              className={`
                w-full min-h-[48px] px-4 rounded-xl border text-base
                focus:outline-none focus:ring-2 focus:ring-brand-600
                ${errors.houseId ? "border-red-400 bg-red-50" : "border-gray-300"}
              `}
              disabled={mutation.isPending}
            >
              <option value="">{t("flock.create.house_placeholder")}</option>
              {availableHouses.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.unitName} — {h.name} ({h.house_type}, cap {h.capacity.toLocaleString()})
                </option>
              ))}
            </select>
          )}
          {errors.houseId && (
            <p className="mt-1.5 text-xs text-red-600">{errors.houseId}</p>
          )}
        </div>

        {/* Flock Name */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.create.name_label")} *
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("flock.create.name_placeholder")}
            maxLength={255}
            disabled={mutation.isPending}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${errors.name ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
          />
          {errors.name && (
            <p className="mt-1.5 text-xs text-red-600">{errors.name}</p>
          )}
        </div>

        {/* Breed */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.create.breed_label")}
          </label>
          <select
            value={breed}
            onChange={(e) => setBreed(e.target.value)}
            className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
            disabled={mutation.isPending}
          >
            <option value="">{t("flock.create.breed_placeholder")}</option>
            {COMMON_BREEDS.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
          {breed === "Other" && (
            <input
              type="text"
              value={customBreed}
              onChange={(e) => setCustomBreed(e.target.value)}
              placeholder={t("flock.create.breed_custom")}
              maxLength={100}
              className="mt-2 w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              disabled={mutation.isPending}
            />
          )}
        </div>

        {/* Initial Count */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.create.count_label")} *
          </label>
          <input
            type="number"
            inputMode="numeric"
            value={initialCount}
            onChange={(e) => setInitialCount(e.target.value)}
            placeholder="500"
            min={1}
            max={1000000}
            disabled={mutation.isPending}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${errors.initialCount ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
          />
          {errors.initialCount && (
            <p className="mt-1.5 text-xs text-red-600">{errors.initialCount}</p>
          )}
        </div>

        {/* Batch Number */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.create.batch_label")}
          </label>
          <input
            type="text"
            value={batchNumber}
            onChange={(e) => setBatchNumber(e.target.value)}
            placeholder={t("flock.create.batch_placeholder")}
            maxLength={50}
            disabled={mutation.isPending}
            className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
          />
        </div>

        {/* Placement Date */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.create.placement_date_label")} *
          </label>
          <input
            type="date"
            value={placementDate}
            onChange={(e) => setPlacementDate(e.target.value)}
            max={today}
            disabled={mutation.isPending}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${errors.placementDate ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
          />
          {errors.placementDate && (
            <p className="mt-1.5 text-xs text-red-600">{errors.placementDate}</p>
          )}
        </div>

        {/* Expected Cycle Days */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.create.cycle_label")} *
          </label>
          <div className="grid grid-cols-3 gap-2 mb-2">
            {[
              { label: t("flock.create.cycle_broiler"), value: "42" },
              { label: t("flock.create.cycle_layer"), value: "350" },
              { label: t("flock.create.cycle_custom"), value: "custom" },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  if (opt.value !== "custom") setExpectedCycleDays(opt.value);
                }}
                className={`
                  min-h-[44px] rounded-xl border text-sm font-medium transition-colors
                  ${
                    (opt.value !== "custom" && expectedCycleDays === opt.value) ||
                    (opt.value === "custom" && expectedCycleDays !== "42" && expectedCycleDays !== "350")
                      ? "border-brand-600 bg-brand-50 text-brand-700"
                      : "border-gray-200 bg-white text-gray-600"
                  }
                `}
                disabled={mutation.isPending}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <input
            type="number"
            inputMode="numeric"
            value={expectedCycleDays}
            onChange={(e) => setExpectedCycleDays(e.target.value)}
            min={1}
            max={1000}
            disabled={mutation.isPending}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${errors.expectedCycleDays ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
          />
          {errors.expectedCycleDays && (
            <p className="mt-1.5 text-xs text-red-600">{errors.expectedCycleDays}</p>
          )}
        </div>

        {mutation.error && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">
              {(mutation.error as Error).message}
            </p>
          </div>
        )}

        <div className="flex-1" />

        <button
          type="submit"
          disabled={mutation.isPending || !houseId || !name.trim() || !initialCount}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {mutation.isPending
            ? t("common.loading")
            : t("flock.create.submit")}
        </button>
      </form>
    </div>
  );
}
