/**
 * Greena — Screen FM-02: Farm Edit
 * Allows the farm_owner or farm_manager to update farm details.
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getFarm, updateFarm } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import type { FarmUpdateInput } from "@/types";

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

export default function FarmEditScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [county, setCounty] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");

  const { data: farm } = useQuery({
    queryKey: queryKeys.farm(farmId!),
    queryFn: () => getFarm(farmId!),
    enabled: !!farmId,
  });

  // Populate fields when farm loads
  useEffect(() => {
    if (farm) {
      setName(farm.name);
      setCounty(farm.county ?? "");
      setLocation(farm.location ?? "");
      setDescription(farm.description ?? "");
    }
  }, [farm]);

  const mutation = useMutation({
    mutationFn: (input: FarmUpdateInput) => updateFarm(farmId!, input),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.farm(farmId!), updated);
      queryClient.invalidateQueries({ queryKey: queryKeys.farms() });
      navigate(`/farms/${farmId}`, { replace: true });
    },
  });

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || trimmed.length < 2) return;
    mutation.mutate({
      name: trimmed,
      county: county || undefined,
      location: location.trim() || undefined,
      description: description.trim() || undefined,
    });
  }

  const isLoading = mutation.isPending;
  const serverError = mutation.error as Error | null;

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-12 pb-4 border-b border-gray-100">
        <button
          onClick={() => navigate(-1)}
          className="min-h-[48px] min-w-[48px] flex items-center justify-center rounded-xl text-gray-600"
        >
          ←
        </button>
        <h1 className="text-lg font-bold text-gray-900">{t("farm.edit.title")}</h1>
      </div>

      {/* Form */}
      <form onSubmit={handleSave} className="flex flex-col flex-1 px-6 py-6 gap-5">
        {/* Name */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("onboarding.farm.name_label")} *
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="
              w-full min-h-[48px] px-4 rounded-xl border border-gray-300
              text-base focus:outline-none focus:ring-2 focus:ring-brand-600
            "
            disabled={isLoading}
            maxLength={255}
          />
        </div>

        {/* County */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("onboarding.farm.county_label")}
          </label>
          <select
            value={county}
            onChange={(e) => setCounty(e.target.value)}
            className="
              w-full min-h-[48px] px-4 rounded-xl border border-gray-300
              text-base focus:outline-none focus:ring-2 focus:ring-brand-600
            "
            disabled={isLoading}
          >
            <option value="">— None —</option>
            {KENYA_COUNTIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        {/* Location */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("onboarding.farm.location_label")}
          </label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder={t("onboarding.farm.location_placeholder")}
            className="
              w-full min-h-[48px] px-4 rounded-xl border border-gray-300
              text-base focus:outline-none focus:ring-2 focus:ring-brand-600
            "
            disabled={isLoading}
            maxLength={255}
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            Description (optional)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="
              w-full px-4 py-3 rounded-xl border border-gray-300
              text-base focus:outline-none focus:ring-2 focus:ring-brand-600
              resize-none
            "
            disabled={isLoading}
            maxLength={1000}
          />
        </div>

        {serverError && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">{serverError.message}</p>
          </div>
        )}

        <div className="flex-1" />

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="
              flex-1 min-h-[52px] rounded-xl border border-gray-300
              text-gray-700 font-semibold text-base
            "
            disabled={isLoading}
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            disabled={isLoading || !name.trim()}
            className="
              flex-1 min-h-[52px] rounded-xl bg-brand-600 text-white
              font-semibold text-base
              disabled:opacity-50
            "
          >
            {isLoading ? t("farm.edit.saving") : t("farm.edit.save")}
          </button>
        </div>
      </form>
    </div>
  );
}
