/**
 * Mission Control — the CEO dashboard (Module 14).
 *
 * "Build the farm you envision." A farmer sets a long-term mission and ARIA turns
 * it into a roadmap, a living business plan, a daily mission, progress and a CEO
 * advisor — all computed live from the deterministic engines, so nothing here is
 * ever stale.
 *
 * The honesty rules from the rest of ARIA are made visible: every figure is
 * tagged with how it is known — a recorded fact, a calculated forecast, a
 * strategic recommendation, or an AI suggestion — so a projection never masquerades
 * as a promise. Where a value can't be computed, it reads "not enough data".
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bird,
  Compass,
  FileText,
  Flag,
  Loader2,
  Map as MapIcon,
  MessageSquare,
  Send,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";

import {
  askAdvisor,
  createMission,
  getAvicultureBriefing,
  getDashboard,
  getManual,
  getPlan,
  getRoadmap,
  listMissions,
  type FactType,
  type Insight,
  type MValue,
} from "@/api/mission";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { AriaAvatar } from "@/components/aria";
import { cn } from "@/lib/cn";

const FACT_BADGE: Record<FactType, { label: string; cls: string }> = {
  recorded_fact: { label: "recorded", cls: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300" },
  calculated_forecast: { label: "forecast", cls: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" },
  strategic_recommendation: { label: "recommendation", cls: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300" },
  ai_suggestion: { label: "AI", cls: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" },
};

type Tab = "dashboard" | "roadmap" | "plan" | "manual" | "advisor" | "aviculture";

export default function MissionControlScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [tab, setTab] = useState<Tab>("dashboard");

  const missionsQ = useQuery({
    queryKey: ["missions", farmId],
    queryFn: () => listMissions(farmId as string),
    enabled: !!farmId,
  });

  const mission = missionsQ.data?.find((m) => m.is_primary) ?? missionsQ.data?.[0];

  if (!farmId) {
    return <p className="py-16 text-center text-sm text-gray-500">Select a farm to open Mission Control.</p>;
  }
  if (missionsQ.isLoading) {
    return <div className="space-y-4"><Skeleton className="h-40 rounded-2xl" /><Skeleton className="h-64 rounded-2xl" /></div>;
  }
  if (!mission) {
    return <CreateMission farmId={farmId} onCreated={() => missionsQ.refetch()} />;
  }

  const tabs: { key: Tab; label: string; icon: typeof Compass }[] = [
    { key: "dashboard", label: "Dashboard", icon: Target },
    { key: "roadmap", label: "Roadmap", icon: MapIcon },
    { key: "plan", label: "Business plan", icon: FileText },
    { key: "manual", label: "Manual", icon: Compass },
    { key: "advisor", label: "CEO advisor", icon: MessageSquare },
    { key: "aviculture", label: "Aviculture", icon: Bird },
  ];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <AriaAvatar size={44} state="idle" animated />
        <div className="min-w-0 flex-1">
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
            <Flag className="h-5 w-5 text-brand-500" aria-hidden /> {mission.name}
          </h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">
            {mission.description || "Your mission, guided day by day."}
            {mission.target_date && ` · target ${new Date(mission.target_date).toLocaleDateString()}`}
          </p>
        </div>
      </header>

      <div className="flex flex-wrap gap-1 border-b border-gray-100 pb-2 dark:border-white/[0.06]" role="tablist">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                tab === t.key
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                  : "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/[0.06]",
              )}
            >
              <Icon className="h-4 w-4" aria-hidden /> {t.label}
            </button>
          );
        })}
      </div>

      {tab === "dashboard" && <DashboardTab farmId={farmId} missionId={mission.id} />}
      {tab === "roadmap" && <RoadmapTab farmId={farmId} missionId={mission.id} />}
      {tab === "plan" && <PlanTab farmId={farmId} missionId={mission.id} />}
      {tab === "manual" && <ManualTab farmId={farmId} missionId={mission.id} />}
      {tab === "advisor" && <AdvisorTab farmId={farmId} missionId={mission.id} />}
      {tab === "aviculture" && <AvicultureTab farmId={farmId} />}

      <FactLegend />
    </div>
  );
}

/* ── Value rendering ─────────────────────────────────────────────────────── */

