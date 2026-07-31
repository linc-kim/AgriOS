/**
 * BSF — Environment Monitoring (Module 16, Frontend Milestone 6).
 *
 * Pick a production unit, record immutable environmental readings, and see the
 * backend's live threshold assessment (against the species' recommended ranges)
 * plus per-parameter stability. Threshold violations are highlighted. The unit
 * roster is managed here too (units are the module's physical infrastructure).
 * All assessment/severity logic is the backend's — the frontend presents it.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Thermometer } from "lucide-react";

import { UNIT_TYPES, createUnit, listUnits } from "@/api/bsf";
import {
  ENV_SOURCES, getUnitAssessment, listReadings, recordReading,
  type Assessment, type ReadingResult,
} from "@/api/bsfEnvironment";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { FactBadge } from "@/components/common/FactBadge";
import { BsfSubnav } from "./BsfSubnav";

const OVERALL_STYLES: Record<string, string> = {
  ok: "text-emerald-600", warning: "text-amber-600", critical: "text-red-600",
};

export default function BsfEnvironmentScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [unitId, setUnitId] = useState("");
  const [addUnitOpen, setAddUnitOpen] = useState(false);
  const [recordOpen, setRecordOpen] = useState(false);

  const unitsQ = useQuery({ queryKey: ["bsf-units", farmId], queryFn: () => listUnits(farmId as string), enabled: !!farmId });
  const assessQ = useQuery({ queryKey: ["bsf-env-assess", farmId, unitId], queryFn: () => getUnitAssessment(farmId as string, unitId), enabled: !!farmId && !!unitId });
  const readingsQ = useQuery({ queryKey: ["bsf-env-readings", farmId, unitId], queryFn: () => listReadings(farmId as string, { production_unit_id: unitId, limit: 20 }), enabled: !!farmId && !!unitId });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const units = unitsQ.data ?? [];
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["bsf-env-assess", farmId, unitId] });
    qc.invalidateQueries({ queryKey: ["bsf-env-readings", farmId, unitId] });
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <BsfSubnav active="/bsf/environment" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Thermometer className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Environment</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Readings &amp; threshold assessment</p>
          </div>
        </div>
        <Button variant="ghost" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddUnitOpen(true)}>Add unit</Button>
      </div>

      <div className="mb-5 max-w-md">
        <Select label="Production unit" value={unitId} onChange={(e) => setUnitId(e.target.value)}
          options={[{ value: "", label: units.length ? "Select a unit…" : "No units — add one" }, ...units.map((u) => ({ value: u.id, label: `${u.name} (${u.unit_type})` }))]} />
      </div>

      {!unitId ? (
        <p className="text-sm text-gray-400">Select a production unit to view its environment.</p>
      ) : (
        <div className="space-y-5">
          <div className="flex justify-end">
            <Button size="sm" leftIcon={<Thermometer className="h-4 w-4" />} onClick={() => setRecordOpen(true)}>Record reading</Button>
          </div>

          {/* Latest assessment */}
          {assessQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : assessQ.data && (
            <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
              {assessQ.data.assessment == null ? (
                <p className="text-sm text-gray-400">No readings recorded for this unit yet.</p>
              ) : (
                <>
                  <div className="mb-3 flex items-center justify-between">
                    <p className={`text-lg font-semibold capitalize ${OVERALL_STYLES[assessQ.data.assessment.overall]}`}>
                      {assessQ.data.assessment.overall}
                    </p>
                    <p className="text-xs text-gray-400">as of {assessQ.data.latest_recorded_at?.slice(0, 10)}</p>
                  </div>
                  <AssessmentGrid a={assessQ.data.assessment} stability={assessQ.data.stability} />
                </>
              )}
            </div>
          )}

          {/* Recent readings */}
          <section>
            <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Recent readings</h2>
            {(readingsQ.data ?? []).length === 0 ? <p className="text-sm text-gray-400">No readings yet.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-gray-400">
                    <tr><th className="py-1 pr-4">When</th><th className="pr-4">Temp °C</th><th className="pr-4">Humidity %</th><th className="pr-4">Moisture %</th><th className="pr-4">Airflow m/s</th><th>Source</th></tr>
                  </thead>
                  <tbody>
                    {readingsQ.data!.map((r) => (
                      <tr key={r.id} className="border-t border-gray-100 dark:border-gray-800">
                        <td className="py-1.5 pr-4 text-gray-500">{new Date(r.recorded_at).toLocaleString()}</td>
                        <td className="pr-4">{r.temperature_c ?? "—"}</td>
                        <td className="pr-4">{r.humidity_pct ?? "—"}</td>
                        <td className="pr-4">{r.moisture_pct ?? "—"}</td>
                        <td className="pr-4">{r.airflow_mps ?? "—"}</td>
                        <td className="capitalize text-gray-500">{r.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      <AddUnitModal open={addUnitOpen} onClose={() => setAddUnitOpen(false)} farmId={farmId}
        onCreated={() => qc.invalidateQueries({ queryKey: ["bsf-units", farmId] })} />
      {recordOpen && unitId && (
        <RecordReadingModal onClose={() => setRecordOpen(false)} farmId={farmId} unitId={unitId} onDone={invalidate} />
      )}
    </div>
  );
}

function AssessmentGrid({ a, stability }: { a: Assessment; stability: Record<string, { label: string; value: unknown }> }) {
  const params = ["temperature", "humidity", "moisture", "airflow"];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {params.map((p) => {
        const param = a.parameters[p];
        const violated = a.violations.find((v) => v.parameter === p);
        const stab = stability?.[p];
        return (
          <div key={p} className={`rounded-lg border p-3 ${violated ? (violated.severity === "critical" ? "border-red-300 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10" : "border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10") : "border-gray-200 dark:border-gray-800"}`}>
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-wide capitalize text-gray-500">{p}</p>
              <FactBadge label={param?.label} />
            </div>
            <p className="mt-1 text-sm font-semibold capitalize text-gray-900 dark:text-gray-100" title={param?.detail}>
              {param?.value != null ? String(param.value) : "—"}
            </p>
            {violated && <p className="mt-1 text-[11px] text-red-600 dark:text-red-400">{violated.detail}</p>}
            {stab && stab.value != null && <p className="mt-1 text-[11px] text-gray-400">σ {String(stab.value)}</p>}
          </div>
        );
      })}
    </div>
  );
}

function AddUnitModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("bin");
  const [capacity, setCapacity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: () => createUnit(farmId, { name: name.trim(), unit_type: type, capacity_grams: capacity ? Number(capacity) : null }),
    onSuccess: () => { setName(""); setCapacity(""); onCreated(); onClose(); },
    onError: () => setError("Could not create the unit."),
  });
  return (
    <Modal open={open} onClose={onClose} title="Add production unit">
      <div className="space-y-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Rearing Bin 1" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Type" value={type} onChange={(e) => setType(e.target.value)} options={UNIT_TYPES.map((t) => ({ value: t, label: t.replace(/_/g, " ") }))} />
          <TextField label="Capacity (grams, opt.)" inputMode="numeric" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!name.trim()} onClick={() => { setError(null); m.mutate(); }}>Add unit</Button>
        </div>
      </div>
    </Modal>
  );
}

