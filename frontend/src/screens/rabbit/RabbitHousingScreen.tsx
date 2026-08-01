/**
 * Rabbit — Housing Workspace (Module 17, Frontend Increment 2).
 *
 * The rabbitry hierarchy, cage capacity and derived occupancy (backend-computed),
 * overcrowding, and rabbit movement between cages. Occupancy is never computed here.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Home } from "lucide-react";

import {
  listRabbitries, createRabbitry, listCages, createCage, getHousingSummary,
  CAGE_TYPES, type Cage,
} from "@/api/rabbitHousing";
import { listRabbits, moveRabbit } from "@/api/rabbit";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { LabelledValue } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

const inputCls = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900";

export default function RabbitHousingScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [modal, setModal] = useState<"rabbitry" | "cage" | "move" | null>(null);

  const summaryQ = useQuery({ queryKey: ["rabbit-housing-summary", farmId], queryFn: () => getHousingSummary(farmId as string), enabled: !!farmId });
  const cagesQ = useQuery({ queryKey: ["rabbit-cages", farmId], queryFn: () => listCages(farmId as string), enabled: !!farmId });
  const rabbitriesQ = useQuery({ queryKey: ["rabbit-rabbitries", farmId], queryFn: () => listRabbitries(farmId as string), enabled: !!farmId });
  const rabbitsQ = useQuery({ queryKey: ["rabbits-active", farmId], queryFn: () => listRabbits(farmId as string, { status: "active", limit: 200 }), enabled: !!farmId && modal === "move" });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["rabbit-housing-summary", farmId] });
    qc.invalidateQueries({ queryKey: ["rabbit-cages", farmId] });
    qc.invalidateQueries({ queryKey: ["rabbit-rabbitries", farmId] });
  };
  const rabbitryM = useMutation({ mutationFn: (name: string) => createRabbitry(farmId as string, { name }), onSuccess: () => { invalidate(); setModal(null); } });
  const cageM = useMutation({ mutationFn: (b: Record<string, unknown>) => createCage(farmId as string, b), onSuccess: () => { invalidate(); setModal(null); } });
  const moveM = useMutation({ mutationFn: (v: { rabbitId: string; cageId: string }) => moveRabbit(farmId as string, v.rabbitId, v.cageId, "Housing workspace"), onSuccess: () => { invalidate(); setModal(null); } });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const summary = summaryQ.data;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <RabbitSubnav active="/rabbit/housing" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Home className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Housing</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Rabbitries, cages, occupancy &amp; movement</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setModal("rabbitry")}>Add rabbitry</Button>
          <Button variant="secondary" onClick={() => setModal("cage")}>Add cage</Button>
          <Button onClick={() => setModal("move")}>Move rabbit</Button>
        </div>
      </div>

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Capacity</h2>
        {summaryQ.isLoading || !summary ? <Skeleton className="h-20 rounded-xl" /> : (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <CountTile label="Cages" value={summary.counts.cages} />
              <CountTile label="Rabbitries" value={summary.counts.rabbitries} />
              <Tile label="Occupied" figure={summary.capacity.occupied} />
              <Tile label="Utilisation" figure={summary.capacity.utilization_pct} suffix="%" />
            </div>
            {summary.overcrowded_cages.length > 0 && (
              <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 dark:border-amber-500/30 dark:bg-amber-500/10">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-300">Overcrowded cages</p>
                <ul className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                  {summary.overcrowded_cages.map((c) => <li key={c.cage_id}>{c.name}: {c.occupied}/{c.capacity ?? "—"}</li>)}
                </ul>
              </div>
            )}
          </>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Cages</h2>
        {cagesQ.isLoading ? <Skeleton className="h-32 rounded-xl" /> : (cagesQ.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-400">No cages yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {cagesQ.data!.map((c: Cage) => (
              <div key={c.id} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{c.name}</p>
                <p className="text-xs capitalize text-gray-500">{c.cage_type.replace(/_/g, " ")} · capacity {c.capacity ?? "—"} · {c.status}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {modal === "rabbitry" && <SimpleNameModal title="Add rabbitry" submitting={rabbitryM.isPending} onCancel={() => setModal(null)} onSubmit={(n) => rabbitryM.mutate(n)} />}
      {modal === "cage" && (
        <Modal open onClose={() => setModal(null)} title="Add cage">
          <CageForm rabbitries={(rabbitriesQ.data ?? []).map((r) => ({ id: r.id, name: r.name }))}
            submitting={cageM.isPending} onCancel={() => setModal(null)} onSubmit={(b) => cageM.mutate(b)} />
        </Modal>
      )}
      {modal === "move" && (
        <Modal open onClose={() => setModal(null)} title="Move rabbit">
          <MoveForm rabbits={(rabbitsQ.data?.data ?? []).map((r) => ({ id: r.id, label: `${r.internal_ref}${r.name ? ` · ${r.name}` : ""}` }))}
            cages={(cagesQ.data ?? []).map((c) => ({ id: c.id, name: c.name }))}
            submitting={moveM.isPending} error={moveM.isError ? "Could not move (already in that cage?)." : null}
            onCancel={() => setModal(null)} onSubmit={(rabbitId, cageId) => moveM.mutate({ rabbitId, cageId })} />
        </Modal>
      )}
    </div>
  );
}

function CountTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">{value}</p>
    </div>
  );
}
function Tile({ label, figure, suffix }: { label: string; figure?: { label: string; value: unknown; detail?: string }; suffix?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100"><LabelledValue figure={figure} format={(v) => `${v}${suffix ?? ""}`} /></p>
    </div>
  );
}

function SimpleNameModal({ title, onSubmit, onCancel, submitting }: { title: string; onSubmit: (n: string) => void; onCancel: () => void; submitting: boolean }) {
  const [name, setName] = useState("");
  return (
    <Modal open onClose={onCancel} title={title}>
      <div className="space-y-3">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className={inputCls} />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button loading={submitting} disabled={!name} onClick={() => onSubmit(name)}>Create</Button>
        </div>
      </div>
    </Modal>
  );
}

function CageForm({ onSubmit, onCancel, submitting }: {
  rabbitries: Array<{ id: string; name: string }>; onSubmit: (b: Record<string, unknown>) => void; onCancel: () => void; submitting: boolean;
}) {
  const [name, setName] = useState("");
  const [cageType, setCageType] = useState("cage");
  const [capacity, setCapacity] = useState("");
  return (
    <div className="space-y-3">
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} /></label>
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Type</span>
        <select value={cageType} onChange={(e) => setCageType(e.target.value)} className={inputCls}>{CAGE_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></label>
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Capacity</span>
        <input type="number" min={0} value={capacity} onChange={(e) => setCapacity(e.target.value)} className={inputCls} /></label>
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button loading={submitting} disabled={!name} onClick={() => onSubmit({ name, cage_type: cageType, capacity: capacity ? Number(capacity) : null })}>Create</Button>
      </div>
    </div>
  );
}

function MoveForm({ rabbits, cages, onSubmit, onCancel, submitting, error }: {
  rabbits: Array<{ id: string; label: string }>; cages: Array<{ id: string; name: string }>;
  onSubmit: (rabbitId: string, cageId: string) => void; onCancel: () => void; submitting: boolean; error: string | null;
}) {
  const [rabbitId, setRabbitId] = useState(rabbits[0]?.id ?? "");
  const [cageId, setCageId] = useState(cages[0]?.id ?? "");
  return (
    <div className="space-y-3">
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Rabbit</span>
        <select value={rabbitId} onChange={(e) => setRabbitId(e.target.value)} className={inputCls}>{rabbits.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Cage</span>
        <select value={cageId} onChange={(e) => setCageId(e.target.value)} className={inputCls}>{cages.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button loading={submitting} disabled={!rabbitId || !cageId} onClick={() => onSubmit(rabbitId, cageId)}>Move</Button>
      </div>
    </div>
  );
}
