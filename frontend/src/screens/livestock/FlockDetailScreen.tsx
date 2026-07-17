/**
 * Greena — Flock detail.
 * Real operational metrics for a single flock plus lifecycle actions:
 * edit, close, and archive.
 */
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bird, Pencil, Archive, CheckCircle2, X } from "lucide-react";

import { getFlock, updateFlock, closeFlock, archiveFlock } from "@/api/flocks";
import { FlockDailyOps } from "./FlockDailyOps";
import { FlockHealth } from "./FlockHealth";
import { FlockFeed } from "./FlockFeed";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import type { FlockDetail, FlockUpdateInput } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
  sold: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  closed: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
  culled: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1.5 text-xl font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{sub}</p>}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-2.5 last:border-0 dark:border-white/5">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-sm font-medium text-gray-900 dark:text-white">{value}</span>
    </div>
  );
}

export default function FlockDetailScreen() {
  const { flockId } = useParams();
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [closing, setClosing] = useState(false);

  const flockQuery = useQuery({
    queryKey: ["flock", farmId, flockId],
    queryFn: () => getFlock(farmId!, flockId!),
    enabled: !!farmId && !!flockId,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["flock", farmId, flockId] });
    qc.invalidateQueries({ queryKey: ["flocks", farmId] });
  };

  const archive = useMutation({
    mutationFn: () => archiveFlock(farmId!, flockId!),
    onSuccess: () => {
      invalidate();
      navigate("/livestock");
    },
  });

  if (flockQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-56" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
      </div>
    );
  }
  if (flockQuery.isError || !flockQuery.data) {
    return (
      <div className="space-y-4">
        <Link to="/livestock" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
          <ArrowLeft className="h-4 w-4" /> Back to livestock
        </Link>
        <p className="text-gray-600 dark:text-gray-300">This flock could not be loaded.</p>
      </div>
    );
  }

  const f: FlockDetail = flockQuery.data;
  const m = f.metrics;
  const mortalityPct = f.initial_count > 0 ? ((m.total_mortality / f.initial_count) * 100).toFixed(1) : "0.0";

  return (
    <div className="space-y-8">
      <div>
        <Link to="/livestock" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400">
          <ArrowLeft className="h-4 w-4" /> Livestock
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300">
              <Bird className="h-5 w-5" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">{f.name}</h1>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[f.status] ?? STATUS_STYLES.closed}`}>
                  {f.status}
                </span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {f.breed ?? "Unspecified breed"}{f.source ? ` · from ${f.source}` : ""}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => setEditing(true)} leftIcon={<Pencil className="h-4 w-4" />}>
              Edit
            </Button>
            {f.status === "active" ? (
              <Button variant="secondary" size="sm" onClick={() => setClosing(true)} leftIcon={<CheckCircle2 className="h-4 w-4" />}>
                Close
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                loading={archive.isPending}
                onClick={() => archive.mutate()}
                leftIcon={<Archive className="h-4 w-4" />}
              >
                Archive
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Live metrics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric label="Live birds" value={m.current_count.toLocaleString()} sub={`of ${f.initial_count.toLocaleString()} placed`} />
        <Metric label="Mortality" value={`${mortalityPct}%`} sub={`${m.total_mortality} dead · ${m.total_culls} culled`} />
        <Metric label="Age" value={`${m.days_alive}d`} sub={`survival ${m.survival_rate}%`} />
        <Metric label="FCR" value={m.fcr ? Number(m.fcr).toFixed(2) : "—"} sub={`${Number(m.total_feed_kg).toLocaleString()} kg feed`} />
      </div>
      {(m.total_eggs_collected != null || m.latest_avg_weight_kg != null) && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {m.total_eggs_collected != null && (
            <Metric label="Eggs collected" value={m.total_eggs_collected.toLocaleString()} sub={m.hen_day_production != null ? `${m.hen_day_production}% HDP` : undefined} />
          )}
          {m.latest_avg_weight_kg != null && (
            <Metric label="Avg weight" value={`${Number(m.latest_avg_weight_kg).toFixed(2)} kg`} sub={m.total_biomass_kg ? `${Number(m.total_biomass_kg).toLocaleString()} kg biomass` : undefined} />
          )}
        </div>
      )}

      {/* Details */}
      <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
        <h2 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">Details</h2>
        <DetailRow label="Placed" value={new Date(f.placement_date).toLocaleDateString()} />
        <DetailRow label="Expected close" value={f.expected_close_date ? new Date(f.expected_close_date).toLocaleDateString() : "—"} />
        <DetailRow label="Cycle" value={`${f.expected_cycle_days} days`} />
        <DetailRow label="Batch" value={f.batch_number ?? "—"} />
        {f.close_date && <DetailRow label="Closed" value={new Date(f.close_date).toLocaleDateString()} />}
      </section>

      {farmId && <FlockDailyOps farmId={farmId} flockId={f.id} disabled={f.status !== "active"} />}

      {farmId && <FlockFeed farmId={farmId} flockId={f.id} disabled={f.status !== "active"} />}

      {farmId && <FlockHealth farmId={farmId} flockId={f.id} disabled={f.status !== "active"} />}

      {editing && farmId && (
        <EditFlockModal farm={farmId} flock={f} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); invalidate(); }} />
      )}
      {closing && farmId && (
        <CloseFlockModal farm={farmId} flockId={f.id} onClose={() => setClosing(false)} onClosed={() => { setClosing(false); invalidate(); }} />
      )}
    </div>
  );
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-t-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#161a20] sm:rounded-3xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function EditFlockModal({ farm, flock, onClose, onSaved }: { farm: string; flock: FlockDetail; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<FlockUpdateInput>({
    name: flock.name,
    breed: flock.breed ?? "",
    source: flock.source ?? "",
    batch_number: flock.batch_number ?? "",
  });
  const set = (patch: Partial<FlockUpdateInput>) => setForm((f) => ({ ...f, ...patch }));
  const save = useMutation({ mutationFn: () => updateFlock(farm, flock.id, form), onSuccess: onSaved });
  return (
    <ModalShell title="Edit flock" onClose={onClose}>
      <div className="space-y-4">
        <TextField label="Flock name" value={form.name ?? ""} onChange={(e) => set({ name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Breed" value={form.breed ?? ""} onChange={(e) => set({ breed: e.target.value })} />
          <TextField label="Source" value={form.source ?? ""} onChange={(e) => set({ source: e.target.value })} />
        </div>
        <TextField label="Batch number" value={form.batch_number ?? ""} onChange={(e) => set({ batch_number: e.target.value })} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth loading={save.isPending} onClick={() => save.mutate()}>Save</Button>
      </div>
    </ModalShell>
  );
}

function CloseFlockModal({ farm, flockId, onClose, onClosed }: { farm: string; flockId: string; onClose: () => void; onClosed: () => void }) {
  const [status, setStatus] = useState("closed");
  const [closeDate, setCloseDate] = useState(new Date().toISOString().slice(0, 10));
  const [salePrice, setSalePrice] = useState("");
  const [birdsSold, setBirdsSold] = useState("");
  const [error, setError] = useState<string | null>(null);

  const close = useMutation({
    mutationFn: () =>
      closeFlock(farm, flockId, {
        status: status as any,
        close_date: closeDate,
        sale_price_per_kg: status === "sold" && salePrice ? salePrice : undefined,
        total_birds_sold: status === "sold" && birdsSold ? Number(birdsSold) : undefined,
      }),
    onSuccess: onClosed,
    onError: (e: any) => setError(e?.response?.data?.error?.message ?? "Couldn't close the flock."),
  });

  return (
    <ModalShell title="Close flock" onClose={onClose}>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
      <div className="space-y-4">
        <Select
          label="Outcome"
          options={[
            { value: "closed", label: "Closed" },
            { value: "sold", label: "Sold" },
            { value: "culled", label: "Culled" },
          ]}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        />
        <TextField label="Close date" type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)} />
        {status === "sold" && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Sale price / kg" type="number" value={salePrice} onChange={(e) => setSalePrice(e.target.value)} />
            <TextField label="Birds sold" type="number" value={birdsSold} onChange={(e) => setBirdsSold(e.target.value)} />
          </div>
        )}
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth loading={close.isPending} onClick={() => { setError(null); close.mutate(); }}>Close flock</Button>
      </div>
    </ModalShell>
  );
}
