/**
 * BSF — Harvest & Frass (Module 16, Frontend Milestone 5).
 *
 * Select a batch, see its deterministic harvest-readiness signal, and record
 * harvests (with revenue as a recorded fact and optional routing into platform
 * Inventory) and frass collection. The backend owns readiness, yield validation
 * and the inventory movement; the frontend presents and triggers.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Scissors, Sprout } from "lucide-react";

import { listBatches } from "@/api/bsf";
import {
  HARVEST_DESTINATIONS, HARVEST_TYPES, QUALITY_GRADES,
  getHarvestReadiness, listFrass, listHarvests, recordFrass, recordHarvest,
} from "@/api/bsfHarvest";
import { listInvItems } from "@/api/inventory";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { FactBadge } from "@/components/common/FactBadge";
import { BsfSubnav } from "./BsfSubnav";

const readyStyle: Record<string, string> = {
  ready: "text-emerald-600", approaching: "text-amber-600",
  not_ready: "text-gray-500", past_window: "text-orange-600", unknown: "text-gray-400",
};

export default function BsfHarvestScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [batchId, setBatchId] = useState("");
  const [modal, setModal] = useState<null | "harvest" | "frass">(null);

  const batchesQ = useQuery({
    queryKey: ["bsf-batches", farmId, "active", ""],
    queryFn: () => listBatches(farmId as string, { status: "active", limit: 200 }),
    enabled: !!farmId,
  });
  const readyQ = useQuery({
    queryKey: ["bsf-readiness", farmId, batchId],
    queryFn: () => getHarvestReadiness(farmId as string, batchId),
    enabled: !!farmId && !!batchId,
  });
  const harvestsQ = useQuery({
    queryKey: ["bsf-harvests", farmId, batchId],
    queryFn: () => listHarvests(farmId as string, batchId),
    enabled: !!farmId && !!batchId,
  });
  const frassQ = useQuery({
    queryKey: ["bsf-frass", farmId, batchId],
    queryFn: () => listFrass(farmId as string, batchId),
    enabled: !!farmId && !!batchId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const batches = batchesQ.data?.batches ?? [];
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["bsf-harvests", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["bsf-frass", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["bsf-readiness", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["bsf-batches", farmId] });
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <BsfSubnav active="/bsf/harvest" />
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <Scissors className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Harvest &amp; Frass</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Record harvests and frass collection</p>
        </div>
      </div>

      <div className="mb-5 max-w-md">
        <Select label="Batch" value={batchId} onChange={(e) => setBatchId(e.target.value)}
          options={[{ value: "", label: "Select a batch…" }, ...batches.map((b) => ({ value: b.id, label: `${b.batch_number}${b.name ? ` · ${b.name}` : ""}` }))]} />
      </div>

      {!batchId ? (
        <p className="text-sm text-gray-400">Select a batch to view readiness and record harvests.</p>
      ) : (
        <div className="space-y-5">
          {/* Readiness */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            {readyQ.isLoading ? <Skeleton className="h-10" /> : readyQ.data && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-gray-400">Harvest readiness</p>
                  <p className={`text-lg font-semibold capitalize ${readyStyle[String(readyQ.data.readiness.value)] ?? readyStyle.unknown}`} title={readyQ.data.readiness.detail}>
                    {String(readyQ.data.readiness.value).replace(/_/g, " ")} <FactBadge label={readyQ.data.readiness.label} />
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs uppercase tracking-wide text-gray-400">Total harvested</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{String(readyQ.data.total_harvested_kg.value)} kg</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" leftIcon={<Scissors className="h-4 w-4" />} onClick={() => setModal("harvest")}>Record harvest</Button>
                  <Button size="sm" variant="ghost" leftIcon={<Sprout className="h-4 w-4" />} onClick={() => setModal("frass")}>Record frass</Button>
                </div>
              </div>
            )}
          </div>

          {/* Histories */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <section>
              <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Harvests</h2>
              {(harvestsQ.data ?? []).length === 0 ? <p className="text-sm text-gray-400">No harvests yet.</p> : (
                <ul className="space-y-2">
                  {harvestsQ.data!.map((h) => (
                    <li key={h.id} className="rounded-lg border border-gray-200 bg-white p-3 text-sm dark:border-gray-800 dark:bg-gray-900">
                      <div className="flex items-center justify-between">
                        <span className="font-medium capitalize text-gray-800 dark:text-gray-200">{h.harvest_type} · {h.quantity_kg} kg{h.is_complete ? " (complete)" : ""}</span>
                        <span className="text-xs text-gray-400">{h.harvested_on}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                        <span className="capitalize">{h.destination}</span>
                        {h.revenue_amount && <span>· {h.currency ? `${h.currency} ` : ""}{h.revenue_amount} <FactBadge label="recorded" /></span>}
                        {h.inventory_movement_id && <span>· stocked <FactBadge label="recorded" /></span>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Frass</h2>
              {(frassQ.data ?? []).length === 0 ? <p className="text-sm text-gray-400">No frass yet.</p> : (
                <ul className="space-y-2">
                  {frassQ.data!.map((fr) => (
                    <li key={fr.id} className="rounded-lg border border-gray-200 bg-white p-3 text-sm dark:border-gray-800 dark:bg-gray-900">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-800 dark:text-gray-200">{fr.weight_kg} kg{fr.moisture_pct ? ` · ${fr.moisture_pct}% moisture` : ""}</span>
                        <span className="text-xs text-gray-400">{fr.collected_on}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </div>
      )}

      {modal && batchId && (
        <HarvestFrassModal kind={modal} onClose={() => setModal(null)} farmId={farmId} batchId={batchId} onDone={() => { invalidate(); setModal(null); }} />
      )}
    </div>
  );
}

function HarvestFrassModal({
  kind, onClose, farmId, batchId, onDone,
}: { kind: "harvest" | "frass"; onClose: () => void; farmId: string; batchId: string; onDone: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const itemsQ = useQuery({ queryKey: ["inv-items", farmId], queryFn: () => listInvItems(farmId), enabled: true });
  const itemOptions = [{ value: "", label: "Don’t stock (record fact only)" }, ...(itemsQ.data ?? []).map((it) => ({ value: it.id, label: it.name }))];

  // Harvest state
  const [type, setType] = useState("larvae");
  const [qty, setQty] = useState("");
  const [complete, setComplete] = useState(false);
  const [grade, setGrade] = useState("ungraded");
  const [destination, setDestination] = useState("inventory");
  const [revenue, setRevenue] = useState("");
  const [itemId, setItemId] = useState("");
  // Frass extra
  const [moisture, setMoisture] = useState("");

  const harvestM = useMutation({
    mutationFn: () => recordHarvest(farmId, batchId, {
      harvest_type: type, quantity_kg: Number(qty), is_complete: complete, quality_grade: grade,
      destination, revenue_amount: revenue ? Number(revenue) : null, inventory_item_id: itemId || null,
    }),
    onSuccess: onDone,
    onError: fail(setError, "Could not record harvest."),
  });
  const frassM = useMutation({
    mutationFn: () => recordFrass(farmId, batchId, {
      weight_kg: Number(qty), moisture_pct: moisture ? Number(moisture) : null, inventory_item_id: itemId || null,
    }),
    onSuccess: onDone,
    onError: fail(setError, "Could not record frass."),
  });

  return (
    <Modal open onClose={onClose} title={kind === "harvest" ? "Record harvest" : "Record frass"}>
      <div className="space-y-4">
        {kind === "harvest" && (
          <div className="grid grid-cols-2 gap-3">
            <Select label="Type" value={type} onChange={(e) => setType(e.target.value)} options={HARVEST_TYPES.map((t) => ({ value: t, label: t }))} />
            <Select label="Quality" value={grade} onChange={(e) => setGrade(e.target.value)} options={QUALITY_GRADES.map((g) => ({ value: g, label: g }))} />
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <TextField label={kind === "harvest" ? "Quantity (kg)" : "Weight (kg)"} inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} />
          {kind === "harvest"
            ? <Select label="Destination" value={destination} onChange={(e) => setDestination(e.target.value)} options={HARVEST_DESTINATIONS.map((d) => ({ value: d, label: d }))} />
            : <TextField label="Moisture (%)" inputMode="numeric" value={moisture} onChange={(e) => setMoisture(e.target.value)} />}
        </div>
        {kind === "harvest" && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Revenue (optional)" inputMode="numeric" value={revenue} onChange={(e) => setRevenue(e.target.value)} />
            <label className="flex items-end gap-2 pb-2 text-sm text-gray-600 dark:text-gray-300">
              <input type="checkbox" checked={complete} onChange={(e) => setComplete(e.target.checked)} /> Complete harvest
            </label>
          </div>
        )}
        <Select label="Add to inventory (optional)" value={itemId} onChange={(e) => setItemId(e.target.value)} options={itemOptions} />
        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          {kind === "harvest"
            ? <Button loading={harvestM.isPending} disabled={!qty} onClick={() => { setError(null); harvestM.mutate(); }}>Record harvest</Button>
            : <Button loading={frassM.isPending} disabled={!qty} onClick={() => { setError(null); frassM.mutate(); }}>Record frass</Button>}
        </div>
      </div>
    </Modal>
  );
}

function fail(setError: (m: string) => void, fallback: string) {
  return (e: unknown) => {
    const d = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
    setError(d || fallback);
  };
}
