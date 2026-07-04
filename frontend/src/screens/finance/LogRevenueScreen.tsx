/**
 * FI-05 — Log Revenue
 * /farms/:farmId/revenue/new
 *
 * Records a revenue event. Type-specific fields:
 *   eggs   → eggs_count, trays_count
 *   birds  → birds_sold (required), avg_weight_kg
 *   manure → quantity + unit
 *   other  → free-form
 *
 * Requires flock selection (revenue is always flock-scoped).
 */

import { useState, useEffect } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { logRevenue } from "@/api/finance";
import { listFlocks } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { RevenueRecordCreateInput, RevenueType } from "@/types";

const REVENUE_TYPES: { value: RevenueType; label: string; icon: string; desc: string }[] = [
  { value: "eggs", label: "Eggs", icon: "🥚", desc: "Egg tray or individual sales" },
  { value: "birds", label: "Birds", icon: "🐔", desc: "Live or dressed bird sales" },
  { value: "manure", label: "Manure", icon: "🌿", desc: "Litter / manure sales" },
  { value: "other", label: "Other", icon: "💰", desc: "Any other income" },
];

const PAYMENT_METHODS = [
  { value: "cash", label: "Cash" },
  { value: "mpesa", label: "M-Pesa" },
  { value: "bank_transfer", label: "Bank" },
  { value: "credit", label: "Credit" },
];

