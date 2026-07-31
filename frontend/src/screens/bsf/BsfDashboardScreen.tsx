/**
 * BSF — Executive Dashboard (Module 16, Frontend Milestone 3).
 *
 * A read-only overview composed entirely from the backend executive dashboard:
 * recorded facts, derived analytics, composite scores, forecasts and ranked
 * bottlenecks. Every figure keeps the honesty label its engine assigned —
 * recorded, calculated, forecast and estimate stay visually distinct — and the
 * frontend recomputes nothing.
 */
import { useQuery } from "@tanstack/react-query";
import { Gauge, TriangleAlert } from "lucide-react";

import type { Figure } from "@/api/bsf";
import { getDashboard, type Bottleneck, type Dashboard, type ForecastBlock } from "@/api/bsfReports";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge, LabelledValue } from "@/components/common/FactBadge";
import { BsfSubnav } from "./BsfSubnav";

const num = (v: unknown) => (v == null ? "—" : Number(v).toLocaleString());
const kg = (v: unknown) => (v == null ? "—" : `${(Number(v) / 1000).toFixed(2)} kg`);
const pct = (v: unknown) => (v == null ? "—" : `${Number(v)}%`);
const money = (v: unknown, ccy?: string) => (v == null ? "—" : `${ccy ? ccy + " " : ""}${Number(v).toLocaleString()}`);

export default function BsfDashboardScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const dashQ = useQuery({
    queryKey: ["bsf-dashboard", farmId],
    queryFn: () => getDashboard(farmId as string),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <BsfSubnav active="/bsf/dashboard" />
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <Gauge className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">BSF Dashboard</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Facts, analytics, forecasts &amp; priorities</p>
        </div>
      </div>

      {dashQ.isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-500/30 dark:bg-red-500/10">
          <p className="text-sm text-red-700 dark:text-red-300">Couldn’t load the dashboard.</p>
          <Button variant="ghost" className="mt-2" onClick={() => dashQ.refetch()}>Try again</Button>
        </div>
      ) : dashQ.isLoading || !dashQ.data ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
      ) : (
        <DashboardView d={dashQ.data} />
      )}
    </div>
  );
}

