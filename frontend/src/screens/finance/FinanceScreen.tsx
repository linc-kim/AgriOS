/**
 * Greena — Finance workspace.
 * Tabbed farm financial system: Dashboard, Revenue, Expenses, Transactions,
 * Analytics, and Reports. Reads from the finance analytics layer and logs
 * revenue/expenses via the Finance API. Wired to the real backend.
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Wallet, TrendingUp, Plus, ArrowDownRight, ArrowUpRight,
  Download, Banknote, PiggyBank, Receipt, Search,
} from "lucide-react";

import {
  getFinanceOverview, getFinanceAnalytics, getFinanceTransactions,
  getFinanceCashflow, getFinanceReport, downloadFinanceCsv,
} from "@/api/financeAnalytics";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type {
  FinanceOverview, FinanceAnalytics, FinTransactionRow, FinCategoryAmount,
} from "@/types";
import { LogExpenseModal, LogRevenueModal } from "./FinanceModals";
import { RevenueExpenseChart, ProfitTrendChart, CategoryChart, CashflowChart } from "./FinanceCharts";

const kes = (v: string | number | null | undefined) =>
  v == null ? "—" : `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const kes2 = (v: string | number | null | undefined) =>
  v == null ? "—" : `KES ${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (v: string | null | undefined) => (v == null ? "—" : `${Number(v).toFixed(1)}%`);
const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString() : "—");

type Tab = "dashboard" | "revenue" | "expenses" | "transactions" | "analytics" | "reports";

function StatTile({ icon: Icon, label, value, sub, tone }: { icon: typeof Wallet; label: string; value: string; sub?: string; tone?: "pos" | "neg" }) {
  const toneCls = tone === "pos" ? "text-brand-500" : tone === "neg" ? "text-red-500" : "text-gray-400";
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className={`flex items-center gap-2 ${toneCls}`}>
        <Icon className="h-4 w-4" />
        <span className="text-[11px] font-semibold uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-2 text-xl font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{sub}</p>}
    </div>
  );
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function FinanceScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [modal, setModal] = useState<null | "revenue" | "expense">(null);

  const overviewQuery = useQuery({
    queryKey: queryKeys.financeOverview(farmId!),
    queryFn: () => getFinanceOverview(farmId!),
    enabled: !!farmId,
  });

  const invalidateAll = () => {
    if (!farmId) return;
    for (const k of [
      queryKeys.financeOverview(farmId), queryKeys.financeAnalytics(farmId),
      queryKeys.financeTransactions(farmId), queryKeys.financeCashflow(farmId),
      queryKeys.financeReport(farmId),
    ]) qc.invalidateQueries({ queryKey: k });
  };
  const afterSave = () => { setModal(null); invalidateAll(); };

  const TABS: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "revenue", label: "Revenue" },
    { id: "expenses", label: "Expenses" },
    { id: "transactions", label: "Transactions" },
    { id: "analytics", label: "Analytics" },
    { id: "reports", label: "Reports" },
  ];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Finance</h1>
          <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">Revenue, expenses, cash flow and profitability across your farm.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => setModal("expense")} leftIcon={<ArrowDownRight className="h-4 w-4" />}>Expense</Button>
          <Button size="sm" onClick={() => setModal("revenue")} leftIcon={<ArrowUpRight className="h-4 w-4" />}>Revenue</Button>
        </div>
      </header>

      <div className="flex gap-1 overflow-x-auto border-b border-gray-200 dark:border-white/10">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-brand-500 text-brand-600 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab overview={overviewQuery.data} loading={overviewQuery.isLoading} onRecord={() => setModal("revenue")} />}
      {tab === "revenue" && farmId && <LedgerTab farmId={farmId} kind="revenue" onRecord={() => setModal("revenue")} overview={overviewQuery.data} />}
      {tab === "expenses" && farmId && <LedgerTab farmId={farmId} kind="expense" onRecord={() => setModal("expense")} overview={overviewQuery.data} />}
      {tab === "transactions" && farmId && <TransactionsTab farmId={farmId} />}
      {tab === "analytics" && farmId && <AnalyticsTab farmId={farmId} />}
      {tab === "reports" && farmId && <ReportsTab farmId={farmId} />}

      {modal === "revenue" && farmId && <LogRevenueModal farmId={farmId} onClose={() => setModal(null)} onSaved={afterSave} />}
      {modal === "expense" && farmId && <LogExpenseModal farmId={farmId} onClose={() => setModal(null)} onSaved={afterSave} />}
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

function DashboardTab({ overview, loading, onRecord }: { overview: FinanceOverview | undefined; loading: boolean; onRecord: () => void }) {
  const d = overview;
  const hasData = d && (Number(d.cash_balance) !== 0 || d.recent_transactions.length > 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)
        ) : (
          <>
            <StatTile icon={ArrowUpRight} label="Today revenue" value={d ? kes(d.today_revenue) : "—"} tone="pos" />
            <StatTile icon={ArrowDownRight} label="Today expenses" value={d ? kes(d.today_expenses) : "—"} tone="neg" />
            <StatTile icon={TrendingUp} label="Today profit" value={d ? kes(d.today_profit) : "—"} tone={d && Number(d.today_profit) < 0 ? "neg" : "pos"} />
            <StatTile icon={PiggyBank} label="Cash balance" value={d ? kes(d.cash_balance) : "—"} sub={d ? `${kes(d.outstanding_costs)} outstanding` : undefined} />
          </>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {!loading && (
          <>
            <StatTile icon={Wallet} label="30-day revenue" value={d ? kes(d.m30_revenue) : "—"} tone="pos" />
            <StatTile icon={Receipt} label="30-day expenses" value={d ? kes(d.m30_expenses) : "—"} tone="neg" />
            <StatTile icon={TrendingUp} label="30-day profit" value={d ? kes(d.m30_profit) : "—"} tone={d && Number(d.m30_profit) < 0 ? "neg" : "pos"} />
            <StatTile icon={Banknote} label="Top expense" value={d?.top_expense_category ? kes(d.top_expense_category.amount) : "—"} sub={d?.top_expense_category?.name} />
          </>
        )}
      </div>

      {loading ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : !hasData ? (
        <EmptyState
          icon={<Wallet className="h-6 w-6" />}
          title="No financial activity yet"
          description="Record revenue and expenses to see your farm's cash flow, profit trend and category breakdown."
          action={<Button onClick={onRecord} leftIcon={<Plus className="h-4 w-4" />}>Record revenue</Button>}
        />
      ) : d && (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Revenue vs expenses (30 days)"><RevenueExpenseChart data={d.revenue_series} /></Card>
            <Card title="Profit trend (30 days)"><ProfitTrendChart data={d.profit_trend} /></Card>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Expense categories (30 days)">
              {d.category_breakdown.length === 0 ? <p className="py-8 text-center text-sm text-gray-400">No expenses in the last 30 days.</p> : <CategoryChart data={d.category_breakdown} />}
            </Card>
            <Card title="Revenue by type (30 days)">
              {d.revenue_by_type.length === 0 ? (
                <p className="py-8 text-center text-sm text-gray-400">No revenue in the last 30 days.</p>
              ) : (
                <ul className="space-y-3">
                  {d.revenue_by_type.map((r) => (
                    <li key={r.revenue_type}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="font-medium capitalize text-gray-800 dark:text-gray-200">{r.revenue_type}</span>
                        <span className="text-gray-500 dark:text-gray-400">{kes(r.amount)}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-white/10">
                        <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, Number(r.pct_of_total ?? 0))}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
          <Card title="Recent activity">
            {d.recent_transactions.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No transactions yet.</p> : <TxnList rows={d.recent_transactions} />}
          </Card>
        </>
      )}
    </div>
  );
}

// ── Revenue / Expense ledger tabs ─────────────────────────────────────────────

function LedgerTab({ farmId, kind, onRecord, overview }: { farmId: string; kind: "revenue" | "expense"; onRecord: () => void; overview: FinanceOverview | undefined }) {
  const query = useQuery({
    queryKey: [...queryKeys.financeTransactions(farmId), kind],
    queryFn: () => getFinanceTransactions(farmId, { kind, page_size: 100, sort: "date_desc" }),
    enabled: !!farmId,
  });
  const page = query.data;
  const breakdown: FinCategoryAmount[] = kind === "expense" ? (overview?.category_breakdown ?? []) : [];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatTile icon={kind === "revenue" ? ArrowUpRight : ArrowDownRight} label={`Total ${kind}`} value={page ? kes(kind === "revenue" ? page.total_revenue : page.total_expenses) : "—"} tone={kind === "revenue" ? "pos" : "neg"} />
        <StatTile icon={Receipt} label="Entries" value={page ? String(page.total) : "—"} />
        {kind === "expense" && <StatTile icon={Banknote} label="Categories" value={String(breakdown.length)} />}
      </div>

      {kind === "expense" && breakdown.length > 0 && (
        <Card title="By category (30 days)"><CategoryChart data={breakdown} /></Card>
      )}

      <Card title={kind === "revenue" ? "Revenue records" : "Expense records"} action={<Button size="sm" variant="secondary" onClick={onRecord} leftIcon={<Plus className="h-4 w-4" />}>{kind === "revenue" ? "Record revenue" : "Record expense"}</Button>}>
        {query.isLoading ? (
          <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 rounded-xl" />)}</div>
        ) : !page || page.items.length === 0 ? (
          <EmptyState icon={<Receipt className="h-5 w-5" />} title={`No ${kind} yet`} description={`Record ${kind} to start tracking it here.`} />
        ) : (
          <TxnList rows={page.items} />
        )}
      </Card>
    </div>
  );
}

// ── Transactions (search / filter / sort / paginate) ──────────────────────────

function TransactionsTab({ farmId }: { farmId: string }) {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [sort, setSort] = useState("date_desc");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const query = useQuery({
    queryKey: [...queryKeys.financeTransactions(farmId), "search", q, kind, sort, dateFrom, dateTo, minAmount, page],
    queryFn: () => getFinanceTransactions(farmId, {
      q: q || undefined, kind: (kind || undefined) as any, sort,
      date_from: dateFrom || undefined, date_to: dateTo || undefined,
      min_amount: minAmount || undefined, page, page_size: pageSize,
    }),
    enabled: !!farmId,
  });
  const data = query.data;
  const pageCount = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  const input = "rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-[180px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search description, supplier, buyer…" className={`${input} w-full pl-9`} />
        </div>
        <Select label="" options={[{ value: "", label: "All types" }, { value: "revenue", label: "Revenue" }, { value: "expense", label: "Expense" }]} value={kind} onChange={(e) => { setKind(e.target.value); setPage(1); }} />
        <Select label="" options={[{ value: "date_desc", label: "Newest" }, { value: "date_asc", label: "Oldest" }, { value: "amount_desc", label: "Amount ↓" }, { value: "amount_asc", label: "Amount ↑" }]} value={sort} onChange={(e) => setSort(e.target.value)} />
        <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} className={input} aria-label="From date" />
        <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} className={input} aria-label="To date" />
        <input type="number" min={0} value={minAmount} onChange={(e) => { setMinAmount(e.target.value); setPage(1); }} placeholder="Min KES" className={`${input} w-28`} aria-label="Minimum amount" />
      </div>

      {data && (
        <div className="flex flex-wrap gap-4 text-sm">
          <span className="text-gray-500 dark:text-gray-400">Revenue <span className="font-semibold text-brand-600 dark:text-brand-300">{kes(data.total_revenue)}</span></span>
          <span className="text-gray-500 dark:text-gray-400">Expenses <span className="font-semibold text-red-600 dark:text-red-400">{kes(data.total_expenses)}</span></span>
          <span className="text-gray-500 dark:text-gray-400">Net <span className={`font-semibold ${Number(data.net) < 0 ? "text-red-600 dark:text-red-400" : "text-gray-900 dark:text-white"}`}>{kes(data.net)}</span></span>
        </div>
      )}

      {query.isLoading ? (
        <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12 rounded-xl" />)}</div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState icon={<Search className="h-5 w-5" />} title="No transactions" description="Adjust your filters, or record revenue and expenses." />
      ) : (
        <>
          <div className="rounded-2xl border border-gray-200 dark:border-white/10">
            <TxnList rows={data.items} />
          </div>
          {pageCount > 1 && (
            <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>{data.total} transactions · page {page} of {pageCount}</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                <Button variant="secondary" size="sm" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Analytics ─────────────────────────────────────────────────────────────────

const WINDOW_LABEL: Record<string, string> = { "7d": "7 days", "30d": "30 days", "90d": "90 days", ytd: "Year to date", lifetime: "Lifetime" };

function AnalyticsTab({ farmId }: { farmId: string }) {
  const analyticsQuery = useQuery({
    queryKey: queryKeys.financeAnalytics(farmId),
    queryFn: () => getFinanceAnalytics(farmId),
    enabled: !!farmId,
  });
  const cashflowQuery = useQuery({
    queryKey: queryKeys.financeCashflow(farmId),
    queryFn: () => getFinanceCashflow(farmId, 12),
    enabled: !!farmId,
  });
  const a: FinanceAnalytics | undefined = analyticsQuery.data;

  if (analyticsQuery.isLoading) return <Skeleton className="h-64 rounded-2xl" />;
  if (!a) return null;

  const pu = a.per_unit;
  const growthCls = (v: string | null) => (v == null ? "text-gray-400" : Number(v) < 0 ? "text-red-500" : "text-brand-500");

  return (
    <div className="space-y-6">
      {/* Rolling windows */}
      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-5">
        {a.windows.map((w) => (
          <div key={w.window} className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{WINDOW_LABEL[w.window] ?? w.window}</p>
            <p className={`mt-1.5 text-lg font-semibold ${Number(w.net_profit) < 0 ? "text-red-600 dark:text-red-400" : "text-gray-900 dark:text-white"}`}>{kes(w.net_profit)}</p>
            <p className="text-xs text-gray-400">net profit</p>
            <div className="mt-2 space-y-0.5 text-xs">
              <div className="flex justify-between"><span className="text-gray-400">Revenue</span><span className="text-gray-700 dark:text-gray-200">{kes(w.revenue)}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Expenses</span><span className="text-gray-700 dark:text-gray-200">{kes(w.expenses)}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Margin</span><span className="text-gray-700 dark:text-gray-200">{pct(w.net_margin_pct)}</span></div>
              {w.revenue_growth_pct != null && (
                <div className="flex justify-between"><span className="text-gray-400">Rev growth</span><span className={growthCls(w.revenue_growth_pct)}>{Number(w.revenue_growth_pct) >= 0 ? "+" : ""}{pct(w.revenue_growth_pct)}</span></div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Per-unit economics */}
      <Card title="Unit economics (lifetime)">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <UnitStat label="Cost / bird" value={kes2(pu.cost_per_bird)} />
          <UnitStat label="Revenue / bird" value={kes2(pu.revenue_per_bird)} />
          <UnitStat label="Profit / bird" value={kes2(pu.profit_per_bird)} tone={pu.profit_per_bird != null && Number(pu.profit_per_bird) < 0 ? "neg" : "pos"} />
          <UnitStat label="Cost / egg" value={kes2(pu.cost_per_egg)} />
          <UnitStat label="Revenue / egg" value={kes2(pu.revenue_per_egg)} />
          <UnitStat label="Profit / egg" value={kes2(pu.profit_per_egg)} tone={pu.profit_per_egg != null && Number(pu.profit_per_egg) < 0 ? "neg" : "pos"} />
          <UnitStat label="Cost / kg" value={kes2(pu.cost_per_kg)} />
          <UnitStat label="Revenue / kg" value={kes2(pu.revenue_per_kg)} />
          <UnitStat label="Birds · eggs · kg" value={`${pu.total_birds} · ${pu.total_eggs} · ${Number(pu.total_kg).toFixed(0)}`} />
        </div>
      </Card>

      {/* Cash flow */}
      <Card title="Cash flow (12 months)">
        {cashflowQuery.isLoading ? <Skeleton className="h-64 rounded-xl" /> : cashflowQuery.data && cashflowQuery.data.points.length > 0 ? (
          <CashflowChart data={cashflowQuery.data.points} />
        ) : <p className="py-8 text-center text-sm text-gray-400">No cash flow yet.</p>}
      </Card>

      {/* Cost centres */}
      <Card title="Cost centres (per flock)">
        {a.cost_centres.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">Attribute revenue and expenses to flocks to see per-flock P&L.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-[11px] uppercase tracking-wide text-gray-400 dark:border-white/10">
                  <th className="pb-2 pr-3 font-semibold">Flock</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Revenue</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Expenses</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Profit</th>
                  <th className="pb-2 text-right font-semibold">Margin</th>
                </tr>
              </thead>
              <tbody>
                {a.cost_centres.map((c) => (
                  <tr key={c.flock_id} className="border-b border-gray-50 last:border-0 dark:border-white/5">
                    <td className="py-2.5 pr-3 font-medium text-gray-900 dark:text-white">{c.flock_name}</td>
                    <td className="py-2.5 pr-3 text-right text-gray-600 dark:text-gray-300">{kes(c.revenue)}</td>
                    <td className="py-2.5 pr-3 text-right text-gray-600 dark:text-gray-300">{kes(c.expenses)}</td>
                    <td className={`py-2.5 pr-3 text-right font-medium ${Number(c.profit) < 0 ? "text-red-600 dark:text-red-400" : "text-brand-600 dark:text-brand-300"}`}>{kes(c.profit)}</td>
                    <td className="py-2.5 text-right text-gray-600 dark:text-gray-300">{pct(c.margin_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function UnitStat({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="rounded-xl border border-gray-100 p-3 dark:border-white/5">
      <p className="text-[11px] uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${tone === "neg" ? "text-red-600 dark:text-red-400" : tone === "pos" ? "text-brand-600 dark:text-brand-300" : "text-gray-900 dark:text-white"}`}>{value}</p>
    </div>
  );
}

// ── Reports ───────────────────────────────────────────────────────────────────

function ReportsTab({ farmId }: { farmId: string }) {
  const now = new Date();
  const [periodType, setPeriodType] = useState<"monthly" | "quarterly" | "yearly">("monthly");
  const [year, setYear] = useState(now.getFullYear());
  const [index, setIndex] = useState(now.getMonth() + 1);
  const [downloading, setDownloading] = useState(false);

  const query = useQuery({
    queryKey: [...queryKeys.financeReport(farmId), periodType, year, index],
    queryFn: () => getFinanceReport(farmId, periodType, year, index),
    enabled: !!farmId,
  });
  const r = query.data;

  const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i);
  const indexOptions = periodType === "quarterly"
    ? [1, 2, 3, 4].map((q) => ({ value: String(q), label: `Q${q}` }))
    : periodType === "monthly"
    ? Array.from({ length: 12 }, (_, i) => ({ value: String(i + 1), label: new Date(2000, i, 1).toLocaleString(undefined, { month: "long" }) }))
    : [];

  const doDownload = async () => {
    setDownloading(true);
    try {
      const blob = await downloadFinanceCsv(farmId, { date_from: r?.start_date, date_to: r?.end_date });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `finance_${periodType}_${r?.period_label ?? ""}.csv`.replace(/\s+/g, "_");
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <Select label="" options={[{ value: "monthly", label: "Monthly" }, { value: "quarterly", label: "Quarterly" }, { value: "yearly", label: "Yearly" }]} value={periodType} onChange={(e) => setPeriodType(e.target.value as any)} />
        <Select label="" options={years.map((y) => ({ value: String(y), label: String(y) }))} value={String(year)} onChange={(e) => setYear(Number(e.target.value))} />
        {periodType !== "yearly" && <Select label="" options={indexOptions} value={String(index)} onChange={(e) => setIndex(Number(e.target.value))} />}
        <Button variant="secondary" size="sm" loading={downloading} onClick={doDownload} leftIcon={<Download className="h-4 w-4" />}>Export CSV</Button>
      </div>

      {query.isLoading ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : r ? (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile icon={ArrowUpRight} label="Revenue" value={kes(r.total_revenue)} tone="pos" />
            <StatTile icon={ArrowDownRight} label="Expenses" value={kes(r.total_expenses)} tone="neg" />
            <StatTile icon={TrendingUp} label="Gross profit" value={kes(r.gross_profit)} sub="revenue − direct costs" />
            <StatTile icon={TrendingUp} label="Net profit" value={kes(r.net_profit)} sub={`${pct(r.net_margin_pct)} margin`} tone={Number(r.net_profit) < 0 ? "neg" : "pos"} />
          </div>

          <Card title={`${r.period_label} — monthly breakdown`}>
            {r.monthly_breakdown.length > 0 ? <RevenueExpenseChart data={r.monthly_breakdown} /> : <p className="py-8 text-center text-sm text-gray-400">No data.</p>}
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Revenue by type">
              {r.revenue_by_type.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No revenue.</p> : (
                <ul className="space-y-2">
                  {r.revenue_by_type.map((rt) => (
                    <li key={rt.revenue_type} className="flex items-center justify-between text-sm">
                      <span className="font-medium capitalize text-gray-800 dark:text-gray-200">{rt.revenue_type}</span>
                      <span className="text-gray-500 dark:text-gray-400">{kes(rt.amount)} · {pct(rt.pct_of_total)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Expenses by category">
              {r.expense_by_category.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No expenses.</p> : (
                <ul className="space-y-2">
                  {r.expense_by_category.map((c) => (
                    <li key={c.slug} className="flex items-center justify-between text-sm">
                      <span className="font-medium text-gray-800 dark:text-gray-200">{c.icon} {c.name}</span>
                      <span className="text-gray-500 dark:text-gray-400">{kes(c.amount)} · {pct(c.pct_of_total)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}

// ── Shared transaction list ───────────────────────────────────────────────────

function TxnList({ rows }: { rows: FinTransactionRow[] }) {
  return (
    <ul className="divide-y divide-gray-100 dark:divide-white/5">
      {rows.map((t) => {
        const isRev = t.kind === "revenue";
        return (
          <li key={`${t.kind}-${t.id}`} className="flex items-center justify-between gap-3 px-1 py-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm ${isRev ? "bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300" : "bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300"}`}>
                {t.icon ?? (isRev ? "＋" : "－")}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{t.label}</p>
                <p className="truncate text-xs text-gray-400">
                  {fmtDate(t.txn_date)}{t.flock_name ? ` · ${t.flock_name}` : ""}{t.description ? ` · ${t.description}` : ""}{t.payment_method ? ` · ${t.payment_method}` : ""}
                </p>
              </div>
            </div>
            <span className={`shrink-0 text-sm font-semibold ${isRev ? "text-brand-600 dark:text-brand-300" : "text-red-600 dark:text-red-400"}`}>
              {isRev ? "+" : "−"}{kes(t.amount)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
