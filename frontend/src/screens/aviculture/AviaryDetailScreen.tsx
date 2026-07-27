/**
 * Aviculture — Aviary Detail (Module 15, Part 3).
 *
 * One aviary's full picture: live occupancy, environment readings summarised
 * against targets, zones, fixtures, cleaning/maintenance tasks and timeline —
 * every derived figure honesty-labelled by the pure aviary engine.
 */
import { useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Plus, Thermometer } from "lucide-react";

import {
  addFixture, addReading, addTask, addZone, completeTask, getAviary,
  listFixtures, listReadings, listTasks, listZones,
} from "@/api/aviaries";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/cn";
import { FactBadge } from "./badges";

type Tab = "overview" | "zones" | "fixtures" | "environment" | "tasks";
const TABS: Tab[] = ["overview", "zones", "fixtures", "environment", "tasks"];
const FIXTURES = ["nest_box", "perch", "feeder", "drinker", "feed_station", "water_station", "equipment", "plant"];
const TASK_TYPES = ["cleaning", "disinfection", "maintenance", "inspection", "repair"];

export default function AviaryDetailScreen() {
  const { aviaryId = "" } = useParams();
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");

  const q = useQuery({ queryKey: ["avi-aviary", farmId, aviaryId], queryFn: () => getAviary(farmId as string, aviaryId), enabled: !!farmId });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  if (q.isLoading) return <div className="mx-auto max-w-4xl px-4 py-6"><Skeleton className="h-40 rounded-xl" /></div>;
  if (q.isError || !q.data) return (
    <div className="mx-auto max-w-4xl px-4 py-16">
      <EmptyState title="Aviary not found" action={<Button variant="secondary" onClick={() => navigate("/aviculture/aviaries")}>Back</Button>} />
    </div>
  );

  const a = q.data;
  const occ = a.occupancy;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <button type="button" onClick={() => navigate("/aviculture/aviaries")}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
        <ArrowLeft className="h-4 w-4" /> Aviaries
      </button>

      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{a.name}</h1>
        <p className="mt-1 text-sm capitalize text-gray-500 dark:text-gray-400">
          {a.aviary_type.replace("_", " ")} · {a.purpose} · biosecurity {a.biosecurity_level}
        </p>
        {occ && (
          <div className="mt-4 grid grid-cols-3 gap-3">
            <Metric label="Occupied" value={occ.occupied.value} fact={occ.occupied.label} />
            <Metric label="Capacity" value={occ.capacity.value} fact={occ.capacity.label} />
            <Metric label="Utilisation" value={occ.utilization_pct.value != null ? `${occ.utilization_pct.value}%` : "—"} fact={occ.utilization_pct.label} />
          </div>
        )}
      </div>

      <div className="mt-5 flex gap-1 overflow-x-auto border-b border-gray-200 dark:border-gray-800">
        {TABS.map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={cn("whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium capitalize transition",
              tab === t ? "border-brand-500 text-brand-700 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300")}>
            {t}
          </button>
        ))}
      </div>

      <div className="py-5">
        {tab === "overview" && <Overview aviary={a} />}
        {tab === "zones" && <Zones farmId={farmId} aviaryId={aviaryId} />}
        {tab === "fixtures" && <Fixtures farmId={farmId} aviaryId={aviaryId} />}
        {tab === "environment" && <Environment farmId={farmId} aviaryId={aviaryId} />}
        {tab === "tasks" && <Tasks farmId={farmId} aviaryId={aviaryId} />}
      </div>
    </div>
  );
}

function Metric({ label, value, fact }: { label: string; value: ReactNode; fact?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        {fact && <FactBadge label={fact} />}
      </div>
      <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{value ?? "—"}</p>
    </div>
  );
}

