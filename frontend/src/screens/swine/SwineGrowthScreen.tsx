/** Swine — Growth: herd growth summary + average weight/ADG by production stage.
 *  All figures are computed by the deterministic growth engine from weight records. */
import { useQuery } from "@tanstack/react-query";

import { getHerdGrowth, getStageComparison } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SwineSubnav } from "./SwineSubnav";

const STAGES = ["weaner", "nursery", "grower", "finisher"];

export default function SwineGrowthScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const herdQ = useQuery({
    queryKey: ["swine-herd-growth", farmId], queryFn: () => getHerdGrowth(farmId as string), enabled: !!farmId,
  });
  const stageQ = useQuery({
    queryKey: ["swine-stage-cmp", farmId], queryFn: () => getStageComparison(farmId as string), enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const herd = herdQ.data?.herd ?? {};
  const byStage = stageQ.data?.by_stage ?? {};

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <SwineSubnav active="/swine/growth" />
      <h1 className="mb-4 text-xl font-semibold text-gray-900 dark:text-gray-100">Growth &amp; Production</h1>

      {herdQ.isLoading ? <Skeleton className="h-20 rounded-xl" /> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Weighed pigs" fig={herd.weighed_count} />
          <Tile label="Avg weight (kg)" fig={herd.avg_weight_kg} />
          <Tile label="Avg daily gain (kg)" fig={herd.avg_daily_gain_kg} />
          <Tile label="Total weighings" fig={{ label: "recorded", value: herdQ.data?.total_weighings }} />
        </div>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">By production stage</h2>
      {stageQ.isLoading ? <Skeleton className="h-40 rounded-xl" /> : (
        <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500 dark:bg-gray-900">
              <tr><th className="px-3 py-2">Stage</th><th className="px-3 py-2">Pigs</th>
                <th className="px-3 py-2">Avg weight (kg)</th><th className="px-3 py-2">Avg daily gain (kg)</th></tr>
            </thead>
            <tbody>
              {STAGES.map((st) => {
                const c = byStage[st] ?? {};
                return (
                  <tr key={st} className="border-t border-gray-100 dark:border-gray-800">
                    <td className="px-3 py-2 capitalize font-medium text-gray-800 dark:text-gray-200">{st}</td>
                    <td className="px-3 py-2"><LabelledValue figure={c.count} /></td>
                    <td className="px-3 py-2"><LabelledValue figure={c.avg_weight_kg} /></td>
                    <td className="px-3 py-2"><LabelledValue figure={c.avg_daily_gain_kg} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Tile({ label, fig }: { label: string; fig?: any }) {
  return (
    <div className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
      <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
      <div className="mt-1 text-sm font-medium"><LabelledValue figure={fig} /></div>
    </div>
  );
}
