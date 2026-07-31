/**
 * BSF — Feedstock & Feeding (Module 16, Frontend Milestone 4).
 *
 * Manage organic feedstock as first-class lots (remaining quantity, quality,
 * cost, status) and record immutable feeding events against a batch. Low-stock
 * and spoilage are surfaced as warnings. Cost posting reuses the shared Finance
 * ledger. The backend owns consumption tracking and feed-conversion maths.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Sprout, UtensilsCrossed } from "lucide-react";

import { listBatches } from "@/api/bsf";
import {
  FEEDING_METHODS, FEEDSTOCK_CATEGORIES, FEEDSTOCK_QUALITIES,
  createFeedstockLot, listFeedstockLots, postFeedstockExpense, recordFeeding,
  type FeedstockLot,
} from "@/api/bsfFeeding";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { BsfSubnav } from "./BsfSubnav";

const LOW_STOCK_KG = 10;
const num = (v: string | null) => (v == null ? 0 : Number(v));

export default function BsfFeedstockScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [feedOpen, setFeedOpen] = useState(false);

  const lotsQ = useQuery({
    queryKey: ["bsf-feedstock", farmId],
    queryFn: () => listFeedstockLots(farmId as string),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const lots = lotsQ.data ?? [];
  const invalidate = () => qc.invalidateQueries({ queryKey: ["bsf-feedstock", farmId] });

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <BsfSubnav active="/bsf/feedstock" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Sprout className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Feedstock &amp; Feeding</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Organic feedstock lots &amp; feeding events</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" leftIcon={<UtensilsCrossed className="h-4 w-4" />} onClick={() => setFeedOpen(true)}>Record feeding</Button>
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>Add lot</Button>
        </div>
      </div>

      {lotsQ.isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-500/30 dark:bg-red-500/10">
          <p className="text-sm text-red-700 dark:text-red-300">Couldn’t load feedstock.</p>
          <Button variant="ghost" className="mt-2" onClick={() => lotsQ.refetch()}>Try again</Button>
        </div>
      ) : lotsQ.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
      ) : lots.length === 0 ? (
        <EmptyState icon={<Sprout className="h-8 w-8" />} title="No feedstock yet"
          description="Add a feedstock lot to feed your batches and track waste conversion."
          action={<Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>Add lot</Button>} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {lots.map((l) => <LotCard key={l.id} lot={l} farmId={farmId} onChanged={invalidate} />)}
        </div>
      )}

      <AddLotModal open={addOpen} onClose={() => setAddOpen(false)} farmId={farmId} onCreated={invalidate} />
      <RecordFeedingModal open={feedOpen} onClose={() => setFeedOpen(false)} farmId={farmId} onDone={invalidate} />
    </div>
  );
}

const QUALITY_STYLES: Record<string, string> = {
  excellent: "text-emerald-600", good: "text-brand-600", fair: "text-amber-600",
  poor: "text-orange-600", spoiled: "text-red-600", unknown: "text-gray-400",
};

function LotCard({ lot, farmId, onChanged }: { lot: FeedstockLot; farmId: string; onChanged: () => void }) {
  const remaining = num(lot.remaining_kg);
  const weight = num(lot.weight_kg);
  const pct = weight > 0 ? Math.min(100, (remaining / weight) * 100) : 0;
  const low = remaining <= LOW_STOCK_KG && lot.status !== "depleted";
  const [msg, setMsg] = useState<string | null>(null);

  const postM = useMutation({
    mutationFn: () => postFeedstockExpense(farmId, lot.id),
    onSuccess: () => { setMsg("Cost posted to the finance ledger."); onChanged(); },
    onError: (e: unknown) => {
      const d = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
      setMsg(d || "Could not post cost.");
    },
  });

  return (
    <div className="flex flex-col rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900 dark:text-gray-100">{lot.name}</p>
          <p className="truncate text-xs capitalize text-gray-500 dark:text-gray-400">{lot.category.replace(/_/g, " ")}</p>
        </div>
        <span className={`text-xs font-medium capitalize ${QUALITY_STYLES[lot.quality] ?? QUALITY_STYLES.unknown}`}>{lot.quality}</span>
      </div>
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{remaining} / {weight} kg</span>
          <span className="capitalize">{lot.status.replace(/_/g, " ")}</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
          <div className={`h-full rounded-full ${low ? "bg-amber-500" : "bg-brand-500"}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      {low && <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">Low stock — consider restocking.</p>}
      {lot.quality === "spoiled" && <p className="mt-1 text-xs text-red-600 dark:text-red-400">Spoilage risk.</p>}
      {lot.cost && (
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-gray-500">{lot.currency ? `${lot.currency} ` : ""}{lot.cost}</span>
          <Button size="sm" variant="ghost" loading={postM.isPending} onClick={() => { setMsg(null); postM.mutate(); }}>Post to ledger</Button>
        </div>
      )}
      {msg && <p className="mt-1 text-xs text-gray-500">{msg}</p>}
    </div>
  );
}

function AddLotModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("market_waste");
  const [weight, setWeight] = useState("");
  const [quality, setQuality] = useState("good");
  const [cost, setCost] = useState("");
  const [error, setError] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: () => createFeedstockLot(farmId, {
      name: name.trim(), category, weight_kg: Number(weight), quality,
      cost: cost ? Number(cost) : null,
    }),
    onSuccess: () => { setName(""); setWeight(""); setCost(""); onCreated(); onClose(); },
    onError: () => setError("Could not create the lot."),
  });

  return (
    <Modal open={open} onClose={onClose} title="Add feedstock lot">
      <div className="space-y-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Market waste — Tue" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Category" value={category} onChange={(e) => setCategory(e.target.value)}
            options={FEEDSTOCK_CATEGORIES.map((c) => ({ value: c, label: c.replace(/_/g, " ") }))} />
          <Select label="Quality" value={quality} onChange={(e) => setQuality(e.target.value)}
            options={FEEDSTOCK_QUALITIES.map((q) => ({ value: q, label: q }))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Weight (kg)" inputMode="numeric" value={weight} onChange={(e) => setWeight(e.target.value)} />
          <TextField label="Cost (optional)" inputMode="numeric" value={cost} onChange={(e) => setCost(e.target.value)} />
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!name.trim() || !weight} onClick={() => { setError(null); m.mutate(); }}>Add lot</Button>
        </div>
      </div>
    </Modal>
  );
}

function RecordFeedingModal({ open, onClose, farmId, onDone }: { open: boolean; onClose: () => void; farmId: string; onDone: () => void }) {
  const [batchId, setBatchId] = useState("");
  const [lotId, setLotId] = useState("");
  const [qty, setQty] = useState("");
  const [method, setMethod] = useState("manual");
  const [error, setError] = useState<string | null>(null);

  const batchesQ = useQuery({ queryKey: ["bsf-batches", farmId, "active", ""], queryFn: () => listBatches(farmId, { status: "active", limit: 200 }), enabled: open });
  const lotsQ = useQuery({ queryKey: ["bsf-feedstock", farmId], queryFn: () => listFeedstockLots(farmId), enabled: open });

  const m = useMutation({
    mutationFn: () => recordFeeding(farmId, batchId, { feedstock_lot_id: lotId || null, quantity_kg: Number(qty), feeding_method: method }),
    onSuccess: () => { setQty(""); onDone(); onClose(); },
    onError: (e: unknown) => {
      const d = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
      setError(d || "Could not record feeding.");
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Record feeding">
      <div className="space-y-4">
        <Select label="Batch" value={batchId} onChange={(e) => setBatchId(e.target.value)}
          options={[{ value: "", label: "Select a batch…" }, ...(batchesQ.data?.batches ?? []).map((b) => ({ value: b.id, label: `${b.batch_number}${b.name ? ` · ${b.name}` : ""}` }))]} />
        <Select label="Feedstock lot (optional)" value={lotId} onChange={(e) => setLotId(e.target.value)}
          options={[{ value: "", label: "—" }, ...(lotsQ.data ?? []).map((l) => ({ value: l.id, label: `${l.name} (${l.remaining_kg} kg left)` }))]} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Quantity (kg)" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} />
          <Select label="Method" value={method} onChange={(e) => setMethod(e.target.value)}
            options={FEEDING_METHODS.map((mth) => ({ value: mth, label: mth.replace(/_/g, " ") }))} />
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!batchId || !qty} onClick={() => { setError(null); m.mutate(); }}>Record feeding</Button>
        </div>
      </div>
    </Modal>
  );
}
