/**
 * Aviculture — Breeding Workspace (Module 15, Part 4).
 *
 * Pairs, breeding programmes and a live compatibility checker. Every genetic
 * figure — relationship coefficient, expected offspring inbreeding — is computed
 * by the deterministic pedigree engine and shown with its honesty label, so a
 * probability is never presented as a promise (Doc 07 §12, Doc 15 §15).
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GitBranch, HeartHandshake, Plus, Sparkles } from "lucide-react";

import { listBirds, type Bird } from "@/api/aviculture";
import {
  checkCompatibility, createPair, createProgram, dissolvePair, listPairs, listPrograms,
  type Compatibility, type Pair,
} from "@/api/breeding";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { TextField } from "@/components/ui/TextField";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { FactBadge, RiskBadge } from "./badges";
import { AviModal } from "./AviModal";

type Tab = "pairs" | "checker" | "programs";

export default function BreedingScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [tab, setTab] = useState<Tab>("pairs");

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <GitBranch className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Breeding</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Pairs, programmes &amp; deterministic genetics</p>
        </div>
      </div>

      <div className="mb-5 flex gap-1 border-b border-gray-200 dark:border-gray-800">
        {(["pairs", "checker", "programs"] as Tab[]).map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={cn("border-b-2 px-3 py-2 text-sm font-medium capitalize transition",
              tab === t ? "border-brand-500 text-brand-700 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300")}>
            {t === "checker" ? "Compatibility" : t}
          </button>
        ))}
      </div>

      {tab === "pairs" && <Pairs farmId={farmId} />}
      {tab === "checker" && <CompatibilityChecker farmId={farmId} />}
      {tab === "programs" && <Programs farmId={farmId} />}
    </div>
  );
}

// ── Pairs ─────────────────────────────────────────────────────────────────────

function Pairs({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["avi-pairs", farmId], queryFn: () => listPairs(farmId) });
  const dissolve = useMutation({
    mutationFn: (id: string) => dissolvePair(farmId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["avi-pairs", farmId] }),
  });

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>New pair</Button>
      </div>
      {q.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (q.data?.pairs ?? []).length === 0 ? (
        <EmptyState icon={<HeartHandshake className="h-8 w-8" />} title="No breeding pairs yet"
          description="Form a pair to track breeding relationships and genetics." />
      ) : (
        <div className="space-y-2">{(q.data?.pairs ?? []).map((p) => <PairRow key={p.id} pair={p} onDissolve={() => dissolve.mutate(p.id)} />)}</div>
      )}
      <CreatePairModal open={open} onClose={() => setOpen(false)} farmId={farmId}
        onCreated={() => qc.invalidateQueries({ queryKey: ["avi-pairs", farmId] })} />
    </div>
  );
}

function PairRow({ pair, onDissolve }: { pair: Pair; onDissolve: () => void }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {pair.name || `${pair.male_name ?? "?"} × ${pair.female_name ?? "?"}`}
          </p>
          <p className="text-xs capitalize text-gray-500 dark:text-gray-400">{pair.status} · {pair.formation_type}</p>
        </div>
        {pair.status === "active" && <Button variant="ghost" onClick={onDissolve}>Dissolve</Button>}
      </div>
    </div>
  );
}

function BirdPicker({ label, value, onChange, birds, sexFilter }: {
  label: string; value: string; onChange: (v: string) => void; birds: Bird[]; sexFilter?: string;
}) {
  const opts = [{ value: "", label: `Select ${label}…` }, ...birds
    .filter((b) => !sexFilter || b.sex === sexFilter || b.sex === "unknown")
    .map((b) => ({ value: b.id, label: `${b.name || b.internal_ref} (${b.sex})` }))];
  return <Select label={label} options={opts} value={value} onChange={(e) => onChange(e.target.value)} />;
}

function CreatePairModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [male, setMale] = useState("");
  const [female, setFemale] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const birdsQ = useQuery({ queryKey: ["avi-birds-active", farmId], queryFn: () => listBirds(farmId, { status: "active", limit: 200 }), enabled: open });
  const birds = birdsQ.data?.birds ?? [];

  const m = useMutation({
    mutationFn: () => createPair(farmId, { male_bird_id: male || undefined, female_bird_id: female || undefined, name: name.trim() || undefined }),
    onSuccess: () => { setMale(""); setFemale(""); setName(""); onCreated(); onClose(); },
    onError: () => setError("Could not create pair."),
  });

  return (
    <AviModal open={open} onClose={onClose} title="New breeding pair">
      <div className="space-y-4">
        <BirdPicker label="Male" value={male} onChange={setMale} birds={birds} sexFilter="male" />
        <BirdPicker label="Female" value={female} onChange={setFemale} birds={birds} sexFilter="female" />
        <TextField label="Pair name (optional)" value={name} onChange={(e) => setName(e.target.value)} />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} onClick={() => { setError(null); m.mutate(); }}>Create pair</Button>
        </div>
      </div>
    </AviModal>
  );
}

// ── Compatibility checker ─────────────────────────────────────────────────────

function CompatibilityChecker({ farmId }: { farmId: string }) {
  const [male, setMale] = useState("");
  const [female, setFemale] = useState("");
  const [result, setResult] = useState<Compatibility | null>(null);
  const birdsQ = useQuery({ queryKey: ["avi-birds-active", farmId], queryFn: () => listBirds(farmId, { status: "active", limit: 200 }) });
  const birds = birdsQ.data?.birds ?? [];
  const m = useMutation({
    mutationFn: () => checkCompatibility(farmId, male, female),
    onSuccess: setResult,
  });

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <BirdPicker label="Male" value={male} onChange={setMale} birds={birds} sexFilter="male" />
          <BirdPicker label="Female" value={female} onChange={setFemale} birds={birds} sexFilter="female" />
        </div>
        <div className="mt-3 flex justify-end">
          <Button leftIcon={<Sparkles className="h-4 w-4" />} loading={m.isPending} disabled={!male || !female} onClick={() => m.mutate()}>
            Assess compatibility
          </Button>
        </div>
      </div>

      {result && (
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          <div className="mb-3 flex items-center gap-2">
            <RiskBadge level={result.risk_level} />
            <span className="text-sm text-gray-500 dark:text-gray-400">confidence: {result.confidence}</span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <CoefTile label="Relationship coefficient" v={result.relationship_coefficient} />
            <CoefTile label="Expected offspring inbreeding" v={result.offspring_inbreeding} />
          </div>
          {result.warnings.length > 0 && (
            <div className="mt-3 space-y-1">
              {result.warnings.map((w, i) => (
                <p key={i} className="text-sm text-amber-700 dark:text-amber-300">⚠ {w.detail}</p>
              ))}
            </div>
          )}
          {result.limitations.length > 0 && (
            <ul className="mt-3 list-inside list-disc text-xs text-gray-500 dark:text-gray-400">
              {result.limitations.map((l, i) => <li key={i}>{l}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function CoefTile({ label, v }: { label: string; v: { label: string; value: number; detail?: string } }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        <FactBadge label={v.label} />
      </div>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">{v.value?.toFixed(3)}</p>
      {v.detail && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{v.detail}</p>}
    </div>
  );
}

// ── Programmes ────────────────────────────────────────────────────────────────

function Programs({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["avi-programs", farmId], queryFn: () => listPrograms(farmId) });
  return (
    <div className="space-y-3">
      <div className="flex justify-end"><Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>New programme</Button></div>
      {q.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (q.data ?? []).length === 0 ? (
        <EmptyState title="No breeding programmes yet" description="Create a programme to organise pairs toward an objective." />
      ) : (
        <div className="space-y-2">{(q.data ?? []).map((p) => (
          <div key={p.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{p.name}</p>
              <span className="text-xs capitalize text-gray-500 dark:text-gray-400">{p.strategy.replace("_", " ")} · {p.pair_count} pair(s)</span>
            </div>
            {p.objective && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{p.objective}</p>}
          </div>
        ))}</div>
      )}
      <CreateProgramModal open={open} onClose={() => setOpen(false)} farmId={farmId}
        onCreated={() => qc.invalidateQueries({ queryKey: ["avi-programs", farmId] })} />
    </div>
  );
}

function CreateProgramModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState("outcross");
  const [objective, setObjective] = useState("");
  const m = useMutation({
    mutationFn: () => createProgram(farmId, { name: name.trim(), strategy, objective: objective.trim() || undefined }),
    onSuccess: () => { setName(""); setObjective(""); onCreated(); onClose(); },
  });
  return (
    <AviModal open={open} onClose={onClose} title="New breeding programme">
      <div className="space-y-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Champion Silkies" />
        <Select label="Strategy" options={["outcross", "line_breeding", "inbreeding", "conservation", "exhibition", "mixed"].map((s) => ({ value: s, label: s.replace("_", " ") }))} value={strategy} onChange={(e) => setStrategy(e.target.value)} />
        <TextField label="Objective (optional)" value={objective} onChange={(e) => setObjective(e.target.value)} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!name.trim()} onClick={() => m.mutate()}>Create</Button>
        </div>
      </div>
    </AviModal>
  );
}
