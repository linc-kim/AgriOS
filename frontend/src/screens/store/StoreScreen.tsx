/**
 * Greena — Inventory & Asset Management workspace (Module 6).
 * Tabs: Dashboard | Items | Movements | Assets | Maintenance | Suppliers |
 * Alerts | Analytics. Wired to the real backend; charts via Recharts.
 */
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Package, Boxes, AlertTriangle, Plus, Search, ArrowLeftRight,
  Wrench, Truck, Warehouse, TrendingDown,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import {
  getInvDashboard, listInvItems, listAssets, listMaintenance, listInvSuppliers,
  listInvMovements, getInvAlerts, getInvAnalytics,
} from "@/api/inventory";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Asset, InventoryItem, InventoryMovement, InventoryDashboard, InventoryAnalytics } from "@/types";
import { AssetModal, ItemModal, MaintenanceModal, MovementModal, SupplierModal, CATEGORY_OPTIONS } from "./StoreModals";

const kes = (v: any) => (v == null ? "—" : `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`);
const num = (v: any) => Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString() : "—");
const cap = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

type Tab = "dashboard" | "items" | "movements" | "assets" | "maintenance" | "suppliers" | "alerts" | "analytics";
const PAGE_SIZE = 8;

function StatTile({ icon: Icon, label, value, sub, tone }: { icon: typeof Boxes; label: string; value: string; sub?: string; tone?: "danger" | "warn" }) {
  const t = tone === "danger" ? "text-red-500" : tone === "warn" ? "text-amber-500" : "text-gray-400";
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className={`flex items-center gap-2 ${t}`}><Icon className="h-4 w-4" /><span className="text-[11px] font-semibold uppercase tracking-wide">{label}</span></div>
      <p className="mt-2 text-xl font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{sub}</p>}
    </div>
  );
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>{action}</div>
      {children}
    </section>
  );
}

const SEVERITY: Record<string, string> = {
  critical: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  info: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
};

