/** Small Ruminant — Dashboard (shared): composed deterministic summaries with the
 *  honesty label each engine assigned. The client renders; it never recomputes. */
import { useQuery } from "@tanstack/react-query";

import { getDashboard, type Figure, type Species } from "@/api/smallRuminant";
import { SPECIES_UI } from "./config";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SrSubnav } from "./SrSubnav";

export default function SrDashboardScreen({ species }: { species: Species }) {
  const ui = SPECIES_UI[species];
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const q = useQuery({
    queryKey: ["sr-dashboard", species, farmId],
    queryFn: () => getDashboard(farmId as string, species),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  const d = q.data ?? {};
  const pop = d.population ?? {};
  const repro = d.reproduction ?? {};
  const health = d.health ?? {};
  const pnl = d.finance?.pnl ?? {};
  const forecast = d.forecast ?? {};
  const bottlenecks: any[] = d.bottlenecks ?? [];

  const tiles: { label: string; fig?: Figure }[] = [
    { label: "Active animals", fig: pop.active },
    { label: "Total births", fig: repro.total_births },
    { label: "Birth rate", fig: repro.birth_rate_pct },
    { label: "Offspring survival", fig: repro.offspring_survival_pct },
    { label: "Mortality rate", fig: health.mortality_rate_pct },
    { label: "Revenue", fig: pnl.revenue },
    { label: "Gross margin", fig: pnl.gross_margin },
    { label: "Projected head", fig: forecast.projected_head },
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <SrSubnav species={species} active={`/${species}/dashboard`} />
      <h1 className="mb-1 text-xl font-semibold text-gray-900 dark:text-gray-100">{ui.title} Dashboard</h1>
      <p className="mb-5 text-sm text-gray-500 dark:text-gray-400">
        Every figure carries the honesty label its deterministic engine assigned.
      </p>

      {q.isLoading ? (
        <Skeleton className="h-48 rounded-xl" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {tiles.map((t) => (
              <div key={t.label} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
                <div className="text-xs uppercase tracking-wide text-gray-400">{t.label}</div>
                <div className="mt-1 text-sm font-medium">
                  <LabelledValue figure={t.fig} />
                </div>
              </div>
            ))}
          </div>

          <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">
            Operational bottlenecks
          </h2>
          {bottlenecks.length === 0 ? (
            <p className="text-sm text-gray-400">No significant bottlenecks flagged.</p>
          ) : (
            <ul className="space-y-2">
              {bottlenecks.map((b, i) => (
                <li key={i} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
                  <span className="font-medium capitalize text-gray-800 dark:text-gray-200">
                    {String(b.area).replace(/_/g, " ")}
                  </span>
                  <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] uppercase text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                    {b.severity}
                  </span>
                  <p className="mt-0.5 text-gray-500">{b.impact} <em>Recommended:</em> {b.action}</p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
