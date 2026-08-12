/**
 * Billing — Checkout / Upgrade
 * /billing
 *
 * Lists the subscription plans and starts a Paystack payment for the selected
 * paid plan. Prices come from the backend (never hardcoded here). On success
 * the browser is redirected to Paystack's authorization URL; the customer
 * returns to /billing/callback where the payment is verified.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { billingAPI, type Plan } from "@/api/billing";
import { useShellStore } from "@/stores/shellStore";

function formatPrice(plan: Plan): string {
  if (plan.price_kes === 0) return "Free";
  if (plan.price_kes < 0) return "Custom";
  return `KSh ${plan.price_kes.toLocaleString()}`;
}

export default function BillingCheckoutScreen() {
  const currentOrgId = useShellStore((s) => s.currentOrgId);

  const plansQuery = useQuery({
    queryKey: ["billing", "plans"],
    queryFn: billingAPI.listPlans,
  });

  const initialize = useMutation({
    mutationFn: (planId: string) =>
      billingAPI.initialize({
        organization_id: currentOrgId as string,
        plan_id: planId,
        callback_url: `${window.location.origin}/billing/callback`,
      }),
    onSuccess: (result) => {
      // Full-page redirect to Paystack's hosted checkout.
      window.location.href = result.authorization_url;
    },
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100 px-4 py-4">
        <h1 className="text-lg font-bold text-gray-900">Plans &amp; Billing</h1>
        <p className="text-xs text-gray-400 mt-0.5">Choose a plan for your organization</p>
      </div>

      <div className="p-4 space-y-4">
        {!currentOrgId && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-800">
            Select or create an organization before subscribing.
          </div>
        )}

        {plansQuery.isLoading && (
          <div className="text-sm text-gray-400">Loading plans…</div>
        )}
        {plansQuery.isError && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-700">
            Could not load plans. Please try again.
          </div>
        )}

        {initialize.isError && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-700">
            Could not start the payment. Please try again.
          </div>
        )}

        {plansQuery.data?.map((plan) => (
          <div
            key={plan.id}
            className="bg-white rounded-2xl border border-gray-100 p-5 flex items-center justify-between"
          >
            <div>
              <h2 className="text-base font-bold text-gray-900">{plan.display_name}</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                {formatPrice(plan)}
                {plan.price_kes > 0 && <span className="text-gray-400"> / month</span>}
              </p>
            </div>

            {plan.is_self_serve ? (
              <button
                type="button"
                disabled={!currentOrgId || initialize.isPending}
                onClick={() => initialize.mutate(plan.id)}
                className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold disabled:opacity-50"
              >
                {initialize.isPending && initialize.variables === plan.id
                  ? "Starting…"
                  : "Subscribe"}
              </button>
            ) : plan.price_kes < 0 ? (
              <span className="text-sm font-medium text-gray-500">Contact sales</span>
            ) : (
              <span className="text-sm font-medium text-gray-400">Included</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
