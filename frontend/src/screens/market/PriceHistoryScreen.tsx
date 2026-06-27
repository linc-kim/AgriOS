/**
 * FR-02 — Price History Screen
 * /market/prices/history?commodity=broiler_chick
 *
 * Shows chronological price history for a single commodity.
 * - Commodity passed via ?commodity= query param
 * - Table / list of price entries (date, price, county, source)
 * - Pagination (load more)
 * - Back to MarketPricesScreen
 */

import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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

// ── Price Row ─────────────────────────────────────────────────────────────────

function PriceRow({ price }: { price: MarketPrice }) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl px-4 py-3 flex items-center justify-between gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">
          {fmtDate(price.valid_date)}
        </p>
        {price.county && (
          <p className="text-xs text-gray-400 mt-0.5">📍 {price.county}</p>
        )}
        {price.source && (
          <p className="text-xs text-gray-300 mt-0.5 truncate">
            {price.source}
          </p>
        )}
      </div>
      <div className="text-right flex-shrink-0">
        <p className="text-sm font-bold text-brand-700">
          {fmtKES(price.price_kes)}
        </p>
        <p className="text-xs text-gray-400">{price.unit}</p>
      </div>
    </div>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

export default function PriceHistoryScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [offset, setOffset] = useState(0);

  const commodity = searchParams.get("commodity") ?? "";
  const county    = searchParams.get("county") ?? undefined;

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: [...queryKeys.marketPriceHistory(commodity), offset],
    queryFn: () =>
      marketAPI.listPriceHistory({
        commodity,
        county,
        limit: PAGE_SIZE,
        offset,
      }),
    enabled: !!commodity,
  });

  const commodityLabel = commodity.replace(/_/g, " ");

  // ── No commodity param ──────────────────────────────────────────────────────
  if (!commodity) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-gray-500 text-sm">{t("market.no_commodity_selected")}</p>
          <button
            onClick={() => navigate("/market/prices")}
            className="mt-3 text-brand-600 text-sm font-medium hover:underline"
          >
            {t("market.back_to_prices")}
          </button>
        </div>
      </div>
    );
  }

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
          <button
            onClick={() => navigate(-1)}
            className="mt-3 text-brand-600 text-sm font-medium hover:underline"
          >
            {t("common.go_back")}
          </button>
        </div>
      </div>
    );
  }

  const prices = data.items;
  const total  = data.total;
  const hasMore = offset + PAGE_SIZE < total;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-lg mx-auto px-4 py-4">
          <button
            onClick={() => navigate(-1)}
            className="text-brand-600 text-sm font-medium hover:underline mb-2 block"
          >
            ← {t("market.back_to_prices")}
          </button>
          <h1 className="text-lg font-bold text-gray-900 capitalize">
            {commodityLabel}
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {t("market.history_count", { count: total })}
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-lg mx-auto px-4 py-4 space-y-2">
        {prices.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <span className="text-5xl mb-4">📉</span>
            <h2 className="text-lg font-semibold text-gray-900 mb-1">
              {t("market.history_empty_title")}
            </h2>
            <p className="text-sm text-gray-500 max-w-xs">
              {t("market.history_empty_body")}
            </p>
          </div>
        ) : (
          <>
            {prices.map((p) => (
              <PriceRow
                key={p.id}
                price={p}
              />
            ))}

            {/* Pagination */}
            {hasMore && (
              <button
                onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                disabled={isFetching}
                className="w-full mt-2 py-3 rounded-xl border border-brand-200 text-brand-600 text-sm font-medium hover:bg-brand-50 disabled:opacity-50 transition-colors"
              >
                {isFetching ? <Spinner size="sm" /> : t("common.load_more")}
              </button>
            )}

            <p className="text-center text-xs text-gray-400 pt-2">
              {t("market.showing_of", {
                shown: Math.min(offset + PAGE_SIZE, total),
                total,
              })}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
