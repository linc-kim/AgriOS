/**
 * BSF — Mission Control (Module 16, Frontend Milestone 10).
 *
 * The strategic briefing Mission Control composes from the deterministic engines
 * and the Growth Planner: a headline, ranked priorities, and severity-ordered
 * insights — each citing the recorded/calculated/forecast evidence it rests on,
 * with confidence and limitations. Read-only; Mission Control orchestrates and
 * owns no business logic. The frontend presents; it never recomputes.
 */
import { useQuery } from "@tanstack/react-query";
import { Compass } from "lucide-react";

import { getBsfBriefing, type Insight } from "@/api/bsfMission";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge } from "@/components/common/FactBadge";
import { BsfSubnav } from "./BsfSubnav";

const SEV_STYLES: Record<string, string> = {
  critical: "border-red-300 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10",
  warning: "border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10",
  watch: "border-sky-200 bg-sky-50 dark:border-sky-500/30 dark:bg-sky-500/10",
  info: "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900",
};
const SEV_DOT: Record<string, string> = { critical: "🔴", warning: "🟡", watch: "🔵", info: "🟢" };

export default function BsfMissionScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const q = useQuery({ queryKey: ["bsf-briefing", farmId], queryFn: () => getBsfBriefing(farmId as string), enabled: !!farmId });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <BsfSubnav active="/bsf/mission" />
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <Compass className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Mission Control</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Today’s priorities, evidence-backed</p>
        </div>
      </div>

      {q.isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-500/30 dark:bg-red-500/10">
          <p className="text-sm text-red-700 dark:text-red-300">Couldn’t load the briefing.</p>
          <Button variant="ghost" className="mt-2" onClick={() => q.refetch()}>Try again</Button>
        </div>
      ) : q.isLoading || !q.data ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
      ) : (
        <div className="space-y-5">
          {/* Headline + counts */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <p className="text-base font-medium text-gray-900 dark:text-gray-100">{q.data.headline}</p>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
              {(["critical", "warning", "watch", "info"] as const).map((s) => (
                <span key={s}>{SEV_DOT[s]} {q.data!.counts[s] ?? 0} {s}</span>
              ))}
            </div>
          </div>

          {/* Priorities */}
          {q.data.priorities.length > 0 && (
            <section>
              <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Priorities</h2>
              <ol className="list-decimal space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-300">
                {q.data.priorities.map((p, i) => <li key={i}>{p}</li>)}
              </ol>
            </section>
          )}

          {/* Insights */}
          <section>
            <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Insights</h2>
            {q.data.insights.length === 0 ? (
              <p className="text-sm text-gray-400">Nothing needs attention right now.</p>
            ) : (
              <ul className="space-y-2">{q.data.insights.map((ins, i) => <InsightRow key={i} ins={ins} />)}</ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function InsightRow({ ins }: { ins: Insight }) {
  return (
    <li className={`rounded-xl border p-3 ${SEV_STYLES[ins.severity] ?? SEV_STYLES.info}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{SEV_DOT[ins.severity]} {ins.title}</p>
        <span className="text-[11px] uppercase tracking-wide text-gray-400">{ins.category}</span>
      </div>
      <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">{ins.detail}</p>
      {ins.evidence.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {ins.evidence.map((e, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              {e.source}{e.value != null ? `: ${e.value}` : ""} <FactBadge label={e.fact_type} />
            </span>
          ))}
        </div>
      )}
      <div className="mt-1 text-[11px] text-gray-400">
        confidence: {ins.confidence}{ins.limitations ? ` · ${ins.limitations}` : ""}
      </div>
    </li>
  );
}
