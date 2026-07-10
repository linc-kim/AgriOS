/**
 * Greena — Screen FL-07: Weigh-In
 * Records a live-weight sample from a subset of the flock.
 * Computes and displays estimated FCR after submission.
 * Requires OPS_WEIGHIN_LOG (farm_owner, farm_manager, farm_worker).
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { submitWeighin, listWeighins } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import type { WeighinInput } from "@/types";

export default function WeighInScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const today = new Date().toISOString().split("T")[0];

  // Show last weighin for reference
  const { data: weighins = [] } = useQuery({
    queryKey: queryKeys.flockWeighins(farmId!, flockId!),
    queryFn: () => listWeighins(farmId!, flockId!, { limit: 1 }),
    enabled: !!farmId && !!flockId,
  });
  const lastWeighin = weighins[0] ?? null;

  const [weighedAt, setWeighedAt] = useState(today);
  const [sampleSize, setSampleSize] = useState("");
  const [averageWeightKg, setAverageWeightKg] = useState("");
  const [minWeightKg, setMinWeightKg] = useState("");
  const [maxWeightKg, setMaxWeightKg] = useState("");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const mutation = useMutation({
    mutationFn: (input: WeighinInput) => submitWeighin(farmId!, flockId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.flockWeighins(farmId!, flockId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.flock(farmId!, flockId!) });
      navigate(-1);
    },
  });

  function validate(): boolean {
    const e: Record<string, string> = {};
    const size = parseInt(sampleSize, 10);
    if (!sampleSize || isNaN(size) || size < 1)
      e.sampleSize = t("flock.weighin.sample_required");
    const avg = parseFloat(averageWeightKg);
    if (!averageWeightKg || isNaN(avg) || avg <= 0)
      e.averageWeightKg = t("flock.weighin.avg_required");
    if (minWeightKg && maxWeightKg) {
      if (parseFloat(minWeightKg) > parseFloat(maxWeightKg))
        e.minWeightKg = t("flock.weighin.min_exceeds_max");
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    mutation.mutate({
      weighed_at: weighedAt,
      sample_size: parseInt(sampleSize, 10),
      average_weight_kg: averageWeightKg,
      min_weight_kg: minWeightKg || undefined,
      max_weight_kg: maxWeightKg || undefined,
      notes: notes.trim() || undefined,
    });
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
          {t("flock.weighin.title")}
        </h1>
      </div>

      {/* Last Weighin Reference */}
      {lastWeighin && (
        <div className="mx-4 mt-4 rounded-xl bg-gray-50 border border-gray-200 px-4 py-3">
          <p className="text-xs text-gray-500 font-medium mb-1">
            {t("flock.weighin.last_weighin")}
          </p>
          <p className="text-sm text-gray-700">
            {new Date(lastWeighin.weighed_at).toLocaleDateString()} ·{" "}
            <span className="font-semibold">{lastWeighin.average_weight_kg} kg</span>
            {lastWeighin.fcr_to_date && (
              <> · FCR <span className="font-semibold">{lastWeighin.fcr_to_date}</span></>
            )}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-5 gap-5 overflow-y-auto">

        {/* Weigh Date */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.weighin.date_label")} *
          </label>
          <input
            type="date"
            value={weighedAt}
            onChange={(e) => setWeighedAt(e.target.value)}
            max={today}
            disabled={mutation.isPending}
            className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
          />
        </div>

        {/* Sample Size */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.weighin.sample_size")} *
          </label>
          <input
            type="number"
            inputMode="numeric"
            value={sampleSize}
            onChange={(e) => setSampleSize(e.target.value)}
            placeholder="50"
            min={1}
            disabled={mutation.isPending}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${errors.sampleSize ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
          />
          {errors.sampleSize && (
            <p className="mt-1.5 text-xs text-red-600">{errors.sampleSize}</p>
          )}
          <p className="mt-1 text-xs text-gray-400">{t("flock.weighin.sample_hint")}</p>
        </div>

        {/* Average Weight */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.weighin.avg_weight")} (kg) *
          </label>
          <input
            type="number"
            inputMode="decimal"
            value={averageWeightKg}
            onChange={(e) => setAverageWeightKg(e.target.value)}
            placeholder="1.850"
            min="0.001"
            step="0.001"
            disabled={mutation.isPending}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${errors.averageWeightKg ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
          />
          {errors.averageWeightKg && (
            <p className="mt-1.5 text-xs text-red-600">{errors.averageWeightKg}</p>
          )}
        </div>

        {/* Min / Max Weight */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.weighin.min_max")} (kg)
          </label>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="number"
              inputMode="decimal"
              value={minWeightKg}
              onChange={(e) => setMinWeightKg(e.target.value)}
              placeholder={t("flock.weighin.min_placeholder")}
              min="0.001"
              step="0.001"
              disabled={mutation.isPending}
              className={`
                w-full min-h-[48px] px-4 rounded-xl border text-base
                focus:outline-none focus:ring-2 focus:ring-brand-600
                ${errors.minWeightKg ? "border-red-400 bg-red-50" : "border-gray-300"}
              `}
            />
            <input
              type="number"
              inputMode="decimal"
              value={maxWeightKg}
              onChange={(e) => setMaxWeightKg(e.target.value)}
              placeholder={t("flock.weighin.max_placeholder")}
              min="0.001"
              step="0.001"
              disabled={mutation.isPending}
              className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
            />
          </div>
          {errors.minWeightKg && (
            <p className="mt-1.5 text-xs text-red-600">{errors.minWeightKg}</p>
          )}
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.weighin.notes")}
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t("flock.weighin.notes_placeholder")}
            rows={2}
            maxLength={2000}
            disabled={mutation.isPending}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600 resize-none"
          />
        </div>

        {mutation.error && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">{(mutation.error as Error).message}</p>
          </div>
        )}

        <div className="flex-1" />

        <button
          type="submit"
          disabled={mutation.isPending || !sampleSize || !averageWeightKg}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {mutation.isPending ? t("common.loading") : t("flock.weighin.submit")}
        </button>
      </form>
    </div>
  );
}
