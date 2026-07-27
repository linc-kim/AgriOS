/**
 * Aviculture — Incubation (Module 15, Part 5).
 *
 * The hatch workspace: incubation batches with a species-driven schedule
 * (lockdown/hatch dates computed by the pure engine), eggs, candling, hatching,
 * and honesty-labelled fertility/hatch statistics. A hatched egg becomes a real
 * chick bird linked to its pair.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Egg as EggIcon, Plus } from "lucide-react";

import {
  candleEgg, createBatch, createEgg, getBatch, hatchEgg, listBatches, listEggs, setEggs,
  type Batch,
} from "@/api/incubation";
import { listSpecies } from "@/api/aviculture";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { FactBadge } from "./badges";
import { AviModal } from "./AviModal";
import { AviSubnav } from "./AviSubnav";

export default function IncubationScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const batchesQ = useQuery({ queryKey: ["avi-batches", farmId], queryFn: () => listBatches(farmId as string), enabled: !!farmId });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const batches = batchesQ.data ?? [];

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Incubation</h1>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>New batch</Button>
      </div>
      <AviSubnav farmId={farmId} active="/aviculture/incubation" />

      {batchesQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : batches.length === 0 ? (
        <EmptyState icon={<EggIcon className="h-8 w-8" />} title="No incubation batches yet"
          description="Create a batch to set eggs and track the hatch process."
          action={<Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>New batch</Button>} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {batches.map((b) => <BatchCard key={b.id} batch={b} onClick={() => setSelected(b.id)} active={selected === b.id} />)}
        </div>
      )}

      {selected && <BatchDetail farmId={farmId} batchId={selected} />}

      <NewBatchModal open={addOpen} onClose={() => setAddOpen(false)} farmId={farmId}
        onCreated={() => qc.invalidateQueries({ queryKey: ["avi-batches", farmId] })} />
    </div>
  );
}

function BatchCard({ batch, onClick, active }: { batch: Batch; onClick: () => void; active: boolean }) {
  const phase = batch.progress?.phase?.value as string | undefined;
  return (
    <button type="button" onClick={onClick}
      className={cn("rounded-xl border p-4 text-left transition dark:bg-gray-900",
        active ? "border-brand-400 dark:border-brand-500/50" : "border-gray-200 hover:border-brand-300 dark:border-gray-800")}>
      <div className="flex items-center justify-between">
        <p className="font-medium text-gray-900 dark:text-gray-100">{batch.name}</p>
        <span className="text-xs capitalize text-gray-500 dark:text-gray-400">{batch.status}</span>
      </div>
      <p className="mt-1 text-xs capitalize text-gray-500 dark:text-gray-400">
        {batch.method} · {batch.egg_count} egg(s){phase ? ` · ${phase.replace("_", " ")}` : ""}
      </p>
      {batch.expected_hatch_on && <p className="mt-1 text-xs text-gray-400">Hatch due {batch.expected_hatch_on}</p>}
    </button>
  );
}

function Stat({ label, v }: { label: string; v?: { label: string; value: unknown } }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        {v && <FactBadge label={v.label} />}
      </div>
      <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
        {v && v.value != null ? String(v.value) : "—"}
      </p>
    </div>
  );
}

function BatchDetail({ farmId, batchId }: { farmId: string; batchId: string }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const batchQ = useQuery({ queryKey: ["avi-batch", farmId, batchId], queryFn: () => getBatch(farmId, batchId) });
  const eggsQ = useQuery({ queryKey: ["avi-eggs", farmId, batchId], queryFn: () => listEggs(farmId, { batch_id: batchId }) });
  const speciesQ = useQuery({ queryKey: ["avi-species", farmId], queryFn: () => listSpecies(farmId) });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["avi-batch", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["avi-eggs", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["avi-batches", farmId] });
  };

  const addEgg = useMutation({
    mutationFn: () => createEgg(farmId, { species_id: batchQ.data?.species_id ?? speciesQ.data?.[0]?.id }),
    onSuccess: async (egg) => { await setEggs(farmId, batchId, [egg.id]); refresh(); },
  });
  const candle = useMutation({
    mutationFn: (v: { id: string; result: string }) => candleEgg(farmId, v.id, { result: v.result }),
    onSuccess: refresh,
  });
  const hatch = useMutation({
    mutationFn: (v: { id: string; outcome: string }) => hatchEgg(farmId, v.id, { outcome: v.outcome, create_chick: true }),
    onSuccess: (h) => { refresh(); if (h.chick_bird_id) navigate(`/aviculture/${h.chick_bird_id}`); },
  });

  if (batchQ.isLoading || !batchQ.data) return <div className="mt-5"><Skeleton className="h-40 rounded-xl" /></div>;
  const b = batchQ.data;
  const st = b.statistics ?? {};
  const prog = b.progress ?? {};

  return (
    <div className="mt-6 rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{b.name}</h2>
        <Button variant="secondary" leftIcon={<Plus className="h-4 w-4" />} loading={addEgg.isPending} onClick={() => addEgg.mutate()}>
          Add &amp; set egg
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Phase" v={prog.phase} />
        <Stat label="Day" v={prog.day_number} />
        <Stat label="Eggs set" v={st.eggs_set} />
        <Stat label="Hatch rate %" v={st.hatch_rate_pct} />
        <Stat label="Fertile" v={st.fertile} />
        <Stat label="Hatched" v={st.hatched} />
        <Stat label="Fertility %" v={st.fertility_rate_pct} />
        <Stat label="Of fertile %" v={st.hatch_of_fertile_pct} />
      </div>

      <h3 className="mb-2 mt-5 text-sm font-semibold text-gray-900 dark:text-gray-100">Eggs</h3>
      {(eggsQ.data ?? []).length === 0 ? <p className="text-sm text-gray-500 dark:text-gray-400">No eggs in this batch yet.</p> : (
        <div className="space-y-2">{(eggsQ.data ?? []).map((e) => (
          <div key={e.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-200 p-2 dark:border-gray-800">
            <div className="text-sm">
              <span className="font-mono text-gray-700 dark:text-gray-300">{e.identifier}</span>
              <span className="ml-2 capitalize text-gray-500 dark:text-gray-400">{e.status} · {e.fertility_status}</span>
            </div>
            {e.status !== "hatched" && e.status !== "failed" && (
              <div className="flex flex-wrap gap-1">
                <Button variant="ghost" onClick={() => candle.mutate({ id: e.id, result: "fertile" })}>Candle: fertile</Button>
                <Button variant="ghost" onClick={() => candle.mutate({ id: e.id, result: "infertile" })}>infertile</Button>
                <Button variant="ghost" onClick={() => hatch.mutate({ id: e.id, outcome: "hatched" })}>Hatch</Button>
                <Button variant="ghost" onClick={() => hatch.mutate({ id: e.id, outcome: "failed" })}>Fail</Button>
              </div>
            )}
            {e.hatched_bird_id && (
              <button type="button" className="text-xs text-brand-600 hover:underline dark:text-brand-300"
                onClick={() => navigate(`/aviculture/${e.hatched_bird_id}`)}>View chick →</button>
            )}
          </div>
        ))}</div>
      )}
    </div>
  );
}

function NewBatchModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [method, setMethod] = useState("artificial");
  const [speciesId, setSpeciesId] = useState("");
  const [setOn, setSetOn] = useState("");
  const speciesQ = useQuery({ queryKey: ["avi-species", farmId], queryFn: () => listSpecies(farmId), enabled: open });
  const m = useMutation({
    mutationFn: () => createBatch(farmId, { name: name.trim(), method, species_id: speciesId || undefined, set_on: setOn || undefined }),
    onSuccess: () => { setName(""); setSetOn(""); onCreated(); onClose(); },
  });
  const speciesOpts = [{ value: "", label: "Species (optional)" }, ...(speciesQ.data ?? []).map((s) => ({ value: s.id, label: s.common_name }))];
  return (
    <AviModal open={open} onClose={onClose} title="New incubation batch">
      <div className="space-y-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. July Silkie run" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Method" options={["artificial", "natural", "foster"].map((x) => ({ value: x, label: x }))} value={method} onChange={(e) => setMethod(e.target.value)} />
          <Select label="Species" options={speciesOpts} value={speciesId} onChange={(e) => setSpeciesId(e.target.value)} />
        </div>
        <TextField label="Set date (optional)" type="date" value={setOn} onChange={(e) => setSetOn(e.target.value)} />
        <p className="text-xs text-gray-500 dark:text-gray-400">Lockdown &amp; hatch dates are computed from the species profile.</p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!name.trim()} onClick={() => m.mutate()}>Create batch</Button>
        </div>
      </div>
    </AviModal>
  );
}