function RecordReadingModal({ onClose, farmId, unitId, onDone }: { onClose: () => void; farmId: string; unitId: string; onDone: () => void }) {
  const [temp, setTemp] = useState("");
  const [humidity, setHumidity] = useState("");
  const [moisture, setMoisture] = useState("");
  const [airflow, setAirflow] = useState("");
  const [source, setSource] = useState("manual");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReadingResult | null>(null);

  const num = (s: string) => (s ? Number(s) : null);
  const m = useMutation({
    mutationFn: () => recordReading(farmId, {
      production_unit_id: unitId, temperature_c: num(temp), humidity_pct: num(humidity),
      moisture_pct: num(moisture), airflow_mps: num(airflow), source,
    }),
    onSuccess: (r) => { setResult(r); onDone(); },
    onError: () => setError("Could not record the reading."),
  });

  return (
    <Modal open onClose={onClose} title="Record environmental reading">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Temperature (°C)" inputMode="decimal" value={temp} onChange={(e) => setTemp(e.target.value)} />
          <TextField label="Humidity (%)" inputMode="decimal" value={humidity} onChange={(e) => setHumidity(e.target.value)} />
          <TextField label="Moisture (%)" inputMode="decimal" value={moisture} onChange={(e) => setMoisture(e.target.value)} />
          <TextField label="Airflow (m/s)" inputMode="decimal" value={airflow} onChange={(e) => setAirflow(e.target.value)} />
        </div>
        <Select label="Source" value={source} onChange={(e) => setSource(e.target.value)} options={ENV_SOURCES.map((s) => ({ value: s, label: s }))} />
        {result && (
          <div className={`rounded-lg p-3 text-sm ${result.assessment.overall === "ok" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : result.assessment.overall === "critical" ? "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300" : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"}`}>
            Assessment: <span className="font-semibold capitalize">{result.assessment.overall}</span>
            {result.assessment.violations.map((v, i) => <div key={i} className="text-xs">{v.detail}</div>)}
          </div>
        )}
        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>{result ? "Done" : "Cancel"}</Button>
          {!result && <Button loading={m.isPending} disabled={!temp && !humidity && !moisture && !airflow} onClick={() => { setError(null); m.mutate(); }}>Record</Button>}
        </div>
      </div>
    </Modal>
  );
}
