/**
 * AGRIOS — Screen FM-04: Invite Team Member
 * Sends a farm membership invite to any Kenyan phone number.
 * The role selector is restricted to non-owner roles.
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { inviteFarmMember } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import type { FarmMemberInviteInput } from "@/types";

const ASSIGNABLE_ROLES = [
  { key: "farm_manager", label: "farm.roles.farm_manager" },
  { key: "vet_consultant", label: "farm.roles.vet_consultant" },
  { key: "farm_worker", label: "farm.roles.farm_worker" },
  { key: "viewer", label: "farm.roles.viewer" },
] as const;

export default function InviteMemberScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [phone, setPhone] = useState("");
  const [roleName, setRoleName] = useState<string>("farm_worker");
  const [phoneError, setPhoneError] = useState("");

  const mutation = useMutation({
    mutationFn: (input: FarmMemberInviteInput) =>
      inviteFarmMember(farmId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farmMembers(farmId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.farm(farmId!) });
      navigate(-1);
    },
  });

  function validatePhone(value: string): boolean {
    // Accepts +254XXXXXXXXX with 7 or 1 as first digit after country code
    const cleaned = value.replace(/\s/g, "");
    return /^\+254[17]\d{8}$/.test(cleaned);
  }

  function formatPhoneInput(value: string): string {
    // Auto-prefix +254 when user types local 07XX format
    const digits = value.replace(/\D/g, "");
    if (digits.startsWith("254")) {
      return "+" + digits;
    }
    if (digits.startsWith("0") && digits.length > 1) {
      return "+254" + digits.slice(1);
    }
    return value;
  }

  function handlePhoneChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value;
    const formatted = formatPhoneInput(raw);
    setPhone(formatted);
    if (phoneError) setPhoneError("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cleaned = phone.replace(/\s/g, "");
    if (!validatePhone(cleaned)) {
      setPhoneError(
        "Enter a valid Kenyan phone: +254 7XX XXX XXX or +254 1XX XXX XXX"
      );
      return;
    }
    mutation.mutate({ phone: cleaned, role_name: roleName as any });
  }

  const isLoading = mutation.isPending;
  const serverError = mutation.error as Error | null;

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
          {t("farm.invite.title")}
        </h1>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-6 gap-6">

        {/* Phone number */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("farm.invite.phone_label")} *
          </label>
          <input
            type="tel"
            inputMode="tel"
            value={phone}
            onChange={handlePhoneChange}
            placeholder={t("farm.invite.phone_placeholder")}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600
              ${phoneError ? "border-red-400 bg-red-50" : "border-gray-300"}
            `}
            disabled={isLoading}
            autoFocus
          />
          {phoneError && (
            <p className="mt-1.5 text-sm text-red-600">{phoneError}</p>
          )}
          <p className="mt-1.5 text-xs text-gray-400">
            They will receive an SMS invitation from AGRIOS.
          </p>
        </div>

        {/* Role selector */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            {t("farm.invite.role_label")} *
          </label>
          <div className="flex flex-col gap-2">
            {ASSIGNABLE_ROLES.map(({ key, label }) => (
              <label
                key={key}
                className={`
                  flex items-center gap-3 px-4 min-h-[52px] rounded-xl border cursor-pointer
                  ${roleName === key
                    ? "border-brand-600 bg-brand-50"
                    : "border-gray-200 bg-white"}
                `}
              >
                <input
                  type="radio"
                  name="role"
                  value={key}
                  checked={roleName === key}
                  onChange={() => setRoleName(key)}
                  className="accent-brand-600"
                  disabled={isLoading}
                />
                <span
                  className={`font-medium text-sm ${
                    roleName === key ? "text-brand-700" : "text-gray-700"
                  }`}
                >
                  {t(label)}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Server error */}
        {serverError && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">
              {serverError.message || t("common.error")}
            </p>
          </div>
        )}

        <div className="flex-1" />

        {/* Submit */}
        <button
          type="submit"
          disabled={isLoading || !phone.trim()}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50
            active:scale-[0.98] transition-transform
          "
        >
          {isLoading
            ? t("farm.invite.sending")
            : t("farm.invite.send_invite")}
        </button>
      </form>
    </div>
  );
}