function DashboardView({ d }: { d: Dashboard }) {
  const f = d.recorded_facts;
  const prod = d.analytics.production;
  const fin = d.analytics.finance;
  const health = d.analytics.health;
  const sus = d.analytics.sustainability;
  const ccy = (fin.currency?.value as string) ?? undefined;

  return (
    <div className="space-y-6">
      {/* Scores */}
      <Section title="Business scores">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <ScoreTile label="Business health" figure={d.scores.business_health} highlight />
          <ScoreTile label="Production" figure={d.scores.production} />
          <ScoreTile label="Financial" figure={d.scores.financial} />
          <ScoreTile label="Sustainability" figure={d.scores.sustainability} />
          <ScoreTile label="Health" figure={d.scores.health} />
          <ScoreTile label="Growth" figure={d.scores.growth} />
        </div>
      </Section>

      {/* Production summary (recorded facts) */}
      <Section title="Production summary">
        <Tiles>
          <Tile label="Active batches" figure={f.active_batches} format={num} />
          <Tile label="Active biomass" figure={f.active_biomass_g} format={kg} />
          <Tile label="Total harvested" figure={f.total_harvest_kg} format={(v) => `${Number(v)} kg`} />
          <Tile label="Frass produced" figure={f.total_frass_kg} format={(v) => `${Number(v)} kg`} />
          <Tile label="Feedstock on hand" figure={f.feedstock_available_kg} format={(v) => `${Number(v)} kg`} />
          <Tile label="Total mortality" figure={f.total_mortality} format={num} />
        </Tiles>
      </Section>

      {/* KPIs (calculated) */}
      <Section title="Production KPIs">
        <Tiles>
          <Tile label="Feed conversion" figure={prod.feed_conversion_ratio} />
          <Tile label="Survival" figure={prod.survival_rate_pct} format={pct} />
          <Tile label="Capacity used" figure={prod.capacity_utilisation_pct} format={pct} />
          <Tile label="Mortality rate" figure={health.mortality_rate_pct} format={pct} />
        </Tiles>
      </Section>

      {/* Financial snapshot */}
      <Section title="Financial snapshot">
        <Tiles>
          <Tile label="Revenue" figure={fin.revenue} format={(v) => money(v, ccy)} />
          <Tile label="Operating cost" figure={fin.operating_cost} format={(v) => money(v, ccy)} />
          <Tile label="Gross profit" figure={fin.gross_profit} format={(v) => money(v, ccy)} />
          <Tile label="Gross margin" figure={fin.gross_margin_pct} format={pct} />
          <Tile label="Cost / kg" figure={fin.cost_per_kg} format={(v) => money(v, ccy)} />
          <Tile label="ROI" figure={fin.roi_pct} format={pct} />
        </Tiles>
      </Section>

      {/* Sustainability */}
      <Section title="Sustainability">
        <Tiles>
          <Tile label="Waste diverted" figure={sus.organic_waste_diverted_kg} format={(v) => `${Number(v)} kg`} />
          <Tile label="Conversion efficiency" figure={sus.waste_conversion_efficiency_pct} format={pct} />
          <Tile label="Resource efficiency" figure={sus.resource_efficiency_kg_per_kg} />
          <Tile label="Carbon diverted (est.)" figure={sus.carbon_diversion_estimate_kg} format={(v) => `${Number(v)} kg`} />
        </Tiles>
      </Section>

      {/* Forecast — always labelled forecast, never confirmed */}
      <Section title="Forecast">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <ForecastTile label="Harvest" block={d.forecast.harvest_kg} unit="kg" />
          <ForecastTile label="Feed requirement" block={d.forecast.feed_requirement_kg} unit="kg" />
          <ForecastTile label="Revenue" block={d.forecast.revenue} unit={ccy ?? ""} />
        </div>
      </Section>

      {/* Bottlenecks */}
      <Section title="Bottlenecks">
        {d.bottlenecks.length === 0 ? (
          <p className="text-sm text-gray-400">No significant constraints flagged.</p>
        ) : (
          <ul className="space-y-2">
            {d.bottlenecks.map((b, i) => <BottleneckRow key={i} b={b} />)}
          </ul>
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</h2>
      {children}
    </section>
  );
}

function Tiles({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">{children}</div>;
}

function Tile({ label, figure, format }: { label: string; figure?: Figure; format?: (v: unknown) => string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
        <LabelledValue figure={figure} format={format} />
      </p>
    </div>
  );
}

function ScoreTile({ label, figure, highlight }: { label: string; figure?: Figure; highlight?: boolean }) {
  const val = figure?.value;
  return (
    <div className={`rounded-xl border p-3 ${highlight ? "border-brand-200 bg-brand-50 dark:border-brand-500/30 dark:bg-brand-500/10" : "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"}`}>
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        <FactBadge label={figure?.label} />
      </div>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100" title={figure?.detail}>
        {val == null ? "—" : String(val)}
      </p>
    </div>
  );
}

function ForecastTile({ label, block, unit }: { label: string; block?: ForecastBlock; unit: string }) {
  if (!block) return null;
  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-3 dark:border-indigo-500/30 dark:bg-indigo-500/10">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-500">{label} · {block.horizon_days}d</p>
        <FactBadge label={block.forecast?.label} />
      </div>
      <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100" title={block.forecast?.detail}>
        {block.forecast?.value == null ? "—" : `${block.forecast.value} ${unit}`}
      </p>
      <p className="mt-1 text-[11px] text-gray-500">
        Confidence: {block.confidence}. {block.limitations?.[0] ?? ""}
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
      <div className="flex items-start gap-2">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-gray-500" />
        <div className="min-w-0">
          <p className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">
            {b.constraint.replace(/_/g, " ")} <span className="text-xs font-normal text-gray-500">· {b.severity}</span>
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">{b.impact}</p>
          <p className="mt-1 text-xs text-gray-500"><span className="font-medium">Evidence:</span> {b.evidence}</p>
          <p className="text-xs text-gray-500"><span className="font-medium">Recommended:</span> {b.recommended_action}</p>
        </div>
      </div>
    </li>
  );
}
