/**
 * Greena — Flock Feed.
 * A flock's feed consumption history + logging, wired to the Feed Management
 * backend. Embedded on the flock detail screen (mirrors FlockHealth).
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Wheat, Plus, Package } from "lucide-react";

import { listFlockConsumption } from "@/api/feed";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConsumptionModal } from "@/screens/inventory/FeedModals";
import type { FeedTransaction } from "@/types";

const kes = (v: string | number) => `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function FlockFeed({ farmId, flockId, disabled }: { farmId: string; flockId: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const [logging, setLogging] = useState(false);

  const consumptionQuery = useQuery({
    queryKey: queryKeys.flockFeedConsumption(farmId, flockId),
    queryFn: () => listFlockConsumption(farmId, flockId, { limit: 50 }),
    enabled: !!farmId && !!flockId,
  });
  const rows = consumptionQuery.data ?? [];
  const totalKg = rows.reduce((s, r) => s + Number(r.quantity_kg), 0);
  const totalCost = rows.reduce((s, r) => s + Number(r.total_cost), 0);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: queryKeys.flockFeedConsumption(farmId, flockId) });
    qc.invalidateQueries({ queryKey: queryKeys.feedDashboard(farmId) });
    qc.invalidateQueries({ queryKey: queryKeys.feedInventory(farmId) });
    qc.invalidateQueries({ queryKey: queryKeys.feedAnalytics(farmId) });
    qc.invalidateQueries({ queryKey: ["flock", farmId, flockId] });
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <Wheat className="h-4 w-4 text-brand-500" /> Feed
          {rows.length > 0 && (
            <span className="text-xs font-normal text-gray-400">
              · {totalKg.toLocaleString(undefined, { maximumFractionDigits: 1 })} kg · {kes(totalCost)}
            </span>
          )}
        </h2>
        {!disabled && (
          <Button size="sm" variant="secondary" onClick={() => setLogging(true)} leftIcon={<Plus className="h-4 w-4" />}>
            Record feed
          </Button>
        )}
      </div>

      {consumptionQuery.isLoading ? (
        <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div>
      ) : consumptionQuery.isError ? (
        <EmptyState icon={<Package className="h-5 w-5" />} title="Couldn't load feed records" description="Please try again in a moment." />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Wheat className="h-5 w-5" />}
          title="No feed recorded yet"
          description={disabled ? "This flock is closed." : "Record feed drawn from inventory to track this flock's feed cost per bird and per egg."}
        />
      ) : (
        <ul className="divide-y divide-gray-100 rounded-2xl border border-gray-200 dark:divide-white/5 dark:border-white/10">
          {rows.map((r) => <FeedRow key={r.id} txn={r} />)}
        </ul>
      )}

      {logging && (
        <ConsumptionModal farmId={farmId} flockId={flockId} onClose={() => setLogging(false)} onSaved={() => { setLogging(false); invalidate(); }} />
      )}
    </section>
  );
}

function FeedRow({ txn }: { txn: FeedTransaction }) {
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{txn.feed_type ?? "Feed"}</p>
        <p className="truncate text-xs text-gray-400">
          {new Date(txn.txn_date).toLocaleDateString()}{txn.location ? ` · ${txn.location}` : ""}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-sm font-semibold text-gray-900 dark:text-white">
          {Number(txn.quantity_kg).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
        </p>
        {Number(txn.total_cost) > 0 && <p className="text-xs text-gray-400">{kes(txn.total_cost)}</p>}
      </div>
    </li>
  );
}
