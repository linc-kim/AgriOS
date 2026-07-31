/**
 * BSF — Growth Planner (Module 16, Frontend Milestone 7).
 *
 * Long-term growth as recorded domain objects: goals, milestones and version
 * history. Planned-vs-actual progress is computed by the backend from recorded
 * operational data and rendered honesty-labelled. ARIA/Mission Control may
 * recommend changes elsewhere, but only these explicit user actions mutate a
 * plan — the frontend never fabricates progress.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Flag, Plus, Target } from "lucide-react";

import {
  MILESTONE_STATUSES, createPlan, getPlanDetail, listPlans, listRevisions,
  updateMilestoneStatus, type GoalInput, type PlanDetail,
} from "@/api/bsfGrowth";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { FactBadge } from "@/components/common/FactBadge";
import { BsfSubnav } from "./BsfSubnav";

const METRIC_KEYS = [
  { value: "total_harvest_kg", label: "Total harvest (kg)" },
  { value: "monthly_harvest_kg", label: "Monthly harvest (kg)" },
  { value: "monthly_revenue", label: "Monthly revenue" },
  { value: "total_revenue", label: "Total revenue" },
  { value: "active_biomass_g", label: "Active biomass (g)" },
];
const num = (v: unknown) => (v == null ? "—" : Number(v).toLocaleString());

export default function BsfGrowthScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [planId, setPlanId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const plansQ = useQuery({ queryKey: ["bsf-plans", farmId], queryFn: () => listPlans(farmId as string), enabled: !!farmId });
  const plans = plansQ.data ?? [];
  const activePlanId = planId ?? plans.find((p) => p.is_primary)?.id ?? plans[0]?.id ?? null;

  const detailQ = useQuery({ queryKey: ["bsf-plan", farmId, activePlanId], queryFn: () => getPlanDetail(farmId as string, activePlanId as string), enabled: !!farmId && !!activePlanId });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["bsf-plans", farmId] });
    qc.invalidateQueries({ queryKey: ["bsf-plan", farmId, activePlanId] });
    if (activePlanId) qc.invalidateQueries({ queryKey: ["bsf-revs", farmId, activePlanId] });
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <BsfSubnav active="/bsf/growth" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Target className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Growth Planner</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Goals, milestones &amp; progress</p>
          </div>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>New plan</Button>
      </div>

      {plansQ.isLoading ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : plans.length === 0 ? (
        <EmptyState icon={<Target className="h-8 w-8" />} title="No growth plan yet"
          description="Set a long-term goal and Greena will track progress from your recorded data."
          action={<Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>New plan</Button>} />
      ) : (
        <>
          {plans.length > 1 && (
            <div className="mb-4 max-w-md">
              <Select label="Plan" value={activePlanId ?? ""} onChange={(e) => setPlanId(e.target.value)}
                options={plans.map((p) => ({ value: p.id, label: `${p.title}${p.is_primary ? " (primary)" : ""}` }))} />
            </div>
          )}
          {detailQ.isLoading || !detailQ.data ? <Skeleton className="h-40 rounded-xl" /> : (
            <PlanView detail={detailQ.data} farmId={farmId} onChanged={invalidate} />
          )}
        </>
      )}

      <NewPlanModal open={addOpen} onClose={() => setAddOpen(false)} farmId={farmId} onCreated={(id) => { setPlanId(id); invalidate(); }} />
    </div>
  );
}

function PlanView({ detail, farmId, onChanged }: { detail: PlanDetail; farmId: string; onChanged: () => void }) {
  const overall = detail.progress.overall_percent;
  const overallVal = typeof overall.value === "number" ? overall.value : null;
  const revsQ = useQuery({ queryKey: ["bsf-revs", farmId, detail.id], queryFn: () => listRevisions(farmId, detail.id) });

  return (
    <div className="space-y-5">
      {/* Overall progress */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">{detail.title}</h2>
            <p className="text-xs text-gray-500">Revision {detail.current_revision} · {detail.status}</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-semibold text-gray-900 dark:text-gray-100" title={overall.detail}>
              {overallVal != null ? `${overallVal}%` : "—"} <FactBadge label={overall.label} />
            </p>
            <p className="text-xs text-gray-400">overall progress</p>
          </div>
        </div>
        {overallVal != null && (
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
            <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, overallVal)}%` }} />
          </div>
        )}
      </div>

      {/* Goals */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Goals</h3>
        <div className="space-y-2">
          {detail.progress.goals.map((g) => {
            const p = g.progress.percent;
            const pv = typeof p?.value === "number" ? p.value : null;
            return (
              <div key={g.goal_id} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{g.label} {g.is_primary && <span className="text-xs text-brand-600">· primary</span>}</span>
                  <span className="text-sm" title={p?.detail}>{pv != null ? `${pv}%` : "—"} <FactBadge label={p?.label} /></span>
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                  <span>actual {num(g.progress.actual?.value)} / target {num(g.progress.target?.value)} {g.unit ?? ""}</span>
                  {g.run_rate?.verdict?.value != null && <span>· {String(g.run_rate.verdict.value)}</span>}
                </div>
                {pv != null && (
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                    <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, pv)}%` }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Milestones */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Milestones</h3>
        {detail.milestones.length === 0 ? <p className="text-sm text-gray-400">No milestones.</p> : (
          <ol className="space-y-2">
            {detail.milestones.map((m) => <MilestoneRow key={m.id} planId={detail.id} milestone={m} farmId={farmId} onChanged={onChanged} />)}
          </ol>
        )}
      </section>

      {/* Revisions */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Version history</h3>
        <ul className="space-y-1 text-xs text-gray-500">
          {(revsQ.data ?? []).map((r) => (
            <li key={r.id}>#{r.revision_number} · {r.trigger}{r.reason ? ` — ${r.reason}` : ""} <span className="text-gray-400">({new Date(r.created_at).toLocaleDateString()})</span></li>
          ))}
        </ul>
      </section>
    </div>
  );
}

