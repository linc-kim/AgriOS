/** Swine — Dashboard: composed deterministic summaries with the honesty label each
 *  engine assigned. The client renders; it never recomputes. */
import { useQuery } from "@tanstack/react-query";

import { getFarmDashboard, type Figure } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SwineSubnav } from "./SwineSubnav";

export default function SwineDashboardScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const q = useQuery({
    queryKey: ["swine-dashboard", farmId],
    queryFn: () => getFarmDashboard(farmId as string),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  const d = q.data ?? {};
  const repro = d.reproduction ?? {};
  const farrowing = d.farrowing ?? {};
  const health = d.health ?? {};
  const herd = d.growth?.herd ?? {};
  const pnl = d.finance?.pnl ?? {};

  const tiles: { label: string; fig?: Figure }[] = [
    { label: "Active pigs", fig: d.population },
    { label: "Conception rate", fig: repro.conception_rate_pct },
    { label: "Farrowings", fig: farrowing.total_farrowings },
    { label: "Avg litter size", fig: farrowing.avg_litter_size },
    { label: "Pre-wean survival", fig: farrowing.pre_wean_survival_pct },
    { label: "Mortality rate", fig: health.mortality_rate_pct },
    { label: "Avg daily gain (kg)", fig: herd.avg_daily_gain_kg },
    { label: "Gross margin", fig: pnl.gross_margin },
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <SwineSubnav active="/swine/dashboard" />
      <h1 className="mb-1 text-xl font-semibold text-gray-900 dark:text-gray-100">Swine Dashboard</h1>
      <p className="mb-5 text-sm text-gray-500 dark:text-gray-400">
        Every figure carries the honesty label its deterministic engine assigned.
      </p>

      {q.isLoading ? (
        <Skeleton className="h-48 rounded-xl" />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tiles.map((t) => (
            <div key={t.label} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
              <div className="text-xs uppercase tracking-wide text-gray-400">{t.label}</div>
              <div className="mt-1 text-sm font-medium"><LabelledValue figure={t.fig} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
