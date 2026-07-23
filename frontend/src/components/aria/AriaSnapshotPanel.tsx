/**
 * ARIA workspace — today's farm snapshot.
 *
 * The right rail: live numbers from the same read endpoints the rest of Greena
 * uses (production dashboard, vaccination schedule, finance). Everything here is
 * real and deterministic — no forecasts, no model output, no invented figures.
 *
 * Weather is shown honestly as not-connected rather than fabricated. Inventing a
 * temperature would break the one rule the whole module is built on, and a
 * farmer who caught ARIA making up weather would rightly distrust the numbers
 * that are real.
 */
import { useQuery } from "@tanstack/react-query";
import {
  Bird,
  CloudOff,
  Egg,
  Syringe,
  TrendingDown,
  TrendingUp,
  Wallet,
  Wheat,
  type LucideIcon,
} from "lucide-react";
import { getProductionDashboard } from "@/api/flocks";
import { getVaccinationSchedule } from "@/api/health";
import { getFinanceDashboard } from "@/api/finance";
import { queryKeys } from "@/lib/queryClient";
import { Skeleton } from "@/components/ui/Skeleton";
import { AriaAvatar } from "./AriaIdentity";
import { cn } from "@/lib/cn";

const KES = (v: string | number) => {
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? `KES ${Math.round(n).toLocaleString("en-KE")}` : "—";
};

export function AriaSnapshotPanel({
  farmId,
  className,
}: {
  farmId: string;
  className?: string;
}) {
  const production = useQuery({
    queryKey: [...queryKeys.flocks(farmId), "production-dashboard"],
    queryFn: () => getProductionDashboard(farmId),
    enabled: !!farmId,
    staleTime: 60_000,
  });
  const vaccinations = useQuery({
    queryKey: queryKeys.healthSchedule(farmId),
    queryFn: () => getVaccinationSchedule(farmId),
    enabled: !!farmId,
    staleTime: 60_000,
  });
  const finance = useQuery({
    queryKey: queryKeys.financeDashboard(farmId),
    queryFn: () => getFinanceDashboard(farmId),
    enabled: !!farmId,
    staleTime: 60_000,
  });

  const p = production.data;
  const v = vaccinations.data;
  const f = finance.data;

  const dueCount =
    (v?.overdue.length ?? 0) + (v?.due_today.length ?? 0) + (v?.due_this_week.length ?? 0);

  return (
    <aside
      className={cn("flex flex-col gap-4", className)}
      aria-label="Today's farm snapshot"
    >
      <header className="flex items-center gap-2.5">
        <AriaAvatar size={32} />
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Today's snapshot</h2>
          <p className="text-[11px] text-gray-400 dark:text-gray-500">Live from your records</p>
        </div>
      </header>

      {production.isLoading ? (
        <Skeleton className="h-32 rounded-2xl" />
      ) : (
        <div className="grid grid-cols-2 gap-2.5">
          <Stat icon={Egg} label="Eggs today" value={p ? String(p.eggs_today) : "—"} tone="amber" />
          <Stat
            icon={Bird}
            label="Lost this week"
            value={p ? String(p.mortality_this_week) : "—"}
            tone={p && p.mortality_this_week > 0 ? "red" : "brand"}
          />
          <Stat icon={Wheat} label="Feed today" value={p ? `${p.feed_today_kg}kg` : "—"} tone="navy" />
          <Stat
            icon={Bird}
            label="Active birds"
            value={p ? p.total_birds.toLocaleString("en-KE") : "—"}
            tone="brand"
          />
        </div>
      )}

      {/* Finance */}
      <Section title="Financial status" icon={Wallet}>
        {finance.isLoading ? (
          <Skeleton className="h-16 rounded-xl" />
        ) : f ? (
          <div className="space-y-1.5">
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">{f.period_label}</span>
              <span
                className={cn(
                  "inline-flex items-center gap-1 text-sm font-semibold",
                  f.is_profitable
                    ? "text-brand-600 dark:text-brand-400"
                    : "text-red-600 dark:text-red-400",
                )}
              >
                {f.is_profitable ? (
                  <TrendingUp className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5" aria-hidden />
                )}
                {KES(f.gross_profit_kes)}
              </span>
            </div>
            <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500">
              <span>In {KES(f.total_revenue_kes)}</span>
              <span>Out {KES(f.total_expenses_kes)}</span>
            </div>
          </div>
        ) : (
          <Empty>No finance data yet.</Empty>
        )}
      </Section>

      {/* Vaccinations */}
      <Section title="Vaccinations" icon={Syringe} badge={dueCount || undefined}>
        {vaccinations.isLoading ? (
          <Skeleton className="h-16 rounded-xl" />
        ) : dueCount === 0 ? (
          <Empty>Nothing due in the next 7 days.</Empty>
        ) : (
          <ul className="space-y-2">
            {[...(v?.overdue ?? []), ...(v?.due_today ?? []), ...(v?.due_this_week ?? [])]
              .slice(0, 4)
              .map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-2 text-sm">
                  <span className="min-w-0">
                    <span className="block truncate text-gray-800 dark:text-gray-200">
                      {item.next_vaccine_name ?? item.vaccine_name}
                    </span>
                    <span className="text-[11px] text-gray-400 dark:text-gray-500">
                      {item.flock_name}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
                      item.is_overdue
                        ? "bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300"
                        : item.days_until_due === 0
                          ? "bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300"
                          : "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400",
                    )}
                  >
                    {item.is_overdue
                      ? `${Math.abs(item.days_until_due)}d overdue`
                      : item.days_until_due === 0
                        ? "Today"
                        : `${item.days_until_due}d`}
                  </span>
                </li>
              ))}
          </ul>
        )}
      </Section>

      {/* Weather — honestly not connected, never fabricated. */}
      <Section title="Weather" icon={CloudOff}>
        <Empty>
          Weather isn't connected yet. ARIA won't guess conditions it can't measure.
        </Empty>
      </Section>
    </aside>
  );
}

/* ── Pieces ──────────────────────────────────────────────────────────────── */

const TONES: Record<string, string> = {
  brand: "text-brand-600 dark:text-brand-400",
  navy: "text-navy-600 dark:text-navy-300",
  amber: "text-amber-600 dark:text-amber-400",
  red: "text-red-600 dark:text-red-400",
};

function Stat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone: keyof typeof TONES;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-white/10 dark:bg-white/[0.03]">
      <Icon className={cn("h-4 w-4", TONES[tone])} aria-hidden />
      <p className="mt-1.5 text-lg font-semibold tabular-nums tracking-tight text-gray-900 dark:text-white">
        {value}
      </p>
      <p className="text-[11px] text-gray-400 dark:text-gray-500">{label}</p>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  badge,
  children,
}: {
  title: string;
  icon: LucideIcon;
  badge?: number;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
        <Icon className="h-4 w-4 text-gray-400 dark:text-gray-500" aria-hidden />
        {title}
        {badge ? (
          <span className="ml-auto rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            {badge}
          </span>
        ) : null}
      </h3>
      {children}
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-xs leading-relaxed text-gray-400 dark:text-gray-500">{children}</p>;
}