const MS_STYLES: Record<string, string> = {
  pending: "text-gray-500", in_progress: "text-sky-600", achieved: "text-emerald-600", blocked: "text-red-600", skipped: "text-gray-400",
};

function MilestoneRow({ planId, milestone, farmId, onChanged }: { planId: string; milestone: PlanDetail["milestones"][number]; farmId: string; onChanged: () => void }) {
  const m = useMutation({
    mutationFn: (status: string) => updateMilestoneStatus(farmId, planId, milestone.id, status),
    onSuccess: onChanged,
  });
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center gap-2">
        <Flag className={`h-4 w-4 ${MS_STYLES[milestone.status]}`} />
        <span className="text-sm text-gray-800 dark:text-gray-200">{milestone.title}</span>
        {milestone.expected_impact && <span className="text-xs text-gray-400">· {milestone.expected_impact}</span>}
      </div>
      <select
        aria-label={`Status for ${milestone.title}`}
        className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs capitalize dark:border-gray-700 dark:bg-gray-800"
        value={milestone.status}
        onChange={(e) => m.mutate(e.target.value)}
      >
        {MILESTONE_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
      </select>
    </li>
  );
}

function NewPlanModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: (id: string) => void }) {
  const [title, setTitle] = useState("");
  const [metric, setMetric] = useState("total_harvest_kg");
  const [target, setTarget] = useState("");
  const [unit, setUnit] = useState("kg");
  const [targetDate, setTargetDate] = useState("");
  const [milestones, setMilestones] = useState("");
  const [error, setError] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: () => {
      const goal: GoalInput = {
        metric_key: metric, label: METRIC_KEYS.find((k) => k.value === metric)?.label ?? metric,
        unit: unit || null, baseline_value: 0, target_value: Number(target), target_date: targetDate || null, is_primary: true,
      };
      const ms = milestones.split("\n").map((s) => s.trim()).filter(Boolean).map((t, i) => ({ title: t, sequence: i + 1 }));
      return createPlan(farmId, { title: title.trim(), is_primary: true, goals: [goal], milestones: ms });
    },
    onSuccess: (p) => { setTitle(""); setTarget(""); setMilestones(""); onCreated(p.id); onClose(); },
    onError: () => setError("Could not create the plan."),
  });

  return (
    <Modal open={open} onClose={onClose} title="New growth plan">
      <div className="space-y-4">
        <TextField label="Plan title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Reach 2 tonnes/month" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Primary goal metric" value={metric} onChange={(e) => setMetric(e.target.value)} options={METRIC_KEYS} />
          <TextField label="Target value" inputMode="numeric" value={target} onChange={(e) => setTarget(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Unit" value={unit} onChange={(e) => setUnit(e.target.value)} />
          <TextField label="Target date (opt.)" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Milestones (one per line)</label>
          <textarea className="w-full rounded-lg border border-gray-200 bg-white p-2 text-sm dark:border-gray-700 dark:bg-gray-900"
            rows={3} value={milestones} onChange={(e) => setMilestones(e.target.value)} placeholder={"Expand breeder capacity\nAdd 20 rearing bins"} />
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!title.trim() || !target} onClick={() => { setError(null); m.mutate(); }}>Create plan</Button>
        </div>
      </div>
    </Modal>
  );
}
