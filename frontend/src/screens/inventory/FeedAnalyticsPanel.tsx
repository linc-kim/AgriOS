/**
 * Greena — Feed analytics panel.
 * Usage trend (consumption vs purchases), cost per bird/egg by flock, and
 * supplier spend. Uses Recharts; theme-aware and responsive.
 */
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3 } from "lucide-react";

import { getFeedAnalytics } from "@/api/feed";
import { queryKeys } from "@/lib/queryClient";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";

const kes = (v: string | number | null | undefined) =>
  v == null ? "—" : `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
      <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
      {children}
    </section>
  );
}

export function FeedAnalyticsPanel({ farmId }: { farmId: string }) {
  const analyticsQuery = useQuery({
    queryKey: queryKeys.feedAnalytics(farmId),
    queryFn: () => getFeedAnalytics(farmId, 90),
    enabled: !!farmId,
  });

  if (analyticsQuery.isLoading) {
    return <Skeleton className="h-64 rounded-2xl" />;
  }
  const a = analyticsQuery.data;
  if (!a) return null;

  const hasActivity =
    a.usage_trend.length > 0 || a.by_flock.length > 0 || a.by_supplier.length > 0;

  if (!hasActivity) {
    return (
      <Card title="Analytics">
        <EmptyState
          icon={<BarChart3 className="h-5 w-5" />}
          title="No feed activity yet"
          description="Record purchases and consumption to see usage trends, cost per bird and per egg, and supplier spend."
        />
      </Card>
    );
  }

  const trend = a.usage_trend.map((p) => ({
    period: p.period.slice(5),
    Consumed: Number(p.consumed_kg),
    Purchased: Number(p.purchased_kg),
  }));
  const supplierData = a.by_supplier.map((s) => ({
    name: s.supplier_name,
    Spend: Number(s.total_cost_kes),
  }));

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {/* Usage trend */}
      <Card title="Feed usage (last 90 days, kg)">
        {trend.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">No movements yet.</p>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="consumed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#16a34a" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="purchased" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="period" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} />
                <Area type="monotone" dataKey="Purchased" stroke="#0ea5e9" fill="url(#purchased)" strokeWidth={2} />
                <Area type="monotone" dataKey="Consumed" stroke="#16a34a" fill="url(#consumed)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Supplier spend */}
      <Card title="Supplier spend (90 days)">
        {supplierData.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">No purchases attributed to suppliers yet.</p>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={supplierData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} formatter={(v: any) => kes(v)} />
                <Bar dataKey="Spend" fill="#16a34a" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Cost per bird / egg */}
      <Card title="Feed cost by flock">
        {a.by_flock.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">Record consumption against a flock to see cost per bird and per egg.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-[11px] uppercase tracking-wide text-gray-400 dark:border-white/10">
                  <th className="pb-2 pr-3 font-semibold">Flock</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Feed cost</th>
                  <th className="pb-2 pr-3 text-right font-semibold">/ bird</th>
                  <th className="pb-2 text-right font-semibold">/ egg</th>
                </tr>
              </thead>
              <tbody>
                {a.by_flock.map((f) => (
                  <tr key={f.flock_id} className="border-b border-gray-50 last:border-0 dark:border-white/5">
                    <td className="py-2.5 pr-3 font-medium text-gray-900 dark:text-white">{f.flock_name}</td>
                    <td className="py-2.5 pr-3 text-right text-gray-600 dark:text-gray-300">{kes(f.feed_cost_kes)}</td>
                    <td className="py-2.5 pr-3 text-right text-gray-600 dark:text-gray-300">{f.cost_per_bird_kes ? kes(f.cost_per_bird_kes) : "—"}</td>
                    <td className="py-2.5 text-right text-gray-600 dark:text-gray-300">{f.cost_per_egg_kes ? `KES ${Number(f.cost_per_egg_kes).toFixed(2)}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Feed type breakdown */}
      <Card title="Consumption by feed type">
        {a.by_feed_type.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">No consumption recorded yet.</p>
        ) : (
          <ul className="space-y-3">
            {a.by_feed_type.map((b) => (
              <li key={b.feed_type}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-800 dark:text-gray-200">{b.feed_type}</span>
                  <span className="text-gray-500 dark:text-gray-400">{Number(b.consumed_kg).toLocaleString()} kg · {kes(b.consumed_cost_kes)}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-white/10">
                  <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, Number(b.pct_of_total ?? 0))}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
