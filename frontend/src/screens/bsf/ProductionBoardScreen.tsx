/**
 * BSF — Production Board (Module 16, Frontend Milestone 1).
 *
 * The operational heart: every production batch as a card, with lifecycle stage,
 * status, recorded population/biomass and its assigned unit. Presentation only —
 * the backend owns batch numbering, lifecycle validation and all calculations.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Boxes, Layers, Plus } from "lucide-react";

import {
  BATCH_STATUSES, BATCH_TYPES, LIFECYCLE_STAGES, STAGE_LABELS,
  createBatch, listBatches, listColonies, listSpecies, listUnits,
  type Batch, type BatchCreateInput,
} from "@/api/bsf";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { BsfSubnav } from "./BsfSubnav";
import { BatchStatusBadge, StageBadge } from "./badges";

function daysSince(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const d = new Date(dateStr).getTime();
  if (Number.isNaN(d)) return null;
  return Math.max(0, Math.floor((Date.now() - d) / 86_400_000));
}

function grams(v: string | null): string {
  if (v == null) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(2)} kg` : `${n} g`;
}

export default function ProductionBoardScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [status, setStatus] = useState("active");
  const [stage, setStage] = useState("");

  const batchesQ = useQuery({
    queryKey: ["bsf-batches", farmId, status, stage],
    queryFn: () => listBatches(farmId as string, {
      status: status || undefined,
      lifecycle_stage: stage || undefined,
      limit: 200,
    }),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const batches = batchesQ.data?.batches ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <BsfSubnav active="/bsf" />

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Boxes className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Production Board</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Black Soldier Fly batches</p>
          </div>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>New batch</Button>
      </div>

      {/* Filters */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:max-w-md">
        <Select
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: "", label: "All statuses" }, ...BATCH_STATUSES.map((s) => ({ value: s, label: s }))]}
        />
        <Select
          label="Stage"
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          options={[{ value: "", label: "All stages" }, ...LIFECYCLE_STAGES.map((s) => ({ value: s, label: STAGE_LABELS[s] }))]}
        />
      </div>

      {batchesQ.isError ? (
        <ErrorState onRetry={() => batchesQ.refetch()} />
      ) : batchesQ.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}
        </div>
      ) : batches.length === 0 ? (
        <EmptyState
          icon={<Layers className="h-8 w-8" />}
          title="No batches match"
          description="Start a production batch to begin tracking its lifecycle, feeding and harvest."
          action={<Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>New batch</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {batches.map((b) => (
            <BatchCard key={b.id} batch={b} onClick={() => navigate(`/bsf/batches/${b.id}`)} />
          ))}
        </div>
      )}

      <NewBatchModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        farmId={farmId}
        onCreated={() => qc.invalidateQueries({ queryKey: ["bsf-batches", farmId] })}
      />
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-500/30 dark:bg-red-500/10">
      <p className="text-sm text-red-700 dark:text-red-300">Couldn’t load batches.</p>
      <Button variant="ghost" className="mt-2" onClick={onRetry}>Try again</Button>
    </div>
  );
}

function BatchCard({ batch, onClick }: { batch: Batch; onClick: () => void }) {
  const days = daysSince(batch.stage_started_on);
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col rounded-xl border border-gray-200 bg-white p-4 text-left transition hover:border-brand-300 hover:shadow-sm dark:border-gray-800 dark:bg-gray-900 dark:hover:border-brand-500/40"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900 dark:text-gray-100">{batch.batch_number}</p>
          {batch.name && <p className="truncate text-xs text-gray-500 dark:text-gray-400">{batch.name}</p>}
        </div>
        <BatchStatusBadge status={batch.status} />
      </div>
      <div className="mt-3 flex items-center gap-2">
        <StageBadge stage={batch.lifecycle_stage} />
        {days != null && <span className="text-xs text-gray-400">{days}d in stage</span>}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <p className="text-gray-400">Population</p>
          <p className="font-medium text-gray-800 dark:text-gray-200">
            {batch.population_estimate != null ? batch.population_estimate.toLocaleString() : "—"}
          </p>
        </div>
        <div>
          <p className="text-gray-400">Biomass</p>
          <p className="font-medium text-gray-800 dark:text-gray-200">{grams(batch.biomass_estimate_g)}</p>
        </div>
      </div>
    </button>
  );
}

