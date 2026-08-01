/**
 * Rabbit — Breeding Workspace (Module 17, Frontend Increment 2).
 *
 * Breeding cycles (service → pregnancy check → kindling), litters, the pairing
 * compatibility checker (Wright's inbreeding, backend-computed) and the herd
 * reproduction summary. All rules/calculations are the backend's.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HeartHandshake } from "lucide-react";

import {
  listBreedings, createBreeding, pregnancyCheck, recordKindling, closeBreeding,
  listLitters, recordWeaning, checkCompatibility, getReproductionSummary,
  type Breeding, type Litter, type Compatibility,
} from "@/api/rabbitBreeding";
import { listRabbits, type Rabbit } from "@/api/rabbit";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { FactBadge, LabelledValue } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

type Tab = "breedings" | "litters" | "compatibility" | "genetics";
const inputCls = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900";
const today = () => new Date().toISOString().slice(0, 10);

export default function RabbitBreedingScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [tab, setTab] = useState<Tab>("breedings");

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <RabbitSubnav active="/rabbit/breeding" />
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <HeartHandshake className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Breeding</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Cycles, litters, pairing &amp; genetics</p>
        </div>
      </div>

      <div className="mb-4 flex gap-2" role="tablist">
        {(["breedings", "litters", "compatibility", "genetics"] as Tab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium capitalize ${tab === t ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300" : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "breedings" && <BreedingsTab farmId={farmId} />}
      {tab === "litters" && <LittersTab farmId={farmId} />}
      {tab === "compatibility" && <CompatibilityTab farmId={farmId} />}
      {tab === "genetics" && <GeneticsTab farmId={farmId} />}
    </div>
  );
}

// ── Breedings ──────────────────────────────────────────────────────────────────

function BreedingsTab({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const q = useQuery({ queryKey: ["rabbit-breedings", farmId], queryFn: () => listBreedings(farmId), enabled: !!farmId });
  const rabbitsQ = useQuery({ queryKey: ["rabbits-active", farmId], queryFn: () => listRabbits(farmId, { status: "active", limit: 200 }), enabled: !!farmId });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["rabbit-breedings", farmId] });
  const pcM = useMutation({ mutationFn: (v: { id: string; result: string }) => pregnancyCheck(farmId, v.id, v.result), onSuccess: invalidate });
  const closeM = useMutation({ mutationFn: (id: string) => closeBreeding(farmId, id), onSuccess: invalidate });
  const kindleM = useMutation({
    mutationFn: (v: { id: string; total: number; live: number }) =>
      recordKindling(farmId, v.id, { kindling_date: today(), total_kits: v.total, live_kits: v.live, create_kits: true }),
    onSuccess: () => { invalidate(); qc.invalidateQueries({ queryKey: ["rabbit-litters", farmId] }); },
  });
  const createM = useMutation({
    mutationFn: (body: Record<string, unknown>) => createBreeding(farmId, body),
    onSuccess: () => { invalidate(); setShowCreate(false); },
  });

  const does = (rabbitsQ.data?.data ?? []).filter((r) => r.sex === "doe");
  const bucks = (rabbitsQ.data?.data ?? []).filter((r) => r.sex === "buck");

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => setShowCreate(true)} disabled={does.length === 0 || bucks.length === 0}>Record mating</Button>
      </div>
      {q.isLoading ? <Skeleton className="h-40 rounded-xl" /> : (q.data?.data ?? []).length === 0 ? (
        <p className="py-10 text-center text-sm text-gray-400">No breedings recorded yet.</p>
      ) : (
        <ul className="space-y-2">{q.data!.data.map((b) => (
          <BreedingRow key={b.id} b={b}
            onPreg={(res) => pcM.mutate({ id: b.id, result: res })}
            onKindle={() => { const t = Number(prompt("Total kits?", "6")); const l = Number(prompt("Live kits?", String(t || 0))); if (t >= 0 && l >= 0) kindleM.mutate({ id: b.id, total: t, live: l }); }}
            onClose={() => closeM.mutate(b.id)} />
        ))}</ul>
      )}
      {showCreate && (
        <Modal open onClose={() => setShowCreate(false)} title="Record mating">
          <CreateBreedingForm does={does} bucks={bucks} submitting={createM.isPending}
            error={createM.isError ? "Not eligible (check sex/status or an open cycle)." : null}
            onSubmit={(body) => createM.mutate(body)} onCancel={() => setShowCreate(false)} />
        </Modal>
      )}
    </div>
  );
}

function BreedingRow({ b, onPreg, onKindle, onClose }: { b: Breeding; onPreg: (r: string) => void; onKindle: () => void; onClose: () => void }) {
  return (
    <li className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">
          {b.status} <span className="text-xs font-normal text-gray-500">· serviced {b.service_date ?? "—"} · planned kindling {b.planned_kindling_date ?? "—"}</span>
        </p>
        <div className="flex gap-2">
          {b.status === "serviced" && <>
            <Button variant="secondary" onClick={() => onPreg("pregnant")}>Pregnant</Button>
            <Button variant="secondary" onClick={() => onPreg("not_pregnant")}>Not pregnant</Button>
          </>}
          {(b.status === "serviced" || b.status === "pregnant") && <Button onClick={onKindle}>Kindling</Button>}
          {b.status === "kindled" && <Button variant="secondary" onClick={onClose}>Close</Button>}
        </div>
      </div>
    </li>
  );
}

function CreateBreedingForm({ does, bucks, onSubmit, onCancel, submitting, error }: {
  does: Rabbit[]; bucks: Rabbit[]; onSubmit: (b: Record<string, unknown>) => void; onCancel: () => void; submitting: boolean; error: string | null;
}) {
  const [doeId, setDoeId] = useState(does[0]?.id ?? "");
  const [buckId, setBuckId] = useState(bucks[0]?.id ?? "");
  const [serviceDate, setServiceDate] = useState(today());
  return (
    <div className="space-y-3">
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Doe</span>
        <select value={doeId} onChange={(e) => setDoeId(e.target.value)} className={inputCls}>
          {does.map((r) => <option key={r.id} value={r.id}>{r.internal_ref} {r.name ? `· ${r.name}` : ""}</option>)}
        </select></label>
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Buck</span>
        <select value={buckId} onChange={(e) => setBuckId(e.target.value)} className={inputCls}>
          {bucks.map((r) => <option key={r.id} value={r.id}>{r.internal_ref} {r.name ? `· ${r.name}` : ""}</option>)}
        </select></label>
      <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Service date</span>
        <input type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} className={inputCls} /></label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button loading={submitting} onClick={() => onSubmit({ doe_id: doeId, buck_id: buckId, service_date: serviceDate })}>Record</Button>
      </div>
    </div>
  );
}

// ── Litters ──────────────────────────────────────────────────────────────────

function LittersTab({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["rabbit-litters", farmId], queryFn: () => listLitters(farmId), enabled: !!farmId });
  const weanM = useMutation({
    mutationFn: (v: { id: string; weaned: number }) => recordWeaning(farmId, v.id, v.weaned),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rabbit-litters", farmId] }),
  });
  if (q.isLoading) return <Skeleton className="h-40 rounded-xl" />;
  const litters = q.data?.data ?? [];
  if (litters.length === 0) return <p className="py-10 text-center text-sm text-gray-400">No litters yet.</p>;
  return (
    <ul className="space-y-2">{litters.map((li: Litter) => (
      <li key={li.id} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{li.litter_code}
            <span className="text-xs font-normal text-gray-500"> · kindled {li.kindling_date} · {li.total_kits} kits ({li.live_kits} live) · {li.status}</span></p>
          {li.status === "active" && (
            <Button variant="secondary" onClick={() => { const w = Number(prompt("Weaned kits?", String(li.live_kits))); if (w >= 0) weanM.mutate({ id: li.id, weaned: w }); }}>Wean</Button>
          )}
        </div>
        <p className="mt-1 text-xs text-gray-500">Weaned {li.weaned_kits} · stillbirths {li.stillbirths} · mortality {li.mortality}</p>
      </li>
    ))}</ul>
  );
}

// ── Compatibility ──────────────────────────────────────────────────────────────

function CompatibilityTab({ farmId }: { farmId: string }) {
  const rabbitsQ = useQuery({ queryKey: ["rabbits-active", farmId], queryFn: () => listRabbits(farmId, { status: "active", limit: 200 }), enabled: !!farmId });
  const does = (rabbitsQ.data?.data ?? []).filter((r) => r.sex === "doe");
  const bucks = (rabbitsQ.data?.data ?? []).filter((r) => r.sex === "buck");
  const [buckId, setBuckId] = useState("");
  const [doeId, setDoeId] = useState("");
  const [result, setResult] = useState<Compatibility | null>(null);
  const m = useMutation({ mutationFn: () => checkCompatibility(farmId, buckId, doeId), onSuccess: setResult });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <select value={buckId} onChange={(e) => setBuckId(e.target.value)} className={inputCls}>
          <option value="">Select buck…</option>
          {bucks.map((r) => <option key={r.id} value={r.id}>{r.internal_ref} {r.name ? `· ${r.name}` : ""}</option>)}
        </select>
        <select value={doeId} onChange={(e) => setDoeId(e.target.value)} className={inputCls}>
          <option value="">Select doe…</option>
          {does.map((r) => <option key={r.id} value={r.id}>{r.internal_ref} {r.name ? `· ${r.name}` : ""}</option>)}
        </select>
        <Button disabled={!buckId || !doeId} loading={m.isPending} onClick={() => m.mutate()}>Check compatibility</Button>
      </div>
      {result && (
        <div className={`rounded-xl border p-4 ${result.compatible ? "border-brand-200 bg-brand-50/40 dark:border-brand-500/30 dark:bg-brand-500/10" : "border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10"}`}>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {result.compatible ? "Compatible" : "Not recommended"} · risk: {result.risk_level} · confidence {result.confidence}
          </p>
          <p className="mt-2 text-sm">Relatedness: <LabelledValue figure={result.relationship_coefficient} /></p>
          <p className="text-sm">Offspring inbreeding F: <LabelledValue figure={result.offspring_inbreeding} /></p>
          {result.warnings.map((w, i) => <p key={i} className="mt-1 text-xs text-amber-700 dark:text-amber-300">⚠ {w.detail}</p>)}
          {result.limitations.map((l, i) => <p key={i} className="mt-1 text-[11px] text-gray-500">{l}</p>)}
        </div>
      )}
    </div>
  );
}

// ── Genetics / reproduction ──────────────────────────────────────────────────

function GeneticsTab({ farmId }: { farmId: string }) {
  const q = useQuery({ queryKey: ["rabbit-repro", farmId], queryFn: () => getReproductionSummary(farmId), enabled: !!farmId });
  if (q.isLoading || !q.data) return <Skeleton className="h-40 rounded-xl" />;
  const s = q.data;
  const tiles: Array<[string, string]> = [
    ["Total services", "total_services"], ["Pregnancies", "total_pregnancies"], ["Litters", "total_litters"],
    ["Kits born", "total_kits_born"], ["Kits weaned", "total_kits_weaned"], ["Conception rate", "conception_rate_pct"],
    ["Pregnancy rate", "pregnancy_rate_pct"], ["Kindling rate", "kindling_rate_pct"], ["Avg litter size", "avg_litter_size"],
    ["Kit survival", "kit_survival_pct"],
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {tiles.map(([label, key]) => (
        <div key={key} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
          <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
          <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100"><LabelledValue figure={s[key]} /></p>
        </div>
      ))}
    </div>
  );
}
