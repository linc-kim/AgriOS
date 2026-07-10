/**
 * Greena — Screen FL-05: Daily Log
 * The primary DAL (Daily Active Logger) data entry screen.
 * Submits or updates today's log (upsert via DB-06 Frozen).
 * Requires OPS_LOG_SUBMIT (farm_owner, farm_manager, farm_worker).
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { submitDailyLog, getDailyLog } from "@/api/flocks";
import { queryKeys } from "@/lib/queryClient";
import type { DailyLogSubmitInput } from "@/types";

export default function DailyLogScreen() {
  const { farmId, flockId } = useParams<{ farmId: string; flockId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const today = new Date().toISOString().split("T")[0];

  // Try to load today's existing log (for upsert awareness)
  const { data: existingLog } = useQuery({
    queryKey: queryKeys.flockLog(farmId!, flockId!, today),
    queryFn: () => getDailyLog(farmId!, flockId!, today),
    enabled: !!farmId && !!flockId,
    retry: false, // 404 is expected if no log yet
  });

  // Form state
  const [logDate] = useState(today);
  const [morningCount, setMorningCount] = useState("");
  const [mortalityCount, setMortalityCount] = useState("0");
  const [mortalityCause, setMortalityCause] = useState("");
  const [feedConsumedKg, setFeedConsumedKg] = useState("");
  const [waterLitres, setWaterLitres] = useState("");
  const [houseTempAm, setHouseTempAm] = useState("");
  const [houseTempPm, setHouseTempPm] = useState("");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Pre-fill if existing log found (upsert: show current values)
  useEffect(() => {
    if (existingLog) {
      setMorningCount(existingLog.morning_count?.toString() ?? "");
      setMortalityCount(existingLog.mortality_count.toString());
      setMortalityCause(existingLog.mortality_cause ?? "");
      setFeedConsumedKg(existingLog.feed_consumed_kg);
      setWaterLitres(existingLog.water_litres ?? "");
      setHouseTempAm(existingLog.house_temp_am ?? "");
      setHouseTempPm(existingLog.house_temp_pm ?? "");
      setNotes(existingLog.notes ?? "");
    }
  }, [existingLog]);

  const mutation = useMutation({
    mutationFn: (input: DailyLogSubmitInput) =>
      submitDailyLog(farmId!, flockId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.flockLogs(farmId!, flockId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.flock(farmId!, flockId!) });
      navigate(-1);
    },
  });

  function validate(): boolean {
    const e: Record<string, string> = {};
    const mortality = parseInt(mortalityCount, 10);
    if (isNaN(mortality) || mortality < 0) e.mortalityCount = t("flock.log.mortality_invalid");
    const feed = parseFloat(feedConsumedKg);
    if (!feedConsumedKg || isNaN(feed) || feed < 0) e.feedConsumedKg = t("flock.log.feed_required");
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    mutation.mutate({
      log_date: logDate,
      morning_count: morningCount ? parseInt(morningCount, 10) : undefined,
      mortality_count: parseInt(mortalityCount, 10),
      mortality_cause: mortalityCause.trim() || undefined,
      feed_consumed_kg: feedConsumedKg || "0",
      water_litres: waterLitres || undefined,
      house_temp_am: houseTempAm || undefined,
      house_temp_pm: houseTempPm || undefined,
      notes: notes.trim() || undefined,
    });
  }

  const isUpdate = !!existingLog;

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
        <div>
          <h1 className="text-lg font-bold text-gray-900">
            {t("flock.log.title")}
          </h1>
          <p className="text-xs text-gray-500">
            {isUpdate ? t("flock.log.updating") : t("flock.log.for_today")}{" "}
            {new Date(logDate).toLocaleDateString()}
          </p>
        </div>
      </div>

      {isUpdate && (
        <div className="mx-4 mt-4 rounded-xl bg-blue-50 border border-blue-200 px-4 py-2">
          <p className="text-xs text-blue-700 font-medium">
            {t("flock.log.update_notice")}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col flex-1 px-6 py-5 gap-5 overflow-y-auto">

        {/* Section: Bird Count */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {t("flock.log.section_count")}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.log.morning_count")}
              </label>
              <input
                type="number"
                inputMode="numeric"
                value={morningCount}
                onChange={(e) => setMorningCount(e.target.value)}
                placeholder="—"
                min={0}
                disabled={mutation.isPending}
                className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.log.mortality")} *
              </label>
              <input
                type="number"
                inputMode="numeric"
                value={mortalityCount}
                onChange={(e) => setMortalityCount(e.target.value)}
                placeholder="0"
                min={0}
                disabled={mutation.isPending}
                className={`
                  w-full min-h-[48px] px-4 rounded-xl border text-base
                  focus:outline-none focus:ring-2 focus:ring-brand-600
                  ${errors.mortalityCount ? "border-red-400 bg-red-50" : "border-gray-300"}
                `}
              />
              {errors.mortalityCount && (
                <p className="mt-1 text-xs text-red-600">{errors.mortalityCount}</p>
              )}
            </div>
          </div>

          {parseInt(mortalityCount, 10) > 0 && (
            <div className="mt-3">
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.log.mortality_cause")}
              </label>
              <input
                type="text"
                value={mortalityCause}
                onChange={(e) => setMortalityCause(e.target.value)}
                placeholder={t("flock.log.mortality_cause_placeholder")}
                maxLength={100}
                disabled={mutation.isPending}
                className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              />
            </div>
          )}
        </div>

        {/* Section: Feed & Water */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {t("flock.log.section_feed")}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.log.feed_kg")} *
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={feedConsumedKg}
                onChange={(e) => setFeedConsumedKg(e.target.value)}
                placeholder="25.000"
                min="0"
                step="0.001"
                disabled={mutation.isPending}
                className={`
                  w-full min-h-[48px] px-4 rounded-xl border text-base
                  focus:outline-none focus:ring-2 focus:ring-brand-600
                  ${errors.feedConsumedKg ? "border-red-400 bg-red-50" : "border-gray-300"}
                `}
              />
              {errors.feedConsumedKg && (
                <p className="mt-1 text-xs text-red-600">{errors.feedConsumedKg}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.log.water_litres")}
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={waterLitres}
                onChange={(e) => setWaterLitres(e.target.value)}
                placeholder="120"
                min="0"
                step="0.1"
                disabled={mutation.isPending}
                className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              />
            </div>
          </div>
        </div>

        {/* Section: House Temperature */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {t("flock.log.section_temp")}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.log.temp_am")} (°C)
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={houseTempAm}
                onChange={(e) => setHouseTempAm(e.target.value)}
                placeholder="28.5"
                min="0"
                max="60"
                step="0.1"
                disabled={mutation.isPending}
                className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {t("flock.log.temp_pm")} (°C)
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={houseTempPm}
                onChange={(e) => setHouseTempPm(e.target.value)}
                placeholder="31.2"
                min="0"
                max="60"
                step="0.1"
                disabled={mutation.isPending}
                className="w-full min-h-[48px] px-4 rounded-xl border border-gray-300 text-base focus:outline-none focus:ring-2 focus:ring-brand-600"
              />
            </div>
          </div>
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1.5">
            {t("flock.log.notes")}
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t("flock.log.notes_placeholder")}
            rows={3}
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
          disabled={mutation.isPending || !feedConsumedKg}
          className="
            w-full min-h-[56px] rounded-xl bg-brand-600 text-white
            font-semibold text-base
            disabled:opacity-50 active:scale-[0.98] transition-transform
          "
        >
          {mutation.isPending
            ? t("common.loading")
            : isUpdate
            ? t("flock.log.update_submit")
            : t("flock.log.submit")}
        </button>
      </form>
    </div>
  );
}