function Overview({ aviary }: { aviary: import("@/api/aviaries").AviaryDetail }) {
  const env = aviary.environment_summary;
  const housing = aviary.housing_assessment;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Zones" value={aviary.zone_count} />
        <Metric label="Fixtures" value={aviary.fixture_count} />
        <Metric label="Readings" value={env?.reading_count ?? 0} />
        <Metric label="Overdue tasks" value={(aviary.cleaning?.overdue_count?.value as number) ?? 0} fact={aviary.cleaning?.overdue_count?.label} />
      </div>
      {env && env.findings.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-500/30 dark:bg-amber-500/10">
          <p className="mb-1 text-sm font-medium text-amber-800 dark:text-amber-300">Environment recommendations</p>
          {env.findings.map((f, i) => (
            <p key={i} className="text-sm text-amber-700 dark:text-amber-200">• {f.detail}</p>
          ))}
        </div>
      )}
      {housing && housing.findings.length > 0 && (
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 dark:border-violet-500/30 dark:bg-violet-500/10">
          <p className="mb-1 flex items-center gap-2 text-sm font-medium text-violet-800 dark:text-violet-300">
            Housing suitability <FactBadge label="recommendation" />
          </p>
          {housing.findings.map((f, i) => <p key={i} className="text-sm text-violet-700 dark:text-violet-200">• {f.detail}</p>)}
        </div>
      )}
    </div>
  );
}

function Zones({ farmId, aviaryId }: { farmId: string; aviaryId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["avi-zones", farmId, aviaryId], queryFn: () => listZones(farmId, aviaryId) });
  const [name, setName] = useState("");
  const [type, setType] = useState("flight");
  const m = useMutation({
    mutationFn: () => addZone(farmId, aviaryId, { name: name.trim(), zone_type: type }),
    onSuccess: () => { setName(""); qc.invalidateQueries({ queryKey: ["avi-zones", farmId, aviaryId] }); },
  });
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800 sm:flex-row">
        <TextField placeholder="Zone name" value={name} onChange={(e) => setName(e.target.value)} className="sm:flex-1" aria-label="Zone name" />
        <Select options={["zone", "section", "flight", "nursery", "holding"].map((z) => ({ value: z, label: z }))} value={type} onChange={(e) => setType(e.target.value)} aria-label="Zone type" className="sm:w-40" />
        <Button leftIcon={<Plus className="h-4 w-4" />} loading={m.isPending} disabled={!name.trim()} onClick={() => m.mutate()}>Add</Button>
      </div>
      {(q.data ?? []).length === 0 ? <EmptyState title="No zones yet" /> : (
        <div className="space-y-2">{(q.data ?? []).map((z) => (
          <div key={z.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <span className="text-sm text-gray-900 dark:text-gray-100">{z.name}</span>
            <span className="text-xs capitalize text-gray-500 dark:text-gray-400">{z.zone_type}</span>
          </div>
        ))}</div>
      )}
    </div>
  );
}

function Fixtures({ farmId, aviaryId }: { farmId: string; aviaryId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["avi-fixtures", farmId, aviaryId], queryFn: () => listFixtures(farmId, aviaryId) });
  const [type, setType] = useState("nest_box");
  const [qty, setQty] = useState("1");
  const m = useMutation({
    mutationFn: () => addFixture(farmId, aviaryId, { fixture_type: type, quantity: Number(qty) || 1 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["avi-fixtures", farmId, aviaryId] }),
  });
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800 sm:flex-row">
        <Select options={FIXTURES.map((f) => ({ value: f, label: f.replace(/_/g, " ") }))} value={type} onChange={(e) => setType(e.target.value)} aria-label="Fixture type" className="sm:flex-1" />
        <TextField inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} className="sm:w-24" aria-label="Quantity" />
        <Button leftIcon={<Plus className="h-4 w-4" />} loading={m.isPending} onClick={() => m.mutate()}>Add</Button>
      </div>
      {(q.data ?? []).length === 0 ? <EmptyState title="No fixtures yet" /> : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{(q.data ?? []).map((f) => (
          <div key={f.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <p className="text-sm capitalize text-gray-900 dark:text-gray-100">{f.fixture_type.replace(/_/g, " ")}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">×{f.quantity}</p>
          </div>
        ))}</div>
      )}
    </div>
  );
}

