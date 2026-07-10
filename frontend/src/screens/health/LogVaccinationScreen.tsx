/**
 * Greena — Screen H-03: Log Vaccination
 * Record a vaccination event for a specific flock.
 * Includes: vaccine selector, administration details, next dose planning.
 *
 * Requires HEALTH_VACCINATION_LOG (farm_owner, farm_manager, vet_consultant).
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { logVaccination, listVaccinations } from "@/api/health";
import { queryKeys } from "@/lib/queryClient";
import type { VaccinationRecordCreateInput } from "@/types";

const COMMON_VACCINES = [
  "Newcastle Disease (ND)",
  "Infectious Bronchitis (IB)",
  "ND+IB Combined",
  "Gumboro (IBD)",
  "Marek's Disease",
  "Fowlpox",
  "Avian Encephalomyelitis (AE)",
  "Infectious Laryngotracheitis (ILT)",
  "Fowl Cholera",
  "Salmonella",
  "Other",
];

const ADMIN_ROUTES = [
  { key: "drinking_water", label: "Drinking Water" },
  { key: "spray", label: "Spray" },
  { key: "eye_drop", label: "Eye Drop" },
  { key: "injection", label: "Injection" },
  { key: "wing_stab", label: "Wing Stab" },
  { key: "oral", label: "Oral" },
];

export default function LogVaccinationScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const today = new Date().toISOString().split("T")[0];

  // Form state
  const [vaccineName, setVaccineName] = useState("");
  const [customVaccineName, setCustomVaccineName] = useState("");
  const [vaccineBrand, setVaccineBrand] = useState("");
  const [doseNumber, setDoseNumber] = useState("1");
  const [administeredDate, setAdministeredDate] = useState(today);
  const [route, setRoute] = useState("");
  const [batchNumber, setBatchNumber] = useState("");
  const [nextDueDate, setNextDueDate] = useState("");
  const [nextVaccineName, setNextVaccineName] = useState("");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Load vaccination history to show last dose context
  const { data: history = [] } = useQuery({
    queryKey: queryKeys.flockVaccinations(farmId!, flockId!),
    queryFn: () => listVaccinations(farmId!, flockId!, { limit: 5 }),
    enabled: !!farmId && !!flockId,
  });
  const lastVaccination = history[0] ?? null;

  const mutation = useMutation({
    mutationFn: (input: VaccinationRecordCreateInput) =>
      logVaccination(farmId!, flockId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.flockVaccinations(farmId!, flockId!),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.healthSchedule(farmId!),
      });
      navigate(-1);
    },
  });

  function validate(): boolean {
    const e: Record<string, string> = {};
    const resolved = vaccineName === "Other" ? customVaccineName.trim() : vaccineName;
    if (!resolved) e.vaccineName = t("health.log.vaccine_required");
    if (!administeredDate) e.administeredDate = t("health.log.date_required");
    const dose = parseInt(doseNumber, 10);
    if (isNaN(dose) || dose < 1 || dose > 10) e.doseNumber = t("health.log.dose_invalid");
    if (nextDueDate && nextDueDate <= administeredDate) {
      e.nextDueDate = t("health.log.next_due_after_admin");
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const resolved = vaccineName === "Other" ? customVaccineName.trim() : vaccineName;
    mutation.mutate({
      vaccine_name: resolved,
      vaccine_brand: vaccineBrand.trim() || undefined,
      dose_number: parseInt(doseNumber, 10),
      administered_date: administeredDate,
      route: route || undefined,
      batch_number: batchNumber.trim() || undefined,
      next_due_date: nextDueDate || undefined,
      next_vaccine_name: nextVaccineName.trim() || undefined,
      notes: notes.trim() || undefined,
    });
  }

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
          {t("health.log.title")}
        </h1>
      </div>

      {/* Previous vaccination context */}
      {lastVaccination && (
        <div className="mx-4 mt-4 rounded-xl bg-gray-50 border border-gray-200 px-4 py-3">
          <p className="text-xs text-gray-500 font-medium mb-1">
            {t("health.log.last_vaccination")}
          </p>
          <p className="text-sm text-gray-700">
            {lastVaccination.vaccine_name} ·{" "}
            {new Date(lastVaccination.administered_date).toLocaleDateString()}
            {lastVaccination.next_due_date && (
              <>
                {" · "}
                <span className={lastVaccination.is_overdue ? "text-red-600 font-semibold" : "text-gray-500"}>
                  {t("health.log.next_due")}: {new Date(lastVaccination.next_due_date).toLocaleDateString()}
                </span>
              </>
            )}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-5 gap-5 overflow-y-auto">

        {/* Vaccine Selection */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            {t("health.log.vaccine_label")} *
          </label>
          <div className="grid grid-cols-2 gap-2">
            {COMMON_VACCINES.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setVaccineName(name)}
                disabled={mutation.isPending}
                className={`
                  min-h-[44px] px-3 rounded-xl border text-xs font-medium transition-colors text-left
                  ${vaccineName === name
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-600"
                  }
                `}
              >
                {name}
              </button>
            ))}
          </div>
          {vaccineName === "Other" && (
            <input
              type="text"
              value={customVaccineName}
              onChange={(e) => setCustomVaccineName(e.target.value)}
              placeholder={t("health.log.vaccine_custom_placeholder")}
              maxLength={200}
              className="mt-2 w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              disabled={mutation.isPending}
            />
          )}
          {errors.vaccineName && (
            <p className="mt-1.5 text-xs text-red-600">{errors.vaccineName}</p>
          )}
        </div>

        {/* Administration date + dose number */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1.5">
              {t("health.log.date_label")} *
            </label>
            <input
              type="date"
              value={administeredDate}
              onChange={(e) => setAdministeredDate(e.target.value)}
              max={today}
              disabled={mutation.isPending}
              className={`
                w-full min-h-[48px] px-3 rounded-xl border text-sm
                focus:outline-none focus:ring-2 focus:ring-brand-600
                ${errors.administeredDate ? "border-red-400 bg-red-50" : "border-gray-300"}
              `}
            />
            {errors.administeredDate && (
              <p className="mt-1 text-xs text-red-600">{errors.administeredDate}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1.5">
              {t("health.log.dose_number")} *
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={doseNumber}
              onChange={(e) => setDoseNumber(e.target.value)}
              min={1}
              max={10}
              disabled={mutation.isPending}
              className={`
                w-full min-h-[48px] px-3 rounded-xl border text-sm
                focus:outline-none focus:ring-2 focus:ring-brand-600
                ${errors.doseNumber ? "border-red-400 bg-red-50" : "border-gray-300"}
              `}
            />
            {errors.doseNumber && (
              <p className="mt-1 text-xs text-red-600">{errors.doseNumber}</p>
            )}
          </div>
        </div>

        {/* Administration route */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            {t("health.log.route_label")}
          </label>
          <div className="flex flex-wrap gap-2">
            {ADMIN_ROUTES.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setRoute(route === key ? "" : key)}
                disabled={mutation.isPending}
                className={`
                  min-h-[36px] px-3 rounded-xl border text-xs font-medium transition-colors
                  ${route === key
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-600"
                  }
                `}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Brand + Batch — optional details */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {t("health.log.section_optional")}
          </div>
          <div className="space-y-3">
            <input
              type="text"
              value={vaccineBrand}
              onChange={(e) => setVaccineBrand(e.target.value)}
              placeholder={t("health.log.brand_placeholder")}
              maxLength={200}
              disabled={mutation.isPending}
              className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
            />
            <input
              type="text"
              value={batchNumber}
              onChange={(e) => setBatchNumber(e.target.value)}
              placeholder={t("health.log.batch_placeholder")}
              maxLength={100}
              disabled={mutation.isPending}
              className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
            />
          </div>
        </div>

        {/* Next dose planning */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {t("health.log.section_next_dose")}
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("health.log.next_due_label")}
              </label>
              <input
                type="date"
                value={nextDueDate}
                onChange={(e) => setNextDueDate(e.target.value)}
                min={administeredDate || today}
                disabled={mutation.isPending}
                className={`
                  w-full min-h-[48px] px-4 rounded-xl border text-base
                  focus:outline-none focus:ring-2 focus:ring-brand-600
                  ${errors.nextDueDate ? "border-red-400 bg-red-50" : "border-gray-300"}
                `}
              />
              {errors.nextDueDate && (
                <p className="mt-1 text-xs text-red-600">{errors.nextDueDate}</p>
              )}
              <p className="mt-1 text-xs text-gray-400">{t("health.log.next_due_hint")}</p>
            </div>

            {nextDueDate && (
              <input
                type="text"
                value={nextVaccineName}
                onChange={(e) => setNextVaccineName(e.target.value)}
                placeholder={t("health.log.next_vaccine_placeholder")}
                maxLength={200}
                disabled={mutation.isPending}
                className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              />
            )}
          </div>
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("health.log.notes")}
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t("health.log.notes_placeholder")}
            rows={2}
            maxLength={2000}
            disabled={mutation.isPending}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600 resize-none"
          />
        </div>

        {mutation.error && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-700">{(mutation.error as Error).message}</p>
          </div>
        )}

        <div className="flex-1" />

        <button
          type="submit"
          disabled={mutation.isPending || !vaccineName || !administeredDate}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {mutation.isPending ? t("common.loading") : t("health.log.submit")}
        </button>
      </form>
    </div>
  );
}
