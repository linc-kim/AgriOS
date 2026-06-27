/**
 * A-03/A-04 — Admin Farms & Subscriptions Screen
 * /admin/farms
 * List all farms, filter by plan, override subscription plan.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { adminAPI } from "@/api/admin";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { AdminFarmSummary } from "@/types";

const PLANS = ["free", "starter", "pro"];

function PlanBadge({ plan }: { plan: string }) {
  const colors: Record<string, string> = {
    free: "bg-gray-100 text-gray-600",
    starter: "bg-blue-100 text-blue-700",
    pro: "bg-brand-100 text-brand-700",
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${colors[plan] ?? "bg-gray-100 text-gray-600"}`}>
      {plan}
    </span>
  );
}

export default function AdminFarmsScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [overrideFarm, setOverrideFarm] = useState<AdminFarmSummary | null>(null);
  const [newPlan, setNewPlan] = useState("free");
  const [overrideReason, setOverrideReason] = useState("");
  const PAGE = 50;

  const { data, isLoading } = useQuery({
    queryKey: [...queryKeys.adminFarms(), search, planFilter, offset],
    queryFn: () =>
      adminAPI.listFarms({ search: search || undefined, plan_name: planFilter || undefined, limit: PAGE, offset }),
    staleTime: 30_000,
  });

  const overrideMut = useMutation({
    mutationFn: () =>
      adminAPI.overrideFarmPlan(overrideFarm!.id, { plan_name: newPlan, reason: overrideReason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.adminFarms() });
      setOverrideFarm(null);
      setOverrideReason("");
    },
  });

  const farms: AdminFarmSummary[] = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.farms.title")}</h1>
      <p className="text-sm text-gray-400 mb-6">{t("admin.farms.subtitle", { total })}</p>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
          placeholder={t("admin.farms.search_placeholder")}
          className="flex-1 max-w-xs rounded-xl border border-gray-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
        />
        <select
          value={planFilter}
          onChange={(e) => { setPlanFilter(e.target.value); setOffset(0); }}
          className="rounded-xl border border-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300"
        >
          <option value="">{t("admin.farms.all_plans")}</option>
          {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-gray-400 text-xs uppercase tracking-wide">
                <th className="text-left px-5 py-3">{t("admin.farms.col_name")}</th>
                <th className="text-center px-4 py-3">{t("admin.farms.col_plan")}</th>
                <th className="text-center px-4 py-3">{t("admin.farms.col_members")}</th>
                <th className="text-center px-4 py-3">{t("admin.farms.col_flocks")}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {farms.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-gray-400">
                    {t("admin.farms.empty")}
                  </td>
                </tr>
              ) : (
                farms.map((f) => (
                  <tr key={f.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-900">{f.name}</td>
                    <td className="px-4 py-3 text-center"><PlanBadge plan={f.subscription_plan} /></td>
                    <td className="px-4 py-3 text-center text-gray-600">{f.member_count}</td>
                    <td className="px-4 py-3 text-center text-gray-600">{f.active_flock_count}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => { setOverrideFarm(f); setNewPlan(f.subscription_plan); }}
                        className="text-xs text-brand-600 font-medium hover:text-brand-700"
                      >
                        {t("admin.farms.action_override_plan")}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Plan override modal */}
      {overrideFarm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 shadow-xl w-full max-w-sm mx-4">
            <h2 className="text-base font-bold text-gray-900 mb-1">
              {t("admin.farms.override_title")}
            </h2>
            <p className="text-sm text-gray-500 mb-4">{overrideFarm.name}</p>

            <label className="block text-xs font-medium text-gray-600 mb-1">
              {t("admin.farms.new_plan")}
            </label>
            <select
              value={newPlan}
              onChange={(e) => setNewPlan(e.target.value)}
              className="w-full mb-4 rounded-xl border border-gray-200 px-3 py-2 text-sm"
            >
              {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>

            <label className="block text-xs font-medium text-gray-600 mb-1">
              {t("admin.farms.override_reason")}
            </label>
            <textarea
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              rows={2}
              className="w-full mb-4 rounded-xl border border-gray-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-300"
              placeholder={t("admin.farms.override_reason_placeholder")}
            />

            <div className="flex gap-2">
              <button
                onClick={() => setOverrideFarm(null)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={() => overrideMut.mutate()}
                disabled={overrideMut.isPending || overrideReason.length < 5}
                className="flex-1 py-2 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {overrideMut.isPending ? t("common.saving") : t("admin.farms.confirm_override")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