export default function StoreScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [modal, setModal] = useState<null | "item" | "movement" | "asset" | "maintenance" | "supplier">(null);
  const [presetItem, setPresetItem] = useState<string | undefined>();

  const dashQuery = useQuery({ queryKey: queryKeys.invDashboard(farmId!), queryFn: () => getInvDashboard(farmId!), enabled: !!farmId });
  const itemsQuery = useQuery({ queryKey: queryKeys.invItems(farmId!), queryFn: () => listInvItems(farmId!), enabled: !!farmId });
  const assetsQuery = useQuery({ queryKey: queryKeys.invAssets(farmId!), queryFn: () => listAssets(farmId!), enabled: !!farmId });

  const items = itemsQuery.data ?? [];
  const assets = assetsQuery.data ?? [];

  const invalidate = () => {
    if (!farmId) return;
    for (const k of [queryKeys.invDashboard(farmId), queryKeys.invItems(farmId), queryKeys.invMovements(farmId),
      queryKeys.invAssets(farmId), queryKeys.invMaintenance(farmId), queryKeys.invSuppliers(farmId),
      queryKeys.invAlerts(farmId), queryKeys.invAnalytics(farmId)]) qc.invalidateQueries({ queryKey: k });
  };
  const afterSave = () => { setModal(null); setPresetItem(undefined); invalidate(); };

  const TABS: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Dashboard" }, { id: "items", label: "Items" },
    { id: "movements", label: "Movements" }, { id: "assets", label: "Assets" },
    { id: "maintenance", label: "Maintenance" }, { id: "suppliers", label: "Suppliers" },
    { id: "alerts", label: "Alerts" }, { id: "analytics", label: "Analytics" },
  ];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Inventory & Assets</h1>
          <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">Stock, movements, suppliers, assets and maintenance across your farm.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => setModal("supplier")} leftIcon={<Truck className="h-4 w-4" />}>Supplier</Button>
          <Button variant="secondary" size="sm" onClick={() => setModal("asset")} leftIcon={<Warehouse className="h-4 w-4" />}>Asset</Button>
          <Button variant="secondary" size="sm" onClick={() => setModal("movement")} leftIcon={<ArrowLeftRight className="h-4 w-4" />}>Movement</Button>
          <Button size="sm" onClick={() => setModal("item")} leftIcon={<Plus className="h-4 w-4" />}>Item</Button>
        </div>
      </header>

      <div className="flex gap-1 overflow-x-auto border-b border-gray-200 dark:border-white/10">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${tab === t.id ? "border-brand-500 text-brand-600 dark:text-brand-300" : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab dash={dashQuery.data} loading={dashQuery.isLoading} onAdd={() => setModal("item")} />}
      {tab === "items" && <ItemsTab items={items} loading={itemsQuery.isLoading} onAdd={() => setModal("item")} onMove={(id) => { setPresetItem(id); setModal("movement"); }} />}
      {tab === "movements" && farmId && <MovementsTab farmId={farmId} />}
      {tab === "assets" && <AssetsTab assets={assets} loading={assetsQuery.isLoading} onAdd={() => setModal("asset")} />}
      {tab === "maintenance" && farmId && <MaintenanceTab farmId={farmId} hasAssets={assets.length > 0} onAdd={() => setModal("maintenance")} />}
      {tab === "suppliers" && farmId && <SuppliersTab farmId={farmId} onAdd={() => setModal("supplier")} />}
      {tab === "alerts" && farmId && <AlertsTab farmId={farmId} />}
      {tab === "analytics" && farmId && <AnalyticsTab farmId={farmId} />}

      {modal === "item" && farmId && <ItemModal farmId={farmId} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "movement" && farmId && (items.length > 0
        ? <MovementModal farmId={farmId} items={items} presetItemId={presetItem} onClose={() => { setModal(null); setPresetItem(undefined); }} onSaved={afterSave} />
        : <SimpleNotice onClose={() => setModal(null)} title="No items yet" body="Add an inventory item before recording a movement." />)}
      {modal === "asset" && farmId && <AssetModal farmId={farmId} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "maintenance" && farmId && (assets.length > 0
        ? <MaintenanceModal farmId={farmId} assets={assets} onClose={() => setModal(null)} onSaved={afterSave} />
        : <SimpleNotice onClose={() => setModal(null)} title="No assets yet" body="Add an asset before logging maintenance." />)}
      {modal === "supplier" && farmId && <SupplierModal farmId={farmId} onClose={() => setModal(null)} onSaved={afterSave} />}
    </div>
  );
}

