/**
 * Greena — Inventory & Asset modals: item, movement, asset, maintenance, supplier.
 */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import {
  createInvItem, recordInvMovement, createAsset, createMaintenance,
  createInvSupplier, listInvSuppliers,
} from "@/api/inventory";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import type { Asset, InventoryItem, InventoryItemInput } from "@/types";

const TODAY = () => new Date().toISOString().slice(0, 10);
const errMsg = (e: any, f: string) => e?.response?.data?.error?.message ?? f;

export const CATEGORY_OPTIONS = [
  { value: "feed", label: "Feed" },
  { value: "medication", label: "Medication" },
  { value: "vaccines", label: "Vaccines" },
  { value: "equipment", label: "Equipment" },
  { value: "consumables", label: "Consumables" },
  { value: "cleaning_supplies", label: "Cleaning supplies" },
  { value: "ppe", label: "PPE" },
  { value: "packaging", label: "Packaging" },
  { value: "fuel", label: "Fuel" },
  { value: "office_supplies", label: "Office supplies" },
  { value: "spare_parts", label: "Spare parts" },
  { value: "miscellaneous", label: "Miscellaneous" },
];

const MOVEMENT_OPTIONS = [
  { value: "stock_in", label: "Stock in (purchase)" },
  { value: "stock_out", label: "Stock out" },
  { value: "consumption", label: "Consumption" },
  { value: "transfer_out", label: "Transfer out" },
  { value: "return", label: "Return" },
  { value: "loss", label: "Loss" },
  { value: "damage", label: "Damage" },
  { value: "adjustment", label: "Adjustment (+)" },
];

const ASSET_TYPE_OPTIONS = [
  "building", "vehicle", "machinery", "generator", "incubator",
  "feeder", "drinker", "solar_system", "computer", "phone", "tool",
].map((v) => ({ value: v, label: v.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) }));

const CONDITION_OPTIONS = ["excellent", "good", "fair", "poor", "needs_repair", "decommissioned"]
  .map((v) => ({ value: v, label: v.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) }));

export function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#161a20] sm:rounded-3xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Err({ message }: { message: string | null }) {
  if (!message) return null;
  return <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">{message}</div>;
}

// ── Item ──────────────────────────────────────────────────────────────────────

