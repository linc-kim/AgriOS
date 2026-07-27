/**
 * ARIA Operations Center (Module 13 Part 7).
 *
 * ARIA lifted from one farm to the whole organization: an aggregated summary,
 * a farm-by-farm roll-up, cross-farm comparison, assignable tasks, the merged
 * timeline, performance analytics and export-ready reports — all deterministic,
 * all from recorded data.
 *
 * The honesty rules from the single-farm surfaces carry through unchanged. An
 * aggregate that no farm could supply is drawn as "not enough recorded data",
 * never a fabricated total; a comparison always shows the farms that are missing
 * a metric rather than quietly dropping them; and the role tier the server
 * resolves decides which tabs render at all, so the UI never shows a section a
 * worker's role isn't allowed to load.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  Building2,
  CheckCircle2,
  ClipboardList,
  Droplets,
  Egg,
  FileText,
  GitCompareArrows,
  History,
  Layers,
  Users,
  Wheat,
  type LucideIcon,
} from "lucide-react";

import {
  assignTask,
  completeTask,
  getAnalytics,
  getComparison,
  getDashboard,
  getReport,
  getTimeline,
  type OpsAggregate,
  type OpsTask,
  type Severity,
} from "@/api/operations";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { AriaAvatar } from "@/components/aria";
import { cn } from "@/lib/cn";

/* ── Severity styling (shared vocabulary with the supervisor) ─────────────── */

const SEV_STYLE: Record<Severity, { label: string; chip: string; dot: string }> = {
  normal: { label: "Normal", chip: "bg-brand-50 text-brand-700 dark:bg-brand-500/12 dark:text-brand-300", dot: "bg-brand-500" },
  watch: { label: "Watch", chip: "bg-sky-50 text-sky-700 dark:bg-sky-500/12 dark:text-sky-300", dot: "bg-sky-500" },
  warning: { label: "Warning", chip: "bg-amber-50 text-amber-700 dark:bg-amber-500/12 dark:text-amber-300", dot: "bg-amber-500" },
  critical: { label: "Critical", chip: "bg-red-50 text-red-700 dark:bg-red-500/12 dark:text-red-300", dot: "bg-red-500" },
};

const STATUS_TITLE: Record<Severity, string> = {
  normal: "All farms operating normally",
  watch: "Stable — minor items to watch",
  warning: "Attention needed",
  critical: "Action required",
};

type Tab = "comparison" | "tasks" | "timeline" | "analytics" | "reports" | "team";

const TAB_META: Record<Tab, { label: string; icon: LucideIcon; section: string }> = {
  comparison: { label: "Compare farms", icon: GitCompareArrows, section: "comparison" },
  tasks: { label: "Tasks", icon: ClipboardList, section: "tasks" },
  timeline: { label: "Timeline", icon: History, section: "timeline" },
  analytics: { label: "Analytics", icon: BarChart3, section: "analytics" },
  reports: { label: "Reports", icon: FileText, section: "reports" },
  team: { label: "Team", icon: Users, section: "workers" },
};

