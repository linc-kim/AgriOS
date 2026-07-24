/**
 * ARIA supervisor dashboard (Module 13 Part 5).
 *
 * What ARIA sees when nobody is asking: the farm's overall state, eight
 * monitors each explaining themselves, alerts for thresholds actually crossed,
 * a ranked priority list, and the recorded activity behind it all.
 *
 * Two presentation decisions carry the honesty rules into the UI. A monitor
 * that is normal only because nothing was recorded is drawn in a distinct muted
 * style and labelled "not measured" — never with the confident green of a
 * genuine all-clear. And anything the reports cannot compute is printed as
 * "Not enough recorded data." rather than left blank, so a farmer can see the
 * gap and go close it.
 *
 * The page never calls the supervisor with `sync`, so loading it has no side
 * effects; writing notifications and reminders is the scheduled pass's job.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bird,
  CheckCircle2,
  ClipboardList,
  CircleHelp,
  Droplets,
  Egg,
  History,
  Package,
  ShieldCheck,
  Syringe,
  Wheat,
  type LucideIcon,
} from "lucide-react";

import {
  getReport,
  getSupervisor,
  getTimeline,
  type AriaMonitor,
  type MonitorState,
} from "@/api/ariaSupervisor";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Skeleton } from "@/components/ui/Skeleton";
import { AriaAvatar } from "@/components/aria";
import { cn } from "@/lib/cn";

/* ── State styling ───────────────────────────────────────────────────────── */

const STATE_STYLE: Record<MonitorState, { label: string; chip: string; dot: string; ring: string }> = {
  normal: {
    label: "Normal",
    chip: "bg-brand-50 text-brand-700 dark:bg-brand-500/12 dark:text-brand-300",
    dot: "bg-brand-500",
    ring: "ring-brand-500/20",
  },
  watch: {
    label: "Watch",
    chip: "bg-sky-50 text-sky-700 dark:bg-sky-500/12 dark:text-sky-300",
    dot: "bg-sky-500",
    ring: "ring-sky-500/20",
  },
  warning: {
    label: "Warning",
    chip: "bg-amber-50 text-amber-700 dark:bg-amber-500/12 dark:text-amber-300",
    dot: "bg-amber-500",
    ring: "ring-amber-500/20",
  },
  critical: {
    label: "Critical",
    chip: "bg-red-50 text-red-700 dark:bg-red-500/12 dark:text-red-300",
    dot: "bg-red-500",
    ring: "ring-red-500/20",
  },
};

/** Unmeasured is deliberately grey, never the green of a real all-clear. */
const UNMEASURED_STYLE = {
  label: "Not measured",
  chip: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400",
  dot: "bg-gray-300 dark:bg-white/25",
  ring: "ring-gray-400/15",
};

const MONITOR_ICON: Record<string, LucideIcon> = {
  mortality: Bird,
  feed: Wheat,
  water: Droplets,
  production: Egg,
  vaccinations: Syringe,
  population: Activity,
  inventory: Package,
  biosecurity: ShieldCheck,
};

const KIND_ICON: Record<string, LucideIcon> = {
  vaccination: Syringe,
  production: Egg,
  feed: Wheat,
  mortality: Bird,
  reminder: ClipboardList,
  weighin: Activity,
};

