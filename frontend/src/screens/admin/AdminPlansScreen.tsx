/**
 * A-04 — Admin Subscription Plans Screen
 * /admin/plans
 * Shows all subscription plans with farm counts per plan.
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { adminAPI } from "@/api/admin";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";

function fmtKES(value: string): string {
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return num.toLocaleString("en-KE", { style: "currency", currency: "KES", minimumFractionDigits: 0 });
}

export default function AdminPlansScreen() {
  const { t } = useTranslation();

  const { data: plans, isLoading } = useQuery({
    queryKey: queryKeys.adminPlans(),
    queryFn: adminAPI.listPlans,
  });

  if (isLoading) {
    return <div className="flex justify-center items-center min-h-screen"><Spinner size="lg" /></div>;
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.plans.title")}</h1>
      <p className="text-sm text-gray-400 mb-8">{t("admin.plans.subtitle")}</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {(plans ?? []).map((plan) => (
          <div key={plan.id} className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-1">
              {plan.name}
            </p>
            <p className="text-xl font-bold text-gray-900">{plan.display_name}</p>
            <p className="text-2xl font-bold text-brand-700 mt-2">
              {plan.price_kes === "0.00" ? t("admin.plans.free") : fmtKES(plan.price_kes)}
              {plan.price_kes !== "0.00" && (
                <span className="text-sm font-normal text-gray-400"> /mo</span>
              )}
            </p>
            <div className="mt-4 pt-4 border-t border-gray-50">
              <p className="text-3xl font-bold text-gray-900">{plan.farm_count.toLocaleString()}</p>
              <p className="text-xs text-gray-400 mt-0.5">{t("admin.plans.farms_on_plan")}</p>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-8 text-xs text-gray-400">{t("admin.plans.note")}</p>
    </div>
  );
}
