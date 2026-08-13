/**
 * Billing — Trial & Referral Dashboard
 * /billing/referral
 *
 * Trial countdown, this org's shareable referral code, referral entry (during
 * onboarding or within 48h), the referrer reward status, and the credit balance
 * with ledger history.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { billingAPI } from "@/api/billing";
import { useShellStore } from "@/stores/shellStore";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">{title}</h2>
      {children}
    </div>
  );
}

function ReferralEntry({ orgId }: { orgId: string }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () => billingAPI.submitReferral(orgId, code.trim()),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["billing", "referral", orgId] });
    },
    onError: () => setError("That referral code could not be applied. Check it and try again."),
  });

  return (
    <div>
      <p className="text-sm text-gray-500 mb-3">
        Were you referred by someone already using Greena? Enter their code.
      </p>
      <div className="flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="GREENA-XXXXXX"
          className="flex-1 rounded-xl border border-gray-200 px-3 py-2 text-sm"
        />
        <button
          type="button"
          disabled={!code.trim() || submit.isPending}
          onClick={() => submit.mutate()}
          className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-semibold disabled:opacity-50"
        >
          Apply
        </button>
      </div>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
    </div>
  );
}

export default function ReferralDashboardScreen() {
  const orgId = useShellStore((s) => s.currentOrgId);

  const trial = useQuery({
    queryKey: ["billing", "trial", orgId],
    queryFn: () => billingAPI.getTrialStatus(orgId as string),
    enabled: Boolean(orgId),
  });
  const referral = useQuery({
    queryKey: ["billing", "referral", orgId],
    queryFn: () => billingAPI.getReferralStatus(orgId as string),
    enabled: Boolean(orgId),
  });
  const credits = useQuery({
    queryKey: ["billing", "credits", orgId],
    queryFn: () => billingAPI.getCredits(orgId as string),
    enabled: Boolean(orgId),
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100 px-4 py-4">
        <h1 className="text-lg font-bold text-gray-900">Trial &amp; Referrals</h1>
        <p className="text-xs text-gray-400 mt-0.5">Your plan, referral code, and credits</p>
      </div>

      <div className="p-4 space-y-4">
        {!orgId && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-800">
            Select an organization to view billing.
          </div>
        )}

        {/* Trial countdown */}
        {trial.data?.is_trial && (
          <div className="bg-brand-600 text-white rounded-2xl p-5">
            <p className="text-sm opacity-90">Professional trial</p>
            <p className="text-2xl font-bold mt-1">{trial.data.days_remaining} days left</p>
            <p className="text-xs opacity-80 mt-1">
              Subscribe before it ends to keep full access — otherwise you move to Free.
            </p>
          </div>
        )}

        {/* Your code */}
        <Card title="Your referral code">
          <p className="text-lg font-bold text-gray-900 tracking-wide">
            {referral.data?.referral_code ?? "—"}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            Share this code. A friend gets a discount on their first Starter payment, and you earn
            KSh 100 in credit once they pay.
          </p>
        </Card>

        {/* Referral entry / status */}
        <Card title="Referred by a friend?">
          {referral.data?.has_referral ? (
            <p className="text-sm text-gray-700">
              Referral applied. Reward status:{" "}
              <span className="font-semibold">{referral.data.reward_status}</span>.
            </p>
          ) : referral.data?.entry_open ? (
            <>
              <ReferralEntry orgId={orgId as string} />
              <p className="text-xs text-gray-400 mt-3">
                You can enter a referral code during onboarding or within 48 hours of creating your
                account. After that, referral entry closes.
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-500">The 48-hour referral entry window has closed.</p>
          )}
        </Card>

        {/* Credits */}
        <Card title="Greena credit">
          <p className="text-2xl font-bold text-gray-900">
            KSh {(credits.data?.balance_kes ?? 0).toLocaleString()}
          </p>
          <div className="mt-3 divide-y divide-gray-50">
            {(credits.data?.entries ?? []).map((e, i) => (
              <div key={i} className="flex items-center justify-between py-2 text-sm">
                <span className="text-gray-500">{e.source.replace("_", " ")}</span>
                <span className={e.amount_kes >= 0 ? "text-green-600" : "text-red-600"}>
                  {e.amount_kes >= 0 ? "+" : ""}
                  KSh {e.amount_kes.toLocaleString()}
                </span>
              </div>
            ))}
            {(credits.data?.entries.length ?? 0) === 0 && (
              <p className="text-sm text-gray-400 py-2">No credit yet.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
