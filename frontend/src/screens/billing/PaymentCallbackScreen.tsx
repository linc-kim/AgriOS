/**
 * Billing — Payment Callback
 * /billing/callback?reference=...
 *
 * Where Paystack returns the customer after checkout. Verifies the payment via
 * the backend (which re-checks the amount/currency/metadata against the plan
 * and activates the subscription). This is a convenience confirmation — the
 * server-side webhook is the authoritative activation, so a missed verify here
 * does not lose the payment.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { billingAPI } from "@/api/billing";

export default function PaymentCallbackScreen() {
  const [params] = useSearchParams();
  const reference = params.get("reference") ?? params.get("trxref");

  const verify = useQuery({
    queryKey: ["billing", "verify", reference],
    queryFn: () => billingAPI.verify(reference as string),
    enabled: Boolean(reference),
    retry: 1,
  });

  const active = verify.data?.subscription_active;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-6 max-w-sm w-full text-center">
        {!reference && (
          <p className="text-sm text-red-700">Missing payment reference.</p>
        )}

        {reference && verify.isLoading && (
          <p className="text-sm text-gray-500">Confirming your payment…</p>
        )}

        {reference && verify.isError && (
          <>
            <div className="text-3xl mb-2">⏳</div>
            <h1 className="text-base font-bold text-gray-900">Payment received</h1>
            <p className="text-sm text-gray-500 mt-1">
              We couldn&apos;t confirm it just now, but it will be applied shortly.
            </p>
          </>
        )}

        {reference && verify.isSuccess && (
          <>
            <div className="text-3xl mb-2">{active ? "✅" : "⏳"}</div>
            <h1 className="text-base font-bold text-gray-900">
              {active ? "Subscription active" : "Payment pending"}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              {active
                ? "Your plan is now active for your organization."
                : "Your payment is being processed."}
            </p>
          </>
        )}

        <Link
          to="/dashboard"
          className="inline-block mt-5 px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold"
        >
          Go to dashboard
        </Link>
      </div>
    </div>
  );
}
