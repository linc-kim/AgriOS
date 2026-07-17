/**
 * Greena — Daily Operations for a flock.
 * Quick record entry (daily log, egg production, weigh-in) plus recent history,
 * all wired to the real backend. Embedded on the flock detail screen.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Egg, Scale, Plus, X } from "lucide-react";

import {
  listDailyLogs,
  submitDailyLog,
  submitProductionRecord,
  submitWeighin,
} from "@/api/flocks";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";

const TODAY = () => new Date().toISOString().slice(0, 10);

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

type Modal = null | "day" | "eggs" | "weighin";

export function FlockDailyOps({ farmId, flockId, disabled }: { farmId: string; flockId: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const [modal, setModal] = useState<Modal>(null);

  const logsQuery = useQuery({
    queryKey: ["daily-logs", farmId, flockId],
    queryFn: () => listDailyLogs(farmId, flockId, { limit: 7 }),
    enabled: !!farmId && !!flockId,
  });
  const logs = logsQuery.data ?? [];

  const afterWrite = () => {
    setModal(null);
    qc.invalidateQueries({ queryKey: ["daily-logs", farmId, flockId] });
    qc.invalidateQueries({ queryKey: ["flock", farmId, flockId] });
    qc.invalidateQueries({ queryKey: ["production-dashboard", farmId] });
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Daily operations</h2>
        {!disabled && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => setModal("day")} leftIcon={<ClipboardList className="h-4 w-4" />}>Log day</Button>
            <Button size="sm" variant="secondary" onClick={() => setModal("eggs")} leftIcon={<Egg className="h-4 w-4" />}>Log eggs</Button>
            <Button size="sm" variant="secondary" onClick={() => setModal("weighin")} leftIcon={<Scale className="h-4 w-4" />}>Weigh-in</Button>
          </div>
        )}
      </div>

      {logsQuery.isLoading ? (
        <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div>
      ) : logs.length === 0 ? (
        <EmptyState
          icon={<Plus className="h-5 w-5" />}
          title="No logs yet"
          description={disabled ? "This flock is closed." : "Record today's feed, water, mortality and culls to start building the flock's history."}
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-gray-200 dark:border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:bg-white/[0.03]">
              <tr>
                <th className="px-4 py-2.5">Date</th>
                <th className="px-4 py-2.5 text-right">Feed kg</th>
                <th className="px-4 py-2.5 text-right">Water L</th>
                <th className="px-4 py-2.5 text-right">Deaths</th>
                <th className="px-4 py-2.5 text-right">Culls</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-white/5">
              {logs.map((l) => (
                <tr key={l.id} className="text-gray-700 dark:text-gray-200">
                  <td className="px-4 py-2.5">{new Date(l.log_date).toLocaleDateString()}</td>
                  <td className="px-4 py-2.5 text-right">{Number(l.feed_consumed_kg)}</td>
                  <td className="px-4 py-2.5 text-right">{l.water_litres ? Number(l.water_litres) : "—"}</td>
                  <td className="px-4 py-2.5 text-right">{l.mortality_count}</td>
                  <td className="px-4 py-2.5 text-right">{l.culls}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal === "day" && <DailyLogModal farmId={farmId} flockId={flockId} onClose={() => setModal(null)} onSaved={afterWrite} />}
      {modal === "eggs" && <EggLogModal farmId={farmId} flockId={flockId} onClose={() => setModal(null)} onSaved={afterWrite} />}
      {modal === "weighin" && <WeighinModal farmId={farmId} flockId={flockId} onClose={() => setModal(null)} onSaved={afterWrite} />}
    </section>
  );
}

function useWriteError() {
  const [error, setError] = useState<string | null>(null);
  const onError = (e: any) => setError(e?.response?.data?.error?.message ?? "Couldn't save. Check the values and try again.");
  return { error, setError, onError };
}

function DailyLogModal({ farmId, flockId, onClose, onSaved }: { farmId: string; flockId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ log_date: TODAY(), feed_consumed_kg: "", water_litres: "", mortality_count: "", culls: "", notes: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const { error, setError, onError } = useWriteError();
  const save = useMutation({
    mutationFn: () =>
      submitDailyLog(farmId, flockId, {
        log_date: f.log_date,
        feed_consumed_kg: f.feed_consumed_kg || "0",
        water_litres: f.water_litres || undefined,
        mortality_count: f.mortality_count ? Number(f.mortality_count) : 0,
        culls: f.culls ? Number(f.culls) : 0,
        notes: f.notes || undefined,
      }),
    onSuccess: onSaved,
    onError,
  });
  return (
    <ModalShell title="Log day" onClose={onClose}>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
      <div className="space-y-4">
        <TextField label="Date" type="date" value={f.log_date} onChange={(e) => set({ log_date: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Feed (kg)" type="number" value={f.feed_consumed_kg} onChange={(e) => set({ feed_consumed_kg: e.target.value })} />
          <TextField label="Water (litres)" type="number" value={f.water_litres} onChange={(e) => set({ water_litres: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Mortality" type="number" min={0} value={f.mortality_count} onChange={(e) => set({ mortality_count: e.target.value })} />
          <TextField label="Culls" type="number" min={0} value={f.culls} onChange={(e) => set({ culls: e.target.value })} />
        </div>
        <TextField label="Notes" value={f.notes} onChange={(e) => set({ notes: e.target.value })} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Save log</Button>
      </div>
    </ModalShell>
  );
}

function EggLogModal({ farmId, flockId, onClose, onSaved }: { farmId: string; flockId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ record_date: TODAY(), eggs_collected: "", broken_eggs: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const { error, setError, onError } = useWriteError();
  const save = useMutation({
    mutationFn: () =>
      submitProductionRecord(farmId, flockId, {
        record_date: f.record_date,
        eggs_collected: f.eggs_collected ? Number(f.eggs_collected) : 0,
        broken_eggs: f.broken_eggs ? Number(f.broken_eggs) : 0,
      }),
    onSuccess: onSaved,
    onError,
  });
  return (
    <ModalShell title="Log egg production" onClose={onClose}>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
      <div className="space-y-4">
        <TextField label="Date" type="date" value={f.record_date} onChange={(e) => set({ record_date: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Eggs collected" type="number" min={0} value={f.eggs_collected} onChange={(e) => set({ eggs_collected: e.target.value })} />
          <TextField label="Broken eggs" type="number" min={0} value={f.broken_eggs} onChange={(e) => set({ broken_eggs: e.target.value })} />
        </div>
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Save</Button>
      </div>
    </ModalShell>
  );
}

function WeighinModal({ farmId, flockId, onClose, onSaved }: { farmId: string; flockId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ weighed_at: TODAY(), sample_size: "", average_weight_kg: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const { error, setError, onError } = useWriteError();
  const save = useMutation({
    mutationFn: () =>
      submitWeighin(farmId, flockId, {
        weighed_at: f.weighed_at,
        sample_size: Number(f.sample_size),
        average_weight_kg: f.average_weight_kg,
      }),
    onSuccess: onSaved,
    onError,
  });
  const valid = Number(f.sample_size) > 0 && Number(f.average_weight_kg) > 0;
  return (
    <ModalShell title="Record weigh-in" onClose={onClose}>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
      <div className="space-y-4">
        <TextField label="Date" type="date" value={f.weighed_at} onChange={(e) => set({ weighed_at: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Sample size" type="number" min={1} value={f.sample_size} onChange={(e) => set({ sample_size: e.target.value })} />
          <TextField label="Avg weight (kg)" type="number" step="0.001" value={f.average_weight_kg} onChange={(e) => set({ average_weight_kg: e.target.value })} />
        </div>
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Save</Button>
      </div>
    </ModalShell>
  );
}