export default function OperationsCenterScreen() {
  const { currentOrg } = useWorkspace();
  const orgId = currentOrg?.id;
  const [tab, setTab] = useState<Tab>("tasks");
  const [farmFilter, setFarmFilter] = useState<string>("");

  const dashboard = useQuery({
    queryKey: ["operations", orgId, "dashboard", farmFilter],
    queryFn: () => getDashboard(orgId as string, farmFilter ? { farm_id: farmFilter } : {}),
    enabled: !!orgId,
    staleTime: 60_000,
  });

  if (!orgId) {
    return (
      <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">
        Select an organization to open the Operations Center.
      </p>
    );
  }

  const d = dashboard.data;
  const sections = new Set(d?.sections ?? []);
  const overall = d?.organization.overall ?? "normal";
  const visibleTabs = (Object.keys(TAB_META) as Tab[]).filter((t) => sections.has(TAB_META[t].section));
  const activeTab = visibleTabs.includes(tab) ? tab : visibleTabs[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center gap-3">
        <AriaAvatar size={44} state="idle" animated />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
            Operations Center
          </h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">
            ARIA supervising {currentOrg?.name ?? "your organization"} — every figure from recorded data.
          </p>
        </div>
        {d && (
          <span className={cn("rounded-full px-3 py-1 text-sm font-semibold", SEV_STYLE[overall].chip)}>
            {STATUS_TITLE[overall]}
          </span>
        )}
      </header>

      {dashboard.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-24 rounded-2xl" />
          <Skeleton className="h-40 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      ) : dashboard.isError || !d ? (
        <p className="rounded-2xl border border-gray-200 p-6 text-sm text-gray-500 dark:border-white/10 dark:text-gray-400">
          {(dashboard.error as { response?: { status?: number } })?.response?.status === 403
            ? "Your role doesn't have access to this organization's operations."
            : "ARIA couldn't assemble the organization view — records are briefly unavailable."}
        </p>
      ) : (
        <>
          {/* Operational status banner */}
          <section
            className={cn(
              "rounded-2xl border p-4",
              overall === "critical"
                ? "border-red-200 bg-red-50/60 dark:border-red-500/25 dark:bg-red-500/[0.07]"
                : overall === "warning"
                  ? "border-amber-200 bg-amber-50/60 dark:border-amber-500/25 dark:bg-amber-500/[0.07]"
                  : "border-brand-200/70 bg-brand-50/50 dark:border-brand-500/25 dark:bg-brand-500/[0.07]",
            )}
          >
            <p className="text-sm font-semibold text-gray-900 dark:text-white">{d.operational_status}</p>
            {d.priorities.length > 0 && (
              <ol className="mt-2 space-y-1">
                {d.priorities.slice(0, 3).map((p) => (
                  <li key={`${p.farm_id}-${p.source}`} className="flex gap-2 text-[13px] text-gray-600 dark:text-gray-300">
                    <span className={cn("mt-1 h-1.5 w-1.5 shrink-0 rounded-full", SEV_STYLE[p.severity].dot)} aria-hidden />
                    <span>
                      <span className="font-medium text-gray-800 dark:text-gray-100">{p.farm_name}</span> — {p.why}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>

          {/* Organization summary aggregates */}
          {sections.has("organization") && (
            <section>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <Building2 className="h-4 w-4 text-gray-400" aria-hidden />
                Organization — {d.organization.farm_count} farm{d.organization.farm_count === 1 ? "" : "s"}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <AggregateCard agg={d.organization.health} icon={Layers} />
                <AggregateCard agg={d.organization.production} icon={Egg} />
                <AggregateCard agg={d.organization.mortality} icon={AlertTriangle} />
                <AggregateCard agg={d.organization.feed_usage} icon={Wheat} />
                <AggregateCard agg={d.organization.water_usage} icon={Droplets} />
                <AggregateCard agg={d.organization.inventory} icon={ClipboardList} />
                <AggregateCard agg={d.organization.financial} icon={BarChart3} />
              </div>
              {d.organization.silent_farms.length > 0 && (
                <p className="mt-2 text-[11px] text-gray-400 dark:text-gray-500">
                  No records at all for: {d.organization.silent_farms.join(", ")} — excluded from every total above.
                </p>
              )}
            </section>
          )}

          {/* Farm summaries */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Farms</h2>
              {d.farms.length > 1 && (
                <select
                  value={farmFilter}
                  onChange={(e) => setFarmFilter(e.target.value)}
                  aria-label="Filter by farm"
                  className="ml-auto rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 dark:border-white/10 dark:bg-white/[0.04] dark:text-gray-200"
                >
                  <option value="">All farms</option>
                  {(d.organization.farm_names ?? []).map((n, i) => (
                    <option key={n} value={d.farms[i]?.farm_id ?? ""}>{n}</option>
                  ))}
                </select>
              )}
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {d.farms.map((f) => (
                <div
                  key={f.farm_id}
                  className="rounded-xl border border-gray-200 bg-white p-3.5 dark:border-white/10 dark:bg-white/[0.03]"
                >
                  <div className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-900 dark:text-white">
                      {f.farm_name}
                    </span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", SEV_STYLE[f.overall].chip)}>
                      {SEV_STYLE[f.overall].label}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-gray-500 dark:text-gray-400">
                    <span>Health <b className="text-gray-800 dark:text-gray-100">{f.health_score}/100</b></span>
                    <span>Open <b className="text-gray-800 dark:text-gray-100">{f.open_tasks}</b></span>
                    {f.overdue_tasks > 0 && <span className="text-amber-600 dark:text-amber-400">{f.overdue_tasks} overdue</span>}
                    {f.alert_count > 0 && <span className="text-red-600 dark:text-red-400">{f.alert_count} alert{f.alert_count === 1 ? "" : "s"}</span>}
                    {f.silent && <span className="italic text-gray-400">no records</span>}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Tabs */}
          {visibleTabs.length > 0 && (
            <section className="rounded-2xl border border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.02]">
              <div className="flex flex-wrap gap-1 border-b border-gray-100 p-2 dark:border-white/[0.06]" role="tablist" aria-label="Operations sections">
                {visibleTabs.map((t) => {
                  const Icon = TAB_META[t].icon;
                  return (
                    <button
                      key={t}
                      role="tab"
                      aria-selected={activeTab === t}
                      onClick={() => setTab(t)}
                      className={cn(
                        "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                        activeTab === t
                          ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                          : "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/[0.06]",
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden />
                      {TAB_META[t].label}
                    </button>
                  );
                })}
              </div>
              <div className="p-4">
                {activeTab === "comparison" && <ComparisonTab orgId={orgId} />}
                {activeTab === "tasks" && <TasksTab orgId={orgId} tasks={d.tasks} workers={d.workers} canAssign={sections.has("workers")} />}
                {activeTab === "timeline" && <TimelineTab orgId={orgId} />}
                {activeTab === "analytics" && <AnalyticsTab orgId={orgId} />}
                {activeTab === "reports" && <ReportsTab orgId={orgId} />}
                {activeTab === "team" && <TeamTab workers={d.workers} />}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

/* ── Aggregate card ──────────────────────────────────────────────────────── */

function AggregateCard({ agg, icon: Icon }: { agg: OpsAggregate; icon: LucideIcon }) {
  return (
    <div className="group rounded-xl border border-gray-200 bg-white p-3 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center gap-2 text-gray-400">
        <Icon className="h-4 w-4" aria-hidden />
        <span className="text-[11px] font-medium uppercase tracking-wide">{agg.label}</span>
      </div>
      <p
        className={cn(
          "mt-1.5 text-xl font-semibold tabular-nums",
          agg.available ? "text-gray-900 dark:text-white" : "text-gray-400 dark:text-gray-500",
        )}
      >
        {agg.available ? `${agg.value}${agg.unit ? ` ${agg.unit}` : ""}` : "—"}
      </p>
      <p className="mt-1 text-[10px] leading-snug text-gray-400 dark:text-gray-500" title={agg.method}>
        {agg.available
          ? `${agg.source_farms.length} farm${agg.source_farms.length === 1 ? "" : "s"}${agg.missing_farms.length ? ` · ${agg.missing_farms.length} missing` : ""}`
          : "Not enough recorded data."}
      </p>
    </div>
  );
}

/* ── Comparison tab ──────────────────────────────────────────────────────── */

function ComparisonTab({ orgId }: { orgId: string }) {
  const q = useQuery({
    queryKey: ["operations", orgId, "comparison"],
    queryFn: () => getComparison(orgId),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-48 rounded-xl" />;
  if (!q.data) return <Empty>No comparison available.</Empty>;

  return (
    <div className="space-y-5">
      {q.data.rankings.map((r) => (
        <div key={r.key}>
          <div className="flex items-baseline gap-2">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{r.label}</h3>
            {r.average && <span className="text-[11px] text-gray-400">avg {r.average} {r.unit}</span>}
            <span className="ml-auto text-[10px] text-gray-400">{r.higher_is_better ? "higher is better" : "lower is better"}</span>
          </div>
          <ol className="mt-2 space-y-1">
            {r.ranked.map((farm, i) => (
              <li key={farm.farm_id} className="flex items-center gap-2 text-sm">
                <span className="w-5 text-right text-[11px] font-semibold text-gray-400">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate text-gray-800 dark:text-gray-200">
                  {farm.farm_name}
                  {i === 0 && <span className="ml-1.5 rounded bg-brand-50 px-1.5 py-0.5 text-[9px] font-semibold text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">BEST</span>}
                  {i === r.ranked.length - 1 && r.ranked.length > 1 && (
                    <span className="ml-1.5 rounded bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">NEEDS ATTENTION</span>
                  )}
                </span>
                <span className="tabular-nums text-gray-500 dark:text-gray-400">{farm.display}</span>
              </li>
            ))}
            {r.missing.map((farm) => (
              <li key={farm.farm_id} className="flex items-center gap-2 text-sm text-gray-400">
                <span className="w-5" aria-hidden />
                <span className="min-w-0 flex-1 truncate italic">{farm.farm_name}</span>
                <span className="text-[11px] italic">no data</span>
              </li>
            ))}
          </ol>
          <p className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">{r.method}</p>
        </div>
      ))}
    </div>
  );
}

/* ── Tasks tab ───────────────────────────────────────────────────────────── */

function TasksTab({
  orgId,
  tasks,
  workers,
  canAssign,
}: {
  orgId: string;
  tasks: OpsTask[];
  workers: { user_id: string; name: string; farm_ids: string[] }[];
  canAssign: boolean;
}) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["operations", orgId] });

  const complete = useMutation({
    mutationFn: (taskId: string) => completeTask(orgId, taskId),
    onSuccess: invalidate,
  });
  const assign = useMutation({
    mutationFn: ({ taskId, ownerId }: { taskId: string; ownerId: string }) => assignTask(orgId, taskId, ownerId),
    onSuccess: invalidate,
  });

  if (tasks.length === 0) return <Empty>No tasks in scope.</Empty>;

  return (
    <ul className="divide-y divide-gray-100 dark:divide-white/[0.06]">
      {tasks.map((t) => {
        const farmWorkers = workers.filter((w) => w.farm_ids.includes(t.farm_id));
        return (
          <li key={t.task_id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5">
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                t.status === "done"
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-500/12 dark:text-brand-300"
                  : t.status === "overdue"
                    ? "bg-red-50 text-red-700 dark:bg-red-500/12 dark:text-red-300"
                    : "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-300",
              )}
            >
              {t.status}
            </span>
            <span className="min-w-0 flex-1">
              <span className={cn("block text-sm", t.status === "done" ? "text-gray-400 line-through" : "text-gray-900 dark:text-white")}>
                {t.title}
              </span>
              <span className="block text-[11px] text-gray-400">
                {t.farm_name}
                {t.owner_name ? ` · ${t.owner_name}` : " · unassigned"}
                {t.due_at && ` · due ${new Date(t.due_at).toLocaleDateString()}`}
              </span>
            </span>
            {canAssign && t.status !== "done" && (
              <select
                aria-label={`Assign ${t.title}`}
                value=""
                onChange={(e) => e.target.value && assign.mutate({ taskId: t.task_id, ownerId: e.target.value })}
                className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-gray-300"
              >
                <option value="">Assign…</option>
                {farmWorkers.map((w) => (
                  <option key={w.user_id} value={w.user_id}>{w.name}</option>
                ))}
              </select>
            )}
            {t.status !== "done" && (
              <button
                type="button"
                onClick={() => complete.mutate(t.task_id)}
                disabled={complete.isPending}
                className="rounded-lg border border-brand-200 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50 dark:border-brand-500/30 dark:text-brand-300 dark:hover:bg-brand-500/10"
              >
                Complete
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/* ── Timeline tab ────────────────────────────────────────────────────────── */

function TimelineTab({ orgId }: { orgId: string }) {
  const q = useQuery({
    queryKey: ["operations", orgId, "timeline"],
    queryFn: () => getTimeline(orgId, { limit: 40 }),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-48 rounded-xl" />;
  if (!q.data?.length) return <Empty>Nothing recorded recently.</Empty>;

  return (
    <ul className="space-y-2.5">
      {q.data.map((e, i) => (
        <li key={`${e.at}-${i}`} className="flex gap-2.5">
          <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", SEV_STYLE[e.severity].dot)} aria-hidden />
          <span className="min-w-0 flex-1">
            <span className="block text-sm text-gray-800 dark:text-gray-200">{e.title}</span>
            <span className="block text-[11px] text-gray-400">
              {new Date(e.at).toLocaleDateString()} · {e.farm_name}
              {e.worker && ` · ${e.worker}`}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ── Analytics tab ───────────────────────────────────────────────────────── */

function AnalyticsTab({ orgId }: { orgId: string }) {
  const q = useQuery({
    queryKey: ["operations", orgId, "analytics"],
    queryFn: () => getAnalytics(orgId),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-48 rounded-xl" />;
  if (!q.data) return <Empty>No analytics available.</Empty>;
  const a = q.data;

  return (
    <div className="space-y-5">
      {a.workers.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">Worker completion</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
                  <th className="py-1 font-medium">Worker</th>
                  <th className="py-1 text-right font-medium">Assigned</th>
                  <th className="py-1 text-right font-medium">Completed</th>
                  <th className="py-1 text-right font-medium">Rate</th>
                  <th className="py-1 text-right font-medium">Avg hrs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-white/[0.06]">
                {a.workers.map((w) => (
                  <tr key={w.user_id}>
                    <td className="py-1.5 text-gray-800 dark:text-gray-200">{w.name}</td>
                    <td className="py-1.5 text-right tabular-nums text-gray-500">{w.assigned}</td>
                    <td className="py-1.5 text-right tabular-nums text-gray-500">{w.completed}</td>
                    <td className="py-1.5 text-right tabular-nums font-medium text-gray-800 dark:text-gray-100">{w.completion_rate ?? "—"}</td>
                    <td className="py-1.5 text-right tabular-nums text-gray-500">{w.avg_completion_hours ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[...a.org_metrics, ...a.trends, ...a.farm_productivity].map((m) => (
          <div key={m.key} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-white/10 dark:bg-white/[0.03]">
            <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400">{m.label}</p>
            <p className={cn("mt-1 text-lg font-semibold tabular-nums", m.available ? "text-gray-900 dark:text-white" : "text-gray-400")}>
              {m.available ? `${m.value}${m.unit ? ` ${m.unit}` : ""}` : "—"}
            </p>
            <p className="mt-1 text-[10px] leading-snug text-gray-400 dark:text-gray-500">{m.method}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Reports tab ─────────────────────────────────────────────────────────── */

function ReportsTab({ orgId }: { orgId: string }) {
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("weekly");
  const q = useQuery({
    queryKey: ["operations", orgId, "report", period],
    queryFn: () => getReport(orgId, period),
    staleTime: 60_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex gap-1" role="tablist" aria-label="Report period">
        {(["daily", "weekly", "monthly"] as const).map((p) => (
          <button
            key={p}
            role="tab"
            aria-selected={period === p}
            onClick={() => setPeriod(p)}
            className={cn(
              "rounded-lg px-2.5 py-1 text-xs font-medium capitalize transition-colors",
              period === p
                ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                : "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/[0.06]",
            )}
          >
            {p}
          </button>
        ))}
      </div>

      {q.isLoading ? (
        <Skeleton className="h-48 rounded-xl" />
      ) : q.data ? (
        <>
          <dl className="space-y-1.5">
            {q.data.sections.map((s) => (
              <div key={s.label} className="flex justify-between gap-3 text-sm" title={s.method}>
                <dt className="text-gray-500 dark:text-gray-400">{s.label}</dt>
                <dd className={cn("text-right", s.available ? "font-medium text-gray-900 dark:text-white" : "italic text-gray-400")}>
                  {s.value}
                </dd>
              </div>
            ))}
          </dl>
          {q.data.risks.length > 0 && (
            <div>
              <h3 className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-gray-900 dark:text-white">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-hidden /> Outstanding risks
              </h3>
              <ul className="space-y-0.5">
                {q.data.risks.map((r, i) => (
                  <li key={i} className="text-[12px] text-gray-500 dark:text-gray-400">· {r}</li>
                ))}
              </ul>
            </div>
          )}
          {q.data.notes.map((n) => (
            <p key={n} className="text-[11px] leading-relaxed text-gray-400 dark:text-gray-500">{n}</p>
          ))}
        </>
      ) : (
        <Empty>No report available.</Empty>
      )}
    </div>
  );
}

/* ── Team tab ────────────────────────────────────────────────────────────── */

function TeamTab({ workers }: { workers: { user_id: string; name: string; role_label: string; farm_names: string[] }[] }) {
  if (workers.length === 0) return <Empty>No team members in scope.</Empty>;
  return (
    <ul className="divide-y divide-gray-100 dark:divide-white/[0.06]">
      {workers.map((w) => (
        <li key={w.user_id} className="flex items-center gap-3 py-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500 dark:bg-white/10 dark:text-gray-300">
            {w.name.slice(0, 2).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium text-gray-900 dark:text-white">{w.name}</span>
            <span className="block text-[11px] text-gray-400">{w.farm_names.join(", ")}</span>
          </span>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600 dark:bg-white/10 dark:text-gray-300">
            {w.role_label}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ── Shared ──────────────────────────────────────────────────────────────── */

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-center gap-1.5 py-6 text-sm text-gray-400">
      <CheckCircle2 className="h-4 w-4 text-brand-500" aria-hidden />
      {children}
    </p>
  );
}