export default function LogRevenueScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const qc = useQueryClient();

  const preFlockId = searchParams.get("flockId") ?? "";

  // ── Form state ─────────────────────────────────────────────────────────────
  const [revenueType, setRevenueType] = useState<RevenueType>("eggs");
  const [flockId, setFlockId] = useState(preFlockId);
  const [revenueDate, setRevenueDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [amount, setAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  // Egg-specific
  const [eggsCount, setEggsCount] = useState("");
  const [traysCount, setTraysCount] = useState("");
  // Bird-specific
  const [birdsSold, setBirdsSold] = useState("");
  const [avgWeight, setAvgWeight] = useState("");
  // General
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Auto-compute amount from quantity × unit price
  useEffect(() => {
    if (quantity && unitPrice) {
      const computed = parseFloat(quantity) * parseFloat(unitPrice);
      if (!isNaN(computed)) setAmount(computed.toFixed(2));
    }
  }, [quantity, unitPrice]);

  // Load active flocks for flock selector
  const { data: flocks } = useQuery({
    queryKey: queryKeys.flocks(farmId!),
    queryFn: () => listFlocks(farmId!),
    enabled: !!farmId,
  });
  const activeFlocks = flocks?.filter((f) => f.status === "active") ?? [];

  const mutation = useMutation({
    mutationFn: (body: RevenueRecordCreateInput) => logRevenue(farmId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.revenue(farmId!) });
      qc.invalidateQueries({ queryKey: queryKeys.financeDashboard(farmId!) });
      if (flockId) {
        qc.invalidateQueries({
          queryKey: queryKeys.flockSnapshot(farmId!, flockId),
        });
      }
      navigate(-1);
    },
    onError: (err: Error) => {
      setError(err.message ?? t("common.error"));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!flockId) {
      setError(t("finance.revenue.flock_required"));
      return;
    }
    if (!amount || parseFloat(amount) <= 0) {
      setError(t("finance.revenue.amount_required"));
      return;
    }
    if (revenueType === "birds" && (!birdsSold || parseInt(birdsSold) <= 0)) {
      setError(t("finance.revenue.birds_sold_required"));
      return;
    }

    mutation.mutate({
      flock_id: flockId,
      revenue_type: revenueType,
      revenue_date: revenueDate,
      amount,
      quantity: quantity || undefined,
      unit: unit || undefined,
      unit_price: unitPrice || undefined,
      birds_sold: birdsSold ? parseInt(birdsSold) : undefined,
      avg_weight_kg: avgWeight || undefined,
      eggs_count: eggsCount ? parseInt(eggsCount) : undefined,
      trays_count: traysCount ? parseInt(traysCount) : undefined,
      buyer_name: buyerName.trim() || undefined,
      payment_method: paymentMethod as RevenueRecordCreateInput["payment_method"] || undefined,
      notes: notes.trim() || undefined,
    });
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-500">←</button>
          <h1 className="text-lg font-bold text-gray-900">{t("finance.revenue.log_title")}</h1>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="px-4 py-4 space-y-4">
        {/* Revenue Type */}
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <p className="text-xs font-medium text-gray-500 mb-3">{t("finance.revenue.type_label")}</p>
          <div className="grid grid-cols-2 gap-2">
            {REVENUE_TYPES.map((rt) => (
              <button
                key={rt.value}
                type="button"
                onClick={() => setRevenueType(rt.value)}
                className={`flex items-center gap-2 p-3 rounded-xl border text-left transition-all ${
                  revenueType === rt.value
                    ? "border-brand-500 bg-brand-50"
                    : "border-gray-100 bg-gray-50"
                }`}
              >
                <span className="text-xl">{rt.icon}</span>
                <div>
                  <p className="text-xs font-semibold text-gray-800">{rt.label}</p>
                  <p className="text-xs text-gray-400">{rt.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Flock selector (if not pre-selected) */}
        {!preFlockId && (
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <label className="text-xs font-medium text-gray-500 block mb-2">
              {t("finance.revenue.flock_label")} *
            </label>
            <select
              value={flockId}
              onChange={(e) => setFlockId(e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">{t("finance.revenue.flock_placeholder")}</option>
              {activeFlocks.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Core fields */}
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 space-y-4">
          {/* Date */}
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">
              {t("finance.revenue.date_label")}
            </label>
            <input
              type="date"
              value={revenueDate}
              onChange={(e) => setRevenueDate(e.target.value)}
              max={new Date().toISOString().split("T")[0]}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Type-specific fields */}
          {revenueType === "eggs" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">
                  {t("finance.revenue.eggs_count")}
                </label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={eggsCount}
                  onChange={(e) => setEggsCount(e.target.value)}
                  placeholder="0"
                  min="1"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">
                  {t("finance.revenue.trays_count")}
                </label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={traysCount}
                  onChange={(e) => {
                    setTraysCount(e.target.value);
                    const t30 = parseInt(e.target.value) * 30;
                    if (!isNaN(t30)) setEggsCount(String(t30));
                  }}
                  placeholder="0"
                  min="1"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>
          )}

          {revenueType === "birds" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">
                  {t("finance.revenue.birds_sold")} *
                </label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={birdsSold}
                  onChange={(e) => setBirdsSold(e.target.value)}
                  placeholder="0"
                  min="1"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">
                  {t("finance.revenue.avg_weight_kg")}
                </label>
                <input
                  type="number"
                  inputMode="decimal"
                  value={avgWeight}
                  onChange={(e) => setAvgWeight(e.target.value)}
                  placeholder="2.5"
                  min="0.1"
                  step="0.01"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>
          )}

          {(revenueType === "manure" || revenueType === "other") && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">
                  {t("finance.revenue.quantity")}
                </label>
                <input
                  type="number"
                  inputMode="decimal"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  placeholder="0"
                  min="0.01"
                  step="0.01"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">
                  {t("finance.revenue.unit")}
                </label>
                <input
                  type="text"
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  placeholder="kg, bag, litre"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>
          )}

          {/* Unit price (optional compute helper) */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {t("finance.revenue.unit_price")} (KES)
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                placeholder="0.00"
                min="0.01"
                step="0.01"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {t("finance.revenue.total_amount")} (KES) *
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                min="0.01"
                step="0.01"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-semibold"
              />
            </div>
          </div>
        </div>

        {/* Buyer + payment */}
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 space-y-4">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">
            {t("finance.revenue.section_buyer")}
          </p>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">
              {t("finance.revenue.buyer_name")}
            </label>
            <input
              type="text"
              value={buyerName}
              onChange={(e) => setBuyerName(e.target.value)}
              placeholder={t("finance.revenue.buyer_placeholder")}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">
              {t("finance.expense.payment_method_label")}
            </label>
            <div className="flex flex-wrap gap-2">
              {PAYMENT_METHODS.map((pm) => (
                <button
                  key={pm.value}
                  type="button"
                  onClick={() =>
                    setPaymentMethod((prev) =>
                      prev === pm.value ? "" : pm.value
                    )
                  }
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                    paymentMethod === pm.value
                      ? "bg-brand-600 text-white border-brand-600"
                      : "bg-gray-50 text-gray-600 border-gray-200"
                  }`}
                >
                  {pm.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">
              {t("finance.expense.notes_label")}
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("finance.revenue.notes_placeholder")}
              rows={2}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full bg-brand-600 text-white font-semibold py-3.5 rounded-xl text-sm disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {mutation.isPending ? (
            <>
              <Spinner size="sm" />
              {t("finance.revenue.saving")}
            </>
          ) : (
            t("finance.revenue.submit")
          )}
        </button>
      </form>
    </div>
  );
}
