/**
 * ARIA — the operations-manager panel.
 *
 * The intelligence surface: a morning briefing, an explainable health score, a
 * dynamic checklist, and insights that each state problem, reason, action and
 * benefit. Everything here comes from the deterministic /aria/intelligence
 * endpoint — real farm data, no model, honest about anything it can't measure.
 *
 * It reads as a manager's report, not a dashboard: every number is attached to
 * a "so what", and every score explains itself.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleCheck,
  ClipboardList,
  Info,
  Lightbulb,
  Sunrise,
  TrendingUp,
} from "lucide-react";
import { getIntelligence, type AriaHealthFactor, type AriaInsight } from "@/api/ariaIntelligence";
import { queryKeys } from "@/lib/queryClient";
import { Skeleton } from "@/components/ui/Skeleton";
import { AriaAvatar, AriaSourceBadge } from "@/components/aria";
import { cn } from "@/lib/cn";

const PRIORITY_TINT: Record<string, string> = {
  high: "bg-red-50 text-red-700 dark:bg-red-500/12 dark:text-red-300",
  medium: "bg-amber-50 text-amber-700 dark:bg-amber-500/12 dark:text-amber-300",
  low: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
};

export function AriaIntelligencePanel({
  farmId,
  className,
}: {
  farmId: string;
  className?: string;
}) {
  const q = useQuery({
    queryKey: [...queryKeys.flocks(farmId), "aria-intelligence"],
    queryFn: () => getIntelligence(farmId),
    enabled: !!farmId,
    staleTime: 60_000,
  });

  if (q.isLoading) {
    return (
      <div className={cn("space-y-4", className)}>
        <Skeleton className="h-40 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
      </div>
    );
  }
  if (q.isError || !q.data) {
    return (
      <div className={cn("rounded-2xl border border-gray-200 p-5 text-sm text-gray-500 dark:border-white/10 dark:text-gray-400", className)}>
        ARIA couldn't compile the briefing — your records are briefly unavailable.
      </div>
    );
  }

  const { briefing, health, insights, checklist, trends } = q.data;

  return (
    <div className={cn("space-y-4", className)} aria-label="ARIA operations briefing">
      {/* Briefing */}
      <section className="overflow-hidden rounded-2xl border border-brand-200/70 bg-brand-50/50 dark:border-brand-500/25 dark:bg-brand-500/[0.07]">
        <div className="flex items-start gap-3 p-4">
          <AriaAvatar size={36} state="responding" animated />
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-brand-900 dark:text-brand-50">
              <Sunrise className="h-4 w-4" aria-hidden />
              {briefing.greeting}
            </p>
            <ul className="mt-2 space-y-1">
              {briefing.lines.map((line, i) => (
                <li key={i} className="flex gap-2 text-sm text-brand-900/90 dark:text-brand-50/90">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-500" aria-hidden />
                  {line}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {briefing.priorities.length > 0 && (
          <div className="border-t border-brand-200/60 px-4 py-3 dark:border-brand-500/20">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-700/80 dark:text-brand-200/70">
              Today's priorities
            </p>
            <ol className="mt-1.5 space-y-1">
              {briefing.priorities.map((p, i) => (
                <li key={i} className="flex gap-2 text-sm text-brand-900 dark:text-brand-50">
                  <span className="font-semibold text-brand-600 dark:text-brand-400">{i + 1}.</span>
                  {p}
                </li>
              ))}
            </ol>
          </div>
        )}

        {briefing.notes.length > 0 && (
          <div className="border-t border-brand-200/60 bg-white/40 px-4 py-2 dark:border-brand-500/20 dark:bg-white/[0.02]">
            {briefing.notes.map((n, i) => (
              <p key={i} className="flex gap-1.5 text-[11px] leading-relaxed text-brand-800/70 dark:text-brand-100/60">
                <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                {n}
              </p>
            ))}
          </div>
        )}
      </section>

      {/* Health score */}
      <HealthScoreCard score={health.score} max={health.max_score} grade={health.grade} factors={health.factors} />

      {/* Checklist */}
      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <ClipboardList className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
          Today's checklist
          <span className="ml-auto text-[11px] font-normal text-gray-400">
            {checklist.filter((c) => c.done).length}/{checklist.length} done
          </span>
        </h3>
        <ul className="space-y-1">
          {checklist.map((item) => (
            <li key={item.key} className="flex items-start gap-2.5 rounded-lg px-1.5 py-1.5" title={item.reason}>
              <span
                className={cn(
                  "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                  item.done
                    ? "border-brand-500 bg-brand-500 text-white"
                    : "border-gray-300 dark:border-white/20",
                )}
                aria-hidden
              >
                {item.done && <Check className="h-3 w-3" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className={cn("block text-sm", item.done ? "text-gray-400 line-through dark:text-gray-500" : "text-gray-800 dark:text-gray-200")}>
                  {item.label}
                </span>
                <span className="block text-[11px] leading-snug text-gray-400 dark:text-gray-500">{item.reason}</span>
              </span>
              {item.priority === "high" && !item.done && (
                <span className="mt-0.5 rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-600 dark:bg-red-500/12 dark:text-red-300">
                  now
                </span>
              )}
            </li>
          ))}
        </ul>
      </section>

      {/* Insights */}
      {insights.length > 0 && (
        <section className="space-y-2.5">
          <h3 className="flex items-center gap-2 px-1 text-sm font-semibold text-gray-900 dark:text-white">
            <Lightbulb className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
            What needs attention
          </h3>
          {insights.map((i) => (
            <InsightCard key={i.key} insight={i} />
          ))}
        </section>
      )}

      {/* Trends */}
      {trends.length > 0 && (
        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <TrendingUp className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
            Trends explained
          </h3>
          <ul className="space-y-2">
            {trends.map((t, i) => (
              <li key={i} className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                {t.explanation}
                {!t.grounded && (
                  <span className="ml-1 text-[11px] text-gray-400 dark:text-gray-500">(no recorded cause)</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/* ── Health score ────────────────────────────────────────────────────────── */

const GRADE_COLOR: Record<string, string> = {
  excellent: "text-brand-600 dark:text-brand-400",
  good: "text-brand-600 dark:text-brand-400",
  fair: "text-amber-600 dark:text-amber-400",
  poor: "text-red-600 dark:text-red-400",
};

const STATUS_ICON = {
  ok: { icon: CircleCheck, tint: "text-brand-500" },
  warn: { icon: AlertTriangle, tint: "text-amber-500" },
  fail: { icon: AlertTriangle, tint: "text-red-500" },
} as const;

function HealthScoreCard({
  score,
  max,
  grade,
  factors,
}: {
  score: number;
  max: number;
  grade: string;
  factors: AriaHealthFactor[];
}) {
  const [open, setOpen] = useState(true);
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3"
        aria-expanded={open}
      >
        <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-xl bg-gray-50 dark:bg-white/[0.04]">
          <span className={cn("text-xl font-bold tabular-nums leading-none", GRADE_COLOR[grade])}>{score}</span>
          <span className="text-[9px] text-gray-400">/ {max}</span>
        </div>
        <div className="min-w-0 flex-1 text-left">
          <p className="text-sm font-semibold text-gray-900 dark:text-white">Farm health</p>
          <p className={cn("text-xs font-medium capitalize", GRADE_COLOR[grade])}>{grade}</p>
        </div>
        <ChevronDown className={cn("h-4 w-4 text-gray-400 transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      {open && (
        <ul className="mt-3 space-y-2 border-t border-gray-100 pt-3 dark:border-white/[0.06]">
          {factors.map((f) => {
            const s = STATUS_ICON[f.status];
            const Icon = s.icon;
            return (
              <li key={f.key} className="flex items-start gap-2.5">
                <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", s.tint)} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{f.label}</span>
                    <span className="shrink-0 text-xs tabular-nums text-gray-400">{f.score}/{f.max_score}</span>
                  </span>
                  <span className="block text-[11px] leading-snug text-gray-500 dark:text-gray-400">{f.explanation}</span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/* ── Insight ─────────────────────────────────────────────────────────────── */

function InsightCard({ insight }: { insight: AriaInsight }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-2.5 p-3 text-left"
        aria-expanded={open}
      >
        <span className={cn("mt-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold capitalize", PRIORITY_TINT[insight.priority])}>
          {insight.priority}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-gray-900 dark:text-white">{insight.title}</span>
          <span className="block text-xs text-gray-500 dark:text-gray-400">{insight.problem}</span>
        </span>
        <ChevronDown className={cn("mt-0.5 h-4 w-4 shrink-0 text-gray-400 transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      {open && (
        <div className="space-y-2 border-t border-gray-100 px-3 py-2.5 text-sm dark:border-white/[0.06]">
          <Row label="Why" value={insight.reason} />
          <Row label="Do" value={insight.action} />
          <Row label="Benefit" value={insight.benefit} />
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[11px] text-gray-400">
              {insight.confidence} confidence · based on
            </span>
            {insight.sources.map((s) => (
              <AriaSourceBadge key={s} source={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex gap-2">
      <span className="w-14 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</span>
      <span className="flex-1 leading-relaxed text-gray-700 dark:text-gray-300">{value}</span>
    </p>
  );
}
