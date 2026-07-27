/**
 * Aviculture — Aviary Management (Module 15, Part 3).
 *
 * The facility view: the aviaries that house the collection, each showing live
 * occupancy (computed from the birds inside, never stored) and a farm-wide
 * infrastructure summary. Individual-aware housing, not a generic shed list.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, Home, Plus, Shield } from "lucide-react";

import { createAviary, getInfrastructure, listAviaries, type Aviary } from "@/api/aviaries";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge } from "./badges";
import { AviModal } from "./AviModal";

const TYPES = ["indoor", "outdoor", "mixed", "flight", "walk_in", "cage", "brooder", "quarantine"];
const PURPOSES = ["general", "breeding", "quarantine", "nursery", "display", "flight", "holding"];

export default function AviariesScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);

  const aviariesQ = useQuery({
    queryKey: ["avi-aviaries", farmId],
    queryFn: () => listAviaries(farmId as string),
    enabled: !!farmId,
  });
  const infraQ = useQuery({
    queryKey: ["avi-infra", farmId],
    queryFn: () => getInfrastructure(farmId as string),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const aviaries = aviariesQ.data?.aviaries ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Building2 className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Aviaries</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Housing &amp; infrastructure</p>
          </div>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>Add aviary</Button>
      </div>

      {/* Infrastructure summary */}
      {infraQ.data && (
        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryTile label="Aviaries" value={infraQ.data.aviary_count} />
          <SummaryTile label="Capacity" value={infraQ.data.total_capacity.value as number} fact={infraQ.data.total_capacity.label} />
          <SummaryTile label="Occupied" value={infraQ.data.total_occupied.value as number} fact={infraQ.data.total_occupied.label} />
          <SummaryTile label="Available" value={infraQ.data.available.value as number} fact={infraQ.data.available.label} />
        </div>
      )}

      {aviariesQ.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
      ) : aviaries.length === 0 ? (
        <EmptyState icon={<Home className="h-8 w-8" />} title="No aviaries yet"
          description="Add an aviary to start housing birds and tracking occupancy."
          action={<Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>Add aviary</Button>} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {aviaries.map((a) => <AviaryCard key={a.id} aviary={a} onClick={() => navigate(`/aviculture/aviaries/${a.id}`)} />)}
        </div>
      )}

      <AddAviaryModal open={addOpen} onClose={() => setAddOpen(false)} farmId={farmId}
        onCreated={() => { qc.invalidateQueries({ queryKey: ["avi-aviaries", farmId] }); qc.invalidateQueries({ queryKey: ["avi-infra", farmId] }); }} />
    </div>
  );
}

function SummaryTile({ label, value, fact }: { label: string; value: number | null; fact?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        {fact && <FactBadge label={fact} />}
      </div>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">{value ?? "—"}</p>
    </div>
  );
}

function AviaryCard({ aviary, onClick }: { aviary: Aviary; onClick: () => void }) {
  const occ = aviary.occupancy;
  return (
    <button type="button" onClick={onClick}
      className="flex flex-col rounded-xl border border-gray-200 bg-white p-4 text-left transition hover:border-brand-300 hover:shadow-sm dark:border-gray-800 dark:bg-gray-900 dark:hover:border-brand-500/40">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900 dark:text-gray-100">{aviary.name}</p>
          <p className="truncate text-xs capitalize text-gray-500 dark:text-gray-400">
            {aviary.aviary_type.replace("_", " ")} · {aviary.purpose}
          </p>
        </div>
        {(aviary.purpose === "quarantine" || aviary.biosecurity_level === "quarantine") && (
          <Shield className="h-4 w-4 shrink-0 text-amber-500" />
        )}
      </div>
      {occ && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>{occ.occupied.value} / {occ.capacity.value ?? "?"} housed</span>
            <span>{occ.utilization_pct.value != null ? `${occ.utilization_pct.value}%` : "—"}</span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
            <div className={`h-full rounded-full ${occ.over_capacity ? "bg-red-500" : "bg-brand-500"}`}
              style={{ width: `${Math.min(100, occ.utilization_pct.value ?? 0)}%` }} />
          </div>
        </div>
      )}
    </button>
  );
}

function AddAviaryModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("flight");
  const [purpose, setPurpose] = useState("general");
  const [capacity, setCapacity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: () => createAviary(farmId, { name: name.trim(), aviary_type: type, purpose,
      capacity: capacity ? Number(capacity) : null }),
    onSuccess: () => { setName(""); setCapacity(""); onCreated(); onClose(); },
    onError: () => setError("Could not create aviary."),
  });
  return (
    <AviModal open={open} onClose={onClose} title="Add aviary">
      <div className="space-y-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Breeding Flight 1" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Type" options={TYPES.map((t) => ({ value: t, label: t.replace("_", " ") }))} value={type} onChange={(e) => setType(e.target.value)} />
          <Select label="Purpose" options={PURPOSES.map((p) => ({ value: p, label: p }))} value={purpose} onChange={(e) => setPurpose(e.target.value)} />
        </div>
        <TextField label="Capacity (optional)" inputMode="numeric" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!name.trim()} onClick={() => { setError(null); m.mutate(); }}>Add aviary</Button>
        </div>
      </div>
    </AviModal>
  );
}
