/**
 * A-06 — Admin Market Prices Screen
 * /admin/market
 * View all published market prices + publish new prices.
 * Uses existing /market/* endpoints.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { marketAPI } from "@/api/market";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";

const COMMODITIES = [
  "broiler_chick", "layer_chick", "maize", "soya_meal",
  "poultry_mash", "growers_mash", "layers_mash", "wheat_bran",
];

export default function AdminMarketScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const today = new Date().toISOString().split("T")[0];
  const [form, setForm] = useState({
    commodity: "broiler_chick",
    price_kes: "",
    unit: "per chick",
    county: "",
    source: "",
    valid_date: today,
  });

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.marketPrices(),
    queryFn: () => marketAPI.listLatestPrices(),
  });

  const createMut = useMutation({
    mutationFn: () => marketAPI.createPrice({ ...form }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.marketPrices() });
      setShowForm(false);
      setForm({ commodity: "broiler_chick", price_kes: "", unit: "per chick", county: "", source: "", valid_date: today });
    },
  });

  const prices = data?.items ?? [];

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.market.title")}</h1>
          <p className="text-sm text-gray-400">{t("admin.market.subtitle")}</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-brand-600 text-white rounded-xl text-sm font-medium hover:bg-brand-700"
        >
          + {t("admin.market.add_price")}
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-gray-400 text-xs uppercase tracking-wide">
                <th className="text-left px-5 py-3">{t("admin.market.col_commodity")}</th>
                <th className="text-right px-4 py-3">{t("admin.market.col_price")}</th>
                <th className="text-left px-4 py-3">{t("admin.market.col_unit")}</th>
                <th className="text-left px-4 py-3">{t("admin.market.col_county")}</th>
                <th className="text-left px-4 py-3">{t("admin.market.col_date")}</th>
              </tr>
            </thead>
            <tbody>
              {prices.length === 0 ? (
                <tr><td colSpan={5} className="text-center py-12 text-gray-400">{t("market.empty_title")}</td></tr>
              ) : (
                prices.map((p) => (
                  <tr key={p.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-900 capitalize">{p.commodity.replace(/_/g, " ")}</td>
                    <td className="px-4 py-3 text-right font-bold text-brand-700">KES {p.price_kes}</td>
                    <td className="px-4 py-3 text-gray-500">{p.unit}</td>
                    <td className="px-4 py-3 text-gray-500">{p.county ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{p.valid_date}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Add price modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 shadow-xl w-full max-w-sm">
            <h2 className="text-base font-bold text-gray-900 mb-4">{t("admin.market.add_price")}</h2>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("admin.market.field_commodity")}</label>
                <select value={form.commodity} onChange={(e) => setForm({ ...form, commodity: e.target.value })}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm">
                  {COMMODITIES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("admin.market.field_price")}</label>
                <input type="number" step="0.01" value={form.price_kes}
                  onChange={(e) => setForm({ ...form, price_kes: e.target.value })}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("admin.market.field_unit")}</label>
                <input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("admin.market.field_county")}</label>
                <input value={form.county} onChange={(e) => setForm({ ...form, county: e.target.value })}
                  placeholder={t("admin.market.field_county_placeholder")}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("admin.market.field_date")}</label>
                <input type="date" value={form.valid_date}
                  max={today}
                  onChange={(e) => setForm({ ...form, valid_date: e.target.value })}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm" />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button onClick={() => setShowForm(false)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">
                {t("common.cancel")}
              </button>
              <button onClick={() => createMut.mutate()}
                disabled={createMut.isPending || !form.price_kes}
                className="flex-1 py-2 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50">
                {createMut.isPending ? t("common.saving") : t("admin.market.publish")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
