/**
 * FR-01 — Market Prices Screen
 * /market/prices
 *
 * Shows the latest price per commodity (platform-wide).
 * - County filter dropdown
 * - Commodity cards with price + date
 * - Link to price history per commodity (FR-02)
 * - Empty state if no prices published yet
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { marketAPI } from "@/api/market";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { MarketPrice } from "@/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtKES(value: string): string {
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return num.toLocaleString("en-KE", {
    style: "currency",
    currency: "KES",
    minimumFractionDigits: 2,
  });
}

function fmtDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-KE", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// ── Price Card ────────────────────────────────────────────────────────────────

function PriceCard({
  price,
  onViewHistory,
}: {
  price: MarketPrice;
  onViewHistory: (commodity: string) => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900 capitalize">
            {price.commodity.replace(/_/g, " ")}
          </h3>
          {price.county && (
            <p className="text-xs text-gray-400 mt-0.5">
              📍 {price.county}
            </p>
          )}
        </div>

        <div className="text-right flex-shrink-0">
          <p className="text-base font-bold text-brand-700">
            {fmtKES(price.price_kes)}
          </p>
          <p className="text-xs text-gray-400">
            {t("market.per_unit", { unit: price.unit })}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-50">
        <span className="text-xs text-gray-400">
          {t("market.as_of", { date: fmtDate(price.valid_date) })}
        </span>
        <button
          onClick={() => onViewHistory(price.commodity)}
          className="text-xs text-brand-600 font-medium hover:text-brand-700"
        >
          {t("market.view_history")} →
        </button>
      </div>

      {price.source && (
        <p className="text-xs text-gray-300 mt-1 truncate">
          {t("market.source")}: {price.source}
        </p>
      )}
    </div>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

const KENYA_COUNTIES = [
  "Nairobi", "Kiambu", "Nakuru", "Meru", "Kakamega",
  "Kisumu", "Machakos", "Murang'a", "Nyeri", "Uasin Gishu",
];

export default function MarketPricesScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [selectedCounty, setSelectedCounty] = useState<string>("");

  const { data, isLoading, isError } = useQuery({
    queryKey: [
      ...queryKeys.marketPrices(),
      selectedCounty || "all",
    ],
    queryFn: () =>
      marketAPI.listLatestPrices(
        selectedCounty ? { county: selectedCounty } : undefined,
      ),
  });

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // ── Error ───────────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-gray-500 text-sm">{t("common.error_loading")}</p>
        </div>
      </div>
    );
  }

  const prices = data.items;
  const asOfDate = data.as_of_date;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-lg mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-gray-900">
                {t("market.title")}
              </h1>
              {asOfDate && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {t("market.latest_as_of", { date: fmtDate(asOfDate) })}
                </p>
              )}
            </div>
          </div>

          {/* County filter */}
          <div className="mt-3">
            <select
              value={selectedCounty}
              onChange={(e) => setSelectedCounty(e.target.value)}
              className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-300"
            >
              <option value="">{t("market.all_counties")}</option>
              {KENYA_COUNTIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-lg mx-auto px-4 py-4 space-y-3">
        {prices.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <span className="text-5xl mb-4">📊</span>
            <h2 className="text-lg font-semibold text-gray-900 mb-1">
              {t("market.empty_title")}
            </h2>
            <p className="text-sm text-gray-500 max-w-xs">
              {t("market.empty_body")}
            </p>
          </div>
        ) : (
          prices.map((price) => (
            <PriceCard
              key={`${price.commodity}-${price.county ?? "all"}-${price.valid_date}`}
              price={price}
              onViewHistory={(commodity) =>
                navigate(
                  `/market/prices/history?commodity=${encodeURIComponent(commodity)}`,
                )
              }
            />
          ))
        )}
      </div>
    </div>
  );
}
