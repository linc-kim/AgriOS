/**
 * FI-03 — Log Expense
 * /farms/:farmId/expenses/new
 *
 * Form to record a new expense.
 * Categories loaded from API (system + custom).
 * Optional flock linking via query param ?flockId=
 */

import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { listExpenseCategories, logExpense } from "@/api/finance";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { ExpenseCreateInput } from "@/types";

const PAYMENT_METHODS = [
  { value: "cash", label: "Cash" },
  { value: "mpesa", label: "M-Pesa" },
  { value: "bank_transfer", label: "Bank Transfer" },
  { value: "credit", label: "Credit" },
];

export default function LogExpenseScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const qc = useQueryClient();

  const preFlockId = searchParams.get("flockId") ?? undefined;

  // ── Form state ────────────────────────────────────────────────────────────
  const [categoryId, setCategoryId] = useState("");
  const [expenseDate, setExpenseDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [supplier, setSupplier] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  // ── Load categories ───────────────────────────────────────────────────────
  const { data: categories, isLoading: catLoading } = useQuery({
    queryKey: queryKeys.expenseCategories(farmId!),
    queryFn: () => listExpenseCategories(farmId!),
    enabled: !!farmId,
  });

  // ── Mutation ──────────────────────────────────────────────────────────────
  const mutation = useMutation({
    mutationFn: (body: ExpenseCreateInput) => logExpense(farmId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.expenses(farmId!) });
      qc.invalidateQueries({ queryKey: queryKeys.financeDashboard(farmId!) });
      if (preFlockId) {
        qc.invalidateQueries({
          queryKey: queryKeys.flockSnapshot(farmId!, preFlockId),
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

    if (!categoryId) {
      setError(t("finance.expense.category_required"));
      return;
    }
    if (!amount || parseFloat(amount) <= 0) {
      setError(t("finance.expense.amount_required"));
      return;
    }
    if (!description.trim()) {
      setError(t("finance.expense.description_required"));
      return;
    }

    mutation.mutate({
      category_id: categoryId,
      flock_id: preFlockId,
      expense_date: expenseDate,
      amount,
      description: description.trim(),
      payment_method: paymentMethod as ExpenseCreateInput["payment_method"] || undefined,
      supplier: supplier.trim() || undefined,
      notes: notes.trim() || undefined,
    });
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-500">←</button>
          <h1 className="text-lg font-bold text-gray-900">{t("finance.expense.log_title")}</h1>
        </div>
      </div>

      {catLoading ? (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="px-4 py-4 space-y-4">
          {/* Category selector */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <p className="text-xs font-medium text-gray-500 mb-3">{t("finance.expense.category_label")}</p>
            {catLoading ? (
              <Spinner size="sm" />
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {categories?.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setCategoryId(cat.id)}
                    className={`flex flex-col items-center p-2.5 rounded-xl border transition-all text-center ${
                      categoryId === cat.id
                        ? "border-brand-500 bg-brand-50"
                        : "border-gray-100 bg-gray-50"
                    }`}
                  >
                    <span className="text-xl">{cat.icon ?? "📦"}</span>
                    <span className="text-xs text-gray-700 mt-1 leading-tight">
                      {cat.name}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Core fields */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 space-y-4">
            {/* Date */}
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {t("finance.expense.date_label")}
              </label>
              <input
                type="date"
                value={expenseDate}
                onChange={(e) => setExpenseDate(e.target.value)}
                max={new Date().toISOString().split("T")[0]}
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {/* Amount */}
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {t("finance.expense.amount_label")} (KES)
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                min="0.01"
                step="0.01"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {/* Description */}
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {t("finance.expense.description_label")}
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("finance.expense.description_placeholder")}
                maxLength={300}
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          {/* Optional details */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 space-y-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">
              {t("finance.expense.section_optional")}
            </p>

            {/* Payment method */}
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

            {/* Supplier */}
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {t("finance.expense.supplier_label")}
              </label>
              <input
                type="text"
                value={supplier}
                onChange={(e) => setSupplier(e.target.value)}
                placeholder={t("finance.expense.supplier_placeholder")}
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {t("finance.expense.notes_label")}
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("finance.expense.notes_placeholder")}
                rows={3}
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={mutation.isPending}
            className="w-full bg-brand-600 text-white font-semibold py-3.5 rounded-xl text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {mutation.isPending ? (
              <>
                <Spinner size="sm" />
                {t("finance.expense.saving")}
              </>
            ) : (
              t("finance.expense.submit")
            )}
          </button>
        </form>
      )}
    </div>
  );
}
