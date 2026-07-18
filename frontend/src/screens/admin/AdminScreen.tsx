/**
 * Greena — Admin Platform workspace (Module 10).
 * Platform administration: Dashboard, Organizations, Users, Farms, Audit,
 * Analytics, Feature Flags, System (config + maintenance), Health, Jobs, plus
 * an admin AI assistant. Platform-admin only. Wired to the real backend.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  ShieldCheck, Building2, Users, Sprout, ScrollText, BarChart3, ToggleLeft, Settings2,
  HeartPulse, Cpu, Search, Download, Play, Sparkles, Send, Bot,
} from "lucide-react";

import * as api from "@/api/adminPlatform";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";

const kes = (v: any) => (v == null ? "—" : `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`);
const cap = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const fmtDT = (d?: string | null) => (d ? new Date(d).toLocaleString() : "—");

type Tab = "dashboard" | "organizations" | "users" | "farms" | "audit" | "analytics" | "flags" | "system" | "health" | "jobs" | "assistant";

const STATUS_CLS: Record<string, string> = {
  ok: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
  success: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
  degraded: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  down: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  failed: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  not_configured: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-300",
  running: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  queued: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-300",
};

const input = "rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white";

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "danger" }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1.5 text-xl font-semibold ${tone === "danger" ? "text-red-600 dark:text-red-400" : "text-gray-900 dark:text-white"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{sub}</p>}
    </div>
  );
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>{action}</div>
      {children}
    </section>
  );
}

const TABS: { id: Tab; label: string; icon: typeof Users }[] = [
  { id: "dashboard", label: "Dashboard", icon: ShieldCheck },
  { id: "organizations", label: "Organizations", icon: Building2 },
  { id: "users", label: "Users", icon: Users },
  { id: "farms", label: "Farms", icon: Sprout },
  { id: "audit", label: "Audit", icon: ScrollText },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "flags", label: "Feature Flags", icon: ToggleLeft },
  { id: "system", label: "System", icon: Settings2 },
  { id: "health", label: "Health", icon: HeartPulse },
  { id: "jobs", label: "Jobs", icon: Cpu },
  { id: "assistant", label: "Assistant", icon: Sparkles },
];

export default function AdminScreen() {
  const [tab, setTab] = useState<Tab>("dashboard");
  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300"><ShieldCheck className="h-5 w-5" /></span>
        <div><h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Administration</h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">Platform-wide management, analytics and system controls.</p></div>
      </header>

      <div className="flex gap-1 overflow-x-auto border-b border-gray-200 dark:border-white/10">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${tab === t.id ? "border-brand-500 text-brand-600 dark:text-brand-300" : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"}`}>
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "organizations" && <OrgsTab />}
      {tab === "users" && <UsersTab />}
      {tab === "farms" && <FarmsTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "analytics" && <AnalyticsTab />}
      {tab === "flags" && <FlagsTab />}
      {tab === "system" && <SystemTab />}
      {tab === "health" && <HealthTab />}
      {tab === "jobs" && <JobsTab />}
      {tab === "assistant" && <AssistantTab />}
    </div>
  );
}

function DashboardTab() {
  const q = useQuery({ queryKey: queryKeys.adminDashboard(), queryFn: api.getAdminDashboard });
  if (q.isLoading) return <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}</div>;
  const d = q.data!;
  return (
    <div className="space-y-6">
      {d.maintenance_mode && <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">⚠ Maintenance mode is ON — the platform is in read-only/maintenance state.</div>}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Organizations" value={String(d.organizations)} sub={`${d.suspended_orgs} suspended`} />
        <Tile label="Farms" value={String(d.farms)} />
        <Tile label="Users" value={String(d.users)} sub={`${d.active_users_today} active today`} />
        <Tile label="Suspended users" value={String(d.suspended_users)} tone={d.suspended_users > 0 ? "danger" : undefined} />
        <Tile label="Monthly revenue" value={kes(d.monthly_revenue_estimate)} />
        <Tile label="AI requests" value={String(d.ai_requests_total)} />
        <Tile label="System health" value={cap(d.health_status)} tone={d.health_status !== "ok" ? "danger" : undefined} />
        <Tile label="Jobs failed (24h)" value={String(d.jobs_failed_24h)} tone={d.jobs_failed_24h > 0 ? "danger" : undefined} />
      </div>
    </div>
  );
}

function OrgsTab() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: [...queryKeys.adminOrgs(), q, status, page], queryFn: () => api.listOrganizations({ q: q || undefined, status: status || undefined, page }) });
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.adminOrgs() });
  const suspend = useMutation({ mutationFn: (o: { id: string; suspend: boolean }) => (o.suspend ? api.suspendOrg(o.id) : api.reactivateOrg(o.id)), onSuccess: invalidate });
  const d = query.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-[180px] flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search organizations…" className={`${input} w-full pl-9`} /></div>
        <Select label="" options={[{ value: "", label: "All" }, { value: "active", label: "Active" }, { value: "suspended", label: "Suspended" }, { value: "deleted", label: "Deleted" }]} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} />
      </div>
      {query.isLoading ? <Skeleton className="h-40 rounded-2xl" /> : !d || d.items.length === 0 ? <EmptyState icon={<Building2 className="h-6 w-6" />} title="No organizations" description="Adjust your search or filters." /> : (
        <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-white/[0.03]"><tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
              <th className="px-4 py-2.5 font-semibold">Organization</th><th className="px-4 py-2.5 font-semibold">Owner</th>
              <th className="px-4 py-2.5 text-right font-semibold">Farms</th><th className="px-4 py-2.5 font-semibold">Plan</th>
              <th className="px-4 py-2.5 font-semibold">Status</th><th className="px-4 py-2.5 text-right font-semibold">Actions</th></tr></thead>
            <tbody>{d.items.map((o) => (
              <tr key={o.id} className="border-t border-gray-100 dark:border-white/5">
                <td className="px-4 py-3"><span className="font-medium text-gray-900 dark:text-white">{o.name}</span><p className="text-xs text-gray-400">{o.slug}</p></td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{o.owner_name ?? "—"}</td>
                <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{o.farm_count}</td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{o.plan_name ?? "free"}</td>
                <td className="px-4 py-3">{o.is_deleted ? <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500 dark:bg-white/10">Deleted</span> : o.is_suspended ? <span className="rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-700 dark:bg-red-500/15 dark:text-red-300">Suspended</span> : <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 dark:bg-brand-600/15 dark:text-brand-300">Active</span>}</td>
                <td className="px-4 py-3 text-right">
                  {!o.is_deleted && <button onClick={() => suspend.mutate({ id: o.id, suspend: !o.is_suspended })} className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10">{o.is_suspended ? "Reactivate" : "Suspend"}</button>}
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {d && d.total > d.page_size && <Pager page={page} total={d.total} pageSize={d.page_size} onPage={setPage} />}
    </div>
  );
}

function UsersTab() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: [...queryKeys.adminUsers2(), q, page], queryFn: () => api.listAdminUsers({ q: q || undefined, page }) });
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.adminUsers2() });
  const disable = useMutation({ mutationFn: (u: { id: string; active: boolean }) => (u.active ? api.reactivateUser(u.id) : api.disableUser(u.id)), onSuccess: invalidate });
  const role = useMutation({ mutationFn: (u: { id: string; role: string }) => api.changeUserRole(u.id, u.role), onSuccess: invalidate });
  const logout = useMutation({ mutationFn: (id: string) => api.forceLogout(id) });
  const reset = useMutation({ mutationFn: (id: string) => api.resetPassword(id) });
  const [banner, setBanner] = useState<string | null>(null);
  const d = query.data;
  const ROLES = ["farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer", "platform_admin"];
  return (
    <div className="space-y-4">
      {banner && <div className="rounded-xl border border-brand-200 bg-brand-50 px-3.5 py-2.5 text-sm text-brand-800 dark:border-brand-600/30 dark:bg-brand-600/10 dark:text-brand-200">{banner}</div>}
      <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search users by name, email or phone…" className={`${input} w-full pl-9`} /></div>
      {query.isLoading ? <Skeleton className="h-40 rounded-2xl" /> : !d || d.items.length === 0 ? <EmptyState icon={<Users className="h-6 w-6" />} title="No users" description="Adjust your search." /> : (
        <ul className="space-y-2">{d.items.map((u) => (
          <li key={u.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
            <div className="min-w-0">
              <div className="flex items-center gap-2"><span className="font-medium text-gray-900 dark:text-white">{u.full_name ?? "Unnamed"}</span>
                {!u.is_active && <span className="rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-700 dark:bg-red-500/15 dark:text-red-300">Disabled</span>}
                {u.roles.map((r) => <span key={r} className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600 dark:bg-white/10 dark:text-gray-300">{cap(r)}</span>)}</div>
              <p className="text-xs text-gray-400">{u.email ?? u.phone ?? "—"} · last login {fmtDT(u.last_login_at)}</p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <select defaultValue="" onChange={(e) => { if (e.target.value) { role.mutate({ id: u.id, role: e.target.value }); e.target.value = ""; } }} className={`${input} py-1.5 text-xs`} aria-label="Change role">
                <option value="">Role…</option>{ROLES.map((r) => <option key={r} value={r}>{cap(r)}</option>)}
              </select>
              <button onClick={() => { logout.mutate(u.id); setBanner("Sessions revoked — user must sign in again."); }} className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10">Force logout</button>
              <button onClick={() => { reset.mutate(u.id); setBanner("Password reset required for this user."); }} className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10">Reset password</button>
              <button onClick={() => disable.mutate({ id: u.id, active: !u.is_active })} className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10">{u.is_active ? "Disable" : "Reactivate"}</button>
            </div>
          </li>
        ))}</ul>
      )}
      {d && d.total > d.page_size && <Pager page={page} total={d.total} pageSize={d.page_size} onPage={setPage} />}
    </div>
  );
}

function FarmsTab() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: [...queryKeys.adminFarms2(), q, page], queryFn: () => api.listAdminFarms({ q: q || undefined, page }) });
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.adminFarms2() });
  const archive = useMutation({ mutationFn: (f: { id: string; archive: boolean }) => (f.archive ? api.archiveFarm(f.id) : api.restoreFarm(f.id)), onSuccess: invalidate });
  const d = query.data;
  return (
    <div className="space-y-4">
      <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search farms…" className={`${input} w-full pl-9`} /></div>
      {query.isLoading ? <Skeleton className="h-40 rounded-2xl" /> : !d || d.items.length === 0 ? <EmptyState icon={<Sprout className="h-6 w-6" />} title="No farms" description="Adjust your search." /> : (
        <div className="overflow-x-auto rounded-2xl border border-gray-200 dark:border-white/10">
          <table className="w-full text-sm"><thead className="bg-gray-50 dark:bg-white/[0.03]"><tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
            <th className="px-4 py-2.5 font-semibold">Farm</th><th className="px-4 py-2.5 font-semibold">Owner</th>
            <th className="px-4 py-2.5 text-right font-semibold">Flocks</th><th className="px-4 py-2.5 font-semibold">Status</th>
            <th className="px-4 py-2.5 text-right font-semibold">Actions</th></tr></thead>
            <tbody>{d.items.map((f) => (
              <tr key={f.id} className="border-t border-gray-100 dark:border-white/5">
                <td className="px-4 py-3"><span className="font-medium text-gray-900 dark:text-white">{f.name}</span><p className="text-xs text-gray-400">{f.county ?? ""}</p></td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{f.owner_name ?? "—"}</td>
                <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{f.flock_count}</td>
                <td className="px-4 py-3">{f.is_archived ? <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500 dark:bg-white/10">Archived</span> : <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 dark:bg-brand-600/15 dark:text-brand-300">Active</span>}</td>
                <td className="px-4 py-3 text-right"><button onClick={() => archive.mutate({ id: f.id, archive: !f.is_archived })} className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10">{f.is_archived ? "Restore" : "Archive"}</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {d && d.total > d.page_size && <Pager page={page} total={d.total} pageSize={d.page_size} onPage={setPage} />}
    </div>
  );
}

function AuditTab() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [downloading, setDownloading] = useState(false);
  const query = useQuery({ queryKey: [...queryKeys.adminAudit(), q, page], queryFn: () => api.listAudit({ q: q || undefined, page }) });
  const d = query.data;
  const doDownload = async () => {
    setDownloading(true);
    try { const blob = await api.downloadAuditCsv(); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "audit_log.csv"; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); } finally { setDownloading(false); }
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-[180px] flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search actions / resources…" className={`${input} w-full pl-9`} /></div>
        <Button size="sm" variant="secondary" loading={downloading} onClick={doDownload} leftIcon={<Download className="h-4 w-4" />}>Export CSV</Button>
      </div>
      {query.isLoading ? <Skeleton className="h-40 rounded-2xl" /> : !d || d.items.length === 0 ? <EmptyState icon={<ScrollText className="h-6 w-6" />} title="No audit entries" description="Admin actions appear here." /> : (
        <ol className="space-y-2">{d.items.map((a) => (
          <li key={a.id} className="flex items-start justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-900 dark:text-white">{a.action} <span className="text-gray-400">· {a.resource_type}</span></p>
              <p className="text-xs text-gray-400">{a.actor_name ?? "System"} · {fmtDT(a.created_at)}{a.ip_address ? ` · ${a.ip_address}` : ""}{a.new_value?.reason ? ` · "${a.new_value.reason}"` : ""}</p>
            </div>
          </li>
        ))}</ol>
      )}
      {d && d.total > d.page_size && <Pager page={page} total={d.total} pageSize={d.page_size} onPage={setPage} />}
    </div>
  );
}

function AnalyticsTab() {
  const q = useQuery({ queryKey: queryKeys.adminAnalytics(), queryFn: api.getPlatformAnalytics });
  if (q.isLoading) return <Skeleton className="h-64 rounded-2xl" />;
  const d = q.data!;
  const growth = d.growth.map((g) => ({ period: g.period.slice(2), Orgs: g.organizations, Farms: g.farms, Users: g.users }));
  const ai = [{ name: "Gemini", v: d.ai_gemini }, { name: "Claude", v: d.ai_claude }, { name: "Offline", v: d.ai_offline }];
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="AI requests" value={String(d.ai_requests_total)} sub={`${d.ai_offline} offline`} />
        <Tile label="API requests (est.)" value={d.api_requests_estimate.toLocaleString()} />
        <Tile label="Storage (est.)" value={`${Number(d.storage_mb_estimate).toLocaleString()} MB`} />
        <Tile label="Monthly revenue" value={kes(d.monthly_revenue_estimate)} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Growth (6 months)">
          <div className="h-56"><ResponsiveContainer width="100%" height="100%"><LineChart data={growth} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" /><XAxis dataKey="period" tick={{ fontSize: 11, fill: "#94a3b8" }} /><YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} />
            <Line type="monotone" dataKey="Users" stroke="#16a34a" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="Farms" stroke="#0ea5e9" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="Orgs" stroke="#f59e0b" strokeWidth={2} dot={false} />
          </LineChart></ResponsiveContainer></div>
        </Card>
        <Card title="AI usage by provider">
          <div className="h-56"><ResponsiveContainer width="100%" height="100%"><BarChart data={ai} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" /><XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} /><YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 }} /><Bar dataKey="v" fill="#16a34a" radius={[4, 4, 0, 0]} />
          </BarChart></ResponsiveContainer></div>
        </Card>
        <Card title="Subscriptions">
          <ul className="space-y-2">{d.subscription_breakdown.map((s) => (
            <li key={s.plan} className="flex items-center justify-between text-sm"><span className="font-medium capitalize text-gray-800 dark:text-gray-200">{s.plan}</span><span className="text-gray-500 dark:text-gray-400">{s.farm_count} farm(s) · {kes(s.monthly_revenue)}</span></li>
          ))}</ul>
        </Card>
        <Card title="Top farms by AI usage">
          {d.top_farms.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No AI usage yet.</p> : (
            <ul className="space-y-2">{d.top_farms.map((f) => <li key={f.farm_id} className="flex items-center justify-between text-sm"><span className="font-medium text-gray-800 dark:text-gray-200">{f.name}</span><span className="text-gray-500 dark:text-gray-400">{f.ai_requests} requests</span></li>)}</ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function FlagsTab() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.adminFlags(), queryFn: api.listFeatureFlags });
  const toggle = useMutation({ mutationFn: (f: { key: string; enabled: boolean }) => api.setFeatureFlag({ flag_key: f.key, is_enabled: f.enabled }), onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.adminFlags() }) });
  if (query.isLoading) return <Skeleton className="h-40 rounded-2xl" />;
  const flags = (query.data ?? []).filter((f) => !f.organization_id);
  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-500 dark:text-gray-400">Global module toggles. Disabling hides a module across the platform.</p>
      <ul className="space-y-2">{flags.map((f) => (
        <li key={f.id} className="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
          <div><p className="font-medium text-gray-900 dark:text-white">{cap(f.flag_key)}</p><p className="text-xs text-gray-400">{f.description}</p></div>
          <button onClick={() => toggle.mutate({ key: f.flag_key, enabled: !f.is_enabled })} aria-label="Toggle" className={`relative h-6 w-11 rounded-full transition-colors ${f.is_enabled ? "bg-brand-500" : "bg-gray-300 dark:bg-white/20"}`}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${f.is_enabled ? "translate-x-5" : "translate-x-0.5"}`} />
          </button>
        </li>
      ))}</ul>
    </div>
  );
}

function SystemTab() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.adminConfig(), queryFn: api.getSystemConfig });
  const [form, setForm] = useState<Record<string, any> | null>(null);
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({ mutationFn: (patch: Record<string, any>) => api.updateSystemConfig(patch), onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.adminConfig() }); qc.invalidateQueries({ queryKey: queryKeys.adminDashboard() }); setConfirm(false); } });
  if (query.isLoading) return <Skeleton className="h-64 rounded-2xl" />;
  const cfg = query.data!;
  const f = form ?? { maintenance_mode: cfg.maintenance_mode, read_only_mode: cfg.read_only_mode, banner_message: cfg.banner_message ?? "", email_sender: cfg.email_sender, sms_sender: cfg.sms_sender, default_currency: cfg.default_currency, default_timezone: cfg.default_timezone, data_retention_days: cfg.data_retention_days };
  const set = (p: Record<string, any>) => setForm({ ...f, ...p });
  return (
    <div className="max-w-2xl space-y-5">
      <Card title="Maintenance">
        <label className="flex items-center justify-between py-2">
          <span className="text-sm text-gray-700 dark:text-gray-200">Maintenance mode</span>
          <input type="checkbox" checked={!!f.maintenance_mode} onChange={(e) => set({ maintenance_mode: e.target.checked })} className="h-5 w-5 accent-brand-500" />
        </label>
        <label className="flex items-center justify-between py-2">
          <span className="text-sm text-gray-700 dark:text-gray-200">Read-only mode</span>
          <input type="checkbox" checked={!!f.read_only_mode} onChange={(e) => set({ read_only_mode: e.target.checked })} className="h-5 w-5 accent-brand-500" />
        </label>
        <label className="mt-2 block"><span className="text-xs font-medium text-gray-500 dark:text-gray-400">Banner message</span>
          <input value={f.banner_message} onChange={(e) => set({ banner_message: e.target.value })} className={`${input} mt-1 w-full`} placeholder="Shown to all users when set" /></label>
      </Card>
      <Card title="Configuration">
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="text-xs font-medium text-gray-500 dark:text-gray-400">Email sender</span><input value={f.email_sender} onChange={(e) => set({ email_sender: e.target.value })} className={`${input} mt-1 w-full`} /></label>
          <label className="block"><span className="text-xs font-medium text-gray-500 dark:text-gray-400">SMS sender</span><input value={f.sms_sender} onChange={(e) => set({ sms_sender: e.target.value })} className={`${input} mt-1 w-full`} /></label>
          <label className="block"><span className="text-xs font-medium text-gray-500 dark:text-gray-400">Currency</span><input value={f.default_currency} onChange={(e) => set({ default_currency: e.target.value })} className={`${input} mt-1 w-full`} /></label>
          <label className="block"><span className="text-xs font-medium text-gray-500 dark:text-gray-400">Timezone</span><input value={f.default_timezone} onChange={(e) => set({ default_timezone: e.target.value })} className={`${input} mt-1 w-full`} /></label>
          <label className="block"><span className="text-xs font-medium text-gray-500 dark:text-gray-400">Retention (days)</span><input type="number" value={f.data_retention_days} onChange={(e) => set({ data_retention_days: Number(e.target.value) })} className={`${input} mt-1 w-full`} /></label>
        </div>
        <p className="mt-2 text-xs text-gray-400">AI provider priority: {cfg.ai_provider_priority.join(" → ")}</p>
      </Card>
      {!confirm ? <Button onClick={() => setConfirm(true)}>Save changes</Button> : (
        <div className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-500/20 dark:bg-amber-500/10">
          <span className="text-sm text-amber-800 dark:text-amber-300">{f.maintenance_mode ? "This will put the platform into maintenance mode. " : ""}Apply configuration changes?</span>
          <Button size="sm" loading={save.isPending} onClick={() => save.mutate(f)}>Confirm</Button>
          <Button size="sm" variant="secondary" onClick={() => setConfirm(false)}>Cancel</Button>
        </div>
      )}
    </div>
  );
}

function HealthTab() {
  const query = useQuery({ queryKey: queryKeys.adminHealth(), queryFn: api.getSystemHealth, refetchInterval: 15000 });
  if (query.isLoading) return <Skeleton className="h-40 rounded-2xl" />;
  const d = query.data!;
  const up = Math.floor(d.uptime_seconds / 60);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Overall" value={cap(d.status)} tone={d.status !== "ok" ? "danger" : undefined} />
        <Tile label="Version" value={d.version} />
        <Tile label="Environment" value={cap(d.environment)} />
        <Tile label="Uptime" value={`${up} min`} />
      </div>
      <ul className="space-y-2">{d.components.map((c) => (
        <li key={c.name} className="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-white/10">
          <div><p className="font-medium text-gray-900 dark:text-white">{c.name}</p>{c.detail && <p className="text-xs text-gray-400">{c.detail}</p>}</div>
          <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${STATUS_CLS[c.status] ?? STATUS_CLS.not_configured}`}>{cap(c.status)}</span>
        </li>
      ))}</ul>
    </div>
  );
}

function JobsTab() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.adminJobs(), queryFn: api.getJobs });
  const run = useMutation({ mutationFn: (name: string) => api.runJob(name), onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.adminJobs() }) });
  if (query.isLoading) return <Skeleton className="h-40 rounded-2xl" />;
  const d = query.data!;
  const JOBS = ["cleanup_expired_sessions", "recompute_feature_flags", "purge_stale_ai_cache"];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Tile label="Total" value={String(d.total)} /><Tile label="Success" value={String(d.success)} />
        <Tile label="Failed" value={String(d.failed)} tone={d.failed > 0 ? "danger" : undefined} />
        <Tile label="Queue depth" value={String(d.queue_depth)} /><Tile label="Avg duration" value={d.avg_duration_ms != null ? `${d.avg_duration_ms} ms` : "—"} />
      </div>
      <Card title="Run a job">
        <div className="flex flex-wrap gap-2">{JOBS.map((j) => <Button key={j} size="sm" variant="secondary" loading={run.isPending} onClick={() => run.mutate(j)} leftIcon={<Play className="h-4 w-4" />}>{cap(j)}</Button>)}</div>
      </Card>
      <Card title="Recent runs">
        {d.recent.length === 0 ? <p className="py-6 text-center text-sm text-gray-400">No jobs run yet.</p> : (
          <ul className="divide-y divide-gray-100 dark:divide-white/5">{d.recent.map((j) => (
            <li key={j.id} className="flex items-center justify-between gap-3 py-2.5">
              <div><span className="text-sm font-medium text-gray-900 dark:text-white">{cap(j.name)}</span><p className="text-xs text-gray-400">{fmtDT(j.finished_at ?? j.started_at)}{j.duration_ms != null ? ` · ${j.duration_ms} ms` : ""}{j.error ? ` · ${j.error}` : ""}</p></div>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_CLS[j.status] ?? STATUS_CLS.queued}`}>{cap(j.status)}</span>
            </li>
          ))}</ul>
        )}
      </Card>
    </div>
  );
}

function AssistantTab() {
  const [messages, setMessages] = useState<{ role: "user" | "aria"; text: string; sources?: string[] }[]>([
    { role: "aria", text: "Ask me about platform metrics — AI usage, organizations, users, revenue, or system status." },
  ]);
  const [inputV, setInputV] = useState("");
  const ask = useMutation({
    mutationFn: (q: string) => api.adminAsk(q),
    onSuccess: (r) => setMessages((m) => [...m, { role: "aria", text: r.answer, sources: r.sources }]),
    onError: () => setMessages((m) => [...m, { role: "aria", text: "Sorry, I couldn't answer that." }]),
  });
  const submit = () => { const q = inputV.trim(); if (!q || ask.isPending) return; setMessages((m) => [...m, { role: "user", text: q }]); setInputV(""); ask.mutate(q); };
  const suggestions = ["Which farms generated the most AI requests?", "How many organizations and users?", "What's the monthly revenue?", "Is maintenance mode on?"];
  return (
    <div className="flex h-[calc(100dvh-18rem)] min-h-[380px] flex-col rounded-2xl border border-gray-200 dark:border-white/10">
      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${m.role === "user" ? "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300" : "bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300"}`}>{m.role === "user" ? "🧑" : <Bot className="h-4 w-4" />}</span>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${m.role === "user" ? "bg-brand-500 text-white" : "bg-gray-50 text-gray-800 dark:bg-white/[0.04] dark:text-gray-200"}`}>
              <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
              {m.sources && m.sources.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{m.sources.map((s) => <span key={s} className="rounded-md bg-white/60 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 dark:bg-white/10 dark:text-gray-400">{s}</span>)}</div>}
            </div>
          </div>
        ))}
        {ask.isPending && <p className="text-sm text-gray-400">Thinking…</p>}
      </div>
      {messages.length <= 1 && <div className="flex flex-wrap gap-2 px-5 pb-2">{suggestions.map((s) => <button key={s} onClick={() => { setInputV(s); setTimeout(submit, 0); }} className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-white/10 dark:text-gray-300">{s}</button>)}</div>}
      <div className="flex items-center gap-2 border-t border-gray-200 p-3 dark:border-white/10">
        <input value={inputV} onChange={(e) => setInputV(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") submit(); }} placeholder="Ask about the platform…" className={`${input} flex-1`} />
        <Button onClick={submit} disabled={!inputV.trim() || ask.isPending} leftIcon={<Send className="h-4 w-4" />}>Send</Button>
      </div>
    </div>
  );
}

function Pager({ page, total, pageSize, onPage }: { page: number; total: number; pageSize: number; onPage: (p: number) => void }) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
      <span>{total} total · page {page} of {pageCount}</span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Prev</Button>
        <Button variant="secondary" size="sm" disabled={page >= pageCount} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  );
}
