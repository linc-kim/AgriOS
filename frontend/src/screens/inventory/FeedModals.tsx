/**
 * Greena — Feed Management modals.
 * Add purchase, transfer between stores, record wastage, add an inventory item,
 * and manage suppliers. Shared by the Inventory (Feed) screen.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Trash2, Star } from "lucide-react";

import {
  createInventoryItem,
  createSupplier,
  deleteSupplier,
  listInventory,
  listSuppliers,
  recordConsumption,
  recordPurchase,
  recordTransfer,
  recordWastage,
  updateSupplier,
} from "@/api/feed";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { queryKeys } from "@/lib/queryClient";
import type { FeedInventoryItem, FeedSupplier } from "@/types";

const TODAY = () => new Date().toISOString().slice(0, 10);

export const FEED_TYPE_OPTIONS = [
  { value: "chick_mash", label: "Chick mash" },
  { value: "broiler_starter", label: "Broiler starter" },
  { value: "broiler_finisher", label: "Broiler finisher" },
  { value: "grower_mash", label: "Grower mash" },
  { value: "layer_mash", label: "Layer mash" },
  { value: "kienyeji_mash", label: "Kienyeji mash" },
  { value: "supplement", label: "Supplement" },
];

const WASTAGE_REASONS = [
  { value: "spoilage", label: "Spoilage" },
  { value: "spillage", label: "Spillage" },
  { value: "contamination", label: "Contamination" },
  { value: "pest_damage", label: "Pest damage" },
  { value: "moisture_mould", label: "Moisture / mould" },
  { value: "theft", label: "Theft" },
  { value: "expired", label: "Expired" },
  { value: "other", label: "Other" },
];

export function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#161a20] sm:rounded-3xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
      {message}
    </div>
  );
}

const errMsg = (e: any, fallback: string) => e?.response?.data?.error?.message ?? fallback;

// ── Add Purchase ──────────────────────────────────────────────────────────────

export function AddPurchaseModal({
  farmId,
  suppliers,
  onClose,
  onSaved,
}: {
  farmId: string;
  suppliers: FeedSupplier[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    feed_type: "broiler_starter",
    location: "main_store",
    quantity_kg: "",
    price_per_kg: "",
    purchase_date: TODAY(),
    supplier_id: "",
    reference: "",
    brand: "",
    batch_number: "",
    expiry_date: "",
    delivery_date: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      recordPurchase(farmId, {
        feed_type: f.feed_type,
        location: f.location.trim() || "main_store",
        quantity_kg: f.quantity_kg,
        price_per_kg: f.price_per_kg,
        purchase_date: f.purchase_date,
        supplier_id: f.supplier_id || undefined,
        reference: f.reference || undefined,
        brand: f.brand || undefined,
        batch_number: f.batch_number || undefined,
        expiry_date: f.expiry_date || undefined,
        delivery_date: f.delivery_date || undefined,
      }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't record the purchase.")),
  });

  const total = Number(f.quantity_kg || 0) * Number(f.price_per_kg || 0);
  const valid = Number(f.quantity_kg) > 0 && Number(f.price_per_kg) >= 0 && f.purchase_date;

  return (
    <ModalShell title="Record feed purchase" onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="space-y-4">
        <Select label="Feed type" options={FEED_TYPE_OPTIONS} value={f.feed_type} onChange={(e) => set({ feed_type: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Quantity (kg)" type="number" min={0} value={f.quantity_kg} onChange={(e) => set({ quantity_kg: e.target.value })} />
          <TextField label="Price / kg (KES)" type="number" min={0} value={f.price_per_kg} onChange={(e) => set({ price_per_kg: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Store / location" value={f.location} onChange={(e) => set({ location: e.target.value })} />
          <TextField label="Date" type="date" value={f.purchase_date} onChange={(e) => set({ purchase_date: e.target.value })} />
        </div>
        <Select
          label="Supplier (optional)"
          options={[{ value: "", label: "—" }, ...suppliers.map((s) => ({ value: s.id, label: s.name }))]}
          value={f.supplier_id}
          onChange={(e) => set({ supplier_id: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Brand (optional)" value={f.brand} onChange={(e) => set({ brand: e.target.value })} />
          <TextField label="Batch no. (optional)" value={f.batch_number} onChange={(e) => set({ batch_number: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Expiry date (optional)" type="date" value={f.expiry_date} onChange={(e) => set({ expiry_date: e.target.value })} />
          <TextField label="Delivery date (optional)" type="date" value={f.delivery_date} onChange={(e) => set({ delivery_date: e.target.value })} />
        </div>
        <TextField label="Invoice reference (optional)" hint="Invoice or delivery note" value={f.reference} onChange={(e) => set({ reference: e.target.value })} />
        {total > 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Total: <span className="font-semibold text-gray-900 dark:text-white">KES {total.toLocaleString()}</span> · booked as a farm expense.
          </p>
        )}
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Record</Button>
      </div>
    </ModalShell>
  );
}

// ── Transfer ──────────────────────────────────────────────────────────────────

export function TransferModal({
  farmId,
  items,
  onClose,
  onSaved,
}: {
  farmId: string;
  items: FeedInventoryItem[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const stocked = items.filter((i) => Number(i.quantity_kg) > 0);
  const [f, setF] = useState({
    from_item_id: stocked[0]?.id ?? "",
    to_location: "",
    quantity_kg: "",
    transfer_date: TODAY(),
    reason: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);
  const src = items.find((i) => i.id === f.from_item_id);

  const save = useMutation({
    mutationFn: () =>
      recordTransfer(farmId, {
        from_item_id: f.from_item_id,
        to_location: f.to_location.trim(),
        quantity_kg: f.quantity_kg,
        transfer_date: f.transfer_date,
        reason: f.reason || undefined,
      }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't transfer the feed.")),
  });

  const valid =
    f.from_item_id && f.to_location.trim() && Number(f.quantity_kg) > 0 &&
    src && Number(f.quantity_kg) <= Number(src.quantity_kg);

  return (
    <ModalShell title="Transfer feed" onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="space-y-4">
        <Select
          label="From"
          options={stocked.map((i) => ({ value: i.id, label: `${i.feed_type} @ ${i.location} (${Number(i.quantity_kg)} kg)` }))}
          value={f.from_item_id}
          onChange={(e) => set({ from_item_id: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="To location" value={f.to_location} onChange={(e) => set({ to_location: e.target.value })} />
          <TextField label="Quantity (kg)" type="number" min={0} value={f.quantity_kg} onChange={(e) => set({ quantity_kg: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Date" type="date" value={f.transfer_date} onChange={(e) => set({ transfer_date: e.target.value })} />
          <TextField label="Reason (optional)" value={f.reason} onChange={(e) => set({ reason: e.target.value })} />
        </div>
        {src && <p className="text-xs text-gray-400">Available: {Number(src.quantity_kg)} kg at {src.location}.</p>}
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Transfer</Button>
      </div>
    </ModalShell>
  );
}

// ── Wastage ───────────────────────────────────────────────────────────────────

export function WastageModal({
  farmId,
  items,
  onClose,
  onSaved,
}: {
  farmId: string;
  items: FeedInventoryItem[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const stocked = items.filter((i) => Number(i.quantity_kg) > 0);
  const [f, setF] = useState({
    item_id: stocked[0]?.id ?? "",
    quantity_kg: "",
    wastage_date: TODAY(),
    reason: "spoilage",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);
  const item = items.find((i) => i.id === f.item_id);

  const save = useMutation({
    mutationFn: () =>
      recordWastage(farmId, {
        item_id: f.item_id,
        quantity_kg: f.quantity_kg,
        wastage_date: f.wastage_date,
        reason: f.reason,
      }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't record wastage.")),
  });

  const valid = f.item_id && Number(f.quantity_kg) > 0 && item && Number(f.quantity_kg) <= Number(item.quantity_kg);

  return (
    <ModalShell title="Record wastage" onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="space-y-4">
        <Select
          label="Feed item"
          options={stocked.map((i) => ({ value: i.id, label: `${i.feed_type} @ ${i.location} (${Number(i.quantity_kg)} kg)` }))}
          value={f.item_id}
          onChange={(e) => set({ item_id: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Quantity (kg)" type="number" min={0} value={f.quantity_kg} onChange={(e) => set({ quantity_kg: e.target.value })} />
          <TextField label="Date" type="date" value={f.wastage_date} onChange={(e) => set({ wastage_date: e.target.value })} />
        </div>
        <Select label="Reason" options={WASTAGE_REASONS} value={f.reason} onChange={(e) => set({ reason: e.target.value })} />
        {item && <p className="text-xs text-gray-400">On hand: {Number(item.quantity_kg)} kg. Value written off at KES {Number(item.avg_cost_per_kg).toLocaleString()}/kg.</p>}
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Write off</Button>
      </div>
    </ModalShell>
  );
}

// ── Add inventory item ──────────────────────────────────────────────────────

export function AddItemModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({
    feed_type: "broiler_starter",
    location: "main_store",
    reorder_level_kg: "",
    opening_quantity_kg: "",
    opening_cost_per_kg: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      createInventoryItem(farmId, {
        feed_type: f.feed_type,
        location: f.location.trim() || "main_store",
        reorder_level_kg: f.reorder_level_kg || undefined,
        opening_quantity_kg: f.opening_quantity_kg || undefined,
        opening_cost_per_kg: f.opening_cost_per_kg || undefined,
      }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't create the item.")),
  });

  return (
    <ModalShell title="Add inventory item" onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="space-y-4">
        <Select label="Feed type" options={FEED_TYPE_OPTIONS} value={f.feed_type} onChange={(e) => set({ feed_type: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Store / location" value={f.location} onChange={(e) => set({ location: e.target.value })} />
          <TextField label="Reorder level (kg)" type="number" min={0} value={f.reorder_level_kg} onChange={(e) => set({ reorder_level_kg: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Opening qty (kg)" type="number" min={0} value={f.opening_quantity_kg} onChange={(e) => set({ opening_quantity_kg: e.target.value })} />
          <TextField label="Opening cost / kg" type="number" min={0} value={f.opening_cost_per_kg} onChange={(e) => set({ opening_cost_per_kg: e.target.value })} />
        </div>
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Add item</Button>
      </div>
    </ModalShell>
  );
}

// ── Suppliers management ──────────────────────────────────────────────────────

export function SuppliersModal({ farmId, onClose }: { farmId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const suppliersQuery = useQuery({
    queryKey: queryKeys.feedSuppliers(farmId),
    queryFn: () => listSuppliers(farmId, true),
  });
  const suppliers = suppliersQuery.data ?? [];

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.feedSuppliers(farmId) });

  const add = useMutation({
    mutationFn: () => createSupplier(farmId, { name: name.trim(), phone: phone || undefined }),
    onSuccess: () => { setName(""); setPhone(""); invalidate(); },
    onError: (e) => setError(errMsg(e, "Couldn't add the supplier.")),
  });
  const toggle = useMutation({
    mutationFn: (s: FeedSupplier) => updateSupplier(farmId, s.id, { is_active: !s.is_active }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteSupplier(farmId, id),
    onSuccess: invalidate,
  });

  return (
    <ModalShell title="Feed suppliers" onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="mb-4 flex gap-2">
        <TextField label="" placeholder="Supplier name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField label="" placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <Button disabled={name.trim().length < 2} loading={add.isPending} onClick={() => { setError(null); add.mutate(); }}>Add</Button>
      </div>
      {suppliersQuery.isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : suppliers.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">No suppliers yet.</p>
      ) : (
        <ul className="space-y-2">
          {suppliers.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 px-3 py-2.5 dark:border-white/10">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                  {s.name} {!s.is_active && <span className="text-xs text-gray-400">(inactive)</span>}
                </p>
                <p className="truncate text-xs text-gray-400">
                  {s.phone ?? "no phone"} · KES {Number(s.total_spend_kes ?? 0).toLocaleString()} spent · {s.purchase_count ?? 0} orders
                  {s.rating ? <> · <Star className="inline h-3 w-3 text-amber-500" /> {Number(s.rating)}</> : null}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <button onClick={() => toggle.mutate(s)} className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10">
                  {s.is_active ? "Disable" : "Enable"}
                </button>
                <button onClick={() => remove.mutate(s.id)} aria-label="Delete supplier" className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-6">
        <Button variant="secondary" fullWidth onClick={onClose}>Done</Button>
      </div>
    </ModalShell>
  );
}

// ── Record consumption (used on the flock detail screen) ──────────────────────

export function ConsumptionModal({
  farmId,
  flockId,
  onClose,
  onSaved,
}: {
  farmId: string;
  flockId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const itemsQuery = useQuery({
    queryKey: queryKeys.feedInventory(farmId),
    queryFn: () => listInventory(farmId),
  });
  const stocked = (itemsQuery.data ?? []).filter((i) => Number(i.quantity_kg) > 0);

  const [f, setF] = useState({ item_id: "", quantity_kg: "", consumption_date: TODAY() });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);
  const item = stocked.find((i) => i.id === f.item_id) ?? stocked[0];
  const itemId = f.item_id || stocked[0]?.id || "";

  const save = useMutation({
    mutationFn: () =>
      recordConsumption(farmId, {
        item_id: itemId,
        flock_id: flockId,
        quantity_kg: f.quantity_kg,
        consumption_date: f.consumption_date,
      }),
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't record feed consumption.")),
  });

  const valid = itemId && Number(f.quantity_kg) > 0 && item && Number(f.quantity_kg) <= Number(item.quantity_kg);

  return (
    <ModalShell title="Record feed consumption" onClose={onClose}>
      <ErrorBanner message={error} />
      {itemsQuery.isLoading ? (
        <p className="text-sm text-gray-400">Loading stock…</p>
      ) : stocked.length === 0 ? (
        <p className="py-4 text-sm text-gray-500 dark:text-gray-400">No feed in stock. Record a purchase in the Inventory module first.</p>
      ) : (
        <div className="space-y-4">
          <Select
            label="Feed item"
            options={stocked.map((i) => ({ value: i.id, label: `${i.feed_type} @ ${i.location} (${Number(i.quantity_kg)} kg)` }))}
            value={itemId}
            onChange={(e) => set({ item_id: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Quantity (kg)" type="number" min={0} value={f.quantity_kg} onChange={(e) => set({ quantity_kg: e.target.value })} />
            <TextField label="Date" type="date" value={f.consumption_date} onChange={(e) => set({ consumption_date: e.target.value })} />
          </div>
          {item && <p className="text-xs text-gray-400">On hand: {Number(item.quantity_kg)} kg at KES {Number(item.avg_cost_per_kg).toLocaleString()}/kg.</p>}
        </div>
      )}
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Record</Button>
      </div>
    </ModalShell>
  );
}