function Environment({ farmId, aviaryId }: { farmId: string; aviaryId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["avi-readings", farmId, aviaryId], queryFn: () => listReadings(farmId, aviaryId) });
  const [temp, setTemp] = useState("");
  const [hum, setHum] = useState("");
  const m = useMutation({
    mutationFn: () => addReading(farmId, aviaryId, { temperature_c: temp || undefined, humidity_pct: hum || undefined }),
    onSuccess: () => { setTemp(""); setHum(""); qc.invalidateQueries({ queryKey: ["avi-readings", farmId, aviaryId] }); qc.invalidateQueries({ queryKey: ["avi-aviary", farmId, aviaryId] }); },
  });
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800 sm:flex-row">
        <TextField placeholder="Temp °C" inputMode="decimal" value={temp} onChange={(e) => setTemp(e.target.value)} className="sm:flex-1" aria-label="Temperature" leftIcon={<Thermometer className="h-4 w-4" />} />
        <TextField placeholder="Humidity %" inputMode="decimal" value={hum} onChange={(e) => setHum(e.target.value)} className="sm:flex-1" aria-label="Humidity" />
        <Button leftIcon={<Plus className="h-4 w-4" />} loading={m.isPending} disabled={!temp && !hum} onClick={() => m.mutate()}>Record</Button>
      </div>
      {(q.data ?? []).length === 0 ? <EmptyState title="No readings yet" /> : (
        <div className="space-y-2">{(q.data ?? []).map((r) => (
          <div key={r.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-800">
            <span className="text-gray-900 dark:text-gray-100">
              {r.temperature_c != null ? `${r.temperature_c}°C` : "—"} · {r.humidity_pct != null ? `${r.humidity_pct}%` : "—"}
            </span>
            <span className="text-xs text-gray-400">{new Date(r.recorded_at).toLocaleDateString()}</span>
          </div>
        ))}</div>
      )}
    </div>
  );
}

function Tasks({ farmId, aviaryId }: { farmId: string; aviaryId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["avi-tasks", farmId, aviaryId], queryFn: () => listTasks(farmId, aviaryId) });
  const [title, setTitle] = useState("");
  const [type, setType] = useState("cleaning");
  const [rec, setRec] = useState("none");
  const add = useMutation({
    mutationFn: () => addTask(farmId, aviaryId, { task_type: type, title: title.trim(), recurrence: rec }),
    onSuccess: () => { setTitle(""); qc.invalidateQueries({ queryKey: ["avi-tasks", farmId, aviaryId] }); },
  });
  const done = useMutation({
    mutationFn: (id: string) => completeTask(farmId, aviaryId, id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["avi-tasks", farmId, aviaryId] }); qc.invalidateQueries({ queryKey: ["avi-aviary", farmId, aviaryId] }); },
  });
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Select options={TASK_TYPES.map((t) => ({ value: t, label: t }))} value={type} onChange={(e) => setType(e.target.value)} aria-label="Task type" className="sm:w-40" />
          <TextField placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)} className="sm:flex-1" aria-label="Task title" />
          <Select options={["none", "daily", "weekly", "monthly", "quarterly"].map((r) => ({ value: r, label: r }))} value={rec} onChange={(e) => setRec(e.target.value)} aria-label="Recurrence" className="sm:w-32" />
          <Button leftIcon={<Plus className="h-4 w-4" />} loading={add.isPending} disabled={!title.trim()} onClick={() => add.mutate()}>Add</Button>
        </div>
      </div>
      {(q.data ?? []).length === 0 ? <EmptyState title="No tasks yet" /> : (
        <div className="space-y-2">{(q.data ?? []).map((t) => (
          <div key={t.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <div>
              <p className="text-sm text-gray-900 dark:text-gray-100">{t.title}</p>
              <p className="text-xs capitalize text-gray-500 dark:text-gray-400">
                {t.task_type} · {t.status}{t.scheduled_for ? ` · ${t.scheduled_for}` : ""}{t.recurrence !== "none" ? ` · ${t.recurrence}` : ""}
              </p>
            </div>
            {t.status === "scheduled" && (
              <Button variant="ghost" leftIcon={<CheckCircle2 className="h-4 w-4" />} loading={done.isPending} onClick={() => done.mutate(t.id)}>Done</Button>
            )}
          </div>
        ))}</div>
      )}
    </div>
  );
}
