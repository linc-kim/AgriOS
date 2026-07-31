/**
 * BSF — Reports & Analytics (Module 16, Frontend Milestone 8).
 *
 * Forecast detail (with the engine's method / assumptions / confidence /
 * limitations), the full ranked bottleneck list, sustainability metrics, and an
 * authenticated CSV export. Forecasts are always labelled forecast and never
 * shown as confirmed. All figures are the backend's — nothing is recomputed.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, FileBarChart } from "lucide-react";

import {
  exportProductionCsv, getBottlenecks, getDashboard, getForecast,
  type Bottleneck, type ForecastBlock,
} from "@/api/bsfReports";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge, LabelledValue } from "@/components/common/FactBadge";
import { BsfSubnav } from "./BsfSubnav";

export default function BsfReportsScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [downloading, setDownloading] = useState(false);

  const forecastQ = useQuery({ queryKey: ["bsf-forecast", farmId], queryFn: () => getForecast(farmId as string, 90, 90), enabled: !!farmId });
  const bottlenecksQ = useQuery({ queryKey: ["bsf-bottlenecks", farmId], queryFn: () => getBottlenecks(farmId as string), enabled: !!farmId });
  const dashQ = useQuery({ queryKey: ["bsf-dashboard", farmId], queryFn: () => getDashboard(farmId as string), enabled: !!farmId });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  async function download() {
    setDownloading(true);
    try {
      const blob = await exportProductionCsv(farmId as string);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "bsf_production.csv";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }

  const sus = dashQ.data?.analytics.sustainability;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <BsfSubnav active="/bsf/reports" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <FileBarChart className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Reports &amp; Analytics</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Forecasts, bottlenecks, sustainability &amp; exports</p>
          </div>
        </div>
        <Button leftIcon={<Download className="h-4 w-4" />} loading={downloading} onClick={download}>Export production CSV</Button>
      </div>

      <div className="space-y-6">
        {/* Forecast */}
        <section>
          <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Forecast (90 days)</h2>
          {forecastQ.isLoading || !forecastQ.data ? <Skeleton className="h-32 rounded-xl" /> : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <ForecastCard title="Harvest" block={forecastQ.data.harvest_kg} unit="kg" />
              <ForecastCard title="Feed requirement" block={forecastQ.data.feed_requirement_kg} unit="kg" />
              <ForecastCard title="Revenue" block={forecastQ.data.revenue} unit="" />
            </div>
          )}
        </section>

        {/* Sustainability */}
        <section>
          <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Sustainability</h2>
          {dashQ.isLoading || !sus ? <Skeleton className="h-20 rounded-xl" /> : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SusTile label="Waste diverted" figure={sus.organic_waste_diverted_kg} suffix=" kg" />
              <SusTile label="Conversion eff." figure={sus.waste_conversion_efficiency_pct} suffix="%" />
              <SusTile label="Resource eff." figure={sus.resource_efficiency_kg_per_kg} />
              <SusTile label="Carbon (est.)" figure={sus.carbon_diversion_estimate_kg} suffix=" kg" />
            </div>
          )}
        </section>

        {/* Bottlenecks */}
        <section>
          <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Bottlenecks</h2>
          {bottlenecksQ.isLoading ? <Skeleton className="h-16 rounded-xl" /> : (bottlenecksQ.data ?? []).length === 0 ? (
            <p className="text-sm text-gray-400">No significant constraints flagged.</p>
          ) : (
            <ul className="space-y-2">{bottlenecksQ.data!.map((b, i) => <BottleneckRow key={i} b={b} />)}</ul>
          )}
        </section>
      </div>
    </div>
  );
}

function ForecastCard({ title, block, unit }: { title: string; block: ForecastBlock; unit: string }) {
  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-3 dark:border-indigo-500/30 dark:bg-indigo-500/10">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-500">{title} · {block.horizon_days}d</p>
        <FactBadge label={block.forecast?.label} />
      </div>
      <p className="mt-1 text-xl font-semibold text-gray-900 dark:text-gray-100" title={block.forecast?.detail}>
        {block.forecast?.value == null ? "—" : `${block.forecast.value} ${unit}`}
      </p>
      <p className="mt-2 text-[11px] text-gray-500">{block.method}</p>
      <p className="text-[11px] text-gray-500">Confidence: <span className="font-medium">{block.confidence}</span></p>
      {block.assumptions?.length > 0 && (
        <details className="mt-1 text-[11px] text-gray-500">
          <summary className="cursor-pointer">Assumptions &amp; limitations</summary>
          <ul className="ml-3 list-disc">
            {block.assumptions.map((a, i) => <li key={`a${i}`}>{a}</li>)}
            {block.limitations?.map((l, i) => <li key={`l${i}`} className="text-gray-400">{l}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}

function SusTile({ label, figure, suffix }: { label: string; figure?: { label: string; value: unknown; detail?: string }; suffix?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
        <LabelledValue figure={figure} format={(v) => `${v}${suffix ?? ""}`} />
      </p>
    </div>
  );
}

const SEV_STYLES: Record<string, string> = {
  critical: "border-red-300 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10",
  high: "border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10",
  medium: "border-sky-200 bg-sky-50 dark:border-sky-500/30 dark:bg-sky-500/10",
  low: "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900",
};

function BottleneckRow({ b }: { b: Bottleneck }) {
  return (
    <li className={`rounded-xl border p-3 ${SEV_STYLES[b.severity] ?? SEV_STYLES.low}`}>
      <p className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">
        {b.constraint.replace(/_/g, " ")} <span className="text-xs font-normal text-gray-500">· {b.severity} · confidence {b.confidence}</span>
      </p>
      <p className="text-xs text-gray-600 dark:text-gray-400">{b.impact}</p>
      <p className="mt-1 text-xs text-gray-500"><span className="font-medium">Evidence:</span> {b.evidence}</p>
      <p className="text-xs text-gray-500"><span className="font-medium">Recommended:</span> {b.recommended_action}</p>
    </li>
  );
}
