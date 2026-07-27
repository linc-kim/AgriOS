/**
 * Aviculture — Automation & Tasks (Module 15, Part 9).
 *
 * Deterministic operational tasks (vaccinations due, permits expiring, incubation
 * milestones, aviary cleaning) generated from recorded facts and materialised into
 * the platform Reminder engine — each with Priority / Reason / Suggested-Due. Plus
 * staged workflows (intake, quarantine, incubation, sale) that advance through
 * deterministic templates. Automation never acts irreversibly on its own.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ListChecks, Plus, RefreshCw, Workflow as WorkflowIcon } from "lucide-react";

import {
  advanceWorkflow, completeTask, generateReminders, listTasks, listWorkflows, previewAutomation,
  startWorkflow, type Task, type Workflow,
} from "@/api/avicultureAutomation";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { PriorityBadge } from "./badges";
import { AviModal } from "./AviModal";
import { AviSubnav } from "./AviSubnav";

type Tab = "tasks" | "workflows";
const WORKFLOW_TYPES = ["intake", "quarantine", "treatment", "incubation", "sale", "purchase", "transfer", "exhibition"];

export default function AutomationScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [tab, setTab] = useState<Tab>("tasks");

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <ListChecks className="h-6 w-6" />
        </div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Automation &amp; Tasks</h1>
      </div>
      <AviSubnav farmId={farmId} active="/aviculture/automation" />

      <div className="mb-5 flex gap-1 border-b border-gray-200 dark:border-gray-800">
        {(["tasks", "workflows"] as Tab[]).map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={cn("border-b-2 px-3 py-2 text-sm font-medium capitalize transition",
              tab === t ? "border-brand-500 text-brand-700 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300")}>
            {t}
          </button>
        ))}
      </div>

      {tab === "tasks" ? <Tasks farmId={farmId} /> : <Workflows farmId={farmId} />}
    </div>
  );
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

function Tasks({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const previewQ = useQuery({ queryKey: ["avi-automation-preview", farmId], queryFn: () => previewAutomation(farmId) });
  const tasksQ = useQuery({ queryKey: ["avi-tasks", farmId], queryFn: () => listTasks(farmId) });

  const generate = useMutation({
    mutationFn: () => generateReminders(farmId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["avi-tasks", farmId] }); qc.invalidateQueries({ queryKey: ["avi-automation-preview", farmId] }); },
  });
  const done = useMutation({
    mutationFn: (id: string) => completeTask(farmId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["avi-tasks", farmId] }),
  });

  const preview = previewQ.data ?? [];
  const tasks = tasksQ.data ?? [];

  return (
    <div className="space-y-6">
      {/* Due items computed from recorded facts */}
      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Due &amp; upcoming ({preview.length})</h2>
          <Button variant="secondary" leftIcon={<RefreshCw className="h-4 w-4" />} loading={generate.isPending}
            onClick={() => generate.mutate()}>Generate reminders</Button>
        </div>
        {previewQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : preview.length === 0 ? (
          <EmptyState title="Nothing due" description="No operational items are due within the horizon." />
        ) : (
          <div className="space-y-2">
            {preview.map((it) => (
              <div key={it.dedup_key} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{it.title}</p>
                  <PriorityBadge priority={it.priority} />
                </div>
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{it.reason}</p>
                {it.suggested_due_on && <p className="mt-0.5 text-xs text-gray-400">Suggested due {it.suggested_due_on}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Materialised reminders */}
      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">Active reminders ({tasks.length})</h2>
        {tasksQ.isLoading ? <Skeleton className="h-20 rounded-xl" /> : tasks.length === 0 ? (
          <EmptyState title="No reminders yet" description="Generate reminders from the due items above." />
        ) : (
          <div className="space-y-2">{tasks.map((t: Task) => (
            <div key={t.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-800">
              <div>
                <p className="text-sm text-gray-900 dark:text-gray-100">{t.title}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Due {new Date(t.due_at).toLocaleDateString()}</p>
              </div>
              <div className="flex items-center gap-2">
                <PriorityBadge priority={t.priority} />
                <Button variant="ghost" leftIcon={<CheckCircle2 className="h-4 w-4" />} loading={done.isPending} onClick={() => done.mutate(t.id)}>Done</Button>
              </div>
            </div>
          ))}</div>
        )}
      </section>
    </div>
  );
}

// ── Workflows ─────────────────────────────────────────────────────────────────

function Workflows({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["avi-workflows", farmId], queryFn: () => listWorkflows(farmId) });
  const advance = useMutation({
    mutationFn: (id: string) => advanceWorkflow(farmId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["avi-workflows", farmId] }),
  });

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>Start workflow</Button>
      </div>
      {q.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (q.data ?? []).length === 0 ? (
        <EmptyState icon={<WorkflowIcon className="h-8 w-8" />} title="No workflows yet"
          description="Start a staged process (intake, quarantine, incubation, sale…)." />
      ) : (
        <div className="space-y-2">{(q.data ?? []).map((w: Workflow) => <WorkflowRow key={w.id} wf={w} onAdvance={() => advance.mutate(w.id)} advancing={advance.isPending} />)}</div>
      )}
      <StartWorkflowModal open={open} onClose={() => setOpen(false)} farmId={farmId}
        onCreated={() => qc.invalidateQueries({ queryKey: ["avi-workflows", farmId] })} />
    </div>
  );
}

function WorkflowRow({ wf, onAdvance, advancing }: { wf: Workflow; onAdvance: () => void; advancing: boolean }) {
  const idx = wf.stages.indexOf(wf.current_stage);
  return (
    <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">{wf.workflow_type}</p>
        <span className={cn("text-xs capitalize", wf.status === "completed" ? "text-brand-600 dark:text-brand-300" : "text-gray-500 dark:text-gray-400")}>{wf.status}</span>
      </div>
      {/* Stage progress */}
      <div className="mt-2 flex flex-wrap items-center gap-1">
        {wf.stages.map((s, i) => (
          <span key={s} className={cn("rounded px-2 py-0.5 text-[11px] capitalize",
            i < idx ? "bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300"
              : i === idx ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-400 dark:bg-gray-800")}>
            {s.replace(/_/g, " ")}
          </span>
        ))}
      </div>
      {wf.status === "active" && (
        <div className="mt-2 flex justify-end">
          <Button variant="ghost" loading={advancing} onClick={onAdvance}>Advance →</Button>
        </div>
      )}
    </div>
  );
}

function StartWorkflowModal({ open, onClose, farmId, onCreated }: { open: boolean; onClose: () => void; farmId: string; onCreated: () => void }) {
  const [type, setType] = useState("intake");
  const m = useMutation({
    mutationFn: () => startWorkflow(farmId, { workflow_type: type }),
    onSuccess: () => { onCreated(); onClose(); },
  });
  return (
    <AviModal open={open} onClose={onClose} title="Start workflow">
      <div className="space-y-4">
        <Select label="Workflow type" options={WORKFLOW_TYPES.map((t) => ({ value: t, label: t }))} value={type} onChange={(e) => setType(e.target.value)} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} onClick={() => m.mutate()}>Start</Button>
        </div>
      </div>
    </AviModal>
  );
}
