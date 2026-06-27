/**
 * AGRIOS — Onboarding Screen O-03: Farm Setup
 * The first and only step after name collection for new users.
 * Creates the user's first farm on the Free plan.
 *
 * Design System: brand-600 = #076524 (Forest Green), navy-600 = #063491
 * Mobile-first: 48px min touch targets, no horizontal scroll.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFarm } from "@/api/farms";
import type { FarmCreateInput } from "@/types";
import { queryKeys } from "@/lib/queryClient";

const KENYA_COUNTIES = [
  "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu",
  "Garissa", "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho",
  "Kiambu", "Kilifi", "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale",
  "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit",
  "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru",
  "Nandi", "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu",
  "Siaya", "Taita-Taveta", "Tana River", "Tharaka-Nithi",
  "Trans Nzoia", "Turkana", "Uasin Gishu", "Vihiga", "Wajir",
  "West Pokot",
].sort();

export default function FarmSetupScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [county, setCounty] = useState("");
  const [location, setLocation] = useState("");
  const [nameError, setNameError] = useState("");

  const mutation = useMutation({
    mutationFn: (input: FarmCreateInput) => createFarm(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farms() });
      navigate("/", { replace: true });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || trimmed.length < 2) {
      setNameError("Farm name must be at least 2 characters");
      return;
    }
    setNameError("");
    mutation.mutate({
      name: trimmed,
      county: county || undefined,
      location: location.trim() || undefined,
    });
  }

  const isLoading = mutation.isPending;
  const serverError = mutation.error as Error | null;

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <div className="bg-brand-600 px-6 pt-14 pb-10">
        <div className="text-white/70 text-sm font-medium mb-1 uppercase tracking-widest">
          AGRIOS
        </div>
        <h1 className="text-white text-2xl font-bold leading-tight">
          {t("onboarding.farm.title")}
        </h1>
        <p className="text-white/80 text-sm mt-1">
          {t("onboarding.farm.subtitle")}
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-8 gap-6">

        {/* Farm name */}
        <div>
          <label
            htmlFor="farm-name"
            className="block text-sm font-semibold text-gray-700 mb-1.5"
          >
            {t("onboarding.farm.name_label")} *
          </label>
          <input
            id="farm-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("onboarding.farm.name_placeholder")}
            className={`
              w-full min-h-[48px] px-4 rounded-xl border text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent
              ${nameError ? "border-red-400 bg-red-50" : "border-gray-300 bg-white"}
            `}
            disabled={isLoading}
            autoFocus
            maxLength={255}
          />
          {nameError && (
            <p className="mt-1.5 text-sm text-red-600">{nameError}</p>
          )}
        </div>

        {/* County */}
        <div>
          <label
            htmlFor="county"
            className="block text-sm font-semibold text-gray-700 mb-1.5"
          >
            {t("onboarding.farm.county_label")}
          </label>
          <select
            id="county"
            value={county}
            onChange={(e) => setCounty(e.target.value)}
            className="
              w-full min-h-[48px] px-4 rounded-xl border border-gray-300 bg-white
              text-base text-gray-800
              focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent
            "
            disabled={isLoading}
          >
            <option value="">{t("onboarding.farm.county_placeholder")}</option>
            {KENYA_COUNTIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Location (optional) */}
        <div>
          <label
            htmlFor="location"
            className="block text-sm font-semibold text-gray-700 mb-1.5"
          >
            {t("onboarding.farm.location_label")}
          </label>
          <input
            id="location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder={t("onboarding.farm.location_placeholder")}
            className="
              w-full min-h-[48px] px-4 rounded-xl border border-gray-300 bg-white
              text-base
              focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent
            "
            disabled={isLoading}
            maxLength={255}
          />
        </div>

        {/* Server error */}
        {serverError && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">
              {serverError.message || t("common.error")}
            </p>
          </div>
        )}

        {/* Spacer to push button to bottom on short screens */}
        <div className="flex-1" />

        {/* Submit */}
        <button
          type="submit"
          disabled={isLoading || !name.trim()}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            text-base font-semibold
            disabled:opacity-50 disabled:cursor-not-allowed
            active:scale-[0.98] transition-transform
          "
        >
          {isLoading
            ? t("onboarding.farm.creating")
            : t("onboarding.farm.create")}
        </button>
      </form>
    </div>
  );
}
