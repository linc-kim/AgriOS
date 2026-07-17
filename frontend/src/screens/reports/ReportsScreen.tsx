/**
 * Greena — Reporting & Business Intelligence workspace (Module 7).
 * Tabs: Reports | Dashboards | Comparisons | Saved. Renders any report from a
 * uniform section-based payload (KPIs, charts, tables, breakdowns).
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Download, Star, Trash2, Pin, BarChart3 } from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import {
  generateReport, getRoleDashboard, getComparison, downloadReportCsv,
  listSavedReports, createSavedReport, updateSavedReport, deleteSavedReport,
} from "@/api/reporting";
import { listFlocks } from "@/api/flocks";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Report, ReportSection } from "@/types";

type Tab = "reports" | "dashboards" | "comparisons" | "saved";

const REPORT_TYPES = [
  "farm_summary", "production", "finance", "feed", "health", "inventory",
  "mortality", "vaccination", "sales", "purchases", "assets", "maintenance",
  "staff_activity", "ai_insights",
].map((v) => ({ value: v, label: v.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) }));

const PERIODS = [
  { value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" }, { value: "quarterly", label: "Quarterly" },
  { value: "annual", label: "Annual" }, { value: "custom", label: "Custom range" },
];

const ROLES = [
  { value: "executive", label: "Executive" }, { value: "farm_manager", label: "Farm Manager" },
  { value: "veterinary", label: "Veterinary" }, { value: "finance", label: "Finance" },
  { value: "production", label: "Production" }, { value: "inventory", label: "Inventory" },
];

const COLORS = ["#16a34a", "#0ea5e9", "#ef4444", "#f59e0b", "#8b5cf6"];
const toneCls = (t?: string | null) => t === "pos" ? "text-brand-600 dark:text-brand-300" : t === "neg" ? "text-red-600 dark:text-red-400" : t === "warn" ? "text-amber-600 dark:text-amber-400" : "text-gray-900 dark:text-white";

// ── Generic section renderer ──────────────────────────────────────────────────

function SectionView({ section }: { section: ReportSection }) {
  if (section.kind === "kpis") {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {section.kpis.map((k, i) => (
          <div key={i} className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{k.label}</p>
            <p className={`mt-1.5 text-lg font-semibold ${toneCls(k.tone)}`}>{k.value}</p>
            {k.sub && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{k.sub}</p>}
          </div>
        ))}
      </div>
    );
  }
  if (section.kind === "series") {
    const multi = section.series_keys.length > 1;
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{section.heading}</h3>
        {section.series.length === 0 ? <p className="py-8 text-center text-sm text-gray-400">No data in this period.</p> : (
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              {multi ? (
                <BarChart data={section.series} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                  <XAxis dataKey="period" tickFormatter={(v) => String(v).slice(5)} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} />
                  {section.series_keys.map((k, i) => <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} />)}
                </BarChart>
              ) : (
                <AreaChart data={section.series} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
                  <defs><linearGradient id="rg" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#16a34a" stopOpacity={0.4} /><stop offset="95%" stopColor="#16a34a" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                  <XAxis dataKey="period" tickFormatter={(v) => String(v).slice(5)} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} />
                  <Area type="monotone" dataKey={section.series_keys[0]} stroke="#16a34a" fill="url(#rg)" strokeWidth={2} />
                </AreaChart>
              )}
            </ResponsiveContainer>
          </div>
        )}
      </div>
    );
  }
  if (section.kind === "breakdown") {
    const max = Math.max(1, ...section.breakdown.map((b) => Number(String(b.value).replace(/[^0-9.]/g, "")) || 0));
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{section.heading}</h3>
        {section.breakdown.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No data.</p> : (
          <ul className="space-y-3">
            {section.breakdown.map((b, i) => {
              const v = Number(String(b.value).replace(/[^0-9.]/g, "")) || 0;
              return (
                <li key={i}>
                  <div className="mb-1 flex items-center justify-between text-sm"><span className="font-medium text-gray-800 dark:text-gray-200">{b.label}</span><span className="text-gray-500 dark:text-gray-400">{b.value}{b.pct ? ` · ${b.pct}%` : ""}</span></div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-white/10"><div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, (v / max) * 100)}%` }} /></div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    );
  }
  if (section.kind === "table") {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{section.heading}</h3>
        {section.table_rows.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No records.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-100 text-left text-[11px] uppercase tracking-wide text-gray-400 dark:border-white/10">{section.table_columns.map((c, i) => <th key={i} className="px-2 pb-2 font-semibold">{c}</th>)}</tr></thead>
              <tbody>{section.table_rows.map((row, ri) => (
                <tr key={ri} className="border-b border-gray-50 last:border-0 dark:border-white/5">{row.map((cell, ci) => <td key={ci} className={`px-2 py-2.5 ${ci === 0 ? "font-medium text-gray-900 dark:text-white" : "text-gray-600 dark:text-gray-300"}`}>{String(cell)}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
    );
  }
  return <div className="rounded-2xl border border-gray-200 bg-white p-5 text-sm text-gray-500 dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-400"><h3 className="mb-1 font-semibold text-gray-900 dark:text-white">{section.heading}</h3>{section.note}</div>;
}

function ReportView({ report }: { report: Report }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{report.title}</h2>
        <span className="text-sm text-gray-500 dark:text-gray-400">{report.period_label}</span>
      </div>
      {report.sections.map((s, i) => <SectionView key={i} section={s} />)}
    </div>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

export default function ReportsScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [tab, setTab] = useState<Tab>("reports");

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Reports</h1>
        <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">Farm-wide reports, role dashboards, comparisons and exports.</p>
      </header>

      <div className="flex gap-1 overflow-x-auto border-b border-gray-200 dark:border-white/10">
        {(["reports", "dashboards", "comparisons", "saved"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium capitalize transition-colors ${tab === t ? "border-brand-500 text-brand-600 dark:text-brand-300" : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "reports" && farmId && <ReportsTab farmId={farmId} />}
      {tab === "dashboards" && farmId && <DashboardsTab farmId={farmId} />}
      {tab === "comparisons" && farmId && <ComparisonsTab farmId={farmId} />}
      {tab === "saved" && farmId && <SavedTab farmId={farmId} onOpen={() => setTab("reports")} />}
    </div>
  );
}

function ReportsTab({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [reportType, setReportType] = useState("farm_summary");
  const [period, setPeriod] = useState("monthly");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [downloading, setDownloading] = useState(false);

  const params = { report_type: reportType, period_type: period, start: period === "custom" ? start : undefined, end: period === "custom" ? end : undefined };
  const query = useQuery({
    queryKey: [...queryKeys.reportGenerate(farmId), reportType, period, start, end],
    queryFn: () => generateReport(farmId, params),
    enabled: !!farmId && (period !== "custom" || (!!start && !!end)),
  });

  const save = useMutation({
    mutationFn: () => createSavedReport(farmId, { name: `${REPORT_TYPES.find((r) => r.value === reportType)?.label} (${period})`, report_type: reportType, config: { period_type: period }, is_pinned: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.savedReports(farmId) }),
  });

  const doDownload = async () => {
    setDownloading(true);
    try {
      const blob = await downloadReportCsv(farmId, params);
      const url = URL.createObjectURL(blob); const a = document.createElement("a");
      a.href = url; a.download = `${reportType}_report.csv`; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    } finally { setDownloading(false); }
  };

  const input = "rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <Select label="" options={REPORT_TYPES} value={reportType} onChange={(e) => setReportType(e.target.value)} />
        <Select label="" options={PERIODS} value={period} onChange={(e) => setPeriod(e.target.value)} />
        {period === "custom" && <><input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={input} aria-label="Start" /><input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={input} aria-label="End" /></>}
        <Button size="sm" variant="secondary" onClick={doDownload} loading={downloading} leftIcon={<Download className="h-4 w-4" />}>CSV</Button>
        <Button size="sm" variant="secondary" onClick={() => save.mutate()} loading={save.isPending} leftIcon={<Pin className="h-4 w-4" />}>Save & pin</Button>
      </div>
      {query.isLoading ? <Skeleton className="h-64 rounded-2xl" /> : query.data ? <ReportView report={query.data} /> : <EmptyState icon={<FileText className="h-6 w-6" />} title="Select a report" description="Choose a report type and period." />}
    </div>
  );
}

function DashboardsTab({ farmId }: { farmId: string }) {
  const [role, setRole] = useState("executive");
  const query = useQuery({ queryKey: [...queryKeys.reportDashboard(farmId), role], queryFn: () => getRoleDashboard(farmId, role), enabled: !!farmId });
  return (
    <div className="space-y-5">
      <Select label="" options={ROLES} value={role} onChange={(e) => setRole(e.target.value)} />
      {query.isLoading ? <Skeleton className="h-64 rounded-2xl" /> : query.data ? <ReportView report={query.data} /> : null}
    </div>
  );
}

function ComparisonsTab({ farmId }: { farmId: string }) {
  const [type, setType] = useState("month_vs_month");
  const [flockA, setFlockA] = useState("");
  const [flockB, setFlockB] = useState("");
  const flocksQuery = useQuery({ queryKey: ["flocks", farmId], queryFn: () => listFlocks(farmId), enabled: type === "flock_vs_flock" });
  const flocks = flocksQuery.data ?? [];
  const ready = type !== "flock_vs_flock" || (flockA && flockB && flockA !== flockB);
  const query = useQuery({
    queryKey: [...queryKeys.reportComparison(farmId), type, flockA, flockB],
    queryFn: () => getComparison(farmId, type, flockA || undefined, flockB || undefined),
    enabled: !!farmId && !!ready,
  });
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <Select label="" options={[{ value: "month_vs_month", label: "Month vs Month" }, { value: "year_vs_year", label: "Year vs Year" }, { value: "flock_vs_flock", label: "Flock vs Flock" }]} value={type} onChange={(e) => setType(e.target.value)} />
        {type === "flock_vs_flock" && (
          <>
            <Select label="" options={[{ value: "", label: "Flock A" }, ...flocks.map((f) => ({ value: f.id, label: f.name }))]} value={flockA} onChange={(e) => setFlockA(e.target.value)} />
            <Select label="" options={[{ value: "", label: "Flock B" }, ...flocks.map((f) => ({ value: f.id, label: f.name }))]} value={flockB} onChange={(e) => setFlockB(e.target.value)} />
          </>
        )}
      </div>
      {!ready ? <EmptyState icon={<BarChart3 className="h-6 w-6" />} title="Pick two flocks" description="Select two different flocks to compare." /> : query.isLoading ? <Skeleton className="h-48 rounded-2xl" /> : query.data ? <ReportView report={query.data} /> : null}
    </div>
  );
}

function SavedTab({ farmId, onOpen }: { farmId: string; onOpen: () => void }) {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.savedReports(farmId), queryFn: () => listSavedReports(farmId), enabled: !!farmId });
  const rows = query.data ?? [];
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.savedReports(farmId) });
  const pin = useMutation({ mutationFn: (r: { id: string; is_pinned: boolean }) => updateSavedReport(farmId, r.id, { is_pinned: !r.is_pinned }), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: string) => deleteSavedReport(farmId, id), onSuccess: invalidate });

  if (query.isLoading) return <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div>;
  if (rows.length === 0) return <EmptyState icon={<Star className="h-6 w-6" />} title="No saved reports" description="Save & pin reports from the Reports tab for quick access." />;
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.id} className="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
          <button onClick={onOpen} className="min-w-0 text-left">
            <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{r.name}</p>
            <p className="truncate text-xs text-gray-400">{r.report_type.replace(/_/g, " ")} · {r.config?.period_type ?? "monthly"}</p>
          </button>
          <div className="flex shrink-0 gap-1">
            <button onClick={() => pin.mutate(r)} aria-label="Pin" className={`rounded-lg p-1.5 ${r.is_pinned ? "text-amber-500" : "text-gray-400"} hover:bg-gray-100 dark:hover:bg-white/10`}><Star className="h-4 w-4" fill={r.is_pinned ? "currentColor" : "none"} /></button>
            <button onClick={() => remove.mutate(r.id)} aria-label="Delete" className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"><Trash2 className="h-4 w-4" /></button>
          </div>
        </li>
      ))}
    </ul>
  );
}
