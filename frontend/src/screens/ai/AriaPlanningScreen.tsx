/**
 * ARIA planning workspace (Module 13 Part 6).
 *
 * Looking forward: how long the feed lasts, what production is likely to do,
 * what the month costs, whether the houses can take more birds, what the
 * calendar demands — and a simulator for trying a decision before making it.
 *
 * Two presentation rules carry the honesty guarantees into the UI. Confidence
 * is shown on every projection, because a number from three days of records
 * must not look like one from thirty. And anything the engine declines to
 * project is printed as "Not enough recorded data." in a muted style rather
 * than left blank or filled with a zero — the farmer should see the gap and be
 * able to close it.
 *
 * The page never passes sync_calendar, so opening it creates no reminders.
 */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  CircleHelp,
  FlaskConical,
  Home,
  Info,
  TrendingDown,
  TrendingUp,
  Wallet,
  Wheat,
} from "lucide-react";

import {
  getPlanning,
  runSimulation,
  type AriaForecastItem,
  type Confidence,
  type ScenarioKind,
} from "@/api/ariaPlanning";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Skeleton } from "@/components/ui/Skeleton";
import { AriaAvatar } from "@/components/aria";
import { cn } from "@/lib/cn";

const NOT_ENOUGH = "Not enough recorded data.";

