/**
 * FI-08 — Financial Calculators
 * /farms/:farmId/finance/calculators
 *
 * Four calculators (no DB — pure math):
 *   1. FCR Calculator
 *   2. Profit Projection
 *   3. Break-Even Price
 *   4. Feed Needs Estimate
 *
 * Calculators call the backend /calculators/* endpoints (authenticated,
 * no farm access required) or compute locally.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  calculateFCR,
  calculateProfitProjection,
  calculateBreakEven,
  calculateFeedNeeds,
} from "@/api/finance";
import { Spinner } from "@/components/ui/Spinner";
import type {
  FCRCalculatorResult,
  ProfitProjectionResult,
  BreakEvenResult,
  FeedNeedsResult,
} from "@/types";

type CalcTab = "fcr" | "profit" | "breakeven" | "feed";

function fmtKES(v: string | number): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  return `KES ${n.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function ResultCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-brand-50 border border-brand-100 rounded-2xl p-4 mt-4 space-y-2">
      {children}
    </div>
  );
}

function ResultRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <p className="text-sm text-gray-600">{label}</p>
      <p className={`text-sm font-bold ${highlight ? "text-brand-700" : "text-gray-900"}`}>{value}</p>
    </div>
  );
}

// ── FCR Calculator ────────────────────────────────────────────────────────────

function FCRCalc() {
  const { t } = useTranslation();
  const [feedKg, setFeedKg] = useState("");
  const [liveWeightKg, setLiveWeightKg] = useState("");
  const [result, setResult] = useState<FCRCalculatorResult | null>(null);

  const mutation = useMutation({
    mutationFn: () => calculateFCR(parseFloat(feedKg), parseFloat(liveWeightKg)),
    onSuccess: setResult,
  });

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">{t("finance.calc.fcr_desc")}</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">
            {t("finance.calc.total_feed_kg")}
          </label>
          <input
            type="number"
            inputMode="decimal"
            value={feedKg}
            onChange={(e) => setFeedKg(e.target.value)}
            placeholder="e.g. 2500"
            className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">
            {t("finance.calc.live_weight_kg")}
          </label>
          <input
            type="number"
            inputMode="decimal"
            value={liveWeightKg}
            onChange={(e) => setLiveWeightKg(e.target.value)}
            placeholder="e.g. 1300"
            className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      </div>
      <button
        onClick={() => mutation.mutate()}
        disabled={!feedKg || !liveWeightKg || mutation.isPending}
        className="w-full bg-brand-600 text-white rounded-xl py-3 text-sm font-semibold disabled:opacity-40 flex items-center justify-center gap-2"
      >
        {mutation.isPending ? <Spinner size="sm" /> : null}
        {t("finance.calc.calculate")}
      </button>
      {result && (
        <ResultCard>
          <ResultRow label="FCR" value={parseFloat(result.fcr).toFixed(3)} highlight />
          <p className="text-xs text-brand-700 bg-white rounded-lg p-2 mt-1">
            {result.interpretation}
          </p>
        </ResultCard>
      )}
    </div>
  );
}

// ── Profit Projection ─────────────────────────────────────────────────────────

function ProfitProjectionCalc() {
  const { t } = useTranslation();
  const [birdCount, setBirdCount] = useState("");
  const [closeWeight, setCloseWeight] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [expensesNow, setExpensesNow] = useState("");
  const [extraExpenses, setExtraExpenses] = useState("0");
  const [mortalityPct, setMortalityPct] = useState("3");
  const [result, setResult] = useState<ProfitProjectionResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      calculateProfitProjection({
        current_bird_count: parseInt(birdCount),
        expected_close_weight_kg: parseFloat(closeWeight),
        expected_sale_price_per_kg: parseFloat(salePrice),
        total_expenses_so_far_kes: parseFloat(expensesNow),
        expected_additional_expenses_kes: parseFloat(extraExpenses) || 0,
        expected_mortality_pct: parseFloat(mortalityPct) || 3,
      }),
    onSuccess: setResult,
  });

  const canCompute = birdCount && closeWeight && salePrice && expensesNow;

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">{t("finance.calc.profit_desc")}</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.current_birds")}</label>
          <input type="number" inputMode="numeric" value={birdCount} onChange={(e) => setBirdCount(e.target.value)}
            placeholder="500" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.close_weight_kg")}</label>
          <input type="number" inputMode="decimal" value={closeWeight} onChange={(e) => setCloseWeight(e.target.value)}
            placeholder="2.5" step="0.1" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.sale_price_per_kg")} (KES)</label>
          <input type="number" inputMode="decimal" value={salePrice} onChange={(e) => setSalePrice(e.target.value)}
            placeholder="250" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.expenses_so_far")} (KES)</label>
          <input type="number" inputMode="decimal" value={expensesNow} onChange={(e) => setExpensesNow(e.target.value)}
            placeholder="80000" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.extra_expenses")} (KES)</label>
          <input type="number" inputMode="decimal" value={extraExpenses} onChange={(e) => setExtraExpenses(e.target.value)}
            placeholder="0" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.mortality_pct")} %</label>
          <input type="number" inputMode="decimal" value={mortalityPct} onChange={(e) => setMortalityPct(e.target.value)}
            placeholder="3" min="0" max="100" step="0.5" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
      </div>
      <button
        onClick={() => mutation.mutate()}
        disabled={!canCompute || mutation.isPending}
        className="w-full bg-brand-600 text-white rounded-xl py-3 text-sm font-semibold disabled:opacity-40 flex items-center justify-center gap-2"
      >
        {mutation.isPending ? <Spinner size="sm" /> : null}
        {t("finance.calc.project_profit")}
      </button>
      {result && (
        <ResultCard>
          <ResultRow
            label={t("finance.calc.projected_profit")}
            value={fmtKES(result.projected_profit_kes)}
            highlight
          />
          <ResultRow label={t("finance.calc.projected_margin")} value={`${parseFloat(result.projected_margin_pct).toFixed(1)}%`} />
          <ResultRow label={t("finance.calc.birds_at_sale")} value={result.birds_at_sale.toLocaleString()} />
          <ResultRow label={t("finance.calc.projected_revenue")} value={fmtKES(result.projected_revenue_kes)} />
          <ResultRow label={t("finance.calc.total_expenses")} value={fmtKES(result.projected_total_expenses_kes)} />
          <ResultRow label={t("finance.calc.revenue_per_bird")} value={fmtKES(result.revenue_per_bird_kes)} />
          <ResultRow label={t("finance.calc.cost_per_bird")} value={fmtKES(result.cost_per_bird_kes)} />
          <div className={`mt-2 text-xs font-semibold px-3 py-1.5 rounded-full text-center ${result.is_profitable ? "bg-brand-100 text-brand-700" : "bg-red-100 text-red-700"}`}>
            {result.is_profitable ? "✅ Projected profit" : "⚠️ Projected loss"}
          </div>
        </ResultCard>
      )}
    </div>
  );
}

// ── Break-Even Calculator ─────────────────────────────────────────────────────

function BreakEvenCalc() {
  const { t } = useTranslation();
  const [totalExpenses, setTotalExpenses] = useState("");
  const [birdsSold, setBirdsSold] = useState("");
  const [avgWeight, setAvgWeight] = useState("");
  const [result, setResult] = useState<BreakEvenResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      calculateBreakEven({
        total_expenses_kes: parseFloat(totalExpenses),
        expected_birds_sold: parseInt(birdsSold),
        expected_avg_weight_kg: parseFloat(avgWeight),
      }),
    onSuccess: setResult,
  });

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">{t("finance.calc.breakeven_desc")}</p>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.total_expenses_kes")}</label>
          <input type="number" inputMode="decimal" value={totalExpenses} onChange={(e) => setTotalExpenses(e.target.value)}
            placeholder="100000" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.birds_to_sell")}</label>
          <input type="number" inputMode="numeric" value={birdsSold} onChange={(e) => setBirdsSold(e.target.value)}
            placeholder="480" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.avg_weight_kg")}</label>
          <input type="number" inputMode="decimal" value={avgWeight} onChange={(e) => setAvgWeight(e.target.value)}
            placeholder="2.5" step="0.1" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
      </div>
      <button
        onClick={() => mutation.mutate()}
        disabled={!totalExpenses || !birdsSold || !avgWeight || mutation.isPending}
        className="w-full bg-brand-600 text-white rounded-xl py-3 text-sm font-semibold disabled:opacity-40 flex items-center justify-center gap-2"
      >
        {mutation.isPending ? <Spinner size="sm" /> : null}
        {t("finance.calc.calculate")}
      </button>
      {result && (
        <ResultCard>
          <ResultRow label={t("finance.calc.break_even_per_kg")} value={fmtKES(result.break_even_per_kg_kes)} highlight />
          <ResultRow label={t("finance.calc.break_even_per_bird")} value={fmtKES(result.break_even_per_bird_kes)} />
          <ResultRow label={t("finance.calc.total_live_weight")} value={`${parseFloat(result.total_live_weight_kg).toFixed(1)} kg`} />
        </ResultCard>
      )}
    </div>
  );
}

// ── Feed Needs Calculator ─────────────────────────────────────────────────────

function FeedNeedsCalc() {
  const { t } = useTranslation();
  const [birdCount, setBirdCount] = useState("");
  const [currentWeight, setCurrentWeight] = useState("");
  const [targetWeight, setTargetWeight] = useState("");
  const [targetFCR, setTargetFCR] = useState("1.9");
  const [daysRemaining, setDaysRemaining] = useState("");
  const [result, setResult] = useState<FeedNeedsResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      calculateFeedNeeds({
        current_bird_count: parseInt(birdCount),
        current_avg_weight_kg: parseFloat(currentWeight),
        target_weight_kg: parseFloat(targetWeight),
        target_fcr: parseFloat(targetFCR) || 1.9,
        days_remaining: daysRemaining ? parseInt(daysRemaining) : undefined,
      }),
    onSuccess: setResult,
  });

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">{t("finance.calc.feed_needs_desc")}</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.bird_count")}</label>
          <input type="number" inputMode="numeric" value={birdCount} onChange={(e) => setBirdCount(e.target.value)}
            placeholder="500" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.current_weight_kg")}</label>
          <input type="number" inputMode="decimal" value={currentWeight} onChange={(e) => setCurrentWeight(e.target.value)}
            placeholder="1.2" step="0.1" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.target_weight_kg")}</label>
          <input type="number" inputMode="decimal" value={targetWeight} onChange={(e) => setTargetWeight(e.target.value)}
            placeholder="2.5" step="0.1" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.target_fcr")}</label>
          <input type="number" inputMode="decimal" value={targetFCR} onChange={(e) => setTargetFCR(e.target.value)}
            placeholder="1.9" step="0.05" className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div className="col-span-2">
          <label className="text-xs font-medium text-gray-500 block mb-1">{t("finance.calc.days_remaining")} ({t("finance.calc.optional")})</label>
          <input type="number" inputMode="numeric" value={daysRemaining} onChange={(e) => setDaysRemaining(e.target.value)}
            placeholder={t("finance.calc.days_placeholder")} className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
      </div>
      <button
        onClick={() => mutation.mutate()}
        disabled={!birdCount || !currentWeight || !targetWeight || mutation.isPending}
        className="w-full bg-brand-600 text-white rounded-xl py-3 text-sm font-semibold disabled:opacity-40 flex items-center justify-center gap-2"
      >
        {mutation.isPending ? <Spinner size="sm" /> : null}
        {t("finance.calc.estimate_feed")}
      </button>
      {result && (
        <ResultCard>
          <ResultRow
            label={t("finance.calc.total_feed_needed")}
            value={`${parseFloat(result.total_feed_needed_kg).toFixed(0)} kg`}
            highlight
          />
          {result.feed_per_day_kg && (
            <ResultRow
              label={t("finance.calc.feed_per_day")}
              value={`${parseFloat(result.feed_per_day_kg).toFixed(1)} kg/day`}
            />
          )}
          <ResultRow
            label={t("finance.calc.weight_gain_needed")}
            value={`${parseFloat(result.weight_gain_needed_kg).toFixed(1)} kg`}
          />
          <ResultRow
            label={t("finance.calc.current_biomass")}
            value={`${parseFloat(result.current_biomass_kg).toFixed(1)} kg`}
          />
          <ResultRow
            label={t("finance.calc.target_biomass")}
            value={`${parseFloat(result.target_biomass_kg).toFixed(1)} kg`}
          />
        </ResultCard>
      )}
    </div>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

const TABS: { value: CalcTab; label: string; icon: string }[] = [
  { value: "fcr", label: "FCR", icon: "🌾" },
  { value: "profit", label: "Profit", icon: "📈" },
  { value: "breakeven", label: "Break-Even", icon: "⚖️" },
  { value: "feed", label: "Feed Needs", icon: "🧺" },
];

export default function BreakEvenCalculatorScreen() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<CalcTab>("fcr");

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-500">←</button>
          <div>
            <h1 className="text-lg font-bold text-gray-900">{t("finance.calculators.title")}</h1>
            <p className="text-xs text-gray-400 mt-0.5">{t("finance.calculators.subtitle")}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-3 overflow-x-auto pb-1">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                activeTab === tab.value
                  ? "bg-brand-600 text-white"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4 py-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          {activeTab === "fcr" && <FCRCalc />}
          {activeTab === "profit" && <ProfitProjectionCalc />}
          {activeTab === "breakeven" && <BreakEvenCalc />}
          {activeTab === "feed" && <FeedNeedsCalc />}
        </div>
      </div>
    </div>
  );
}