function NewBatchModal({
  open, onClose, farmId, onCreated,
}: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [form, setForm] = useState<BatchCreateInput>({ batch_type: "production", lifecycle_stage: "egg" });
  const [error, setError] = useState<string | null>(null);

  const speciesQ = useQuery({ queryKey: ["bsf-species", farmId], queryFn: () => listSpecies(farmId), enabled: open });
  const unitsQ = useQuery({ queryKey: ["bsf-units", farmId], queryFn: () => listUnits(farmId), enabled: open });
  const coloniesQ = useQuery({ queryKey: ["bsf-colonies", farmId], queryFn: () => listColonies(farmId), enabled: open });

  const m = useMutation({
    mutationFn: () => createBatch(farmId, {
      ...form,
      name: form.name?.trim() || null,
      population_estimate: form.population_estimate ? Number(form.population_estimate) : null,
      biomass_estimate_g: form.biomass_estimate_g ? Number(form.biomass_estimate_g) : null,
    }),
    onSuccess: () => { setForm({ batch_type: "production", lifecycle_stage: "egg" }); onCreated(); onClose(); },
    onError: () => setError("Could not create batch. Check the values and your permissions."),
  });

  return (
    <Modal open={open} onClose={onClose} title="New production batch">
      <div className="space-y-4">
        <TextField
          label="Name (optional)"
          value={form.name ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          placeholder="e.g. March breeding run"
        />
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Type"
            value={form.batch_type}
            onChange={(e) => setForm((f) => ({ ...f, batch_type: e.target.value }))}
            options={BATCH_TYPES.map((t) => ({ value: t, label: t }))}
          />
          <Select
            label="Starting stage"
            value={form.lifecycle_stage}
            onChange={(e) => setForm((f) => ({ ...f, lifecycle_stage: e.target.value }))}
            options={LIFECYCLE_STAGES.map((s) => ({ value: s, label: STAGE_LABELS[s] }))}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Species (optional)"
            value={form.species_id ?? ""}
            onChange={(e) => setForm((f) => ({ ...f, species_id: e.target.value || null }))}
            options={[{ value: "", label: "—" }, ...(speciesQ.data ?? []).map((s) => ({ value: s.id, label: s.common_name }))]}
          />
          <Select
            label="Production unit (optional)"
            value={form.production_unit_id ?? ""}
            onChange={(e) => setForm((f) => ({ ...f, production_unit_id: e.target.value || null }))}
            options={[{ value: "", label: "—" }, ...(unitsQ.data ?? []).map((u) => ({ value: u.id, label: u.name }))]}
          />
        </div>
        <Select
          label="Source colony (optional)"
          value={form.source_colony_id ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, source_colony_id: e.target.value || null }))}
          options={[{ value: "", label: "—" }, ...(coloniesQ.data ?? []).map((c) => ({ value: c.id, label: c.name }))]}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Population estimate"
            inputMode="numeric"
            value={form.population_estimate != null ? String(form.population_estimate) : ""}
            onChange={(e) => setForm((f) => ({ ...f, population_estimate: e.target.value ? Number(e.target.value) : null }))}
          />
          <TextField
            label="Biomass (grams)"
            inputMode="numeric"
            value={form.biomass_estimate_g != null ? String(form.biomass_estimate_g) : ""}
            onChange={(e) => setForm((f) => ({ ...f, biomass_estimate_g: e.target.value ? Number(e.target.value) : null }))}
          />
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} onClick={() => { setError(null); m.mutate(); }}>Create batch</Button>
        </div>
      </div>
    </Modal>
  );
}
