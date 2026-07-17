/**
 * Greena — Automation & Activity Center (Module 8).
 * Tabs: Activity | Rules | Reminders. Runs the automation engine, manages
 * if/then rules and reminders, and provides an inbox with unread/read/archive,
 * priority and search. Wired to the real backend.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell, Play, Plus, Search, Archive, Check, Trash2, Zap, Clock, X, CalendarClock,
} from "lucide-react";

import {
  listActivity, archiveNotification, listRules, createRule, updateRule, deleteRule,
  listReminders, createReminder, updateReminder, deleteReminder, runEngine,
} from "@/api/automation";
import { notificationsAPI } from "@/api/notifications";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { AutomationRule, Reminder } from "@/types";

type Tab = "activity" | "rules" | "reminders";

const TRIGGERS = [
  { value: "low_feed", label: "Low feed" }, { value: "low_inventory", label: "Low inventory" },
  { value: "vaccination_due", label: "Vaccination due" }, { value: "health_alert", label: "Health alert" },
  { value: "mortality_spike", label: "Mortality spike" }, { value: "maintenance_due", label: "Maintenance due" },
  { value: "financial_anomaly", label: "Financial anomaly" }, { value: "tasks_overdue", label: "Tasks overdue" },
];
const PRIORITIES = [{ value: "low", label: "Low" }, { value: "normal", label: "Normal" }, { value: "high", label: "High" }, { value: "critical", label: "Critical" }];
const RECURRENCE = [{ value: "none", label: "One-time" }, { value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" }, { value: "monthly", label: "Monthly" }];

const PRIO_CLS: Record<string, string> = {
  critical: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  high: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  normal: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  low: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
};
const cap = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const fmtDT = (d?: string | null) => (d ? new Date(d).toLocaleString() : "—");

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#161a20] sm:rounded-3xl">
        <div className="mb-5 flex items-center justify-between"><h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10"><X className="h-5 w-5" /></button></div>
        {children}
      </div>
    </div>
  );
}

export default function AutomationScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("activity");
  const [modal, setModal] = useState<null | "rule" | "reminder">(null);
  const [banner, setBanner] = useState<string | null>(null);

  const invalidate = () => {
    if (!farmId) return;
    for (const k of [queryKeys.autoActivity(farmId), queryKeys.autoRules(farmId), queryKeys.autoReminders(farmId)]) qc.invalidateQueries({ queryKey: k });
  };

  const run = useMutation({
    mutationFn: () => runEngine(farmId!),
    onSuccess: (r) => { setBanner(`Engine run — ${r.triggers_fired} trigger(s) fired, ${r.notifications_created} notification(s) created, ${r.reminders_fired} reminder(s), ${r.rules_matched}/${r.rules_evaluated} rules matched.`); invalidate(); },
  });

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Automation</h1>
          <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">Triggers, rules, reminders and your activity center.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {tab === "rules" && <Button size="sm" variant="secondary" onClick={() => setModal("rule")} leftIcon={<Plus className="h-4 w-4" />}>Rule</Button>}
          {tab === "reminders" && <Button size="sm" variant="secondary" onClick={() => setModal("reminder")} leftIcon={<Plus className="h-4 w-4" />}>Reminder</Button>}
          <Button size="sm" loading={run.isPending} onClick={() => run.mutate()} leftIcon={<Play className="h-4 w-4" />}>Run engine</Button>
        </div>
      </header>

      {banner && (
        <div className="flex items-start justify-between gap-3 rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800 dark:border-brand-600/30 dark:bg-brand-600/10 dark:text-brand-200">
          <span className="flex items-center gap-2"><Zap className="h-4 w-4" /> {banner}</span>
          <button onClick={() => setBanner(null)} aria-label="Dismiss"><X className="h-4 w-4" /></button>
        </div>
      )}

      <div className="flex gap-1 border-b border-gray-200 dark:border-white/10">
        {(["activity", "rules", "reminders"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium capitalize transition-colors ${tab === t ? "border-brand-500 text-brand-600 dark:text-brand-300" : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "activity" && farmId && <ActivityTab farmId={farmId} />}
      {tab === "rules" && farmId && <RulesTab farmId={farmId} onAdd={() => setModal("rule")} />}
      {tab === "reminders" && farmId && <RemindersTab farmId={farmId} onAdd={() => setModal("reminder")} />}

      {modal === "rule" && farmId && <RuleModal farmId={farmId} onClose={() => setModal(null)} onSaved={() => { setModal(null); invalidate(); }} />}
      {modal === "reminder" && farmId && <ReminderModal farmId={farmId} onClose={() => setModal(null)} onSaved={() => { setModal(null); invalidate(); }} />}
    </div>
  );
}

// ── Activity ──────────────────────────────────────────────────────────────────

function ActivityTab({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const [priority, setPriority] = useState("");

  const query = useQuery({
    queryKey: [...queryKeys.autoActivity(farmId), status, q, priority],
    queryFn: () => listActivity(farmId, { status, q: q || undefined, priority: priority || undefined }),
    enabled: !!farmId,
  });
  const rows = query.data ?? [];
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.autoActivity(farmId) });
  const read = useMutation({ mutationFn: (id: string) => notificationsAPI.markRead(farmId, id), onSuccess: invalidate });
  const archive = useMutation({ mutationFn: (r: { id: string; archived: boolean }) => archiveNotification(farmId, r.id, r.archived), onSuccess: invalidate });

  const input = "rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-[180px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notifications…" className={`${input} w-full pl-9`} />
        </div>
        <Select label="" options={[{ value: "all", label: "All" }, { value: "unread", label: "Unread" }, { value: "read", label: "Read" }, { value: "archived", label: "Archived" }]} value={status} onChange={(e) => setStatus(e.target.value)} />
        <Select label="" options={[{ value: "", label: "Any priority" }, ...PRIORITIES]} value={priority} onChange={(e) => setPriority(e.target.value)} />
      </div>
      {query.isLoading ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div> : rows.length === 0 ? (
        <EmptyState icon={<Bell className="h-6 w-6" />} title="Nothing here" description="Run the engine to evaluate triggers, or adjust your filters." />
      ) : (
        <ul className="space-y-2">
          {rows.map((n) => (
            <li key={n.id} className={`flex items-start justify-between gap-3 rounded-2xl border px-4 py-3 ${n.is_read ? "border-gray-200 dark:border-white/10" : "border-brand-200 bg-brand-50/40 dark:border-brand-600/30 dark:bg-brand-600/5"}`}>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-gray-900 dark:text-white">{n.title}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIO_CLS[n.priority] ?? PRIO_CLS.normal}`}>{cap(n.priority)}</span>
                  {!n.is_read && <span className="h-2 w-2 rounded-full bg-brand-500" />}
                </div>
                <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">{n.body}</p>
                <p className="mt-0.5 text-xs text-gray-400">{fmtDT(n.created_at)}{n.source ? ` · ${n.source}` : ""}</p>
              </div>
              <div className="flex shrink-0 gap-1">
                {!n.is_read && <button onClick={() => read.mutate(n.id)} aria-label="Mark read" className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-brand-600 dark:hover:bg-white/10"><Check className="h-4 w-4" /></button>}
                <button onClick={() => archive.mutate({ id: n.id, archived: !n.is_archived })} aria-label="Archive" className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10"><Archive className="h-4 w-4" /></button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Rules ─────────────────────────────────────────────────────────────────────

function RulesTab({ farmId, onAdd }: { farmId: string; onAdd: () => void }) {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.autoRules(farmId), queryFn: () => listRules(farmId), enabled: !!farmId });
  const rows = query.data ?? [];
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.autoRules(farmId) });
  const toggle = useMutation({ mutationFn: (r: AutomationRule) => updateRule(farmId, r.id, { is_active: !r.is_active }), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: string) => deleteRule(farmId, id), onSuccess: invalidate });

  if (query.isLoading) return <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>;
  if (rows.length === 0) return <EmptyState icon={<Zap className="h-6 w-6" />} title="No automation rules" description="Create if/then rules that notify you or create reminders when triggers fire." action={<Button onClick={onAdd} leftIcon={<Plus className="h-4 w-4" />}>New rule</Button>} />;
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.id} className="flex items-start justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-gray-900 dark:text-white">{r.name}</span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIO_CLS[r.priority] ?? PRIO_CLS.normal}`}>{cap(r.priority)}</span>
              {!r.is_active && <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500 dark:bg-white/10 dark:text-gray-300">Paused</span>}
            </div>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">If <span className="font-medium">{cap(r.trigger_type)}</span> → {r.actions.length} action(s) · run {r.run_count}×</p>
          </div>
          <div className="flex shrink-0 gap-1">
            <button onClick={() => toggle.mutate(r)} className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10">{r.is_active ? "Pause" : "Enable"}</button>
            <button onClick={() => remove.mutate(r.id)} aria-label="Delete" className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"><Trash2 className="h-4 w-4" /></button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function RuleModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: "", trigger_type: "low_feed", priority: "high", message: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => createRule(farmId, {
      name: f.name.trim(), trigger_type: f.trigger_type, priority: f.priority,
      conditions: { min_count: 1 },
      actions: [{ type: "notify", priority: f.priority, message: f.message || `${f.name} triggered.` }],
    }),
    onSuccess: onSaved,
    onError: (e: any) => setError(e?.response?.data?.error?.message ?? "Couldn't create the rule."),
  });
  return (
    <ModalShell title="New automation rule" onClose={onClose}>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">{error}</div>}
      <div className="space-y-4">
        <TextField label="Rule name" placeholder="e.g. Alert on low feed" value={f.name} onChange={(e) => set({ name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="When (trigger)" options={TRIGGERS} value={f.trigger_type} onChange={(e) => set({ trigger_type: e.target.value })} />
          <Select label="Priority" options={PRIORITIES} value={f.priority} onChange={(e) => set({ priority: e.target.value })} />
        </div>
        <TextField label="Then notify with message" placeholder="Feed is running low!" value={f.message} onChange={(e) => set({ message: e.target.value })} />
        <p className="text-xs text-gray-400">The rule fires an in-app notification when the trigger condition is met during an engine run.</p>
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={f.name.trim().length < 2} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Create rule</Button>
      </div>
    </ModalShell>
  );
}

// ── Reminders ─────────────────────────────────────────────────────────────────

function RemindersTab({ farmId, onAdd }: { farmId: string; onAdd: () => void }) {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.autoReminders(farmId), queryFn: () => listReminders(farmId, true), enabled: !!farmId });
  const rows = query.data ?? [];
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.autoReminders(farmId) });
  const complete = useMutation({ mutationFn: (r: Reminder) => updateReminder(farmId, r.id, { is_done: !r.is_done }), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: string) => deleteReminder(farmId, id), onSuccess: invalidate });

  if (query.isLoading) return <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div>;
  if (rows.length === 0) return <EmptyState icon={<CalendarClock className="h-6 w-6" />} title="No reminders" description="Set one-time or recurring reminders — they fire in-app when due." action={<Button onClick={onAdd} leftIcon={<Plus className="h-4 w-4" />}>New reminder</Button>} />;
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.id} className="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
          <div className="flex min-w-0 items-center gap-3">
            <button onClick={() => complete.mutate(r)} aria-label="Toggle done" className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border ${r.is_done ? "border-brand-500 bg-brand-500 text-white" : "border-gray-300 dark:border-white/20"}`}>{r.is_done && <Check className="h-4 w-4" />}</button>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`font-medium ${r.is_done ? "text-gray-400 line-through" : "text-gray-900 dark:text-white"}`}>{r.title}</span>
                {r.recurrence !== "none" && <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">{cap(r.recurrence)}</span>}
                {r.is_overdue && <span className="rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700 dark:bg-red-500/15 dark:text-red-300">Overdue</span>}
              </div>
              <p className="text-xs text-gray-400 flex items-center gap-1"><Clock className="h-3 w-3" /> {fmtDT(r.due_at)}{r.notes ? ` · ${r.notes}` : ""}</p>
            </div>
          </div>
          <button onClick={() => remove.mutate(r.id)} aria-label="Delete" className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"><Trash2 className="h-4 w-4" /></button>
        </li>
      ))}
    </ul>
  );
}

function ReminderModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const now = new Date(Date.now() + 3600_000).toISOString().slice(0, 16);
  const [f, setF] = useState({ title: "", due_at: now, recurrence: "none", priority: "normal", notes: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => createReminder(farmId, {
      title: f.title.trim(), due_at: new Date(f.due_at).toISOString(),
      recurrence: f.recurrence, priority: f.priority, notes: f.notes || undefined,
    }),
    onSuccess: onSaved,
    onError: (e: any) => setError(e?.response?.data?.error?.message ?? "Couldn't create the reminder."),
  });
  return (
    <ModalShell title="New reminder" onClose={onClose}>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">{error}</div>}
      <div className="space-y-4">
        <TextField label="Title" placeholder="e.g. Order feed" value={f.title} onChange={(e) => set({ title: e.target.value })} />
        <TextField label="Due" type="datetime-local" value={f.due_at} onChange={(e) => set({ due_at: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Recurrence" options={RECURRENCE} value={f.recurrence} onChange={(e) => set({ recurrence: e.target.value })} />
          <Select label="Priority" options={PRIORITIES} value={f.priority} onChange={(e) => set({ priority: e.target.value })} />
        </div>
        <TextField label="Notes (optional)" value={f.notes} onChange={(e) => set({ notes: e.target.value })} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={f.title.trim().length < 2} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Create reminder</Button>
      </div>
    </ModalShell>
  );
}
