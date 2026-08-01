/**
 * Rabbit — Mission Control (Module 17, Frontend).
 *
 * The strategic briefing composed by the deterministic engines: severity-ranked
 * insights, each citing recorded/calculated evidence. Read-only; Mission Control
 * owns no business logic.
 */
import { useQuery } from "@tanstack/react-query";
import { Compass } from "lucide-react";

import { getRabbitBriefing, type Insight } from "@/api/rabbitMission";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

const SEV_STYLES: Record<string, string> = {
  critical: "border-red-300 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10",
  warning: "border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10",
  watch: "border-sky-200 bg-sky-50 dark:border-sky-500/30 dark:bg-sky-500/10",
  info: "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900",
};

export default function RabbitMissionScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const q = useQuery({
    queryKey: ["rabbit-briefing", farmId],
    queryFn: () => getRabbitBriefing(farmId as string),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <RabbitSubnav active="/rabbit/mission" />
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <Compass className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Mission Control</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Today's priorities from the deterministic engines</p>
        </div>
      </div>

      {q.isLoading || !q.data ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : (
        <>
          <div className="mb-5 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{q.data.headline}</p>
            {q.data.priorities.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm text-gray-600 dark:text-gray-400">
                {q.data.priorities.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            )}
          </div>

          {q.data.insights.length === 0 ? (
            <p className="text-sm text-gray-400">No insights flagged — operations on track.</p>
          ) : (
            <ul className="space-y-2">
              {q.data.insights.map((ins, i) => <InsightRow key={i} ins={ins} />)}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function InsightRow({ ins }: { ins: Insight }) {
  return (
    <li className={`rounded-xl border p-3 ${SEV_STYLES[ins.severity] ?? SEV_STYLES.info}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{ins.title}</p>
        <span className="text-xs capitalize text-gray-500">{ins.category} · {ins.severity}</span>
      </div>
      <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">{ins.detail}</p>
      {ins.evidence.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {ins.evidence.map((e, i) => (
            <span key={i} className="inline-flex items-center gap-1 text-[11px] text-gray-500">
              {e.source}: {e.value ?? "—"} <FactBadge label={e.fact_type} />
            </span>
          ))}
        </div>
      )}
      {ins.limitations && <p className="mt-1 text-[11px] text-gray-400">{ins.limitations}</p>}
    </li>
  );
}
