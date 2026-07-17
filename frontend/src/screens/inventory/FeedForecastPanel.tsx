/**
 * Greena — Feed forecast panel.
 * Predicted depletion per item (days remaining, depletion date, recommended
 * purchase date) from trailing consumption. Theme-aware and responsive.
 */
import { useQuery } from "@tanstack/react-query";
import { CalendarClock, TrendingDown } from "lucide-react";

import { getFeedForecast } from "@/api/feed";
import { queryKeys } from "@/lib/queryClient";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { FeedForecastItem } from "@/types";

const STATUS: Record<string, { label: string; cls: string }> = {
  critical: { label: "Critical", cls: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300" },
  reorder_soon: { label: "Reorder soon", cls: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" },
  depleting: { label: "Depleting", cls: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" },
  ok: { label: "OK", cls: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300" },
  no_data: { label: "No data", cls: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-300" },
};

const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString() : "—");

export function FeedForecastPanel({ farmId }: { farmId: string }) {
  const forecastQuery = useQuery({
    queryKey: queryKeys.feedForecast(farmId),
    queryFn: () => getFeedForecast(farmId, 30, 7),
    enabled: !!farmId,
  });

  if (forecastQuery.isLoading) return <Skeleton className="h-64 rounded-2xl" />;
  const fc = forecastQuery.data;
  if (!fc) return null;

  if (fc.items.length === 0) {
    return (
      <EmptyState
        icon={<TrendingDown className="h-6 w-6" />}
        title="No stock to forecast"
        description="Record feed purchases and consumption to project when each feed type will run out."
      />
    );
  }

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <div className="flex items-center gap-2 text-gray-400"><CalendarClock className="h-4 w-4" /><span className="text-[11px] font-semibold uppercase tracking-wide">Soonest depletion</span></div>
          <p className="mt-2 text-xl font-semibold text-gray-900 dark:text-white">{fmtDate(fc.soonest_depletion_date)}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <div className="flex items-center gap-2 text-gray-400"><span className="text-[11px] font-semibold uppercase tracking-wide">Next purchase by</span></div>
          <p className="mt-2 text-xl font-semibold text-gray-900 dark:text-white">{fmtDate(fc.next_purchase_date)}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <div className="flex items-center gap-2 text-gray-400"><span className="text-[11px] font-semibold uppercase tracking-wide">Items needing purchase</span></div>
          <p className={`mt-2 text-xl font-semibold ${fc.items_needing_purchase > 0 ? "text-amber-600 dark:text-amber-400" : "text-gray-900 dark:text-white"}`}>{fc.items_needing_purchase}</p>
        </div>
      </div>

      {/* Per-item forecast */}
      <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-white/10">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-white/[0.03]">
            <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
              <th className="px-4 py-2.5 font-semibold">Feed type</th>
              <th className="px-4 py-2.5 font-semibold">Location</th>
              <th className="px-4 py-2.5 text-right font-semibold">On hand</th>
              <th className="px-4 py-2.5 text-right font-semibold">Daily use</th>
              <th className="px-4 py-2.5 text-right font-semibold">Days left</th>
              <th className="px-4 py-2.5 font-semibold">Depletes</th>
              <th className="px-4 py-2.5 font-semibold">Buy by</th>
              <th className="px-4 py-2.5 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {fc.items.map((it: FeedForecastItem) => {
              const s = STATUS[it.status] ?? STATUS.no_data;
              return (
                <tr key={it.item_id} className="border-t border-gray-100 dark:border-white/5">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{it.feed_type}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{it.location}</td>
                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">{Number(it.quantity_kg).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg</td>
                  <td className="px-4 py-3 text-right text-gray-500 dark:text-gray-400">{Number(it.avg_daily_consumption_kg).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg</td>
                  <td className="px-4 py-3 text-right font-semibold text-gray-900 dark:text-white">{it.days_remaining ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{fmtDate(it.depletion_date)}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{fmtDate(it.recommended_purchase_date)}</td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${s.cls}`}>{s.label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
