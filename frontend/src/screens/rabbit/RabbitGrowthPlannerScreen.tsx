/**
 * Rabbit — Growth Planner (Module 17, Frontend Increment 2).
 *
 * A thin surface over the PLATFORM Growth Planner (module='rabbit'). No rabbit-
 * specific planner exists. Progress (planned vs actual) is computed by the backend
 * from recorded facts and rendered honesty-labelled; the client never recomputes.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Target } from "lucide-react";

import {
  listPlans, createPlan, getPlanDetail, RABBIT_METRIC_KEYS, type Plan,
} from "@/api/rabbitGrowthPlanner";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { LabelledValue } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

const inputCls = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900";

export default function RabbitGrowthPlannerScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const plansQ = useQuery({ queryKey: ["rabbit-plans", farmId], queryFn: () => listPlans(farmId as string), enabled: !!farmId });
  const detailQ = useQuery({ queryKey: ["rabbit-plan", farmId, selected], queryFn: () => getPlanDetail(farmId as string, selected as string), enabled: !!farmId && !!selected });

  const createM = useMutation({
    mutationFn: (body: Parameters<typeof createPlan>[1]) => createPlan(farmId as string, body),
    onSuccess: (p) => { qc.invalidateQueries({ queryKey: ["rabbit-plans", farmId] }); setShowCreate(false); setSelected(p.id); },
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <RabbitSubnav active="/rabbit/planner" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Target className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Growth Planner</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Long-term goals tracked against recorded facts</p>
          </div>
        </div>
        <Button onClick={() => setShowCreate(true)}>New plan</Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="md:col-span-1">
          {plansQ.isLoading ? <Skeleton className="h-40 rounded-xl" /> : (plansQ.data ?? []).length === 0 ? (
            <p className="text-sm text-gray-400">No plans yet.</p>
          ) : (
            <ul className="space-y-2">
              {plansQ.data!.map((p: Plan) => (
                <li key={p.id}>
                  <button onClick={() => setSelected(p.id)}
                    className={`w-full rounded-xl border p-3 text-left ${selected === p.id ? "border-brand-300 bg-brand-50/40 dark:border-brand-500/30 dark:bg-brand-500/10" : "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"}`}>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{p.title}{p.is_primary ? " ★" : ""}</p>
                    <p className="text-xs capitalize text-gray-500">{p.status} · rev {p.current_revision}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="md:col-span-2">
          {!selected ? <p className="text-sm text-gray-400">Select a plan to see progress.</p> :
            detailQ.isLoading || !detailQ.data ? <Skeleton className="h-64 rounded-xl" /> : (
              <div className="space-y-4">
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Overall progress</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">
                    <LabelledValue figure={detailQ.data.progress.overall_percent} format={(v) => `${v}%`} />
                  </p>
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Goals</h3>
                  {detailQ.data.progress.goals.length === 0 ? <p className="text-sm text-gray-400">No goals.</p> : (
                    <ul className="space-y-2">
                      {detailQ.data.progress.goals.map((g) => (
                        <li key={g.goal_id} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{g.label}{g.is_primary ? " ★" : ""}</p>
                          <p className="mt-1 text-sm">Progress: <LabelledValue figure={g.progress.percent} format={(v) => `${v}%`} /></p>
                          <p className="text-xs text-gray-500">Metric: {g.metric_key}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
        </div>
      </div>

      {showCreate && <CreatePlanModal submitting={createM.isPending} onCancel={() => setShowCreate(false)} onSubmit={(b) => createM.mutate(b)} />}
    </div>
  );
}

function CreatePlanModal({ onSubmit, onCancel, submitting }: {
  onSubmit: (b: Parameters<typeof createPlan>[1]) => void; onCancel: () => void; submitting: boolean;
}) {
  const [title, setTitle] = useState("");
  const [metric, setMetric] = useState<string>(RABBIT_METRIC_KEYS[0]);
  const [target, setTarget] = useState("");
  return (
    <Modal open onClose={onCancel} title="New growth plan">
      <div className="space-y-3">
        <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputCls} placeholder="e.g. 50 breeding does" /></label>
        <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Primary goal metric</span>
          <select value={metric} onChange={(e) => setMetric(e.target.value)} className={inputCls}>
            {RABBIT_METRIC_KEYS.map((k) => <option key={k} value={k}>{k.replace(/_/g, " ")}</option>)}
          </select></label>
        <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Target value</span>
          <input type="number" min={0} value={target} onChange={(e) => setTarget(e.target.value)} className={inputCls} /></label>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button loading={submitting} disabled={!title || !target}
            onClick={() => onSubmit({
              title, is_primary: true,
              goals: [{ metric_key: metric, label: metric.replace(/_/g, " "), target_value: Number(target), is_primary: true }],
            })}>Create</Button>
        </div>
      </div>
    </Modal>
  );
}