function ValueChip({ v }: { v: MValue }) {
  const badge = FACT_BADGE[v.fact_type];
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wide text-gray-400">{v.label}</span>
        <span className={cn("rounded-full px-1.5 py-0.5 text-[9px] font-semibold", badge.cls)}>{badge.label}</span>
      </div>
      <p className={cn("mt-1 text-lg font-semibold tabular-nums", v.available ? "text-gray-900 dark:text-white" : "italic text-gray-400")}>
        {v.available ? `${v.value}${v.unit ? ` ${v.unit}` : ""}` : "Not enough data"}
      </p>
      {v.detail && <p className="mt-0.5 text-[11px] leading-snug text-gray-400">{v.detail}</p>}
    </div>
  );
}

/* ── Dashboard ───────────────────────────────────────────────────────────── */

function DashboardTab({ farmId, missionId }: { farmId: string; missionId: string }) {
  const q = useQuery({
    queryKey: ["mission-dashboard", farmId, missionId],
    queryFn: () => getDashboard(farmId, missionId),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-96 rounded-2xl" />;
  if (!q.data) return <Empty>Dashboard unavailable.</Empty>;
  const d = q.data;

  return (
    <div className="space-y-5">
      {/* Completion + phase */}
      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-brand-200/70 bg-brand-50/50 p-4 dark:border-brand-500/25 dark:bg-brand-500/[0.07] lg:col-span-1">
          <p className="text-[11px] uppercase tracking-wide text-brand-700/70 dark:text-brand-200/70">Mission completion</p>
          <p className="mt-1 text-4xl font-bold tabular-nums text-brand-800 dark:text-brand-100">{d.completion_pct}%</p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/60 dark:bg-white/10">
            <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, d.completion_pct)}%` }} />
          </div>
          <p className="mt-2 text-[13px] font-medium text-brand-800 dark:text-brand-100">{d.current_phase}</p>
          {d.time_remaining_days != null && (
            <p className="text-[11px] text-brand-700/70 dark:text-brand-200/70">{d.time_remaining_days} days to target</p>
          )}
        </div>
        <div className="grid grid-cols-2 gap-3 lg:col-span-2">
          <ValueChip v={d.population} />
          <ValueChip v={d.operations_health} />
          <ValueChip v={d.profit} />
          <ValueChip v={d.cash_runway} />
        </div>
      </section>

      {/* Today's mission */}
      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <Sparkles className="h-4 w-4 text-brand-500" aria-hidden /> {d.daily.headline}
        </h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Today's critical tasks</h3>
            <ul className="space-y-1.5">
              {d.daily.critical_tasks.map((t, i) => (
                <li key={i} className="text-sm text-gray-800 dark:text-gray-200">
                  · {t.label}
                  {t.detail && <span className="block pl-3 text-[11px] text-gray-400">{t.detail}</span>}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Today's KPIs</h3>
            <div className="grid grid-cols-2 gap-2">
              {d.daily.kpis.map((k, i) => <ValueChip key={i} v={k} />)}
            </div>
          </div>
        </div>
      </section>

      {/* Milestones + risks + health */}
      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">Upcoming milestones</h3>
          {d.upcoming_milestones.length === 0 ? <p className="text-sm text-gray-400">All phases complete.</p> : (
            <ul className="space-y-2">
              {d.upcoming_milestones.map((m, i) => (
                <li key={i} className="text-sm">
                  <span className="font-medium text-gray-800 dark:text-gray-100">{m.name}</span>
                  <span className="block text-[11px] text-gray-400">{m.target}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">Current risks</h3>
          <ul className="space-y-2">
            {d.risks.map((r, i) => (
              <li key={i} className="text-sm text-gray-800 dark:text-gray-200">
                {r.label}
                {r.detail && <span className="block text-[11px] text-brand-600 dark:text-brand-400">→ {r.detail}</span>}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">Mission health</h3>
          <p className="text-3xl font-bold tabular-nums text-gray-900 dark:text-white">
            {d.health.score}<span className="text-base text-gray-400">/100</span>
            <span className="ml-2 text-sm font-medium capitalize text-gray-500">{d.health.grade}</span>
          </p>
          <ul className="mt-2 space-y-1">
            {d.health.factors.map((f, i) => (
              <li key={i} className="flex justify-between gap-2 text-[12px]" title={f.explanation}>
                <span className="text-gray-500 dark:text-gray-400">{f.label}</span>
                <span className="tabular-nums text-gray-700 dark:text-gray-200">{f.score}/{f.max_score}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

/* ── Roadmap ─────────────────────────────────────────────────────────────── */

function RoadmapTab({ farmId, missionId }: { farmId: string; missionId: string }) {
  const q = useQuery({
    queryKey: ["mission-roadmap", farmId, missionId],
    queryFn: () => getRoadmap(farmId, missionId),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-96 rounded-2xl" />;
  if (!q.data) return <Empty>No roadmap.</Empty>;
  const r = q.data;

  return (
    <div className="space-y-3">
      <p className="text-[12px] text-gray-400">{r.method}</p>
      <ol className="relative space-y-3 border-l-2 border-gray-200 pl-5 dark:border-white/10">
        {r.phases.map((p) => (
          <li key={p.index} className="relative">
            <span className="absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-white bg-brand-500 dark:border-gray-900" />
            <div className="rounded-xl border border-gray-200 bg-white p-3.5 dark:border-white/10 dark:bg-white/[0.03]">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-semibold text-gray-900 dark:text-white">{p.name}</span>
                {p.bird_target != null && <span className="text-[12px] text-gray-500">→ {p.bird_target.toLocaleString()} birds</span>}
                {p.start_date && <span className="ml-auto text-[11px] text-gray-400">{p.start_date} → {p.end_date}</span>}
              </div>
              {p.objectives.length > 0 && (
                <ul className="mt-1.5 space-y-0.5 text-[13px] text-gray-700 dark:text-gray-300">
                  {p.objectives.map((o, i) => <li key={i}>· {o}</li>)}
                </ul>
              )}
              {p.infrastructure.length > 0 && (
                <p className="mt-1.5 text-[11px] text-sky-700 dark:text-sky-300">🏗 {p.infrastructure.join("; ")}</p>
              )}
              {p.risks.length > 0 && (
                <p className="mt-1 text-[11px] text-amber-600 dark:text-amber-400">⚠ {p.risks[0]}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
      {r.notes.map((n) => <p key={n} className="text-[11px] text-gray-400">{n}</p>)}
    </div>
  );
}

/* ── Business plan ───────────────────────────────────────────────────────── */

function PlanTab({ farmId, missionId }: { farmId: string; missionId: string }) {
  const q = useQuery({
    queryKey: ["mission-plan", farmId, missionId],
    queryFn: () => getPlan(farmId, missionId),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-96 rounded-2xl" />;
  if (!q.data) return <Empty>No plan.</Empty>;
  return (
    <div className="space-y-4">
      {q.data.sections.map((s) => (
        <section key={s.heading} className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">{s.heading}</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {s.body.map((v, i) => <ValueChip key={i} v={v} />)}
          </div>
        </section>
      ))}
      {q.data.notes.map((n) => <p key={n} className="text-[11px] text-gray-400">{n}</p>)}
    </div>
  );
}

/* ── Manual ──────────────────────────────────────────────────────────────── */

function ManualTab({ farmId, missionId }: { farmId: string; missionId: string }) {
  const q = useQuery({
    queryKey: ["mission-manual", farmId, missionId],
    queryFn: () => getManual(farmId, missionId),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-96 rounded-2xl" />;
  if (!q.data) return <Empty>No manual.</Empty>;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {q.data.sections.map((s) => (
        <section key={s.heading} className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">{s.heading}</h3>
          <ul className="space-y-1 text-[13px] text-gray-700 dark:text-gray-300">
            {s.items.map((it, i) => <li key={i}>· {it}</li>)}
          </ul>
        </section>
      ))}
    </div>
  );
}

/* ── CEO advisor ─────────────────────────────────────────────────────────── */

function AdvisorTab({ farmId, missionId }: { farmId: string; missionId: string }) {
  const [q, setQ] = useState("");
  const [thread, setThread] = useState<{ role: "user" | "aria"; text: string; provider?: string; ft?: FactType }[]>([]);
  const ask = useMutation({
    mutationFn: (question: string) => askAdvisor(farmId, missionId, question),
    onSuccess: (a) => setThread((t) => [...t, { role: "aria", text: a.answer, provider: a.provider, ft: a.fact_type }]),
  });
  const suggestions = ["Should I delay expansion?", "What happens if I hire two workers?", "Should I reinvest profits?"];

  const send = (text: string) => {
    if (!text.trim()) return;
    setThread((t) => [...t, { role: "user", text }]);
    setQ("");
    ask.mutate(text);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button key={s} type="button" onClick={() => send(s)}
            className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 dark:border-white/10 dark:text-gray-300 dark:hover:bg-white/[0.04]">
            {s}
          </button>
        ))}
      </div>
      <div className="space-y-3">
        {thread.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-600 px-3.5 py-2 text-sm text-white">{m.text}</div>
            </div>
          ) : (
            <div key={i} className="max-w-[90%] space-y-1">
              <div className="rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-800 dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-100">
                {m.text}
              </div>
              <div className="flex gap-1.5 px-1">
                {m.ft && <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", FACT_BADGE[m.ft].cls)}>{FACT_BADGE[m.ft].label}</span>}
                <span className="text-[10px] text-gray-400">{m.provider}</span>
              </div>
            </div>
          ),
        )}
        {ask.isPending && <div className="flex items-center gap-2 text-sm text-gray-400"><Loader2 className="h-4 w-4 animate-spin" /> Thinking…</div>}
      </div>
      <div className="flex items-end gap-2">
        <textarea
          value={q} onChange={(e) => setQ(e.target.value)} rows={1}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(q); } }}
          placeholder="Ask your CEO advisor…" aria-label="Ask the CEO advisor"
          className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
        />
        <button type="button" onClick={() => send(q)} disabled={!q.trim() || ask.isPending} aria-label="Send"
          className="rounded-xl bg-brand-600 p-2.5 text-white hover:bg-brand-700 disabled:opacity-40">
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

/* ── Mission creation ────────────────────────────────────────────────────── */

const TEMPLATES = [
  { name: "Reach 10,000 Layers", kind: "birds", label: "Layers", target: 10000, unit: "birds" },
  { name: "Generate KES 2,000,000 annual profit", kind: "profit", label: "Annual profit", target: 2000000, unit: "KES" },
  { name: "Expand to three farms", kind: "farms", label: "Farms", target: 3, unit: "farms" },
  { name: "Become fully organic", kind: "qualitative", label: "Fully organic", target: null, unit: "" },
];

function CreateMission({ farmId, onCreated }: { farmId: string; onCreated: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [tpl, setTpl] = useState(TEMPLATES[0]);
  const [target, setTarget] = useState<string>(String(TEMPLATES[0].target ?? ""));
  const [targetDate, setTargetDate] = useState("");

  const create = useMutation({
    mutationFn: () => createMission(farmId, {
      name: name || tpl.name,
      target_date: targetDate || undefined,
      is_primary: true,
      success_metrics: [{
        kind: tpl.kind, label: tpl.label,
        target: tpl.kind === "qualitative" ? null : Number(target) || null,
        unit: tpl.unit, primary: true,
      }],
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["missions", farmId] }); onCreated(); },
  });

  return (
    <div className="mx-auto max-w-lg space-y-6 py-8">
      <div className="text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 dark:bg-brand-500/15">
          <TrendingUp className="h-6 w-6 text-brand-600 dark:text-brand-300" />
        </div>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Build the farm you envision</h1>
        <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">
          Set a mission and ARIA will guide you to it, day by day.
        </p>
      </div>

      <div className="space-y-4 rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
        <div>
          <label className="text-[13px] font-medium text-gray-700 dark:text-gray-300">Choose a mission</label>
          <div className="mt-2 grid gap-2">
            {TEMPLATES.map((t) => (
              <button key={t.name} type="button"
                onClick={() => { setTpl(t); setTarget(String(t.target ?? "")); if (!name) setName(t.name); }}
                aria-pressed={tpl.name === t.name}
                className={cn("rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                  tpl.name === t.name ? "border-brand-400 bg-brand-50 dark:border-brand-500/40 dark:bg-brand-500/10"
                                      : "border-gray-200 hover:bg-gray-50 dark:border-white/10 dark:hover:bg-white/[0.04]")}>
                {t.name}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label htmlFor="mname" className="text-[13px] font-medium text-gray-700 dark:text-gray-300">Mission name</label>
          <input id="mname" value={name} onChange={(e) => setName(e.target.value)} placeholder={tpl.name}
            className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white" />
        </div>
        {tpl.kind !== "qualitative" && (
          <div>
            <label htmlFor="mtarget" className="text-[13px] font-medium text-gray-700 dark:text-gray-300">Target ({tpl.unit})</label>
            <input id="mtarget" type="number" value={target} onChange={(e) => setTarget(e.target.value)}
              className="mt-1 w-40 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white" />
          </div>
        )}
        <div>
          <label htmlFor="mdate" className="text-[13px] font-medium text-gray-700 dark:text-gray-300">Target date</label>
          <input id="mdate" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)}
            className="mt-1 w-48 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white" />
        </div>
        <button type="button" onClick={() => create.mutate()} disabled={create.isPending}
          className="w-full rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
          {create.isPending ? "Creating…" : "Create mission"}
        </button>
        <p className="text-center text-[11px] text-gray-400">
          Your starting point is captured from your recorded data, so progress is measured honestly.
        </p>
      </div>
    </div>
  );
}

/* ── Aviculture briefing (Module 15, Part 11) ────────────────────────────── */

const SEVERITY: Record<Insight["severity"], { dot: string; cls: string }> = {
  critical: { dot: "bg-red-500", cls: "border-red-200 dark:border-red-500/30" },
  warning: { dot: "bg-amber-500", cls: "border-amber-200 dark:border-amber-500/30" },
  watch: { dot: "bg-sky-500", cls: "border-sky-200 dark:border-sky-500/30" },
  info: { dot: "bg-gray-400", cls: "border-gray-200 dark:border-white/10" },
};

const EV_BADGE: Record<string, string> = {
  recorded: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  calculated: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  forecast: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  unknown: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
};

function AvicultureTab({ farmId }: { farmId: string }) {
  const q = useQuery({
    queryKey: ["mission-aviculture-briefing", farmId],
    queryFn: () => getAvicultureBriefing(farmId),
    staleTime: 60_000,
  });
  if (q.isLoading) return <Skeleton className="h-96 rounded-2xl" />;
  if (!q.data) return <Empty>No aviculture briefing.</Empty>;
  const b = q.data;

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <Bird className="h-4 w-4 text-brand-500" aria-hidden /> {b.headline}
        </h2>
        <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
          {(["critical", "warning", "watch", "info"] as Insight["severity"][]).map((k) =>
            (b.counts[k] ?? 0) > 0 ? (
              <span key={k} className="inline-flex items-center gap-1 text-gray-500 dark:text-gray-400">
                <span className={cn("h-2 w-2 rounded-full", SEVERITY[k].dot)} /> {b.counts[k]} {k}
              </span>
            ) : null,
          )}
        </div>
      </section>

      {/* Operational priorities */}
      {b.priorities.length > 0 && (
        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">Operational priorities</h3>
          <ol className="space-y-1.5 text-[13px] text-gray-700 dark:text-gray-300">
            {b.priorities.map((p, i) => (
              <li key={i} className="flex gap-2">
                <span className="font-semibold text-brand-600 dark:text-brand-400">{i + 1}.</span>
                <span>{p}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Insights — each citing recorded evidence */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">Insights</h3>
        {b.insights.length === 0 ? (
          <p className="text-sm text-gray-400">No elevated risks on record — everything reads clean.</p>
        ) : (
          <div className="space-y-2">
            {b.insights.map((ins, i) => (
              <div key={i} className={cn("rounded-xl border bg-white p-3 dark:bg-white/[0.03]", SEVERITY[ins.severity].cls)}>
                <div className="flex items-start gap-2">
                  <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", SEVERITY[ins.severity].dot)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{ins.title}</span>
                      <span className="text-[10px] uppercase tracking-wide text-gray-400">{ins.category.replace(/_/g, " ")}</span>
                    </div>
                    <p className="mt-0.5 text-[13px] leading-snug text-gray-600 dark:text-gray-300">{ins.detail}</p>
                    <p className="mt-1 text-[11px] text-gray-400">
                      <span className="font-medium">Confidence:</span> {ins.confidence}
                      {ins.limitations && <> · <span className="font-medium">Limitations:</span> {ins.limitations}</>}
                    </p>
                    {ins.evidence.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {ins.evidence.map((e, j) => (
                          <span key={j} title={e.source}
                            className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium",
                              EV_BADGE[e.fact_type] ?? EV_BADGE.unknown)}>
                            <span className="uppercase tracking-wide">{e.fact_type}</span>
                            <span className="text-gray-400">·</span>
                            <span className="normal-case">{e.source.split(".").pop()}{e.value != null ? `: ${e.value}` : ""}</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="text-[11px] text-gray-400">
        Mission Control orchestrates the aviculture engines — it computes no figure of its own.
        Every insight above traces to a recorded, calculated or forecast fact from the deterministic engines.
      </p>
    </div>
  );
}

/* ── Shared ──────────────────────────────────────────────────────────────── */

function FactLegend() {
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3 text-[11px] text-gray-400 dark:border-white/[0.06]">
      <span>How to read the figures:</span>
      {(Object.keys(FACT_BADGE) as FactType[]).map((k) => (
        <span key={k} className={cn("rounded-full px-2 py-0.5 font-semibold", FACT_BADGE[k].cls)}>{FACT_BADGE[k].label}</span>
      ))}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-8 text-center text-sm text-gray-400">{children}</p>;
}