export default function AriaSupervisorScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [period, setPeriod] = useState<"today" | "7d" | "30d">("7d");

  const supervisor = useQuery({
    queryKey: [...queryKeys.flocks(farmId ?? ""), "aria-supervisor"],
    queryFn: () => getSupervisor(farmId as string),
    enabled: !!farmId,
    staleTime: 60_000,
  });
  const timeline = useQuery({
    queryKey: [...queryKeys.flocks(farmId ?? ""), "aria-timeline"],
    queryFn: () => getTimeline(farmId as string, { limit: 15 }),
    enabled: !!farmId,
    staleTime: 60_000,
  });
  const report = useQuery({
    queryKey: [...queryKeys.flocks(farmId ?? ""), "aria-report", period],
    queryFn: () => getReport(farmId as string, period),
    enabled: !!farmId,
    staleTime: 60_000,
  });

  if (!farmId) {
    return (
      <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">
        Select a farm to see ARIA's supervision.
      </p>
    );
  }

  const d = supervisor.data;
  const overall = d ? STATE_STYLE[d.overall] : STATE_STYLE.normal;

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center gap-3">
        <AriaAvatar size={44} state="idle" animated />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
            Supervisor
          </h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">
            ARIA watching your farm — deterministic, from your records only.
          </p>
        </div>
        {d && (
          <span className={cn("rounded-full px-3 py-1 text-sm font-semibold", overall.chip)}>
            Farm is {overall.label.toLowerCase()}
          </span>
        )}
      </header>

      {supervisor.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      ) : supervisor.isError || !d ? (
        <p className="rounded-2xl border border-gray-200 p-6 text-sm text-gray-500 dark:border-white/10 dark:text-gray-400">
          ARIA couldn't complete a supervision pass — your records are briefly unavailable.
        </p>
      ) : (
        <>
          {/* Briefing */}
          <section className="overflow-hidden rounded-2xl border border-brand-200/70 bg-brand-50/50 dark:border-brand-500/25 dark:bg-brand-500/[0.07]">
            <div className="p-4">
              <p className="text-sm font-semibold text-brand-900 dark:text-brand-50">
                {d.briefing.greeting}
              </p>
              <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
                {d.briefing.sections.map((s) => (
                  <div key={s.label} className="flex gap-2 text-sm">
                    <dt className="shrink-0 font-medium text-brand-800/70 dark:text-brand-100/70">
                      {s.label}:
                    </dt>
                    <dd
                      className={cn(
                        s.available
                          ? "text-brand-900 dark:text-brand-50"
                          : "italic text-brand-800/50 dark:text-brand-100/40",
                      )}
                    >
                      {s.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
            {d.briefing.notes.length > 0 && (
              <div className="border-t border-brand-200/60 bg-white/40 px-4 py-2 dark:border-brand-500/20 dark:bg-white/[0.02]">
                {d.briefing.notes.map((n) => (
                  <p key={n} className="flex gap-1.5 text-[11px] text-brand-800/70 dark:text-brand-100/60">
                    <CircleHelp className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                    {n}
                  </p>
                ))}
              </div>
            )}
          </section>

          <div className="grid gap-6 lg:grid-cols-3">
            {/* Monitors */}
            <section className="lg:col-span-2">
              <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">
                Farm watch
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {d.monitors.map((m) => (
                  <MonitorCard key={m.key} monitor={m} />
                ))}
              </div>
            </section>

            {/* Priorities + alerts */}
            <div className="space-y-6">
              <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
                <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">
                  Priorities
                </h2>
                {d.priorities.length === 0 ? (
                  <p className="text-sm text-gray-400">Nothing needs attention right now.</p>
                ) : (
                  <ol className="space-y-2.5">
                    {d.priorities.map((p) => (
                      <li key={p.key} className="flex gap-2.5">
                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[11px] font-semibold text-gray-600 dark:bg-white/10 dark:text-gray-300">
                          {p.rank}
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-medium text-gray-900 dark:text-white">
                            {p.label}
                          </span>
                          <span className="block text-[11px] leading-snug text-gray-500 dark:text-gray-400">
                            {p.why}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </section>

              <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                  <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
                  Alerts
                  {d.alerts.length > 0 && (
                    <span className="ml-auto rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/12 dark:text-amber-300">
                      {d.alerts.length}
                    </span>
                  )}
                </h2>
                {d.alerts.length === 0 ? (
                  <p className="flex items-center gap-1.5 text-sm text-gray-400">
                    <CheckCircle2 className="h-4 w-4 text-brand-500" aria-hidden />
                    No thresholds crossed.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {d.alerts.map((a) => {
                      const s = STATE_STYLE[a.severity];
                      return (
                        <li key={a.key} className="border-l-2 pl-3" style={{ borderColor: "currentColor" }}>
                          <span className={cn("inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold", s.chip)}>
                            {s.label}
                          </span>
                          <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">{a.title}</p>
                          <p className="text-[11px] leading-snug text-gray-500 dark:text-gray-400">{a.reason}</p>
                          <p className="mt-1 flex gap-1 text-[11px] text-brand-700 dark:text-brand-300">
                            <ArrowRight className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                            {a.action}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>
            </div>
          </div>

          {/* Reports + timeline */}
          <div className="grid gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
              <div className="mb-3 flex items-center gap-2">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Report</h2>
                <div className="ml-auto flex gap-1" role="tablist" aria-label="Report period">
                  {(["today", "7d", "30d"] as const).map((p) => (
                    <button
                      key={p}
                      role="tab"
                      aria-selected={period === p}
                      onClick={() => setPeriod(p)}
                      className={cn(
                        "rounded-lg px-2.5 py-1 text-xs font-medium transition-colors",
                        period === p
                          ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                          : "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/[0.06]",
                      )}
                    >
                      {p === "today" ? "Today" : p === "7d" ? "7 days" : "30 days"}
                    </button>
                  ))}
                </div>
              </div>
              {report.isLoading ? (
                <Skeleton className="h-32 rounded-xl" />
              ) : report.data ? (
                <>
                  <dl className="space-y-1.5">
                    {report.data.sections.map((s) => (
                      <div key={s.label} className="flex justify-between gap-3 text-sm">
                        <dt className="text-gray-500 dark:text-gray-400">{s.label}</dt>
                        <dd
                          className={cn(
                            "text-right",
                            s.available
                              ? "font-medium text-gray-900 dark:text-white"
                              : "italic text-gray-400 dark:text-gray-500",
                          )}
                        >
                          {s.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {report.data.notes.map((n) => (
                    <p key={n} className="mt-3 text-[11px] leading-relaxed text-gray-400 dark:text-gray-500">
                      {n}
                    </p>
                  ))}
                </>
              ) : null}
            </section>

            <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <History className="h-4 w-4 text-gray-400" aria-hidden />
                Recent activity
              </h2>
              {timeline.isLoading ? (
                <Skeleton className="h-32 rounded-xl" />
              ) : !timeline.data?.length ? (
                <p className="text-sm text-gray-400">Nothing recorded in the last 30 days.</p>
              ) : (
                <ul className="space-y-2.5">
                  {timeline.data.map((e, i) => {
                    const Icon = KIND_ICON[e.kind] ?? Activity;
                    return (
                      <li key={`${e.at}-${e.kind}-${i}`} className="flex gap-2.5">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500 dark:bg-white/[0.06] dark:text-gray-400">
                          <Icon className="h-3 w-3" aria-hidden />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm text-gray-800 dark:text-gray-200">{e.title}</span>
                          <span className="block text-[11px] text-gray-400 dark:text-gray-500">
                            {new Date(e.at).toLocaleDateString()} {e.detail && `· ${e.detail}`}
                          </span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Monitor card ────────────────────────────────────────────────────────── */

function MonitorCard({ monitor }: { monitor: AriaMonitor }) {
  const [open, setOpen] = useState(false);
  // An unmeasured monitor must not wear the green of a genuine all-clear.
  const s = monitor.unmeasured ? UNMEASURED_STYLE : STATE_STYLE[monitor.state];
  const Icon = MONITOR_ICON[monitor.key] ?? Activity;

  return (
    <div
      className={cn(
        "rounded-xl border border-gray-200 bg-white p-3 ring-1 ring-inset dark:border-white/10 dark:bg-white/[0.03]",
        s.ring,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 text-left"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-50 text-gray-500 dark:bg-white/[0.06] dark:text-gray-400">
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-gray-900 dark:text-white">
            {monitor.label}
          </span>
        </span>
        <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold", s.chip)}>
          <span className={cn("h-1.5 w-1.5 rounded-full", s.dot)} aria-hidden />
          {s.label}
        </span>
      </button>

      <p className="mt-2 text-[11px] leading-snug text-gray-500 dark:text-gray-400">{monitor.why}</p>

      {monitor.evidence.length > 0 && (
        <>
          {open && (
            <ul className="mt-2 space-y-0.5 border-t border-gray-100 pt-2 dark:border-white/[0.06]">
              {monitor.evidence.map((e) => (
                <li key={e} className="text-[11px] text-gray-500 dark:text-gray-400">
                  · {e}
                </li>
              ))}
            </ul>
          )}
          {/* Padded to a real touch target — a bare 11px text link is under
              24px tall and awkward to hit on a phone. */}
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="-mx-1 mt-0.5 rounded px-1 py-1.5 text-[11px] font-medium text-brand-600 hover:underline dark:text-brand-400"
          >
            {open ? "Hide evidence" : "Show evidence"}
          </button>
        </>
      )}
    </div>
  );
}
