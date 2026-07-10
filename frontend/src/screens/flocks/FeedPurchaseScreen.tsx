/**
 * Greena — Screen FL-08: Feed Purchase
 * Records a feed buying event at farm or flock level.
 * Shows live total cost calculation (quantity × price).
 * Requires OPS_FEED_LOG (farm_owner, farm_manager, farm_worker).
 */

import { useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFeedPurchase } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import type { FeedPurchaseInput } from "@/types";

const FEED_TYPES = [
  "Starter",
  "Grower",
  "Finisher",
  "Layer Mash",
  "Pre-Lay",
  "Chick Mash",
  "Growers Mash",
  "Concentrates",
  "Other",
];

export default function FeedPurchaseScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  // Optional: flockId passed via route state when accessed from flock detail
  const preselectedFlockId = (location.state as { flockId?: string } | null)
    ?.flockId ?? "";

  const today = new Date().toISOString().split("T")[0];

  const [purchaseDate, setPurchaseDate] = useState(today);
  const [feedType, setFeedType] = useState("");
  const [customFeedType, setCustomFeedType] = useState("");
  const [quantityKg, setQuantityKg] = useState("");
  const [pricePerKg, setPricePerKg] = useState("");
  const [supplier, setSupplier] = useState("");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Live total cost computation
  const qty = parseFloat(quantityKg) || 0;
  const price = parseFloat(pricePerKg) || 0;
  const totalCost = qty * price;
  const showTotal = qty > 0 && price > 0;

  const mutation = useMutation({
    mutationFn: (input: FeedPurchaseInput) => createFeedPurchase(farmId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feedPurchases(farmId!) });
      navigate(-1);
    },
  });

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!feedType) e.feedType = t("flock.feed.type_required");
    if (feedType === "Other" && !customFeedType.trim())
      e.feedType = t("flock.feed.type_custom_required");
    const q = parseFloat(quantityKg);
    if (!quantityKg || isNaN(q) || q <= 0)
      e.quantityKg = t("flock.feed.qty_required");
    const p = parseFloat(pricePerKg);
    if (!pricePerKg || isNaN(p) || p < 0)
      e.pricePerKg = t("flock.feed.price_required");
    if (!purchaseDate) e.purchaseDate = t("flock.feed.date_required");
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const resolvedType = feedType === "Other" ? customFeedType.trim() : feedType;

    mutation.mutate({
      flock_id: preselectedFlockId || undefined,
      purchase_date: purchaseDate,
      feed_type: resolvedType,
      quantity_kg: quantityKg,
      price_per_kg: pricePerKg,
      supplier: supplier.trim() || undefined,
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
          {t("flock.feed.title")}
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-5 gap-5 overflow-y-auto">

        {/* Purchase Date */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.feed.date_label")} *
          </label>
          <input
            type="date"
            value={purchaseDate}
            onChange={(e) => setPurchaseDate(e.target.value)}
            max={today}
            disabled={mutation.isPending}
            className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
          />
        </div>

        {/* Feed Type */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            {t("flock.feed.type_label")} *
          </label>
          <div className="grid grid-cols-2 gap-2">
            {FEED_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setFeedType(type)}
                disabled={mutation.isPending}
                className={`
                  min-h-[44px] rounded-xl border text-sm font-medium transition-colors
                  ${feedType === type
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-600"
                  }
                `}
              >
                {type}
              </button>
            ))}
          </div>
          {feedType === "Other" && (
            <input
              type="text"
              value={customFeedType}
              onChange={(e) => setCustomFeedType(e.target.value)}
              placeholder={t("flock.feed.type_custom_placeholder")}
              maxLength={100}
              className="mt-2 w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              disabled={mutation.isPending}
            />
          )}
          {errors.feedType && (
            <p className="mt-1.5 text-xs text-red-600">{errors.feedType}</p>
          )}
        </div>

        {/* Quantity & Price */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {t("flock.feed.section_amount")}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.feed.quantity_kg")} *
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={quantityKg}
                onChange={(e) => setQuantityKg(e.target.value)}
                placeholder="100"
                min="0.001"
                step="0.001"
                disabled={mutation.isPending}
                className={`
                  w-full min-h-[48px] px-4 rounded-xl border text-base
                  focus:outline-none focus:ring-2 focus:ring-brand-600
                  ${errors.quantityKg ? "border-red-400 bg-red-50" : "border-gray-300"}
                `}
              />
              {errors.quantityKg && (
                <p className="mt-1 text-xs text-red-600">{errors.quantityKg}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.feed.price_per_kg")} (KES) *
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={pricePerKg}
                onChange={(e) => setPricePerKg(e.target.value)}
                placeholder="55.00"
                min="0"
                step="0.01"
                disabled={mutation.isPending}
                className={`
                  w-full min-h-[48px] px-4 rounded-xl border text-base
                  focus:outline-none focus:ring-2 focus:ring-brand-600
                  ${errors.pricePerKg ? "border-red-400 bg-red-50" : "border-gray-300"}
                `}
              />
              {errors.pricePerKg && (
                <p className="mt-1 text-xs text-red-600">{errors.pricePerKg}</p>
              )}
            </div>
          </div>

          {/* Live Total */}
          {showTotal && (
            <div className="mt-3 rounded-xl bg-brand-50 border border-brand-100 px-4 py-3 flex items-center justify-between">
              <span className="text-sm text-brand-700 font-medium">
                {t("flock.feed.total_cost")}
              </span>
              <span className="text-lg font-bold text-brand-700">
                KES {totalCost.toLocaleString("en-KE", { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>

        {/* Supplier */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.feed.supplier")}
          </label>
          <input
            type="text"
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
            placeholder={t("flock.feed.supplier_placeholder")}
            maxLength={255}
            disabled={mutation.isPending}
            className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
          />
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.feed.notes")}
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t("flock.feed.notes_placeholder")}
            rows={2}
            maxLength={2000}
            disabled={mutation.isPending}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600 resize-none"
          />
        </div>

        {preselectedFlockId && (
          <div className="rounded-xl bg-gray-50 border border-gray-200 px-4 py-2">
            <p className="text-xs text-gray-500">
              {t("flock.feed.linked_to_flock")}
            </p>
          </div>
        )}

        {mutation.error && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">{(mutation.error as Error).message}</p>
          </div>
        )}

        <div className="flex-1" />

        <button
          type="submit"
          disabled={mutation.isPending || !feedType || !quantityKg || !pricePerKg}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {mutation.isPending ? t("common.loading") : t("flock.feed.submit")}
        </button>
      </form>
    </div>
  );
}
