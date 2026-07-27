/**
 * Aviculture — Dashboard & Reports (Module 15, Part 8).
 *
 * The evidence-backed landing dashboard (Doc 06 §3): collection composition,
 * infrastructure, breeding, incubation, health and finance KPIs — each composed
 * live from the deterministic engines and honesty-labelled. Plus a transparent
 * population forecast (never a promise) and a CSV export. Nothing is stored;
 * everything is computed from recorded facts.
 */
import { useState, type ReactNode } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Download, Plus, TrendingUp } from "lucide-react";

import {
  downloadCollectionCsv, getCollectionValuation, getDashboard, getForecast, recordValuation,
} from "@/api/avicultureReports";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge } from "./badges";
import { AviModal } from "./AviModal";
import { AviSubnav } from "./AviSubnav";

export default function AvicultureDashboardScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [valOpen, setValOpen] = useState(false);

  const dashQ = useQuery({ queryKey: ["avi-dashboard", farmId], queryFn: () => getDashboard(farmId as string), enabled: !!farmId });
  const foreQ = useQuery({ queryKey: ["avi-forecast", farmId], queryFn: () => getForecast(farmId as string, 90), enabled: !!farmId });
  const valQ = useQuery({ queryKey: ["avi-collection-valuation", farmId], queryFn: () => getCollectionValuation(farmId as string), enabled: !!farmId });

  const csv = useMutation({
    mutationFn: () => downloadCollectionCsv(farmId as string),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "aviculture_collection.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const d = dashQ.data;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <BarChart3 className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Dashboard &amp; Reports</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" leftIcon={<Download className="h-4 w-4" />} loading={csv.isPending}
            onClick={() => csv.mutate()}>Export CSV</Button>
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setValOpen(true)}>Record valuation</Button>
        </div>
      </div>
      <AviSubnav farmId={farmId} active="/aviculture/dashboard" />

      {dashQ.isLoading || !d ? <Skeleton className="h-40 rounded-xl" /> : (
        <>
          {/* KPI row */}
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Birds" v={d.collection.total} />
            <Kpi label="Active pairs" plain={d.breeding.active_pairs} />
            <Kpi label="Active batches" plain={d.incubation.active_batches} />
            <Kpi label="Collection value" v={valQ.data?.total_value} money />
            <Kpi label="Sale income" v={d.finance.sale_income} money />
            <Kpi label="Operational cost" v={d.finance.operational_expenses} money />
            <Kpi label="Net" v={d.finance.net} money />
            <Kpi label="Occupied housing" v={d.infrastructure.total_occupied} />
          </div>

          {/* Composition */}
          <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Panel title="By species"><Bars data={d.collection.by_species} /></Panel>
            <Panel title="By status"><Bars data={d.collection.by_status} /></Panel>
            <Panel title="By sex"><Bars data={d.collection.by_sex} /></Panel>
            <Panel title="By lifecycle stage"><Bars data={d.collection.by_lifecycle_stage} /></Panel>
          </div>

          {/* Forecast */}
          {foreQ.data && (
            <Panel title={<span className="flex items-center gap-2"><TrendingUp className="h-4 w-4" /> Population forecast</span>}>
              <div className="flex items-baseline gap-3">
                <span className="text-3xl font-semibold text-gray-900 dark:text-gray-100">
                  {foreQ.data.forecast.value ?? "—"}
                </span>
                <FactBadge label={foreQ.data.forecast.label} />
                {foreQ.data.confidence && <span className="text-xs text-gray-500 dark:text-gray-400">confidence: {foreQ.data.confidence}</span>}
              </div>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                {foreQ.data.method} Now: {foreQ.data.current.value}.
              </p>
              {foreQ.data.limitations && (
                <ul className="mt-2 list-inside list-disc text-xs text-gray-400">
                  {foreQ.data.limitations.map((l, i) => <li key={i}>{l}</li>)}
                </ul>
              )}
            </Panel>
          )}
        </>
      )}

      <RecordValuationModal open={valOpen} onClose={() => setValOpen(false)} farmId={farmId}
        onDone={() => { qc.invalidateQueries({ queryKey: ["avi-collection-valuation", farmId] }); qc.invalidateQueries({ queryKey: ["avi-dashboard", farmId] }); }} />
    </div>
  );
}

function Kpi({ label, v, plain, money }: { label: string; v?: { label: string; value: unknown }; plain?: number; money?: boolean }) {
  const value = v ? v.value : plain;
  const shown = value == null ? "—" : money ? `KES ${Number(value).toLocaleString()}` : String(value);
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        {v && <FactBadge label={v.label} />}
      </div>
      <p className="mt-1 truncate text-xl font-semibold text-gray-900 dark:text-gray-100">{shown}</p>
    </div>
  );
}

function Panel({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      {children}
    </div>
  );
}

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  if (entries.length === 0) return <p className="text-sm text-gray-400">No data.</p>;
  return (
    <div className="space-y-2">
      {entries.map(([k, n]) => (
        <div key={k}>
          <div className="flex items-center justify-between text-xs">
            <span className="capitalize text-gray-600 dark:text-gray-300">{k.replace(/_/g, " ")}</span>
            <span className="text-gray-500 dark:text-gray-400">{n}</span>
          </div>
          <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
            <div className="h-full rounded-full bg-brand-500" style={{ width: `${(n / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function RecordValuationModal({ open, onClose, farmId, onDone }: { open: boolean; onClose: () => void; farmId: string; onDone: () => void }) {
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("appraised");
  const [error, setError] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: () => recordValuation(farmId, { amount: amount.trim(), method }),
    onSuccess: () => { setAmount(""); onDone(); onClose(); },
    onError: () => setError("Could not record valuation."),
  });
  return (
    <AviModal open={open} onClose={onClose} title="Record collection valuation">
      <div className="space-y-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">A collection-level valuation (leave bird blank). Bird-level valuations can be added from a bird's profile.</p>
        <TextField label="Amount (KES)" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <Select label="Method" options={["appraised", "market", "insured", "breeding_value"].map((x) => ({ value: x, label: x.replace("_", " ") }))} value={method} onChange={(e) => setMethod(e.target.value)} />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!amount.trim()} onClick={() => m.mutate()}>Record</Button>
        </div>
      </div>
    </AviModal>
  );
}
