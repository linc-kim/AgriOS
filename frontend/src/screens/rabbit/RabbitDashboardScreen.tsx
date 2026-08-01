/**
 * Rabbit — Executive Dashboard (Module 17, Frontend).
 *
 * Recorded population facts + composed reproduction / health / finance analytics
 * + a forecast highlight, every figure honesty-labelled by the backend engines.
 * Nothing is recomputed on the client.
 */
import { useQuery } from "@tanstack/react-query";
import { Rabbit as RabbitIcon } from "lucide-react";

import { getDashboard, type Dashboard } from "@/api/rabbitReports";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge, LabelledValue } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

export default function RabbitDashboardScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const dashQ = useQuery({
    queryKey: ["rabbit-dashboard", farmId],
    queryFn: () => getDashboard(farmId as string),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <RabbitSubnav active="/rabbit/dashboard" />
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <RabbitIcon className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Rabbit Dashboard</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Population, production, health &amp; finance at a glance</p>
        </div>
      </div>

      {dashQ.isLoading || !dashQ.data ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : (
        <DashboardBody d={dashQ.data} />
      )}
    </div>
  );
}

function DashboardBody({ d }: { d: Dashboard }) {
  const pop = d.recorded_facts.population;
  const repro = d.reproduction;
  const pnl = d.finance.pnl;
  const herdFc = d.forecast?.herd_size?.forecast;
  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Population</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Total rabbits" figure={pop.total_rabbits} />
          <Tile label="Bucks" figure={pop.bucks} />
          <Tile label="Does" figure={pop.does} />
          <Tile label="Kits" figure={pop.kits} />
          <Tile label="Growers" figure={pop.growers} />
          <Tile label="Breeding adults" figure={pop.breeding_adults} />
          <Tile label="Sold" figure={pop.sold} />
          <Tile label="Deceased" figure={pop.deceased} />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Reproduction</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Litters" figure={repro.total_litters} />
          <Tile label="Kindling rate" figure={repro.kindling_rate_pct} suffix="%" />
          <Tile label="Avg litter size" figure={repro.avg_litter_size} />
          <Tile label="Kit survival" figure={repro.kit_survival_pct} suffix="%" />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Finance</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Revenue" figure={pnl.revenue} />
          <Tile label="Total cost" figure={pnl.total_cost} />
          <Tile label="Gross profit" figure={pnl.gross_profit} />
          <Tile label="Margin" figure={pnl.gross_margin_pct} suffix="%" />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">30-day herd forecast</h2>
        <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-3 dark:border-indigo-500/30 dark:bg-indigo-500/10">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-wide text-gray-500">Projected herd size</p>
            <FactBadge label={herdFc?.label} />
          </div>
          <p className="mt-1 text-xl font-semibold text-gray-900 dark:text-gray-100" title={herdFc?.detail}>
            {herdFc?.value == null ? "—" : String(herdFc.value)}
          </p>
        </div>
      </section>
    </div>
  );
}

function Tile({ label, figure, suffix }: { label: string; figure?: { label: string; value: unknown; detail?: string }; suffix?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
        <LabelledValue figure={figure} format={(v) => `${v}${suffix ?? ""}`} />
      </p>
    </div>
  );
}