function SimpleNotice({ title, body, onClose }: { title: string; body: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-sm rounded-3xl border border-gray-200 bg-white p-6 text-center shadow-2xl dark:border-white/10 dark:bg-[#161a20]">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{body}</p>
        <Button className="mt-5" fullWidth onClick={onClose}>Got it</Button>
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

function DashboardTab({ dash, loading, onAdd }: { dash: InventoryDashboard | undefined; loading: boolean; onAdd: () => void }) {
  const d = dash;
  const catData = (d?.category_valuation ?? []).map((c) => ({ name: cap(c.category), value: Number(c.total_value) }));
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loading ? [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />) : (
          <>
            <StatTile icon={Boxes} label="Inventory value" value={d ? kes(d.total_inventory_value) : "—"} sub={d ? `${d.item_count} items` : undefined} />
            <StatTile icon={Warehouse} label="Asset value" value={d ? kes(d.total_asset_value) : "—"} sub={d ? `${d.asset_count} assets` : undefined} />
            <StatTile icon={AlertTriangle} label="Low / out" value={d ? `${d.low_stock_count} / ${d.out_of_stock_count}` : "—"} tone={d && (d.low_stock_count + d.out_of_stock_count) > 0 ? "danger" : undefined} sub={d ? `${d.expiring_count} expiring` : undefined} />
            <StatTile icon={Wrench} label="Maintenance due" value={d ? String(d.maintenance_due_count) : "—"} tone={d && d.maintenance_due_count > 0 ? "warn" : undefined} />
          </>
        )}
      </div>

      {loading ? <Skeleton className="h-64 rounded-2xl" /> : !d || d.item_count === 0 ? (
        <EmptyState icon={<Package className="h-6 w-6" />} title="No inventory yet" description="Add items and assets to track stock, valuation, movements and maintenance." action={<Button onClick={onAdd} leftIcon={<Plus className="h-4 w-4" />}>Add item</Button>} />
      ) : (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Inventory value by category">
              {catData.length === 0 ? <p className="py-8 text-center text-sm text-gray-400">No stock yet.</p> : (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={catData} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} width={92} />
                      <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} formatter={(v: any) => kes(v)} />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]}>{catData.map((_, i) => <Cell key={i} fill="#16a34a" />)}</Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
            <Card title={`Alerts (${d.alerts.length})`}>
              {d.alerts.length === 0 ? <p className="py-8 text-center text-sm text-gray-400">All clear — no alerts.</p> : (
                <ul className="space-y-2">
                  {d.alerts.slice(0, 8).map((a, i) => (
                    <li key={i} className="flex items-center justify-between gap-3 text-sm">
                      <span className="font-medium text-gray-800 dark:text-gray-200">{a.title}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${SEVERITY[a.severity] ?? SEVERITY.info}`}>{cap(a.kind)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
          <Card title="Recent movements">
            {d.recent_movements.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No movements yet.</p> : <MovementList rows={d.recent_movements} />}
          </Card>
        </>
      )}
    </div>
  );
}

// ── Items (search / filter / sort / paginate) ─────────────────────────────────

type SortKey = "name" | "quantity" | "current_value" | "expiry_date";

function ItemsTab({ items, loading, onAdd, onMove }: { items: InventoryItem[]; loading: boolean; onAdd: () => void; onMove: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [statusF, setStatusF] = useState("");
  const [sort, setSort] = useState<SortKey>("name");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    let rows = items.filter((i) => {
      const hay = `${i.name} ${i.sku ?? ""} ${i.category} ${i.location} ${i.supplier_name ?? ""} ${i.barcode ?? ""}`.toLowerCase();
      if (q && !hay.includes(q.toLowerCase())) return false;
      if (cat && i.category !== cat) return false;
      if (statusF === "low" && !i.is_low_stock) return false;
      if (statusF === "out" && !i.is_out_of_stock) return false;
      if (statusF === "expiring" && !(i.is_expiring_soon || i.is_expired)) return false;
      return true;
    });
    rows = [...rows].sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      if (sort === "expiry_date") return (a.expiry_date ?? "9999").localeCompare(b.expiry_date ?? "9999");
      return Number(b[sort]) - Number(a[sort]);
    });
    return rows;
  }, [items, q, cat, statusF, sort]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const rows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);
  const input = "rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white";

  if (loading) return <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14 rounded-2xl" />)}</div>;
  if (items.length === 0) return <EmptyState icon={<Package className="h-6 w-6" />} title="No items yet" description="Add your first inventory item to start tracking stock." action={<Button onClick={onAdd} leftIcon={<Plus className="h-4 w-4" />}>Add item</Button>} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-[180px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} placeholder="Search name, SKU, supplier, barcode…" className={`${input} w-full pl-9`} />
        </div>
        <Select label="" options={[{ value: "", label: "All categories" }, ...CATEGORY_OPTIONS]} value={cat} onChange={(e) => { setCat(e.target.value); setPage(0); }} />
        <Select label="" options={[{ value: "", label: "All stock" }, { value: "low", label: "Low stock" }, { value: "out", label: "Out of stock" }, { value: "expiring", label: "Expiring / expired" }]} value={statusF} onChange={(e) => { setStatusF(e.target.value); setPage(0); }} />
        <Select label="" options={[{ value: "name", label: "Sort: Name" }, { value: "quantity", label: "Sort: Qty" }, { value: "current_value", label: "Sort: Value" }, { value: "expiry_date", label: "Sort: Expiry" }]} value={sort} onChange={(e) => setSort(e.target.value as SortKey)} />
      </div>
      {filtered.length === 0 ? <EmptyState icon={<Search className="h-5 w-5" />} title="No matching items" description="Adjust your search or filters." /> : (
        <>
          <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-white/10">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-white/[0.03]">
                <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
                  <th className="px-4 py-2.5 font-semibold">Item</th>
                  <th className="px-4 py-2.5 font-semibold">Category</th>
                  <th className="px-4 py-2.5 text-right font-semibold">On hand</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Value</th>
                  <th className="px-4 py-2.5 font-semibold">Expiry</th>
                  <th className="px-4 py-2.5 text-right font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((i) => (
                  <tr key={i.id} className="border-t border-gray-100 dark:border-white/5">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-white">{i.name}</span>
                        {i.is_out_of_stock && <span className="rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-500/15 dark:text-red-300">Out</span>}
                        {!i.is_out_of_stock && i.is_low_stock && <span className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">Low</span>}
                        {i.is_expired && <span className="rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-500/15 dark:text-red-300">Expired</span>}
                      </div>
                      <p className="text-xs text-gray-400">{i.sku ?? ""}{i.location ? ` · ${i.location}` : ""}</p>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{cap(i.category)}</td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">{num(i.quantity)} {i.unit}</td>
                    <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{kes(i.current_value)}</td>
                    <td className={`px-4 py-3 ${i.is_expired ? "text-red-600 dark:text-red-400" : i.is_expiring_soon ? "text-amber-600 dark:text-amber-400" : "text-gray-500 dark:text-gray-400"}`}>{i.expiry_date ? fmtDate(i.expiry_date) : "—"}</td>
                    <td className="px-4 py-3 text-right"><button onClick={() => onMove(i.id)} className="rounded-lg px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:text-brand-300 dark:hover:bg-brand-600/15">Move</button></td>
                  </tr>
                ))}
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

// ── Movements ─────────────────────────────────────────────────────────────────

const MOVE_LABEL: Record<string, string> = {
  stock_in: "Stock in", stock_out: "Stock out", transfer_in: "Transfer in", transfer_out: "Transfer out",
  adjustment: "Adjustment", loss: "Loss", damage: "Damage", return: "Return", consumption: "Consumption",
};

function MovementList({ rows }: { rows: InventoryMovement[] }) {
  return (
    <ul className="divide-y divide-gray-100 dark:divide-white/5">
      {rows.map((m) => {
        const isIn = m.direction > 0;
        return (
          <li key={m.id} className="flex items-center justify-between gap-3 px-1 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{MOVE_LABEL[m.movement_type] ?? m.movement_type} · {m.item_name ?? "item"}</p>
              <p className="truncate text-xs text-gray-400">{fmtDate(m.created_at)}{m.reason ? ` · ${m.reason}` : ""}{m.reference ? ` · ${m.reference}` : ""} · {num(m.qty_before)}→{num(m.qty_after)}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className={`text-sm font-semibold ${isIn ? "text-brand-600 dark:text-brand-300" : "text-gray-700 dark:text-gray-200"}`}>{isIn ? "+" : "−"}{num(m.quantity)}</p>
              {Number(m.total_cost) > 0 && <p className="text-xs text-gray-400">{kes(m.total_cost)}</p>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function MovementsTab({ farmId }: { farmId: string }) {
  const query = useQuery({ queryKey: queryKeys.invMovements(farmId), queryFn: () => listInvMovements(farmId, { limit: 100 }), enabled: !!farmId });
  if (query.isLoading) return <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 rounded-xl" />)}</div>;
  const rows = query.data ?? [];
  if (rows.length === 0) return <EmptyState icon={<ArrowLeftRight className="h-6 w-6" />} title="No movements yet" description="Record stock in/out to build the movement ledger." />;
  return <div className="rounded-2xl border border-gray-200 p-2 dark:border-white/10"><MovementList rows={rows} /></div>;
}

// ── Assets ────────────────────────────────────────────────────────────────────

function AssetsTab({ assets, loading, onAdd }: { assets: Asset[]; loading: boolean; onAdd: () => void }) {
  if (loading) return <div className="space-y-3">{[0, 1].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}</div>;
  if (assets.length === 0) return <EmptyState icon={<Warehouse className="h-6 w-6" />} title="No assets yet" description="Track buildings, machinery, generators and more with depreciation." action={<Button onClick={onAdd} leftIcon={<Plus className="h-4 w-4" />}>Add asset</Button>} />;
  return (
    <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-white/10">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 dark:bg-white/[0.03]">
          <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
            <th className="px-4 py-2.5 font-semibold">Asset</th>
            <th className="px-4 py-2.5 font-semibold">Type</th>
            <th className="px-4 py-2.5 text-right font-semibold">Cost</th>
            <th className="px-4 py-2.5 text-right font-semibold">Current value</th>
            <th className="px-4 py-2.5 font-semibold">Condition</th>
            <th className="px-4 py-2.5 font-semibold">Next service</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((a) => (
            <tr key={a.id} className="border-t border-gray-100 dark:border-white/5">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 dark:text-white">{a.name}</span>
                  {a.is_maintenance_due && <span className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">Service due</span>}
                  {a.is_warranty_expiring && <span className="rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">Warranty</span>}
                </div>
                <p className="text-xs text-gray-400">{a.location ?? ""}{a.age_days ? ` · ${Math.floor(a.age_days / 365)}y old` : ""}</p>
              </td>
              <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{cap(a.asset_type)}</td>
              <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{kes(a.purchase_price)}</td>
              <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">{kes(a.current_value)}</td>
              <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{cap(a.condition)}</td>
              <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{fmtDate(a.next_service_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Maintenance ───────────────────────────────────────────────────────────────

function MaintenanceTab({ farmId, hasAssets, onAdd }: { farmId: string; hasAssets: boolean; onAdd: () => void }) {
  const query = useQuery({ queryKey: queryKeys.invMaintenance(farmId), queryFn: () => listMaintenance(farmId), enabled: !!farmId });
  const rows = query.data ?? [];
  const STATUS: Record<string, string> = {
    completed: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
    scheduled: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
    in_progress: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
    overdue: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  };
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><Button size="sm" variant="secondary" disabled={!hasAssets} onClick={onAdd} leftIcon={<Plus className="h-4 w-4" />}>Log maintenance</Button></div>
      {query.isLoading ? <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div> : rows.length === 0 ? (
        <EmptyState icon={<Wrench className="h-6 w-6" />} title="No maintenance yet" description={hasAssets ? "Schedule or log maintenance for your assets." : "Add an asset first."} />
      ) : (
        <ul className="divide-y divide-gray-100 rounded-2xl border border-gray-200 dark:divide-white/5 dark:border-white/10">
          {rows.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium text-gray-900 dark:text-white">{m.title}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS[m.status] ?? STATUS.scheduled}`}>{cap(m.status)}</span>
                </div>
                <p className="truncate text-xs text-gray-400">{m.asset_name}{m.scheduled_date ? ` · ${fmtDate(m.scheduled_date)}` : ""}{m.completed_date ? ` · done ${fmtDate(m.completed_date)}` : ""}{m.technician ? ` · ${m.technician}` : ""}</p>
              </div>
              {Number(m.cost) > 0 && <span className="shrink-0 text-sm font-semibold text-gray-700 dark:text-gray-200">{kes(m.cost)}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Suppliers ─────────────────────────────────────────────────────────────────

function SuppliersTab({ farmId, onAdd }: { farmId: string; onAdd: () => void }) {
  const query = useQuery({ queryKey: queryKeys.invSuppliers(farmId), queryFn: () => listInvSuppliers(farmId, true), enabled: !!farmId });
  const rows = query.data ?? [];
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><Button size="sm" variant="secondary" onClick={onAdd} leftIcon={<Plus className="h-4 w-4" />}>Add supplier</Button></div>
      {query.isLoading ? <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div> : rows.length === 0 ? (
        <EmptyState icon={<Truck className="h-6 w-6" />} title="No suppliers yet" description="Add suppliers to track spend and outstanding balances." />
      ) : (
        <ul className="divide-y divide-gray-100 rounded-2xl border border-gray-200 dark:divide-white/5 dark:border-white/10">
          {rows.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{s.name}{!s.is_active && <span className="ml-1 text-xs text-gray-400">(inactive)</span>}</p>
                <p className="truncate text-xs text-gray-400">{s.phone ?? "no phone"} · {kes(s.total_spend ?? 0)} spent · {s.order_count ?? 0} orders</p>
              </div>
              {Number(s.outstanding_balance) > 0 && <span className="shrink-0 text-sm font-semibold text-amber-600 dark:text-amber-400">{kes(s.outstanding_balance)} due</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Alerts ────────────────────────────────────────────────────────────────────

function AlertsTab({ farmId }: { farmId: string }) {
  const query = useQuery({ queryKey: queryKeys.invAlerts(farmId), queryFn: () => getInvAlerts(farmId), enabled: !!farmId });
  const rows = query.data ?? [];
  if (query.isLoading) return <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 rounded-xl" />)}</div>;
  if (rows.length === 0) return <EmptyState icon={<AlertTriangle className="h-6 w-6" />} title="All clear" description="No low-stock, expiry, warranty or maintenance alerts." />;
  return (
    <ul className="space-y-2">
      {rows.map((a, i) => (
        <li key={i} className="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
          <div className="flex items-center gap-3">
            <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${SEVERITY[a.severity] ?? SEVERITY.info}`}>{a.ref_type === "asset" ? <Wrench className="h-4 w-4" /> : <Package className="h-4 w-4" />}</span>
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">{a.title}</p>
              <p className="text-xs text-gray-400">{a.detail}</p>
            </div>
          </div>
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${SEVERITY[a.severity] ?? SEVERITY.info}`}>{cap(a.kind)}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Analytics ─────────────────────────────────────────────────────────────────

function AnalyticsTab({ farmId }: { farmId: string }) {
  const query = useQuery({ queryKey: queryKeys.invAnalytics(farmId), queryFn: () => getInvAnalytics(farmId), enabled: !!farmId });
  if (query.isLoading) return <Skeleton className="h-64 rounded-2xl" />;
  const a: InventoryAnalytics | undefined = query.data;
  if (!a) return null;
  const trend = a.movement_trend.map((p) => ({ period: p.period.slice(5), In: Number(p.stock_in), Out: Number(p.stock_out) }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile icon={Boxes} label="Inventory value" value={kes(a.inventory_valuation)} />
        <StatTile icon={Warehouse} label="Asset value" value={kes(a.asset_valuation)} />
        <StatTile icon={TrendingDown} label="Depreciation" value={kes(a.total_depreciation)} />
        <StatTile icon={Wrench} label="Maintenance cost" value={kes(a.maintenance_cost)} />
      </div>

      <Card title="Stock movement trend (12 months)">
        {trend.length === 0 ? <p className="py-8 text-center text-sm text-gray-400">No movements.</p> : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trend} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="period" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} />
                <Bar dataKey="In" fill="#16a34a" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Out" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Most consumed">
          {a.most_consumed.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No consumption yet.</p> : (
            <ul className="space-y-2">{a.most_consumed.map((v) => (
              <li key={v.item_id} className="flex items-center justify-between text-sm"><span className="font-medium text-gray-800 dark:text-gray-200">{v.name}</span><span className="text-gray-500 dark:text-gray-400">{num(v.consumed_qty)} · {kes(v.consumed_value)}</span></li>
            ))}</ul>
          )}
        </Card>
        <Card title="Reorder recommendations">
          {a.reorder_recommendations.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">Nothing to reorder.</p> : (
            <ul className="space-y-2">{a.reorder_recommendations.map((r) => (
              <li key={r.item_id} className="flex items-center justify-between text-sm"><span className="font-medium text-gray-800 dark:text-gray-200">{r.name}</span><span className="text-amber-600 dark:text-amber-400">order {num(r.suggested_order_qty)}</span></li>
            ))}</ul>
          )}
        </Card>
        <Card title="Dead stock">
          {a.dead_stock.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No dead stock.</p> : (
            <ul className="space-y-2">{a.dead_stock.map((i) => (
              <li key={i.id} className="flex items-center justify-between text-sm"><span className="font-medium text-gray-800 dark:text-gray-200">{i.name}</span><span className="text-gray-500 dark:text-gray-400">{num(i.quantity)} {i.unit} · {kes(i.current_value)}</span></li>
            ))}</ul>
          )}
        </Card>
        <Card title="Supplier performance">
          {a.supplier_performance.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No suppliers.</p> : (
            <ul className="space-y-2">{a.supplier_performance.map((s) => (
              <li key={s.supplier_id} className="flex items-center justify-between text-sm"><span className="font-medium text-gray-800 dark:text-gray-200">{s.name}</span><span className="text-gray-500 dark:text-gray-400">{kes(s.total_spend)} · {s.order_count} orders</span></li>
            ))}</ul>
          )}
        </Card>
      </div>
    </div>
  );
}
