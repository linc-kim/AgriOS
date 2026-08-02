/** Small Ruminant — Mission Control briefing (shared): the strategic briefing
 *  Mission Control composes from the deterministic engines (read-only). */
import { useQuery } from "@tanstack/react-query";

import { getMissionBriefing, type Species } from "@/api/smallRuminant";
import { SPECIES_UI } from "./config";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge } from "@/components/common/FactBadge";
import { SrSubnav } from "./SrSubnav";

const SEV: Record<string, string> = {
  critical: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  watch: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  info: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300",
};

export default function SrMissionScreen({ species }: { species: Species }) {
  const ui = SPECIES_UI[species];
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const q = useQuery({
    queryKey: ["sr-mission", species, farmId],
    queryFn: () => getMissionBriefing(farmId as string, species),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const b = q.data ?? {};
  const insights: any[] = b.insights ?? [];

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <SrSubnav species={species} active={`/${species}/mission`} />
      <h1 className="mb-1 text-xl font-semibold text-gray-900 dark:text-gray-100">
        Mission Control · {ui.title}
      </h1>
      {q.isLoading ? (
        <Skeleton className="mt-4 h-48 rounded-xl" />
      ) : (
        <>
          <p className="mb-4 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">
            {b.headline}
          </p>
          {insights.length === 0 ? (
            <p className="text-sm text-gray-400">No insights — operations look steady.</p>
          ) : (
            <ul className="space-y-2">
              {insights.map((i, idx) => (
                <li key={idx} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
                  <div className="flex items-center gap-2">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${SEV[i.severity] ?? SEV.info}`}>
                      {i.severity}
                    </span>
                    <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{i.title}</span>
                  </div>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{i.detail}</p>
                  {(i.evidence ?? []).length > 0 && (
                    <p className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-gray-400">
                      evidence:
                      {i.evidence.map((e: any, k: number) => (
                        <span key={k} className="inline-flex items-center gap-1">
                          {e.source}={e.value ?? "—"} <FactBadge label={e.fact_type} />
                        </span>
                      ))}
                    </p>
                  )}
                  {i.limitations && <p className="mt-1 text-[11px] italic text-gray-400">{i.limitations}</p>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
