/**
 * Greena — Inventory (Feed Management).
 * Tabbed Feed workspace: Dashboard (stock, alerts, forecast summary, top flocks),
 * Inventory (searchable/filterable/sortable/paginated stock with batch + expiry),
 * Forecast (depletion + purchase recommendations), and Analytics (usage, FCR,
 * cost per bird/egg/kg gain, supplier spend). Wired to the real backend.
 */
import { useMemo, useState } from "react";
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
  CalendarX,
  Search,
} from "lucide-react";

import { getFeedDashboard, listSuppliers, listInventory } from "@/api/feed";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { FeedDashboard, FeedInventoryItem, FeedTransaction } from "@/types";
import {
  AddItemModal,
  AddPurchaseModal,
  SuppliersModal,
  TransferModal,
  WastageModal,
} from "./FeedModals";
import { FeedAnalyticsPanel } from "./FeedAnalyticsPanel";
import { FeedForecastPanel } from "./FeedForecastPanel";

const kes = (v: string | number | null | undefined) =>
  v == null ? "—" : `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const kg = (v: string | number) => `${Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg`;
const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString() : "—");

const TXN_LABEL: Record<string, string> = {
  purchase: "Purchase", consumption: "Consumption", transfer_in: "Transfer in",
  transfer_out: "Transfer out", wastage: "Wastage", adjustment: "Adjustment",
};

type Tab = "dashboard" | "inventory" | "forecast" | "analytics";
const PAGE_SIZE = 8;

function StatTile({ icon: Icon, label, value, sub, tone }: { icon: typeof Boxes; label: string; value: string; sub?: string; tone?: "danger" | "warn" }) {
  const toneCls = tone === "danger" ? "text-red-500" : tone === "warn" ? "text-amber-500" : "text-gray-400";
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className={`flex items-center gap-2 ${toneCls}`}>
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

  const [tab, setTab] = useState<Tab>("dashboard");
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
    for (const k of [
      queryKeys.feedDashboard(farmId), queryKeys.feedInventory(farmId),
      queryKeys.feedSuppliers(farmId), queryKeys.feedAnalytics(farmId),
      queryKeys.feedForecast(farmId), queryKeys.feedTransactions(farmId),
    ]) qc.invalidateQueries({ queryKey: k });
  };
  const afterSave = () => { setModal(null); invalidateAll(); };

  const TABS: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "inventory", label: "Inventory" },
    { id: "forecast", label: "Forecast" },
    { id: "analytics", label: "Analytics" },
  ];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Inventory</h1>
          <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">Feed stock, purchases, consumption, cost and forecast across your farm.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => setModal("suppliers")} leftIcon={<Truck className="h-4 w-4" />}>Suppliers</Button>
          <Button variant="secondary" size="sm" onClick={() => setModal("transfer")} leftIcon={<ArrowLeftRight className="h-4 w-4" />}>Transfer</Button>
          <Button variant="secondary" size="sm" onClick={() => setModal("wastage")} leftIcon={<Trash2 className="h-4 w-4" />}>Wastage</Button>
          <Button size="sm" onClick={() => setModal("purchase")} leftIcon={<Plus className="h-4 w-4" />}>Purchase</Button>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-white/10">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-brand-500 text-brand-600 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && (
        <DashboardTab dash={d} loading={dashQuery.isLoading} onRecord={() => setModal("purchase")} />
      )}

      {tab === "inventory" && (
        <InventoryTab
          items={items}
          loading={itemsQuery.isLoading}
          error={itemsQuery.isError}
          onRecord={() => setModal("purchase")}
          onAddItem={() => setModal("item")}
        />
      )}

      {tab === "forecast" && farmId && <FeedForecastPanel farmId={farmId} />}

      {tab === "analytics" && farmId && <FeedAnalyticsPanel farmId={farmId} />}

      {modal === "purchase" && farmId && <AddPurchaseModal farmId={farmId} suppliers={suppliers} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "transfer" && farmId && <TransferModal farmId={farmId} items={items} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "wastage" && farmId && <WastageModal farmId={farmId} items={items} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "item" && farmId && <AddItemModal farmId={farmId} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "suppliers" && farmId && <SuppliersModal farmId={farmId} onClose={() => { setModal(null); invalidateAll(); }} />}
    </div>
  );
}

// ── Dashboard tab ─────────────────────────────────────────────────────────────

function DashboardTab({ dash, loading, onRecord }: { dash: FeedDashboard | undefined; loading: boolean; onRecord: () => void }) {
  const d = dash;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {loading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)
        ) : (
          <>
            <StatTile icon={Boxes} label="Stock on hand" value={d ? kg(d.total_stock_kg) : "—"} sub={d ? `${d.item_count} items` : undefined} />
            <StatTile icon={Wallet} label="Inventory value" value={d ? kes(d.total_stock_value_kes) : "—"} />
            <StatTile icon={TrendingDown} label="Consumed today" value={d ? kg(d.consumed_today_kg) : "—"} sub={d ? `${kg(d.consumed_week_kg)} this week` : undefined} />
            <StatTile icon={AlertTriangle} label="Low stock" value={d ? String(d.low_stock_count) : "—"} tone={d && d.low_stock_count > 0 ? "danger" : undefined} sub={d ? `${d.expiring_count} expiring` : undefined} />
          </>
        )}
      </div>

      {d && (d.reorder_alerts.length > 0 || d.expiry_alerts.length > 0) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {d.reorder_alerts.length > 0 && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/10">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-800 dark:text-amber-300">
                <AlertTriangle className="h-4 w-4" /> Reorder alerts ({d.reorder_alerts.length})
              </h2>
              <ul className="space-y-2">
                {d.reorder_alerts.map((a: any) => (
                  <li key={a.item_id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium text-amber-900 dark:text-amber-200">{a.feed_type} · {a.location}</span>
                    <span className="text-amber-700 dark:text-amber-300">{kg(a.quantity_kg)} left</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {d.expiry_alerts.length > 0 && (
            <section className="rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-500/20 dark:bg-red-500/10">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-800 dark:text-red-300">
                <CalendarX className="h-4 w-4" /> Expiry alerts ({d.expiry_alerts.length})
              </h2>
              <ul className="space-y-2">
                {d.expiry_alerts.map((a: any) => (
                  <li key={a.item_id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium text-red-900 dark:text-red-200">{a.feed_type}{a.batch_number ? ` · ${a.batch_number}` : ""}</span>
                    <span className="text-red-700 dark:text-red-300">
                      {a.is_expired ? "Expired" : `${a.days_to_expiry}d`} · {fmtDate(a.expiry_date)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {/* Forecast summary + top flocks */}
      {d && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
            <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Forecast</h2>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div><p className="text-[11px] uppercase tracking-wide text-gray-400">Soonest depletion</p><p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{fmtDate(d.forecast.soonest_depletion_date)}</p></div>
              <div><p className="text-[11px] uppercase tracking-wide text-gray-400">Next purchase</p><p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{fmtDate(d.forecast.next_purchase_date)}</p></div>
              <div><p className="text-[11px] uppercase tracking-wide text-gray-400">Need purchase</p><p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{d.forecast.items_needing_purchase}</p></div>
            </div>
          </section>
          <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
            <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Top consuming flocks</h2>
            {d.top_flocks.length === 0 ? (
              <p className="py-4 text-center text-sm text-gray-400">No flock consumption yet.</p>
            ) : (
              <ul className="space-y-2">
                {d.top_flocks.map((f: any) => (
                  <li key={f.flock_id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium text-gray-800 dark:text-gray-200">{f.flock_name}</span>
                    <span className="text-gray-500 dark:text-gray-400">{kg(f.consumed_kg)} · {kes(f.feed_cost_kes)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {/* Recent activity */}
      {d && d.recent_transactions.length > 0 ? (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Recent activity</h2>
          <ul className="divide-y divide-gray-100 rounded-2xl border border-gray-200 dark:divide-white/5 dark:border-white/10">
            {d.recent_transactions.map((t: FeedTransaction) => <ActivityRow key={t.id} txn={t} />)}
          </ul>
        </section>
      ) : d && d.item_count === 0 ? (
        <EmptyState
          icon={<Package className="h-6 w-6" />}
          title="No feed stock yet"
          description="Record a feed purchase to start tracking stock, valuation, forecast and cost per bird."
          action={<Button onClick={onRecord} leftIcon={<Plus className="h-4 w-4" />}>Record purchase</Button>}
        />
      ) : null}
    </div>
  );
}

// ── Inventory tab (search / filter / sort / paginate) ─────────────────────────

type SortKey = "feed_type" | "quantity_kg" | "stock_value_kes" | "expiry_date";

function InventoryTab({ items, loading, error, onRecord, onAddItem }: {
  items: FeedInventoryItem[]; loading: boolean; error: boolean; onRecord: () => void; onAddItem: () => void;
}) {
  const [q, setQ] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sort, setSort] = useState<SortKey>("feed_type");
  const [page, setPage] = useState(0);

  const feedTypes = useMemo(() => Array.from(new Set(items.map((i) => i.feed_type))).sort(), [items]);

  const filtered = useMemo(() => {
    let rows = items.filter((i) => {
      const hay = `${i.feed_type} ${i.location} ${i.brand ?? ""} ${i.batch_number ?? ""} ${i.supplier_name ?? ""}`.toLowerCase();
      if (q && !hay.includes(q.toLowerCase())) return false;
      if (typeFilter && i.feed_type !== typeFilter) return false;
      if (statusFilter === "low" && !i.is_low_stock) return false;
      if (statusFilter === "expiring" && !(i.is_expiring_soon || i.is_expired)) return false;
      return true;
    });
    rows = [...rows].sort((a, b) => {
      if (sort === "feed_type") return a.feed_type.localeCompare(b.feed_type);
      if (sort === "expiry_date") return (a.expiry_date ?? "9999").localeCompare(b.expiry_date ?? "9999");
      return Number(b[sort]) - Number(a[sort]);
    });
    return rows;
  }, [items, q, typeFilter, statusFilter, sort]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  if (loading) return <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14 rounded-2xl" />)}</div>;
  if (error) return <EmptyState icon={<Package className="h-5 w-5" />} title="Couldn't load inventory" description="Please try again in a moment." />;
  if (items.length === 0)
    return (
      <EmptyState
        icon={<Package className="h-6 w-6" />}
        title="No feed stock yet"
        description="Record a feed purchase to start tracking stock, valuation and cost per bird."
        action={<Button onClick={onRecord} leftIcon={<Plus className="h-4 w-4" />}>Record purchase</Button>}
      />
    );

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-[180px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(0); }}
            placeholder="Search feed, brand, batch, supplier…"
            className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white"
          />
        </div>
        <Select label="" options={[{ value: "", label: "All types" }, ...feedTypes.map((t) => ({ value: t, label: t }))]} value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(0); }} />
        <Select label="" options={[{ value: "", label: "All stock" }, { value: "low", label: "Low stock" }, { value: "expiring", label: "Expiring / expired" }]} value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }} />
        <Select label="" options={[{ value: "feed_type", label: "Sort: Type" }, { value: "quantity_kg", label: "Sort: Quantity" }, { value: "stock_value_kes", label: "Sort: Value" }, { value: "expiry_date", label: "Sort: Expiry" }]} value={sort} onChange={(e) => setSort(e.target.value as SortKey)} />
        <Button variant="ghost" size="sm" onClick={onAddItem} leftIcon={<Plus className="h-4 w-4" />}>Add item</Button>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={<Search className="h-5 w-5" />} title="No matching items" description="Adjust your search or filters." />
      ) : (
        <>
          <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-white/10">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-white/[0.03]">
                <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
                  <th className="px-4 py-2.5 font-semibold">Feed type</th>
                  <th className="px-4 py-2.5 font-semibold">Batch</th>
                  <th className="px-4 py-2.5 font-semibold">Location</th>
                  <th className="px-4 py-2.5 text-right font-semibold">On hand</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Avg cost</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Value</th>
                  <th className="px-4 py-2.5 font-semibold">Expiry</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((it) => <StockRow key={it.id} item={it} />)}
              </tbody>
            </table>
          </div>

          {pageCount > 1 && (
            <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>{filtered.length} items · page {safePage + 1} of {pageCount}</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>Prev</Button>
                <Button variant="secondary" size="sm" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>Next</Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StockRow({ item }: { item: FeedInventoryItem }) {
  const expiryCls = item.is_expired
    ? "text-red-600 dark:text-red-400"
    : item.is_expiring_soon
    ? "text-amber-600 dark:text-amber-400"
    : "text-gray-500 dark:text-gray-400";
  return (
    <tr className="border-t border-gray-100 dark:border-white/5">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900 dark:text-white">{item.feed_type}</span>
          {item.is_low_stock && <span className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">Low</span>}
          {item.is_expired && <span className="rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-500/15 dark:text-red-300">Expired</span>}
        </div>
        {(item.brand || item.supplier_name) && <p className="text-xs text-gray-400">{[item.brand, item.supplier_name].filter(Boolean).join(" · ")}</p>}
      </td>
      <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{item.batch_number ?? "—"}</td>
      <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{item.location}</td>
      <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">{kg(item.quantity_kg)}</td>
      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">KES {Number(item.avg_cost_per_kg).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{kes(item.stock_value_kes)}</td>
      <td className={`px-4 py-3 ${expiryCls}`}>{item.expiry_date ? fmtDate(item.expiry_date) : "—"}</td>
    </tr>
  );
}

function ActivityRow({ txn }: { txn: FeedTransaction }) {
  const isIn = txn.direction > 0;
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{TXN_LABEL[txn.txn_type] ?? txn.txn_type} · {txn.feed_type ?? "feed"}</p>
        <p className="truncate text-xs text-gray-400">
          {new Date(txn.txn_date).toLocaleDateString()}{txn.location ? ` · ${txn.location}` : ""}{txn.flock_name ? ` · ${txn.flock_name}` : ""}{txn.reason ? ` · ${txn.reason}` : ""}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className={`text-sm font-semibold ${isIn ? "text-brand-600 dark:text-brand-300" : "text-gray-700 dark:text-gray-200"}`}>{isIn ? "+" : "−"}{kg(txn.quantity_kg)}</p>
        {Number(txn.total_cost) > 0 && <p className="text-xs text-gray-400">{kes(txn.total_cost)}</p>}
      </div>
    </li>
  );
}
