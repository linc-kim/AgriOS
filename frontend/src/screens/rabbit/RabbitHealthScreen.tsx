/**
 * Rabbit — Health Workspace (Module 17, Frontend Increment 2).
 *
 * Deterministic health summary (patterns, never a diagnosis), vaccination records
 * (which reuse the platform Reminder engine), and mortality. Recording is per-
 * rabbit; all analytics are the backend's.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stethoscope } from "lucide-react";

import {
  getHealthSummary, listVaccinations, listMortality, recordVaccination, recordMortality, recordHealth,
  HEALTH_EVENT_TYPES, HEALTH_SEVERITIES, MORTALITY_CAUSES,
  type Vaccination, type Mortality,
} from "@/api/rabbitHealth";
import { listRabbits } from "@/api/rabbit";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { LabelledValue } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

const inputCls = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900";
const today = () => new Date().toISOString().slice(0, 10);
type RecordKind = "health" | "vaccination" | "mortality";

export default function RabbitHealthScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [modal, setModal] = useState<RecordKind | null>(null);

  const summaryQ = useQuery({ queryKey: ["rabbit-health-summary", farmId], queryFn: () => getHealthSummary(farmId as string), enabled: !!farmId });
  const vacQ = useQuery({ queryKey: ["rabbit-vaccinations", farmId], queryFn: () => listVaccinations(farmId as string), enabled: !!farmId });
  const mortQ = useQuery({ queryKey: ["rabbit-mortality", farmId], queryFn: () => listMortality(farmId as string), enabled: !!farmId });
  const rabbitsQ = useQuery({ queryKey: ["rabbits-active", farmId], queryFn: () => listRabbits(farmId as string, { status: "active", limit: 200 }), enabled: !!farmId && !!modal });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["rabbit-health-summary", farmId] });
    qc.invalidateQueries({ queryKey: ["rabbit-vaccinations", farmId] });
    qc.invalidateQueries({ queryKey: ["rabbit-mortality", farmId] });
  };
  const recM = useMutation({
    mutationFn: (v: { kind: RecordKind; rabbitId: string; body: Record<string, unknown> }) =>
      v.kind === "vaccination" ? recordVaccination(farmId as string, v.rabbitId, v.body)
        : v.kind === "mortality" ? recordMortality(farmId as string, v.rabbitId, v.body)
          : recordHealth(farmId as string, v.rabbitId, v.body),
    onSuccess: () => { invalidate(); setModal(null); },
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const sum = summaryQ.data as Record<string, { label: string; value: unknown; detail?: string }> | undefined;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <RabbitSubnav active="/rabbit/health" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Stethoscope className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Health</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Records, vaccinations &amp; mortality</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setModal("health")}>Log health</Button>
          <Button variant="secondary" onClick={() => setModal("vaccination")}>Vaccinate</Button>
          <Button variant="secondary" onClick={() => setModal("mortality")}>Record death</Button>
        </div>
      </div>

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Summary</h2>
        {summaryQ.isLoading || !sum ? <Skeleton className="h-20 rounded-xl" /> : (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Tile label="Mortality rate" figure={sum.mortality_rate_pct} suffix="%" />
              <VacTile compliance={sum.vaccination_compliance as unknown as Record<string, { value: unknown }>} />
            </div>
            {typeof sum.disclaimer === "string" && <p className="mt-2 text-[11px] text-gray-400">{sum.disclaimer as string}</p>}
          </>
        )}
      </section>

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Vaccinations</h2>
        {vacQ.isLoading ? <Skeleton className="h-16 rounded-xl" /> : (vacQ.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-400">None recorded.</p>
        ) : <ul className="space-y-2">{vacQ.data!.map((v: Vaccination) => (
          <li key={v.id} className="rounded-lg border border-gray-200 bg-white p-3 text-sm dark:border-gray-800 dark:bg-gray-900">
            <span className="font-medium text-gray-900 dark:text-gray-100">{v.vaccine}</span>
            <span className="text-xs text-gray-500"> · given {v.administered_on}{v.next_due_on ? ` · next due ${v.next_due_on}` : ""}{v.reminder_id ? " · reminder set" : ""}</span>
          </li>
        ))}</ul>}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Mortality</h2>
        {mortQ.isLoading ? <Skeleton className="h-16 rounded-xl" /> : (mortQ.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-400">No mortality recorded.</p>
        ) : <ul className="space-y-2">{mortQ.data!.map((m: Mortality) => (
          <li key={m.id} className="rounded-lg border border-gray-200 bg-white p-3 text-sm dark:border-gray-800 dark:bg-gray-900">
            <span className="font-medium capitalize text-gray-900 dark:text-gray-100">{m.cause.replace(/_/g, " ")}</span>
            <span className="text-xs text-gray-500"> · {m.occurred_on}{m.age_days != null ? ` · age ${m.age_days}d` : ""}</span>
          </li>
        ))}</ul>}
      </section>

      {modal && (
        <RecordModal kind={modal} rabbits={(rabbitsQ.data?.data ?? []).map((r) => ({ id: r.id, label: `${r.internal_ref}${r.name ? ` · ${r.name}` : ""}` }))}
          submitting={recM.isPending} error={recM.isError ? "Could not save (already recorded or invalid?)." : null}
          onCancel={() => setModal(null)} onSubmit={(rabbitId, body) => recM.mutate({ kind: modal, rabbitId, body })} />
      )}
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

function VacTile({ compliance }: { compliance?: Record<string, { value: unknown }> }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">Vaccinations overdue</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
        {compliance?.overdue?.value != null ? String(compliance.overdue.value) : "—"}
      </p>
    </div>
  );
}

function RecordModal({ kind, rabbits, onSubmit, onCancel, submitting, error }: {
  kind: RecordKind; rabbits: Array<{ id: string; label: string }>;
  onSubmit: (rabbitId: string, body: Record<string, unknown>) => void; onCancel: () => void; submitting: boolean; error: string | null;
}) {
  const [rabbitId, setRabbitId] = useState(rabbits[0]?.id ?? "");
  const [text1, setText1] = useState("");
  const [sel, setSel] = useState(kind === "health" ? "exam" : kind === "mortality" ? "unknown" : "");
  const [severity, setSeverity] = useState("info");
  const title = kind === "vaccination" ? "Record vaccination" : kind === "mortality" ? "Record death" : "Log health event";

  function submit() {
    if (kind === "vaccination") onSubmit(rabbitId, { vaccine: text1 || "Vaccine", administered_on: today() });
    else if (kind === "mortality") onSubmit(rabbitId, { occurred_on: today(), cause: sel, suspected_cause: text1 || null });
    else onSubmit(rabbitId, { event_type: sel, severity, title: text1 || null, occurred_on: today() });
  }

  return (
    <Modal open onClose={onCancel} title={title}>
      <div className="space-y-3">
        <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Rabbit</span>
          <select value={rabbitId} onChange={(e) => setRabbitId(e.target.value)} className={inputCls}>
            {rabbits.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select></label>
        {kind === "vaccination" && <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Vaccine</span>
          <input value={text1} onChange={(e) => setText1(e.target.value)} className={inputCls} placeholder="e.g. RHDV2" /></label>}
        {kind === "mortality" && <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Cause</span>
          <select value={sel} onChange={(e) => setSel(e.target.value)} className={inputCls}>{MORTALITY_CAUSES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}</select></label>}
        {kind === "health" && <>
          <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Event type</span>
            <select value={sel} onChange={(e) => setSel(e.target.value)} className={inputCls}>{HEALTH_EVENT_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></label>
          <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Severity</span>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className={inputCls}>{HEALTH_SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
          <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Title</span>
            <input value={text1} onChange={(e) => setText1(e.target.value)} className={inputCls} /></label>
        </>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button loading={submitting} disabled={!rabbitId} onClick={submit}>Save</Button>
        </div>
      </div>
    </Modal>
  );
}
