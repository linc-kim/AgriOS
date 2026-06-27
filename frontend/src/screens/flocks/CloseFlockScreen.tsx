/**
 * AGRIOS — Screen FL-04: Close Flock
 * Allows farm_owner / farm_manager to close a flock.
 * Close reasons: sold | closed | culled.
 * "sold" requires price_per_kg and total_birds_sold.
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { closeFlock } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import type { CloseStatus, FlockCloseInput } from "@/types";

const CLOSE_OPTIONS: Array<{ status: CloseStatus; labelKey: string; descKey: string; color: string }> = [
  {
    status: "sold",
    labelKey: "flock.close.sold",
    descKey: "flock.close.sold_desc",
    color: "border-blue-400 bg-blue-50 text-blue-700",
  },
  {
    status: "closed",
    labelKey: "flock.close.closed",
    descKey: "flock.close.closed_desc",
    color: "border-gray-400 bg-gray-50 text-gray-700",
  },
  {
    status: "culled",
    labelKey: "flock.close.culled",
    descKey: "flock.close.culled_desc",
    color: "border-red-400 bg-red-50 text-red-700",
  },
];

export default function CloseFlockScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [closeStatus, setCloseStatus] = useState<CloseStatus>("sold");
  const [closeDate, setCloseDate] = useState(new Date().toISOString().split("T")[0]);
  const [closeReason, setCloseReason] = useState("");
  const [salePricePerKg, setSalePricePerKg] = useState("");
  const [totalBirdsSold, setTotalBirdsSold] = useState("");
  const [closingWeightKg, setClosingWeightKg] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const mutation = useMutation({
    mutationFn: (input: FlockCloseInput) => closeFlock(farmId!, flockId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.flocks(farmId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.flock(farmId!, flockId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.farmHouses(farmId!) });
      navigate(`/farms/${farmId}/flocks`, { replace: true });
    },
  });

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!closeDate) e.closeDate = t("flock.close.date_required");
    if (closeStatus === "sold") {
      if (!salePricePerKg || parseFloat(salePricePerKg) <= 0)
        e.salePricePerKg = t("flock.close.price_required");
      if (!totalBirdsSold || parseInt(totalBirdsSold, 10) < 1)
        e.totalBirdsSold = t("flock.close.birds_sold_required");
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const input: FlockCloseInput = {
      status: closeStatus,
      close_date: closeDate,
      close_reason: closeReason.trim() || undefined,
    };

    if (closeStatus === "sold") {
      input.sale_price_per_kg = salePricePerKg;
      input.total_birds_sold = parseInt(totalBirdsSold, 10);
      if (closingWeightKg) input.closing_weight_kg = closingWeightKg;
    } else if (closingWeightKg) {
      input.closing_weight_kg = closingWeightKg;
    }

    mutation.mutate(input);
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
        <div>
          <h1 className="text-lg font-bold text-gray-900">
            {t("flock.close.title")}
          </h1>
          <p className="text-xs text-gray-500">{t("flock.close.subtitle")}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-5 gap-5 overflow-y-auto">

        {/* Warning Banner */}
        <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3">
          <p className="text-sm text-amber-800 font-medium">
            {t("flock.close.warning")}
          </p>
        </div>

        {/* Close Status */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            {t("flock.close.reason_label")} *
          </label>
          <div className="flex flex-col gap-2">
            {CLOSE_OPTIONS.map((opt) => (
              <button
                key={opt.status}
                type="button"
                onClick={() => setCloseStatus(opt.status)}
                disabled={mutation.isPending}
                className={`
                  w-full text-left px-4 py-3 rounded-xl border-2 transition-colors
                  ${closeStatus === opt.status ? opt.color : "border-gray-200 bg-white text-gray-600"}
                `}
              >
                <div className="font-semibold text-sm">{t(opt.labelKey)}</div>
                <div className="text-xs mt-0.5 opacity-75">{t(opt.descKey)}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Close Date */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.close.date_label")} *
          </label>
          <input
            type="date"
            value={closeDate}
            onChange={(e) => setCloseDate(e.target.value)}
            max={today}
            disabled={mutation.isPending}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${errors.closeDate ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
          />
          {errors.closeDate && (
            <p className="mt-1.5 text-xs text-red-600">{errors.closeDate}</p>
          )}
        </div>

        {/* Sold-specific fields */}
        {closeStatus === "sold" && (
          <>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.close.price_label")} (KES/kg) *
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={salePricePerKg}
                onChange={(e) => setSalePricePerKg(e.target.value)}
                placeholder="185.00"
                min="0"
                step="0.01"
                disabled={mutation.isPending}
                className={`
                  w-full min-h-[48px] px-4 rounded-xl border text-base
                  focus:outline-none focus:ring-2 focus:ring-brand-600
                  ${errors.salePricePerKg ? "border-red-400 bg-red-50" : "border-gray-300"}
                `}
              />
              {errors.salePricePerKg && (
                <p className="mt-1.5 text-xs text-red-600">{errors.salePricePerKg}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.close.birds_sold_label")} *
              </label>
              <input
                type="number"
                inputMode="numeric"
                value={totalBirdsSold}
                onChange={(e) => setTotalBirdsSold(e.target.value)}
                placeholder="490"
                min="1"
                disabled={mutation.isPending}
                className={`
                  w-full min-h-[48px] px-4 rounded-xl border text-base
                  focus:outline-none focus:ring-2 focus:ring-brand-600
                  ${errors.totalBirdsSold ? "border-red-400 bg-red-50" : "border-gray-300"}
                `}
              />
              {errors.totalBirdsSold && (
                <p className="mt-1.5 text-xs text-red-600">{errors.totalBirdsSold}</p>
              )}
            </div>
          </>
        )}

        {/* Closing Weight (all close types) */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.close.weight_label")} (kg)
          </label>
          <input
            type="number"
            inputMode="decimal"
            value={closingWeightKg}
            onChange={(e) => setClosingWeightKg(e.target.value)}
            placeholder="2.150"
            min="0"
            step="0.001"
            disabled={mutation.isPending}
            className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
          />
          <p className="mt-1 text-xs text-gray-400">{t("flock.close.weight_hint")}</p>
        </div>

        {/* Close Reason / Notes */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.close.notes_label")}
          </label>
          <textarea
            value={closeReason}
            onChange={(e) => setCloseReason(e.target.value)}
            placeholder={t("flock.close.notes_placeholder")}
            rows={3}
            maxLength={1000}
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
          disabled={mutation.isPending}
          className="
            w-full min-h-[56px] rounded-xl bg-red-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {mutation.isPending
            ? t("common.loading")
            : t("flock.close.confirm")}
        </button>
      </form>
    </div>
  );
}
