/** Small Ruminant — species production workspace (shared shell). Dairy (milk/
 *  lactation) for goats; Wool (shearing/fleece) for sheep. The tab shown is driven
 *  by the species capability, demonstrating the config-gated design end to end. */
import { useQuery } from "@tanstack/react-query";

import {
  getDairySummary, getWoolSummary, listLactations, listShearings,
  type Figure, type Species,
} from "@/api/smallRuminant";
import { SPECIES_UI } from "./config";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SrSubnav } from "./SrSubnav";

export default function SrProductionScreen({ species }: { species: Species }) {
  const ui = SPECIES_UI[species];
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const isGoat = species === "goat";

  const summaryQ = useQuery({
    queryKey: ["sr-production-summary", species, farmId],
    queryFn: () => (isGoat ? getDairySummary(farmId as string) : getWoolSummary(farmId as string)),
    enabled: !!farmId,
  });
  const recordsQ = useQuery({
    queryKey: ["sr-production-records", species, farmId],
    queryFn: () => (isGoat ? listLactations(farmId as string) : listShearings(farmId as string)),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  const s = summaryQ.data ?? {};
  const tiles: { label: string; fig?: Figure }[] = isGoat
    ? [
        { label: "Active milkers", fig: s.active_milkers },
        { label: "Active lactations", fig: s.active_lactations },
        { label: "Total recorded milk (L)", fig: s.total_recorded_yield_l },
      ]
    : [
        { label: "Shearing sessions", fig: s.shearing_sessions },
        { label: "Total greasy (kg)", fig: s.total_greasy_kg },
        { label: "Total clean (kg)", fig: s.total_clean_kg },
        { label: "Avg micron", fig: s.avg_micron },
        { label: "Avg staple (cm)", fig: s.avg_staple_length_cm },
      ];

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <SrSubnav species={species} active={`/${species}/${ui.productionPath}`} />
      <h1 className="mb-1 text-xl font-semibold text-gray-900 dark:text-gray-100">
        {ui.title} · {ui.productionLabel}
      </h1>
      <p className="mb-5 text-sm text-gray-500 dark:text-gray-400">
        {isGoat
          ? "Lactation cycles and milk yields. Totals, peak and the 305-day projection are computed deterministically."
          : "Shearing sessions and fleece. Clean weight, micron grade and value are computed deterministically."}
      </p>

      {summaryQ.isLoading ? (
        <Skeleton className="h-24 rounded-xl" />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {tiles.map((t) => (
            <div key={t.label} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
              <div className="text-xs uppercase tracking-wide text-gray-400">{t.label}</div>
              <div className="mt-1 text-sm font-medium"><LabelledValue figure={t.fig} /></div>
            </div>
          ))}
        </div>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">
        {isGoat ? "Lactations" : "Shearing sessions"}
      </h2>
      {recordsQ.isLoading ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : (recordsQ.data ?? []).length === 0 ? (
        <p className="text-sm text-gray-400">None recorded yet.</p>
      ) : (
        <ul className="space-y-2">
          {(recordsQ.data ?? []).map((r: any) => (
            <li key={r.id} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
              {isGoat ? (
                <>Lactation #{r.lactation_number} · freshened {r.freshening_date} · <span className="capitalize">{r.status}</span></>
              ) : (
                <>Sheared {r.shearing_date} · {r.method}{r.shearer ? ` · by ${r.shearer}` : ""}</>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
