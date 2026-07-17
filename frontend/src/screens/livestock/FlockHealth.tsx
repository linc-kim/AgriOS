/**
 * Greena — Flock Health.
 * Health event timeline + logging (observations, symptoms, diagnoses,
 * treatments, medication, quarantine, vet visits, recovery, follow-ups) for a
 * flock, wired to the real backend. Embedded on the flock detail screen.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HeartPulse, Plus, X, CheckCircle2, CalendarClock, Stethoscope } from "lucide-react";

import { listHealthEvents, createHealthEvent, updateHealthEvent } from "@/api/health";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { HealthEvent, HealthEventCreateInput, HealthEventType, HealthSeverity } from "@/types";

const TODAY = () => new Date().toISOString().slice(0, 10);

const EVENT_TYPES: { value: HealthEventType; label: string }[] = [
  { value: "observation", label: "Observation" },
  { value: "symptom", label: "Symptom" },
  { value: "diagnosis", label: "Diagnosis" },
  { value: "treatment", label: "Treatment" },
  { value: "medication", label: "Medication" },
  { value: "mortality_investigation", label: "Mortality investigation" },
  { value: "quarantine", label: "Quarantine / isolation" },
  { value: "vet_visit", label: "Vet visit" },
  { value: "recovery", label: "Recovery" },
  { value: "followup", label: "Follow-up" },
];
const TYPE_LABEL = Object.fromEntries(EVENT_TYPES.map((t) => [t.value, t.label]));

const SEVERITY_STYLES: Record<HealthSeverity, string> = {
  info: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
  watch: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  critical: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};
const STATUS_STYLES: Record<string, string> = {
  open: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  monitoring: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  resolved: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
};

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#161a20] sm:rounded-3xl">
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

export function FlockHealth({ farmId, flockId, disabled }: { farmId: string; flockId: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const [logging, setLogging] = useState(false);

  const eventsQuery = useQuery({
    queryKey: ["health-events", farmId, flockId],
    queryFn: () => listHealthEvents(farmId, flockId, { limit: 50 }),
    enabled: !!farmId && !!flockId,
  });
  const events = eventsQuery.data ?? [];

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["health-events", farmId, flockId] });
    qc.invalidateQueries({ queryKey: ["health-summary", farmId] });
    qc.invalidateQueries({ queryKey: ["flock", farmId, flockId] });
  };

  const resolve = useMutation({
    mutationFn: (id: string) => updateHealthEvent(farmId, flockId, id, { status: "resolved" }),
    onSuccess: invalidate,
  });

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <HeartPulse className="h-4 w-4 text-brand-500" /> Health
        </h2>
        {!disabled && (
          <Button size="sm" variant="secondary" onClick={() => setLogging(true)} leftIcon={<Plus className="h-4 w-4" />}>
            Log health event
          </Button>
        )}
      </div>

      {eventsQuery.isLoading ? (
        <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>
      ) : eventsQuery.isError ? (
        <EmptyState icon={<Stethoscope className="h-5 w-5" />} title="Couldn't load health records" description="Please try again in a moment." />
      ) : events.length === 0 ? (
        <EmptyState
          icon={<HeartPulse className="h-5 w-5" />}
          title="No health records yet"
          description={disabled ? "This flock is closed." : "Log symptoms, treatments, medication or vet visits to build this flock's health history."}
        />
      ) : (
        <ol className="space-y-3">
          {events.map((e) => (
            <HealthRow key={e.id} event={e} onResolve={() => resolve.mutate(e.id)} resolving={resolve.isPending} canEdit={!disabled} />
          ))}
        </ol>
      )}

      {logging && (
        <LogHealthModal farmId={farmId} flockId={flockId} onClose={() => setLogging(false)} onSaved={() => { setLogging(false); invalidate(); }} />
      )}
    </section>
  );
}

function HealthRow({ event, onResolve, resolving, canEdit }: { event: HealthEvent; onResolve: () => void; resolving: boolean; canEdit: boolean }) {
  return (
    <li className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-gray-900 dark:text-white">{event.title}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${SEVERITY_STYLES[event.severity]}`}>{event.severity}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[event.status]}`}>{event.status}</span>
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {TYPE_LABEL[event.event_type]} · {new Date(event.event_date).toLocaleDateString()}
            {event.affected_count != null ? ` · ${event.affected_count} birds` : ""}
          </p>
          {event.symptoms.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {event.symptoms.map((s) => (
                <span key={s} className="rounded-md bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600 dark:bg-white/10 dark:text-gray-300">{s}</span>
              ))}
            </div>
          )}
          {event.medication_name && <p className="mt-1.5 text-sm text-gray-600 dark:text-gray-300">💊 {event.medication_name}{event.dosage ? ` — ${event.dosage}` : ""}</p>}
          {event.treatment && <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{event.treatment}</p>}
          {event.vet_name && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Vet: {event.vet_name}</p>}
          {event.cost_kes && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Cost: KES {Number(event.cost_kes).toLocaleString()}</p>}
          {event.follow_up_date && event.status !== "resolved" && (
            <p className="mt-1 inline-flex items-center gap-1 text-sm text-amber-600 dark:text-amber-400">
              <CalendarClock className="h-3.5 w-3.5" /> Follow-up {new Date(event.follow_up_date).toLocaleDateString()}
            </p>
          )}
        </div>
        {canEdit && event.status !== "resolved" && (
          <button
            onClick={onResolve}
            disabled={resolving}
            className="inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50 disabled:opacity-50 dark:text-brand-300 dark:hover:bg-brand-600/15"
          >
            <CheckCircle2 className="h-4 w-4" /> Resolve
          </button>
        )}
      </div>
    </li>
  );
}

function LogHealthModal({ farmId, flockId, onClose, onSaved }: { farmId: string; flockId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({
    event_type: "symptom" as HealthEventType,
    event_date: TODAY(),
    title: "",
    symptoms: "",
    severity: "watch" as HealthSeverity,
    affected_count: "",
    diagnosis: "",
    treatment: "",
    medication_name: "",
    dosage: "",
    vet_name: "",
    cost_kes: "",
    follow_up_date: "",
    notes: "",
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const showMed = f.event_type === "medication" || f.event_type === "treatment";
  const showVet = f.event_type === "vet_visit";

  const save = useMutation({
    mutationFn: () => {
      const input: HealthEventCreateInput = {
        event_type: f.event_type,
        event_date: f.event_date,
        title: f.title.trim(),
        severity: f.severity,
        symptoms: f.symptoms.split(",").map((s) => s.trim()).filter(Boolean),
        affected_count: f.affected_count ? Number(f.affected_count) : undefined,
        diagnosis: f.diagnosis || undefined,
        treatment: f.treatment || undefined,
        medication_name: f.medication_name || undefined,
        dosage: f.dosage || undefined,
        vet_name: f.vet_name || undefined,
        cost_kes: f.cost_kes || undefined,
        follow_up_date: f.follow_up_date || undefined,
        notes: f.notes || undefined,
      };
      return createHealthEvent(farmId, flockId, input);
    },
    onSuccess: onSaved,
    onError: (e: any) => setError(e?.response?.data?.error?.message ?? "Couldn't save the health record."),
  });

  const valid = f.title.trim().length >= 2 && f.event_date;

  return (
    <ModalShell title="Log health event" onClose={onClose}>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
      <div className="space-y-4">
        <Select label="Type" options={EVENT_TYPES} value={f.event_type} onChange={(e) => set({ event_type: e.target.value as HealthEventType })} />
        <TextField label="Title" placeholder="e.g. Reduced feed intake" value={f.title} onChange={(e) => set({ title: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Date" type="date" value={f.event_date} onChange={(e) => set({ event_date: e.target.value })} />
          <Select
            label="Severity"
            options={[
              { value: "info", label: "Info" },
              { value: "watch", label: "Watch" },
              { value: "warning", label: "Warning" },
              { value: "critical", label: "Critical" },
            ]}
            value={f.severity}
            onChange={(e) => set({ severity: e.target.value as HealthSeverity })}
          />
        </div>
        <TextField label="Symptoms" hint="Comma-separated, e.g. lethargy, nasal discharge" value={f.symptoms} onChange={(e) => set({ symptoms: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Birds affected" type="number" min={0} value={f.affected_count} onChange={(e) => set({ affected_count: e.target.value })} />
          <TextField label="Follow-up date" type="date" value={f.follow_up_date} onChange={(e) => set({ follow_up_date: e.target.value })} />
        </div>
        {showMed && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Medication" value={f.medication_name} onChange={(e) => set({ medication_name: e.target.value })} />
            <TextField label="Dosage" value={f.dosage} onChange={(e) => set({ dosage: e.target.value })} />
          </div>
        )}
        {showVet && <TextField label="Vet name" value={f.vet_name} onChange={(e) => set({ vet_name: e.target.value })} />}
        {(showMed || showVet) && (
          <TextField label="Cost (KES)" hint="Recorded as a farm expense automatically." type="number" min={0} value={f.cost_kes} onChange={(e) => set({ cost_kes: e.target.value })} />
        )}
        <TextField label="Diagnosis" value={f.diagnosis} onChange={(e) => set({ diagnosis: e.target.value })} />
        <TextField label="Treatment / notes" value={f.treatment} onChange={(e) => set({ treatment: e.target.value })} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Save</Button>
      </div>
    </ModalShell>
  );
}
