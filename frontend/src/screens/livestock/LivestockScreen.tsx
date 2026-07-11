/**
 * Greena — Livestock (Flock Management).
 * Lists a farm's flocks with live operational stats, a production summary from
 * real data, and flock creation. Each flock links to its detail screen.
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bird, Plus, Egg, Wheat, Skull, X, ArrowRight } from "lucide-react";

import {
  listFlocks,
  createFlock,
  getProductionDashboard,
} from "@/api/flocks";
import { listFarmHouses } from "@/api/farms";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Flock, FlockCreateInput } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
  sold: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  closed: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
  culled: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

function StatTile({ icon: Icon, label, value }: { icon: typeof Egg; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center gap-2 text-gray-400">
        <Icon className="h-4 w-4" />
        <span className="text-[11px] font-semibold uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-2 text-xl font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">{value}</p>
    </div>
  );
}

function flockAge(placement: string): number {
  const ms = Date.now() - new Date(placement).getTime();
  return Math.max(0, Math.floor(ms / 86_400_000));
}

export default function LivestockScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const flocksQuery = useQuery({
    queryKey: ["flocks", farmId],
    queryFn: () => listFlocks(farmId!),
    enabled: !!farmId,
  });
  const dashQuery = useQuery({
    queryKey: ["production-dashboard", farmId],
    queryFn: () => getProductionDashboard(farmId!),
    enabled: !!farmId,
  });

  const flocks = flocksQuery.data ?? [];
  const d = dashQuery.data;

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
            Livestock
          </h1>
          <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">
            Your flocks and their day-to-day performance.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} leftIcon={<Plus className="h-4 w-4" />}>
          New flock
        </Button>
      </header>

      {/* Production summary — real data */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {dashQuery.isLoading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)
        ) : (
          <>
            <StatTile icon={Bird} label="Live birds" value={d ? String(d.total_birds) : "—"} />
            <StatTile icon={Egg} label="Eggs today" value={d ? String(d.eggs_today) : "—"} />
            <StatTile icon={Wheat} label="Feed today (kg)" value={d ? Number(d.feed_today_kg).toString() : "—"} />
            <StatTile icon={Skull} label="Deaths this wk" value={d ? String(d.mortality_this_week + d.culls_this_week) : "—"} />
          </>
        )}
      </div>

      {/* Flock list */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">
          Flocks {flocks.length > 0 && <span className="text-gray-400">({flocks.length})</span>}
        </h2>
        {flocksQuery.isLoading ? (
          <div className="space-y-3">
            {[0, 1].map((i) => <Skeleton key={i} className="h-20 rounded-2xl" />)}
          </div>
        ) : flocks.length === 0 ? (
          <EmptyState
            icon={<Bird className="h-6 w-6" />}
            title="No flocks yet"
            description="Add your first flock to start tracking birds, feed, and production."
            action={<Button onClick={() => setShowCreate(true)} leftIcon={<Plus className="h-4 w-4" />}>New flock</Button>}
          />
        ) : (
          <ul className="space-y-3">
            {flocks.map((f) => (
              <FlockRow key={f.id} flock={f} />
            ))}
          </ul>
        )}
      </section>

      {showCreate && farmId && (
        <CreateFlockModal
          farmId={farmId}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            qc.invalidateQueries({ queryKey: ["flocks", farmId] });
            qc.invalidateQueries({ queryKey: ["production-dashboard", farmId] });
          }}
        />
      )}
    </div>
  );
}

function FlockRow({ flock }: { flock: Flock }) {
  const age = flockAge(flock.placement_date);
  return (
    <li>
      <Link
        to={`/livestock/${flock.id}`}
        className="group flex items-center gap-4 rounded-2xl border border-gray-200 bg-white p-4 transition-all hover:border-brand-200 hover:shadow-sm dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-brand-600/40"
      >
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300">
          <Bird className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold text-gray-900 dark:text-white">{flock.name}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[flock.status] ?? STATUS_STYLES.closed}`}>
              {flock.status}
            </span>
          </div>
          <p className="mt-0.5 truncate text-sm text-gray-500 dark:text-gray-400">
            {flock.breed ? `${flock.breed} · ` : ""}
            {flock.initial_count.toLocaleString()} placed · {age}d old
          </p>
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-gray-300 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-500" />
      </Link>
    </li>
  );
}

function CreateFlockModal({
  farmId,
  onClose,
  onCreated,
}: {
  farmId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const housesQuery = useQuery({
    queryKey: ["houses", farmId],
    queryFn: () => listFarmHouses(farmId),
  });
  const houses = housesQuery.data ?? [];
  const houseOptions = useMemo(
    () => houses.map((h) => ({ value: h.id, label: h.name + (h.is_occupied ? " (occupied)" : "") })),
    [houses],
  );

  const [form, setForm] = useState<FlockCreateInput>({
    house_id: "",
    name: "",
    breed: "",
    source: "",
    initial_count: 0,
    placement_date: new Date().toISOString().slice(0, 10),
    expected_cycle_days: 42,
  });
  const [error, setError] = useState<string | null>(null);

  const set = (patch: Partial<FlockCreateInput>) => setForm((f) => ({ ...f, ...patch }));

  const create = useMutation({
    mutationFn: () =>
      createFlock(farmId, {
        ...form,
        breed: form.breed || undefined,
        source: form.source || undefined,
      }),
    onSuccess: onCreated,
    onError: (e: any) =>
      setError(e?.response?.data?.error?.message ?? "Couldn't create the flock. Check the details and try again."),
  });

  const valid =
    form.house_id && form.name.trim().length >= 2 && form.initial_count >= 1 && form.placement_date;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-t-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#161a20] sm:rounded-3xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">New flock</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <TextField label="Flock name" placeholder="Batch 3 — Broiler" value={form.name} onChange={(e) => set({ name: e.target.value })} />
          <Select
            label="House"
            options={[{ value: "", label: housesQuery.isLoading ? "Loading…" : "Select a house" }, ...houseOptions]}
            value={form.house_id}
            onChange={(e) => set({ house_id: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Breed" placeholder="Ross 308" value={form.breed ?? ""} onChange={(e) => set({ breed: e.target.value })} />
            <TextField label="Source" placeholder="Kenchic hatchery" value={form.source ?? ""} onChange={(e) => set({ source: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="Birds placed"
              type="number"
              min={1}
              value={form.initial_count || ""}
              onChange={(e) => set({ initial_count: Number(e.target.value) })}
            />
            <TextField label="Placement date" type="date" value={form.placement_date} onChange={(e) => set({ placement_date: e.target.value })} />
          </div>
          <TextField
            label="Expected cycle (days)"
            type="number"
            min={1}
            hint="42 for broilers, 350+ for layers."
            value={form.expected_cycle_days ?? 42}
            onChange={(e) => set({ expected_cycle_days: Number(e.target.value) })}
          />
        </div>

        <div className="mt-6 flex gap-3">
          <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
          <Button fullWidth disabled={!valid} loading={create.isPending} onClick={() => { setError(null); create.mutate(); }}>
            Create flock
          </Button>
        </div>
      </div>
    </div>
  );
}
