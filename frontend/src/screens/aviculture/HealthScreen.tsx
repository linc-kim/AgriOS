/**
 * Aviculture — Health (Module 15, Part 6).
 *
 * Farm-wide individual-bird health: honesty-labelled KPIs (mortality, vaccination
 * coverage, preventive-care due), disease/outbreak tracking, and active quarantine.
 * Every figure carries how it is known; nothing is diagnosed here — ARIA explains,
 * a veterinarian decides.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, Plus, ShieldAlert } from "lucide-react";

import {
  createDiseaseEvent, getHealthSummary, listDiseaseEvents, listQuarantine, updateDiseaseEvent,
} from "@/api/avicultureHealth";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge } from "./badges";
import { AviModal } from "./AviModal";
import { AviSubnav } from "./AviSubnav";

export default function HealthScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);

  const summaryQ = useQuery({ queryKey: ["avi-health-summary", farmId], queryFn: () => getHealthSummary(farmId as string), enabled: !!farmId });
  const diseaseQ = useQuery({ queryKey: ["avi-disease", farmId], queryFn: () => listDiseaseEvents(farmId as string), enabled: !!farmId });
  const quarantineQ = useQuery({ queryKey: ["avi-quarantine-active", farmId], queryFn: () => listQuarantine(farmId as string, true), enabled: !!farmId });

  const resolve = useMutation({
    mutationFn: (id: string) => updateDiseaseEvent(farmId as string, id, { status: "resolved" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["avi-disease", farmId] }); qc.invalidateQueries({ queryKey: ["avi-health-summary", farmId] }); },
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const s = summaryQ.data;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <Activity className="h-6 w-6" />
        </div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Health</h1>
      </div>
      <AviSubnav farmId={farmId} active="/aviculture/health" />

      {/* KPIs */}
      {summaryQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : s && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Mortality" v={s.mortality_rate_pct} suffix="%" />
          <Kpi label="Vaccination coverage" v={s.vaccination_coverage_pct} suffix="%" />
          <Kpi label="Active quarantine" v={s.active_quarantines} />
          <Kpi label="Active disease" v={s.active_disease_events} />
          <Kpi label="Preventive due" v={s.preventive_due.due_count} />
          <Kpi label="Overdue" v={s.preventive_due.overdue_count} />
          <Kpi label="Records" v={s.records_total} />
          <Kpi label="Active birds" v={s.active_birds} />
        </div>
      )}

      {/* Disease events */}
      <div className="mb-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
            <ShieldAlert className="h-4 w-4" /> Disease &amp; outbreaks
          </h2>
          <Button variant="secondary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>Record</Button>
        </div>
        {(diseaseQ.data ?? []).length === 0 ? <EmptyState title="No disease events recorded" /> : (
          <div className="space-y-2">{(diseaseQ.data ?? []).map((d) => (
            <div key={d.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-800">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {d.disease_name}{d.is_notifiable ? " · notifiable" : ""}
                </p>
                <p className="text-xs capitalize text-gray-500 dark:text-gray-400">
                  {d.status} · {d.affected_count} affected · from {d.started_on}{d.resolved_on ? ` · resolved ${d.resolved_on}` : ""}
                </p>
              </div>
              {d.status !== "resolved" && <Button variant="ghost" loading={resolve.isPending} onClick={() => resolve.mutate(d.id)}>Resolve</Button>}
            </div>
          ))}</div>
        )}
      </div>

      {/* Active quarantine */}
      <div>
        <h2 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">Active quarantine</h2>
        {(quarantineQ.data ?? []).length === 0 ? <EmptyState title="No birds in quarantine" /> : (
          <div className="space-y-2">{(quarantineQ.data ?? []).map((q) => (
            <div key={q.id} className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-800">
              <span className="text-gray-900 dark:text-gray-100">{q.reason || "Quarantine"}</span>
              <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">since {q.started_on}{q.expected_end_on ? ` · until ${q.expected_end_on}` : ""}</span>
            </div>
          ))}</div>
        )}
      </div>

      <NewDiseaseModal open={addOpen} onClose={() => setAddOpen(false)} farmId={farmId}
        onCreated={() => { qc.invalidateQueries({ queryKey: ["avi-disease", farmId] }); qc.invalidateQueries({ queryKey: ["avi-health-summary", farmId] }); }} />
    </div>
  );
}

function Kpi({ label, v, suffix = "" }: { label: string; v: { label: string; value: unknown }; suffix?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        <FactBadge label={v.label} />
      </div>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">
        {v.value != null ? `${v.value}${suffix}` : "—"}
      </p>
    </div>
  );
}

function NewDiseaseModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [status, setStatus] = useState("suspected");
  const [affected, setAffected] = useState("0");
  const [notifiable, setNotifiable] = useState("no");
  const m = useMutation({
    mutationFn: () => createDiseaseEvent(farmId, { disease_name: name.trim(), status, affected_count: Number(affected) || 0, is_notifiable: notifiable === "yes" }),
    onSuccess: () => { setName(""); setAffected("0"); onCreated(); onClose(); },
  });
  return (
    <AviModal open={open} onClose={onClose} title="Record disease event">
      <div className="space-y-4">
        <TextField label="Disease name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Coccidiosis" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Status" options={["suspected", "confirmed", "contained", "resolved"].map((x) => ({ value: x, label: x }))} value={status} onChange={(e) => setStatus(e.target.value)} />
          <TextField label="Affected count" inputMode="numeric" value={affected} onChange={(e) => setAffected(e.target.value)} />
        </div>
        <Select label="Notifiable?" options={[{ value: "no", label: "No" }, { value: "yes", label: "Yes" }]} value={notifiable} onChange={(e) => setNotifiable(e.target.value)} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!name.trim()} onClick={() => m.mutate()}>Record</Button>
        </div>
      </div>
    </AviModal>
  );
}
