/**
 * Greena — Inventory (Feed Management).
 * The Feed dashboard: stock levels + valuation, reorder alerts, recent activity,
 * and analytics (usage, cost per bird / egg, supplier spend). Wired to the real
 * backend. Actions: record purchase, transfer, write off wastage, add an item,
 * and manage suppliers.
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Package,
  Plus,
  ArrowLeftRight,
  Trash2,
  Wallet,
  AlertTriangle,
  Boxes,
  Truck,
  TrendingDown,
} from "lucide-react";

import { getFeedDashboard, listSuppliers, listInventory } from "@/api/feed";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { FeedInventoryItem, FeedTransaction } from "@/types";
import {
  AddItemModal,
  AddPurchaseModal,
  SuppliersModal,
  TransferModal,
  WastageModal,
} from "./FeedModals";
import { FeedAnalyticsPanel } from "./FeedAnalyticsPanel";

const kes = (v: string | number | null | undefined) =>
  v == null ? "—" : `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const kg = (v: string | number) => `${Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg`;

const TXN_LABEL: Record<string, string> = {
  purchase: "Purchase",
  consumption: "Consumption",
  transfer_in: "Transfer in",
  transfer_out: "Transfer out",
  wastage: "Wastage",
  adjustment: "Adjustment",
};

function StatTile({ icon: Icon, label, value, sub, tone }: { icon: typeof Boxes; label: string; value: string; sub?: string; tone?: "danger" }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className={`flex items-center gap-2 ${tone === "danger" ? "text-red-500" : "text-gray-400"}`}>
        <Icon className="h-4 w-4" />
        <span className="text-[11px] font-semibold uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-2 text-xl font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{sub}</p>}
    </div>
  );
}

export default function InventoryScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();

  const [modal, setModal] = useState<null | "purchase" | "transfer" | "wastage" | "item" | "suppliers">(null);

  const dashQuery = useQuery({
    queryKey: queryKeys.feedDashboard(farmId!),
    queryFn: () => getFeedDashboard(farmId!, 30),
    enabled: !!farmId,
  });
  const suppliersQuery = useQuery({
    queryKey: queryKeys.feedSuppliers(farmId!),
    queryFn: () => listSuppliers(farmId!),
    enabled: !!farmId,
  });
  const itemsQuery = useQuery({
    queryKey: queryKeys.feedInventory(farmId!),
    queryFn: () => listInventory(farmId!),
    enabled: !!farmId,
  });

  const d = dashQuery.data;
  const items = itemsQuery.data ?? [];
  const suppliers = suppliersQuery.data ?? [];

  const invalidateAll = () => {
    if (!farmId) return;
    qc.invalidateQueries({ queryKey: queryKeys.feedDashboard(farmId) });
    qc.invalidateQueries({ queryKey: queryKeys.feedInventory(farmId) });
    qc.invalidateQueries({ queryKey: queryKeys.feedSuppliers(farmId) });
    qc.invalidateQueries({ queryKey: queryKeys.feedAnalytics(farmId) });
    qc.invalidateQueries({ queryKey: queryKeys.feedTransactions(farmId) });
  };
  const afterSave = () => { setModal(null); invalidateAll(); };

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Inventory</h1>
          <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">Feed stock, purchases, consumption and cost across your farm.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => setModal("suppliers")} leftIcon={<Truck className="h-4 w-4" />}>Suppliers</Button>
          <Button variant="secondary" size="sm" onClick={() => setModal("transfer")} leftIcon={<ArrowLeftRight className="h-4 w-4" />}>Transfer</Button>
          <Button variant="secondary" size="sm" onClick={() => setModal("wastage")} leftIcon={<Trash2 className="h-4 w-4" />}>Wastage</Button>
          <Button size="sm" onClick={() => setModal("purchase")} leftIcon={<Plus className="h-4 w-4" />}>Purchase</Button>
        </div>
      </header>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {dashQuery.isLoading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)
        ) : (
          <>
            <StatTile icon={Boxes} label="Stock on hand" value={d ? kg(d.total_stock_kg) : "—"} sub={d ? `${d.item_count} items` : undefined} />
            <StatTile icon={Wallet} label="Inventory value" value={d ? kes(d.total_stock_value_kes) : "—"} />
            <StatTile icon={TrendingDown} label="Consumed (30d)" value={d ? kg(d.consumed_kg) : "—"} sub={d ? kes(d.consumed_cost_kes) : undefined} />
            <StatTile icon={AlertTriangle} label="Low stock" value={d ? String(d.low_stock_count) : "—"} tone={d && d.low_stock_count > 0 ? "danger" : undefined} sub={d ? `${kg(d.wasted_kg)} wasted` : undefined} />
          </>
        )}
      </div>

      {/* Reorder alerts */}
      {d && d.reorder_alerts.length > 0 && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/10">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-800 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4" /> Reorder alerts ({d.reorder_alerts.length})
          </h2>
          <ul className="space-y-2">
            {d.reorder_alerts.map((a) => (
              <li key={a.item_id} className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-amber-900 dark:text-amber-200">{a.feed_type} · {a.location}</span>
                <span className="text-amber-700 dark:text-amber-300">
                  {kg(a.quantity_kg)} left (reorder at {kg(a.reorder_level_kg)}){a.supplier_name ? ` · ${a.supplier_name}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Stock levels */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
            Stock levels {items.length > 0 && <span className="text-gray-400">({items.length})</span>}
          </h2>
          <Button variant="ghost" size="sm" onClick={() => setModal("item")} leftIcon={<Plus className="h-4 w-4" />}>Add item</Button>
        </div>
        {itemsQuery.isLoading ? (
          <div className="space-y-3">{[0, 1].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}</div>
        ) : itemsQuery.isError ? (
          <EmptyState icon={<Package className="h-5 w-5" />} title="Couldn't load inventory" description="Please try again in a moment." />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Package className="h-6 w-6" />}
            title="No feed stock yet"
            description="Record a feed purchase to start tracking stock, valuation and cost per bird."
            action={<Button onClick={() => setModal("purchase")} leftIcon={<Plus className="h-4 w-4" />}>Record purchase</Button>}
          />
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-white/10">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-white/[0.03]">
                <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
                  <th className="px-4 py-2.5 font-semibold">Feed type</th>
                  <th className="px-4 py-2.5 font-semibold">Location</th>
                  <th className="px-4 py-2.5 text-right font-semibold">On hand</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Avg cost</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Value</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <StockRow key={it.id} item={it} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Analytics */}
      {farmId && <FeedAnalyticsPanel farmId={farmId} />}

      {/* Recent activity */}
      {d && d.recent_transactions.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Recent activity</h2>
          <ul className="divide-y divide-gray-100 rounded-2xl border border-gray-200 dark:divide-white/5 dark:border-white/10">
            {d.recent_transactions.map((t) => <ActivityRow key={t.id} txn={t} />)}
          </ul>
        </section>
      )}

      {modal === "purchase" && farmId && <AddPurchaseModal farmId={farmId} suppliers={suppliers} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "transfer" && farmId && <TransferModal farmId={farmId} items={items} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "wastage" && farmId && <WastageModal farmId={farmId} items={items} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "item" && farmId && <AddItemModal farmId={farmId} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "suppliers" && farmId && <SuppliersModal farmId={farmId} onClose={() => { setModal(null); invalidateAll(); }} />}
    </div>
  );
}

function StockRow({ item }: { item: FeedInventoryItem }) {
  return (
    <tr className="border-t border-gray-100 dark:border-white/5">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900 dark:text-white">{item.feed_type}</span>
          {item.is_low_stock && (
            <span className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">Low</span>
          )}
        </div>
        {item.supplier_name && <p className="text-xs text-gray-400">{item.supplier_name}</p>}
      </td>
      <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{item.location}</td>
      <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">{kg(item.quantity_kg)}</td>
      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">KES {Number(item.avg_cost_per_kg).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{kes(item.stock_value_kes)}</td>
    </tr>
  );
}

function ActivityRow({ txn }: { txn: FeedTransaction }) {
  const isIn = txn.direction > 0;
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
          {TXN_LABEL[txn.txn_type] ?? txn.txn_type} · {txn.feed_type ?? "feed"}
        </p>
        <p className="truncate text-xs text-gray-400">
          {new Date(txn.txn_date).toLocaleDateString()}
          {txn.location ? ` · ${txn.location}` : ""}
          {txn.flock_name ? ` · ${txn.flock_name}` : ""}
          {txn.reason ? ` · ${txn.reason}` : ""}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className={`text-sm font-semibold ${isIn ? "text-brand-600 dark:text-brand-300" : "text-gray-700 dark:text-gray-200"}`}>
          {isIn ? "+" : "−"}{kg(txn.quantity_kg)}
        </p>
        {Number(txn.total_cost) > 0 && <p className="text-xs text-gray-400">{kes(txn.total_cost)}</p>}
      </div>
    </li>
  );
}