export function ItemModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const suppliersQuery = useQuery({ queryKey: queryKeys.invSuppliers(farmId), queryFn: () => listInvSuppliers(farmId) });
  const suppliers = suppliersQuery.data ?? [];
  const [f, setF] = useState({
    name: "", category: "consumables", unit: "unit", location: "main_store",
    reorder_level: "", min_stock: "", opening_quantity: "", opening_cost: "",
    supplier_id: "", batch_number: "", expiry_date: "", serial_number: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const input: InventoryItemInput = {
        name: f.name.trim(), category: f.category as any, unit: f.unit || "unit", location: f.location || "main_store",
        reorder_level: f.reorder_level || undefined, min_stock: f.min_stock || undefined,
        opening_quantity: f.opening_quantity || undefined, opening_cost: f.opening_cost || undefined,
        supplier_id: f.supplier_id || undefined, batch_number: f.batch_number || undefined,
        expiry_date: f.expiry_date || undefined, serial_number: f.serial_number || undefined,
      };
      return createInvItem(farmId, input);
    },
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't create the item.")),
  });

  return (
    <ModalShell title="Add inventory item" onClose={onClose}>
      <Err message={error} />
      <div className="space-y-4">
        <TextField label="Name" value={f.name} onChange={(e) => set({ name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Category" options={CATEGORY_OPTIONS} value={f.category} onChange={(e) => set({ category: e.target.value })} />
          <TextField label="Unit" value={f.unit} onChange={(e) => set({ unit: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Opening qty" type="number" min={0} value={f.opening_quantity} onChange={(e) => set({ opening_quantity: e.target.value })} />
          <TextField label="Unit cost (KES)" type="number" min={0} value={f.opening_cost} onChange={(e) => set({ opening_cost: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Reorder level" type="number" min={0} value={f.reorder_level} onChange={(e) => set({ reorder_level: e.target.value })} />
          <TextField label="Location" value={f.location} onChange={(e) => set({ location: e.target.value })} />
        </div>
        <Select label="Supplier (optional)" options={[{ value: "", label: "—" }, ...suppliers.map((s) => ({ value: s.id, label: s.name }))]} value={f.supplier_id} onChange={(e) => set({ supplier_id: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Batch no. (optional)" value={f.batch_number} onChange={(e) => set({ batch_number: e.target.value })} />
          <TextField label="Expiry (optional)" type="date" value={f.expiry_date} onChange={(e) => set({ expiry_date: e.target.value })} />
        </div>
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={f.name.trim().length < 1} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Add item</Button>
      </div>
    </ModalShell>
  );
}

// ── Movement ──────────────────────────────────────────────────────────────────

export function MovementModal({ farmId, items, presetItemId, onClose, onSaved }: { farmId: string; items: InventoryItem[]; presetItemId?: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({
    item_id: presetItemId ?? items[0]?.id ?? "", movement_type: "stock_in",
    quantity: "", unit_cost: "", reason: "", reference: "", location_to: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);
  const item = items.find((i) => i.id === f.item_id);
  const isIn = ["stock_in", "return", "adjustment"].includes(f.movement_type);

  const save = useMutation({
    mutationFn: () => recordInvMovement(farmId, {
      item_id: f.item_id, movement_type: f.movement_type as any, quantity: f.quantity,
      unit_cost: f.movement_type === "stock_in" && f.unit_cost ? f.unit_cost : undefined,
      reason: f.reason || undefined, reference: f.reference || undefined, location_to: f.location_to || undefined,
    }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't record the movement.")),
  });

  const valid = f.item_id && Number(f.quantity) > 0 && (isIn || (item && Number(f.quantity) <= Number(item.quantity)));

  return (
    <ModalShell title="Record stock movement" onClose={onClose}>
      <Err message={error} />
      <div className="space-y-4">
        <Select label="Item" options={items.map((i) => ({ value: i.id, label: `${i.name} (${Number(i.quantity)} ${i.unit})` }))} value={f.item_id} onChange={(e) => set({ item_id: e.target.value })} />
        <Select label="Movement type" options={MOVEMENT_OPTIONS} value={f.movement_type} onChange={(e) => set({ movement_type: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Quantity" type="number" min={0} value={f.quantity} onChange={(e) => set({ quantity: e.target.value })} />
          {f.movement_type === "stock_in" ? (
            <TextField label="Unit cost (KES)" type="number" min={0} value={f.unit_cost} onChange={(e) => set({ unit_cost: e.target.value })} />
          ) : (
            <TextField label="Reason" value={f.reason} onChange={(e) => set({ reason: e.target.value })} />
          )}
        </div>
        {f.movement_type === "stock_in" && <TextField label="Reference / invoice" value={f.reference} onChange={(e) => set({ reference: e.target.value })} />}
        {item && !isIn && <p className="text-xs text-gray-400">On hand: {Number(item.quantity)} {item.unit} @ KES {Number(item.avg_cost).toLocaleString()}/unit.</p>}
        {f.movement_type === "stock_in" && <p className="text-xs text-gray-400">Books a finance expense automatically.</p>}
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Record</Button>
      </div>
    </ModalShell>
  );
}

// ── Asset ─────────────────────────────────────────────────────────────────────

export function AssetModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({
    name: "", asset_type: "machinery", purchase_date: TODAY(), purchase_price: "",
    useful_life_years: "10", salvage_value: "", location: "", condition: "good",
    service_interval_days: "", warranty_expiry: "", serial_number: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => createAsset(farmId, {
      name: f.name.trim(), asset_type: f.asset_type as any, purchase_date: f.purchase_date,
      purchase_price: f.purchase_price, useful_life_years: f.useful_life_years ? Number(f.useful_life_years) : undefined,
      salvage_value: f.salvage_value || undefined, location: f.location || undefined, condition: f.condition,
      service_interval_days: f.service_interval_days ? Number(f.service_interval_days) : undefined,
      warranty_expiry: f.warranty_expiry || undefined, serial_number: f.serial_number || undefined,
    }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't create the asset.")),
  });

  const valid = f.name.trim() && Number(f.purchase_price) >= 0 && f.purchase_date;

  return (
    <ModalShell title="Add asset" onClose={onClose}>
      <Err message={error} />
      <div className="space-y-4">
        <TextField label="Name" value={f.name} onChange={(e) => set({ name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Type" options={ASSET_TYPE_OPTIONS} value={f.asset_type} onChange={(e) => set({ asset_type: e.target.value })} />
          <Select label="Condition" options={CONDITION_OPTIONS} value={f.condition} onChange={(e) => set({ condition: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Purchase date" type="date" value={f.purchase_date} onChange={(e) => set({ purchase_date: e.target.value })} />
          <TextField label="Purchase price (KES)" type="number" min={0} value={f.purchase_price} onChange={(e) => set({ purchase_price: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Useful life (yrs)" type="number" min={1} value={f.useful_life_years} onChange={(e) => set({ useful_life_years: e.target.value })} />
          <TextField label="Salvage value" type="number" min={0} value={f.salvage_value} onChange={(e) => set({ salvage_value: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Service every (days)" type="number" min={1} value={f.service_interval_days} onChange={(e) => set({ service_interval_days: e.target.value })} />
          <TextField label="Warranty expiry" type="date" value={f.warranty_expiry} onChange={(e) => set({ warranty_expiry: e.target.value })} />
        </div>
        <TextField label="Location (optional)" value={f.location} onChange={(e) => set({ location: e.target.value })} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Add asset</Button>
      </div>
    </ModalShell>
  );
}

// ── Maintenance ───────────────────────────────────────────────────────────────

export function MaintenanceModal({ farmId, assets, onClose, onSaved }: { farmId: string; assets: Asset[]; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({
    asset_id: assets[0]?.id ?? "", title: "", status: "scheduled",
    scheduled_date: TODAY(), completed_date: "", cost: "", technician: "", parts_used: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);
  const done = f.status === "completed";

  const save = useMutation({
    mutationFn: () => createMaintenance(farmId, {
      asset_id: f.asset_id, title: f.title.trim(), status: f.status,
      scheduled_date: f.scheduled_date || undefined,
      completed_date: done ? (f.completed_date || TODAY()) : undefined,
      cost: done && f.cost ? f.cost : undefined, technician: f.technician || undefined,
      parts_used: f.parts_used ? f.parts_used.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
    }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't log the maintenance.")),
  });

  const valid = f.asset_id && f.title.trim().length >= 2;

  return (
    <ModalShell title="Log maintenance" onClose={onClose}>
      <Err message={error} />
      <div className="space-y-4">
        <Select label="Asset" options={assets.map((a) => ({ value: a.id, label: a.name }))} value={f.asset_id} onChange={(e) => set({ asset_id: e.target.value })} />
        <TextField label="Title" placeholder="e.g. Oil change" value={f.title} onChange={(e) => set({ title: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Status" options={[{ value: "scheduled", label: "Scheduled" }, { value: "in_progress", label: "In progress" }, { value: "completed", label: "Completed" }]} value={f.status} onChange={(e) => set({ status: e.target.value })} />
          <TextField label={done ? "Completed date" : "Scheduled date"} type="date" value={done ? f.completed_date || TODAY() : f.scheduled_date} onChange={(e) => set(done ? { completed_date: e.target.value } : { scheduled_date: e.target.value })} />
        </div>
        {done && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Cost (KES)" hint="Booked as an expense." type="number" min={0} value={f.cost} onChange={(e) => set({ cost: e.target.value })} />
            <TextField label="Technician" value={f.technician} onChange={(e) => set({ technician: e.target.value })} />
          </div>
        )}
        <TextField label="Parts used (comma-separated)" value={f.parts_used} onChange={(e) => set({ parts_used: e.target.value })} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Log</Button>
      </div>
    </ModalShell>
  );
}

// ── Supplier ──────────────────────────────────────────────────────────────────

export function SupplierModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: "", phone: "", email: "", address: "", outstanding_balance: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => createInvSupplier(farmId, {
      name: f.name.trim(), phone: f.phone || undefined, email: f.email || undefined,
      address: f.address || undefined, outstanding_balance: (f.outstanding_balance || "0") as any,
    } as any),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't add the supplier.")),
  });

  return (
    <ModalShell title="Add supplier" onClose={onClose}>
      <Err message={error} />
      <div className="space-y-4">
        <TextField label="Name" value={f.name} onChange={(e) => set({ name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Phone" value={f.phone} onChange={(e) => set({ phone: e.target.value })} />
          <TextField label="Email" value={f.email} onChange={(e) => set({ email: e.target.value })} />
        </div>
        <TextField label="Address" value={f.address} onChange={(e) => set({ address: e.target.value })} />
        <TextField label="Outstanding balance (KES)" type="number" min={0} value={f.outstanding_balance} onChange={(e) => set({ outstanding_balance: e.target.value })} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={f.name.trim().length < 2} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Add supplier</Button>
      </div>
    </ModalShell>
  );
}