const CONFIDENCE_STYLE: Record<Confidence, { label: string; chip: string }> = {
  high: { label: "High confidence", chip: "bg-brand-50 text-brand-700 dark:bg-brand-500/12 dark:text-brand-300" },
  medium: { label: "Medium confidence", chip: "bg-sky-50 text-sky-700 dark:bg-sky-500/12 dark:text-sky-300" },
  low: { label: "Low confidence", chip: "bg-amber-50 text-amber-700 dark:bg-amber-500/12 dark:text-amber-300" },
  none: { label: "Not projected", chip: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400" },
};

const KIND_TINT: Record<string, string> = {
  vaccination: "bg-brand-50 text-brand-700 dark:bg-brand-500/12 dark:text-brand-300",
  inventory: "bg-amber-50 text-amber-700 dark:bg-amber-500/12 dark:text-amber-300",
  cleaning: "bg-sky-50 text-sky-700 dark:bg-sky-500/12 dark:text-sky-300",
  inspection: "bg-navy-50 text-navy-700 dark:bg-navy-500/12 dark:text-navy-200",
  recording: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
};

const HOUSE_STATE: Record<string, string> = {
  over: "text-red-600 dark:text-red-400",
  crowded: "text-amber-600 dark:text-amber-400",
  healthy: "text-brand-600 dark:text-brand-400",
  under: "text-sky-600 dark:text-sky-400",
  empty: "text-gray-400",
  unknown: "text-gray-400",
};

const SCENARIOS: { key: ScenarioKind; label: string; unit: string; default: number }[] = [
  { key: "add_birds", label: "Add birds", unit: "birds", default: 100 },
  { key: "mortality_change", label: "Mortality change", unit: "% of flock/week", default: 2 },
  { key: "feed_price_change", label: "Feed price change", unit: "%", default: 10 },
  { key: "production_change", label: "Egg production change", unit: "%", default: -5 },
];

export default function AriaPlanningScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const planning = useQuery({
    queryKey: [...queryKeys.flocks(farmId ?? ""), "aria-planning"],
    queryFn: () => getPlanning(farmId as string),
    enabled: !!farmId,
    staleTime: 60_000,
  });

  if (!farmId) {
    return (
      <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">
        Select a farm to see ARIA's plan.
      </p>
    );
  }

  const d = planning.data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <AriaAvatar size={44} state="idle" animated />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
            Planning
          </h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">
            Forecasts and budgets from your records — every projection shows its method.
          </p>
        </div>
      </header>

      {planning.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-40 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      ) : planning.isError || !d ? (
        <p className="rounded-2xl border border-gray-200 p-6 text-sm text-gray-500 dark:border-white/10 dark:text-gray-400">
          ARIA couldn't build a plan — your records are briefly unavailable.
        </p>
      ) : (
        <>
          {/* Feed forecast */}
          <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
            <header className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <Wheat className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
                Feed forecast
              </h2>
              <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold",
                CONFIDENCE_STYLE[d.feed.confidence].chip)}>
                {CONFIDENCE_STYLE[d.feed.confidence].label}
              </span>
            </header>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Daily use" value={d.feed.daily_rate_kg ? `${d.feed.daily_rate_kg}kg` : null} />
              <Stat label="Days remaining" value={d.feed.days_remaining != null ? String(d.feed.days_remaining) : null} />
              <Stat label="Runs out" value={d.feed.depletion_date} />
              <Stat label="Needed, 30 days" value={d.feed.required_30d_kg ? `${d.feed.required_30d_kg}kg` : null} />
            </div>

            {d.feed.method && (
              <Explain method={d.feed.method} assumptions={d.feed.assumptions} evidence={d.feed.evidence} />
            )}
            {d.feed.notes.map((n) => (
              <p key={n} className="mt-2 flex gap-1.5 text-[11px] leading-relaxed text-gray-500 dark:text-gray-400">
                <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                {n}
              </p>
            ))}
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Production forecast */}
            <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
              <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">
                Production forecast
              </h2>
              <ForecastTable items={d.production} />
            </section>

            {/* Capacity */}
            <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <Home className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
                Capacity
              </h2>
              {d.capacity.utilisation_pct == null ? (
                <Muted>{d.capacity.notes[0] ?? NOT_ENOUGH}</Muted>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <Stat label="Capacity" value={String(d.capacity.total_capacity)} />
                    <Stat label="Birds" value={String(d.capacity.total_birds)} />
                    <Stat label="Space left" value={String(d.capacity.available_space)} />
                  </div>
                  <ul className="mt-3 space-y-1.5">
                    {d.capacity.houses.map((h) => (
                      <li key={h.name} className="flex items-start justify-between gap-3 text-sm">
                        <span className="min-w-0">
                          <span className="block text-gray-800 dark:text-gray-200">{h.name}</span>
                          <span className="block text-[11px] text-gray-400 dark:text-gray-500">{h.note}</span>
                        </span>
                        <span className={cn("shrink-0 text-xs font-semibold tabular-nums", HOUSE_STATE[h.state])}>
                          {h.utilisation_pct != null ? `${h.utilisation_pct}%` : "—"}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {d.capacity.recommendations.map((r) => (
                    <p key={r} className="mt-2 flex gap-1.5 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                      {r}
                    </p>
                  ))}
                </>
              )}
            </section>

            {/* Budget */}
            <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <Wallet className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
                Budget · {d.budget.label}
              </h2>
              {!d.budget.available ? (
                <Muted>{d.budget.notes[0] ?? NOT_ENOUGH}</Muted>
              ) : (
                <>
                  <dl className="space-y-1.5">
                    {d.budget.lines.map((l) => (
                      <div key={l.category} className="flex justify-between gap-3 text-sm">
                        <dt className="min-w-0">
                          <span className="block text-gray-700 dark:text-gray-300">{l.category}</span>
                          <span className="block text-[11px] text-gray-400 dark:text-gray-500">{l.basis}</span>
                        </dt>
                        <dd className="shrink-0 font-medium tabular-nums text-gray-900 dark:text-white">
                          KES {l.amount}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  <p className="mt-2 flex justify-between border-t border-gray-100 pt-2 text-sm font-semibold dark:border-white/[0.06]">
                    <span className="text-gray-700 dark:text-gray-300">Total</span>
                    <span className="tabular-nums text-gray-900 dark:text-white">KES {d.budget.total}</span>
                  </p>
                  <Explain method={d.budget.method} assumptions={d.budget.assumptions} evidence={[]} />
                </>
              )}
              {d.budget.notes.map((n) => (
                <p key={n} className="mt-2 text-[11px] leading-relaxed text-gray-400 dark:text-gray-500">{n}</p>
              ))}
            </section>

            {/* Cash flow */}
            <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                {d.cashflow.outlook === "shortfall" ? (
                  <TrendingDown className="h-4 w-4 text-red-500" aria-hidden />
                ) : (
                  <TrendingUp className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
                )}
                Cash flow · next {d.cashflow.period_days} days
              </h2>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="In" value={d.cashflow.expected_income ? `KES ${d.cashflow.expected_income}` : null} />
                <Stat label="Out" value={d.cashflow.expected_expenses ? `KES ${d.cashflow.expected_expenses}` : null} />
                <Stat label="Net" value={d.cashflow.net ? `KES ${d.cashflow.net}` : null} />
              </div>
              {d.cashflow.upcoming.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {d.cashflow.upcoming.map((u) => (
                    <li key={u} className="flex gap-1.5 text-[12px] text-gray-600 dark:text-gray-300">
                      <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-gray-400" aria-hidden />
                      {u}
                    </li>
                  ))}
                </ul>
              )}
              {d.cashflow.notes.map((n) => (
                <p key={n} className="mt-2 text-[11px] leading-relaxed text-gray-400 dark:text-gray-500">{n}</p>
              ))}
            </section>
          </div>

          {/* Simulator */}
          <Simulator farmId={farmId} />

          {/* Calendar */}
          <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <CalendarDays className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
              Operational calendar
            </h2>
            {d.calendar.length === 0 ? (
              <Muted>Nothing scheduled from your records in this window.</Muted>
            ) : (
              <ul className="space-y-2">
                {d.calendar.map((e, i) => (
                  <li key={`${e.on}-${e.title}-${i}`} className="flex items-start gap-2.5">
                    <span className="w-20 shrink-0 text-[11px] tabular-nums text-gray-400 dark:text-gray-500">
                      {new Date(e.on).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm text-gray-800 dark:text-gray-200">{e.title}</span>
                      <span className="block text-[11px] text-gray-400 dark:text-gray-500">{e.why}</span>
                    </span>
                    <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium capitalize",
                      KIND_TINT[e.kind] ?? KIND_TINT.recording)}>
                      {e.kind}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}

/* ── Pieces ──────────────────────────────────────────────────────────────── */

/** A figure, or an explicit "not enough data" — never a blank or a zero. */
function Stat({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50/60 p-2.5 dark:border-white/10 dark:bg-white/[0.02]">
      <p className="text-[11px] text-gray-400 dark:text-gray-500">{label}</p>
      {value ? (
        <p className="mt-0.5 text-base font-semibold tabular-nums tracking-tight text-gray-900 dark:text-white">
          {value}
        </p>
      ) : (
        <p className="mt-0.5 text-[11px] italic leading-snug text-gray-400 dark:text-gray-500">
          {NOT_ENOUGH}
        </p>
      )}
    </div>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <p className="text-sm italic text-gray-400 dark:text-gray-500">{children}</p>;
}

/** The "how was this worked out" disclosure every projection carries. */
function Explain({
  method,
  assumptions,
  evidence,
}: {
  method: string;
  assumptions: string[];
  evidence: string[];
}) {
  const [open, setOpen] = useState(false);
  if (!method && !assumptions.length && !evidence.length) return null;
  return (
    <div className="mt-3 border-t border-gray-100 pt-2 dark:border-white/[0.06]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="-mx-1 rounded px-1 py-1.5 text-[11px] font-medium text-brand-600 hover:underline dark:text-brand-400"
      >
        {open ? "Hide how this was calculated" : "How was this calculated?"}
      </button>
      {open && (
        <div className="mt-1 space-y-1.5 text-[11px] leading-relaxed text-gray-500 dark:text-gray-400">
          {method && <p><span className="font-semibold">Method:</span> {method}</p>}
          {assumptions.length > 0 && (
            <p><span className="font-semibold">Assuming:</span> {assumptions.join(" ")}</p>
          )}
          {evidence.length > 0 && (
            <p><span className="font-semibold">From:</span> {evidence.join("; ")}</p>
          )}
        </div>
      )}
    </div>
  );
}

function ForecastTable({ items }: { items: AriaForecastItem[] }) {
  // Group by metric so each row reads "eggs: today / 7d / 30d".
  const byMetric = new Map<string, AriaForecastItem[]>();
  for (const item of items) {
    const metric = item.key.replace(/_\d+d$/, "");
    if (!byMetric.has(metric)) byMetric.set(metric, []);
    byMetric.get(metric)!.push(item);
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
            <th className="pb-2 font-medium">Metric</th>
            <th className="pb-2 text-right font-medium">Today</th>
            <th className="pb-2 text-right font-medium">7 days</th>
            <th className="pb-2 text-right font-medium">30 days</th>
          </tr>
        </thead>
        <tbody>
          {[...byMetric.entries()].map(([metric, rows]) => {
            const label = rows[0]?.label ?? metric;
            const unit = rows[0]?.unit ?? "";
            const cell = (h: string) => {
              const r = rows.find((x) => x.key.endsWith(`_${h}d`));
              if (!r || !r.available) {
                return <span className="text-[11px] italic text-gray-400">n/a</span>;
              }
              return (
                <span className="tabular-nums text-gray-900 dark:text-white">
                  {r.value}
                  <span className="ml-0.5 text-[11px] text-gray-400">{unit}</span>
                </span>
              );
            };
            const conf = rows[0]?.confidence ?? "none";
            return (
              <tr key={metric} className="border-t border-gray-100 dark:border-white/[0.06]">
                <td className="py-2">
                  <span className="text-gray-800 dark:text-gray-200">{label}</span>
                  <span className={cn("ml-2 rounded-full px-1.5 py-0.5 text-[9px] font-semibold",
                    CONFIDENCE_STYLE[conf].chip)}>
                    {conf === "none" ? "n/a" : conf}
                  </span>
                </td>
                <td className="py-2 text-right">{cell("1")}</td>
                <td className="py-2 text-right">{cell("7")}</td>
                <td className="py-2 text-right">{cell("30")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] leading-relaxed text-gray-400 dark:text-gray-500">
        Each projection is the recorded daily rate multiplied by the horizon. "n/a" means
        there isn't enough recorded history to project from.
      </p>
    </div>
  );
}

/* ── Scenario simulator ──────────────────────────────────────────────────── */

function Simulator({ farmId }: { farmId: string }) {
  const [scenario, setScenario] = useState<ScenarioKind>("add_birds");
  const [magnitude, setMagnitude] = useState<number>(100);

  const active = SCENARIOS.find((s) => s.key === scenario)!;
  const sim = useMutation({
    mutationFn: () => runSimulation(farmId, scenario, magnitude),
  });

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
        <FlaskConical className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
        What if…
      </h2>
      <p className="mb-3 text-[11px] text-gray-400 dark:text-gray-500">
        Simulations are read-only — nothing here changes your farm records.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-[180px] flex-1">
          <span className="mb-1 block text-[11px] font-medium text-gray-500 dark:text-gray-400">Scenario</span>
          <select
            value={scenario}
            onChange={(e) => {
              const next = e.target.value as ScenarioKind;
              setScenario(next);
              setMagnitude(SCENARIOS.find((s) => s.key === next)!.default);
              sim.reset();
            }}
            className="h-11 w-full rounded-xl border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white"
          >
            {SCENARIOS.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
        </label>

        <label className="w-40">
          <span className="mb-1 block text-[11px] font-medium text-gray-500 dark:text-gray-400">
            {active.unit}
          </span>
          <input
            type="number"
            value={magnitude}
            onChange={(e) => setMagnitude(Number(e.target.value))}
            className="h-11 w-full rounded-xl border border-gray-200 bg-white px-3 text-sm tabular-nums text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white"
          />
        </label>

        <button
          type="button"
          onClick={() => sim.mutate()}
          disabled={sim.isPending}
          className="h-11 rounded-xl bg-brand-600 px-4 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
        >
          {sim.isPending ? "Simulating…" : "Simulate"}
        </button>
      </div>

      {sim.data && (
        <div className="mt-4 border-t border-gray-100 pt-3 dark:border-white/[0.06]">
          {!sim.data.available ? (
            <p className="flex gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <CircleHelp className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              {sim.data.note}
            </p>
          ) : (
            <>
              <p className="text-sm font-medium text-gray-900 dark:text-white">{sim.data.description}</p>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
                      <th className="pb-1.5 font-medium">Measure</th>
                      <th className="pb-1.5 text-right font-medium">Now</th>
                      <th className="pb-1.5 text-right font-medium">Projected</th>
                      <th className="pb-1.5 text-right font-medium">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sim.data.changes.map((c) => (
                      <tr key={c.label} className="border-t border-gray-100 dark:border-white/[0.06]">
                        <td className="py-1.5 text-gray-700 dark:text-gray-300">{c.label}</td>
                        <td className="py-1.5 text-right tabular-nums text-gray-500 dark:text-gray-400">{c.current}</td>
                        <td className="py-1.5 text-right font-medium tabular-nums text-gray-900 dark:text-white">{c.projected}</td>
                        <td className="py-1.5 text-right tabular-nums text-brand-600 dark:text-brand-400">{c.difference}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {sim.data.implications.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {sim.data.implications.map((i) => (
                    <li key={i} className="flex gap-1.5 text-[12px] text-gray-700 dark:text-gray-300">
                      <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-gray-400" aria-hidden />
                      {i}
                    </li>
                  ))}
                </ul>
              )}
              {sim.data.assumptions.length > 0 && (
                <p className="mt-2 text-[11px] leading-relaxed text-gray-400 dark:text-gray-500">
                  <span className="font-semibold">Assuming:</span> {sim.data.assumptions.join(" ")}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {sim.isError && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">
          The simulation couldn't run — please try again.
        </p>
      )}
    </section>
  );
}
