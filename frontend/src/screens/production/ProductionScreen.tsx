/**
 * Greena — Production workspace (Module 11).
 *
 * Seven pages: Reports, Imports, Exports, Backups, Diagnostics, System Status
 * and Release Information. Wired to the real backend throughout.
 *
 * Responsive by construction: the tab strip scrolls horizontally on narrow
 * screens, tiles reflow from four columns to one, and every table is wrapped in
 * its own horizontal scroll container so the page body never scrolls sideways.
 */
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, AlertTriangle, ArrowDownToLine, ArrowUpFromLine, CheckCircle2, Clock,
  Database, FileText, GitBranch, Rocket, Stethoscope, Trash2, Upload, XCircle,
} from "lucide-react";

import * as api from "@/api/production";
import { generateReport, downloadReportCsv } from "@/api/reporting";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type {
  BackupRow, DiagnosticCheck, ImportJobRow, RestoreRunRow,
} from "@/types/production";

// ── Helpers ──────────────────────────────────────────────────────────────────

const cap = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const fmtDT = (d?: string | null) => (d ? new Date(d).toLocaleString() : "—");

function fmtBytes(n: number): string {
  if (!n) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1_048_576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1_048_576).toFixed(1)} MB`;
}

function fmtUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m`;
}

const STATUS_TONE: Record<string, string> = {
  healthy: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
  success: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
  degraded: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  unhealthy: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  failed: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  running: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  pending: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-300",
};

function Pill({ status, children }: { status: string; children?: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_TONE[status] ?? STATUS_TONE.pending}`}>
      {children ?? cap(status)}
    </span>
  );
}

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "danger" | "warn" }) {
  const valueCls =
    tone === "danger" ? "text-red-600 dark:text-red-400"
      : tone === "warn" ? "text-amber-600 dark:text-amber-400"
        : "text-gray-900 dark:text-white";
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1.5 text-xl font-semibold ${valueCls}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{sub}</p>}
    </div>
  );
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Wraps wide content so it scrolls itself instead of the page. */
function ScrollX({ children }: { children: React.ReactNode }) {
  return <div className="-mx-1 overflow-x-auto px-1">{children}</div>;
}

const TH = "whitespace-nowrap px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-gray-400";
const TD = "whitespace-nowrap px-3 py-2 text-sm text-gray-700 dark:text-gray-200";

// ── Diagnostics ──────────────────────────────────────────────────────────────

function CheckRow({ check }: { check: DiagnosticCheck }) {
  const Icon = check.passed ? CheckCircle2 : check.severity === "critical" ? XCircle : AlertTriangle;
  const iconCls = check.passed
    ? "text-brand-600 dark:text-brand-300"
    : check.severity === "critical"
      ? "text-red-600 dark:text-red-400"
      : "text-amber-600 dark:text-amber-400";
  return (
    <li className="flex gap-3 border-b border-gray-100 py-3 last:border-0 dark:border-white/5">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconCls}`} />
      <div className="min-w-0">
        <p className="text-sm font-medium text-gray-900 dark:text-white">
          {cap(check.name)}
          <span className="ml-2 text-[11px] font-normal uppercase tracking-wide text-gray-400">{check.group}</span>
        </p>
        {/* break-words: details carry paths and connection strings that would
            otherwise force the whole page to scroll sideways on mobile. */}
        <p className="mt-0.5 break-words text-sm text-gray-500 dark:text-gray-400">{check.detail}</p>
      </div>
    </li>
  );
}

function DiagnosticsPage() {
  const q = useQuery({ queryKey: ["production", "diagnostics"], queryFn: api.getDiagnostics });
  const deploy = useMutation({ mutationFn: api.verifyDeployment });
  const rollback = useMutation({ mutationFn: api.verifyRollback });

  if (q.isLoading) return <Skeleton className="h-64 w-full" />;
  if (q.isError || !q.data) return <EmptyState title="Diagnostics unavailable" description="Could not reach the diagnostics endpoint." />;

  const report = q.data;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Status" value={cap(report.status)} tone={report.status === "unhealthy" ? "danger" : report.status === "degraded" ? "warn" : undefined} />
        <Tile label="Checks passing" value={`${report.passed_count}/${report.checks.length}`} />
        <Tile label="Sweep time" value={`${report.duration_ms} ms`} />
        <Tile label="Environment" value={cap(report.environment)} sub={`v${report.version}`} />
      </div>

      {report.critical_failures.length > 0 && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-500/30 dark:bg-red-500/10">
          <p className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
            <XCircle className="h-4 w-4" /> Critical checks failing
          </p>
          <p className="mt-1 text-sm text-red-600 dark:text-red-300">
            {report.critical_failures.map(cap).join(", ")} — this instance should not serve traffic.
          </p>
        </div>
      )}

      <Card title="All checks" action={<Button variant="secondary" onClick={() => q.refetch()} disabled={q.isFetching}>{q.isFetching ? "Running…" : "Re-run"}</Button>}>
        <ul>{report.checks.map((c) => <CheckRow key={c.name} check={c} />)}</ul>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Deployment verification" action={
          <Button onClick={() => deploy.mutate()} disabled={deploy.isPending}>
            {deploy.isPending ? "Verifying…" : "Verify deployment"}
          </Button>
        }>
          {deploy.data ? (
            <div className="space-y-2">
              <Pill status={deploy.data.passed ? "healthy" : "unhealthy"}>{deploy.data.passed ? "Passed" : "Failed"}</Pill>
              <ul className="mt-2">
                {deploy.data.checks.map((c) => (
                  <li key={c.name} className="flex gap-2 border-b border-gray-100 py-2 text-sm last:border-0 dark:border-white/5">
                    {c.passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />}
                    <span className="min-w-0"><b className="text-gray-900 dark:text-white">{cap(c.name)}</b>
                      <span className="block break-words text-gray-500 dark:text-gray-400">{c.detail}</span></span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Confirms the database, migrations, configuration and schema before cutting traffic over.
            </p>
          )}
        </Card>

        <Card title="Rollback verification" action={
          <Button variant="secondary" onClick={() => rollback.mutate()} disabled={rollback.isPending}>
            {rollback.isPending ? "Checking…" : "Verify rollback"}
          </Button>
        }>
          {rollback.data ? (
            <div className="space-y-2">
              <Pill status={rollback.data.passed ? "healthy" : "unhealthy"}>{rollback.data.passed ? "Coherent" : "Incoherent"}</Pill>
              <ul className="mt-2">
                {rollback.data.checks.map((c) => (
                  <li key={c.name} className="flex gap-2 border-b border-gray-100 py-2 text-sm last:border-0 dark:border-white/5">
                    {c.passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />}
                    <span className="min-w-0"><b className="text-gray-900 dark:text-white">{cap(c.name)}</b>
                      <span className="block break-words text-gray-500 dark:text-gray-400">{c.detail}</span></span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Checks whether the database schema has moved ahead of the running code — the failure a rollback introduces.
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}

// ── System status ────────────────────────────────────────────────────────────

function SystemStatusPage() {
  const q = useQuery({
    queryKey: ["production", "status"],
    queryFn: api.getSystemStatus,
    refetchInterval: 30_000,
  });

  if (q.isLoading) return <Skeleton className="h-64 w-full" />;
  if (q.isError || !q.data) return <EmptyState title="Status unavailable" description="Could not reach the status endpoint." />;

  const { metrics, entities, diagnostics, status, active_users_24h } = q.data;
  const errorPct = (metrics.error_rate * 100).toFixed(2);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Status" value={cap(status)} sub={`${diagnostics.passed_count}/${diagnostics.checks.length} checks`}
          tone={status === "unhealthy" ? "danger" : status === "degraded" ? "warn" : undefined} />
        <Tile label="Uptime" value={fmtUptime(metrics.uptime_seconds)} sub={`v${q.data.version}`} />
        <Tile label="Requests" value={metrics.total_requests.toLocaleString()} sub={`${metrics.avg_latency_ms} ms average`} />
        <Tile label="Server errors" value={`${errorPct}%`} sub={`${metrics.server_errors} of ${metrics.total_requests}`}
          tone={metrics.server_errors > 0 ? "danger" : undefined} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Slowest routes">
          {metrics.slowest_routes.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">No traffic recorded since the last restart.</p>
          ) : (
            <ScrollX>
              <table className="w-full min-w-[420px]">
                <thead><tr><th className={TH}>Route</th><th className={TH}>Calls</th><th className={TH}>Average</th></tr></thead>
                <tbody>
                  {metrics.slowest_routes.map((r) => (
                    <tr key={`${r.method}-${r.path}`} className="border-t border-gray-100 dark:border-white/5">
                      <td className={TD}><span className="font-mono text-xs text-gray-500">{r.method}</span> {r.path}</td>
                      <td className={TD}>{r.count}</td>
                      <td className={TD}>{r.avg_ms} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollX>
          )}
        </Card>

        <Card title="Data volume">
          <dl className="grid grid-cols-2 gap-3">
            {Object.entries(entities).map(([name, count]) => (
              <div key={name} className="rounded-xl border border-gray-100 p-3 dark:border-white/5">
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{cap(name)}</dt>
                <dd className="mt-0.5 text-lg font-semibold text-gray-900 dark:text-white">
                  {count < 0 ? "—" : count.toLocaleString()}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">{active_users_24h} user(s) active in the last 24 hours.</p>
        </Card>
      </div>

      {Object.keys(metrics.events).length > 0 && (
        <Card title="Operational events">
          <div className="flex flex-wrap gap-2">
            {Object.entries(metrics.events).map(([name, count]) => (
              <span key={name} className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700 dark:bg-white/10 dark:text-gray-200">
                {cap(name)} · {count}
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Release information ──────────────────────────────────────────────────────

function ReleasePage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["production", "release"], queryFn: api.getReleaseInfo });
  const record = useMutation({
    mutationFn: () => api.recordRelease(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["production", "release"] }),
  });

  if (q.isLoading) return <Skeleton className="h-64 w-full" />;
  if (q.isError || !q.data) return <EmptyState title="Release info unavailable" description="Could not reach the release endpoint." />;

  const { current, migrations_at_head, migration_current, migration_expected, history } = q.data;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Version" value={`v${current.version}`} sub={cap(current.environment)} />
        <Tile label="Commit" value={current.git_sha_short ?? "—"} sub={current.build_time ? new Date(current.build_time).toLocaleDateString() : "no build time"} />
        <Tile label="Uptime" value={fmtUptime(current.uptime_seconds)} sub={`since ${fmtDT(current.started_at)}`} />
        <Tile label="Migrations" value={migrations_at_head ? "At head" : "Behind"}
          sub={migrations_at_head ? migration_current ?? "" : `db ${migration_current} · code ${migration_expected}`}
          tone={migrations_at_head ? undefined : "danger"} />
      </div>

      {!migrations_at_head && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-500/30 dark:bg-red-500/10">
          <p className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
            <AlertTriangle className="h-4 w-4" /> Migrations are not at head
          </p>
          <p className="mt-1 text-sm text-red-600 dark:text-red-300">
            The database is at {migration_current ?? "unknown"} but this build expects {migration_expected}. Run <code className="font-mono">alembic upgrade head</code>.
          </p>
        </div>
      )}

      <Card title="Build details">
        <dl className="grid gap-3 sm:grid-cols-2">
          {[
            ["Version", `v${current.version}`],
            ["Environment", cap(current.environment)],
            ["Git SHA", current.git_sha ?? "—"],
            ["Build time", current.build_time ? new Date(current.build_time).toLocaleString() : "—"],
            ["Runtime", current.python_version ? `Python ${current.python_version}` : "—"],
            ["Started", fmtDT(current.started_at)],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</dt>
              <dd className="mt-0.5 break-all font-mono text-sm text-gray-900 dark:text-white">{value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card title="Deployment history" action={
        <Button variant="secondary" onClick={() => record.mutate()} disabled={record.isPending}>
          {record.isPending ? "Recording…" : "Record current"}
        </Button>
      }>
        {history.length === 0 ? (
          <EmptyState title="No releases recorded" description="A release is recorded automatically each time a new version starts up." />
        ) : (
          <ScrollX>
            <table className="w-full min-w-[640px]">
              <thead><tr>
                <th className={TH}>Version</th><th className={TH}>Environment</th><th className={TH}>Commit</th>
                <th className={TH}>Deployed</th><th className={TH}>Verified</th><th className={TH}>Type</th>
              </tr></thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100 dark:border-white/5">
                    <td className={TD}>v{r.version}</td>
                    <td className={TD}>{cap(r.environment)}</td>
                    <td className={`${TD} font-mono text-xs`}>{r.git_sha?.slice(0, 8) ?? "—"}</td>
                    <td className={TD}>{fmtDT(r.deployed_at)}</td>
                    <td className={TD}><Pill status={r.verified ? "success" : "pending"}>{r.verified ? "Verified" : "Unverified"}</Pill></td>
                    <td className={TD}>
                      {r.is_rollback
                        ? <Pill status="degraded">Rollback from v{r.previous_version}</Pill>
                        : <span className="text-gray-500 dark:text-gray-400">Forward</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollX>
        )}
      </Card>
    </div>
  );
}

// ── Backups ──────────────────────────────────────────────────────────────────

function BackupsPage({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [confirmRestore, setConfirmRestore] = useState<BackupRow | null>(null);
  const [dryRunResult, setDryRunResult] = useState<RestoreRunRow | null>(null);
  const [verifyResult, setVerifyResult] = useState<Record<string, string>>({});

  const backups = useQuery({ queryKey: ["production", "backups", farmId], queryFn: () => api.listBackups(farmId) });
  const restores = useQuery({ queryKey: ["production", "restores", farmId], queryFn: () => api.listRestores(farmId) });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["production", "backups", farmId] });
    qc.invalidateQueries({ queryKey: ["production", "restores", farmId] });
  };

  const create = useMutation({ mutationFn: () => api.createBackup(farmId, {}), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: string) => api.deleteBackup(farmId, id), onSuccess: invalidate });
  const retention = useMutation({ mutationFn: () => api.applyRetention(farmId), onSuccess: invalidate });
  const verify = useMutation({
    mutationFn: (id: string) => api.verifyBackup(farmId, id),
    onSuccess: (r) => setVerifyResult((prev) => ({ ...prev, [r.backup_id]: r.valid ? "valid" : "invalid" })),
  });
  const restore = useMutation({
    mutationFn: (v: { id: string; dryRun: boolean }) =>
      api.restoreBackup(farmId, { backup_id: v.id, dry_run: v.dryRun }),
    onSuccess: (run) => {
      if (run.dry_run) setDryRunResult(run);
      else { setDryRunResult(null); setConfirmRestore(null); invalidate(); }
    },
  });
  const download = useMutation({
    mutationFn: async (b: BackupRow) => {
      const blob = await api.downloadBackup(farmId, b.id);
      api.saveBlob(blob, `${b.label.replace(/[^\w-]/g, "_")}.json`);
    },
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          <Database className="mr-1.5 h-4 w-4" />{create.isPending ? "Creating…" : "Create backup"}
        </Button>
        <Button variant="secondary" onClick={() => retention.mutate()} disabled={retention.isPending}>
          <Clock className="mr-1.5 h-4 w-4" />Apply retention
        </Button>
      </div>

      {retention.data && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Retention: removed {retention.data.expired_removed} expired and pruned {retention.data.pruned_over_limit} over the
          {" "}{retention.data.max_per_farm}-backup limit.
        </p>
      )}

      <Card title="Backups">
        {backups.isLoading ? <Skeleton className="h-32 w-full" />
          : (backups.data?.length ?? 0) === 0 ? (
            <EmptyState title="No backups yet" description="Create a backup before making bulk changes to this farm's data." />
          ) : (
            <ScrollX>
              <table className="w-full min-w-[760px]">
                <thead><tr>
                  <th className={TH}>Label</th><th className={TH}>Status</th><th className={TH}>Size</th>
                  <th className={TH}>Records</th><th className={TH}>Created</th><th className={TH}>Expires</th>
                  <th className={TH}>Actions</th>
                </tr></thead>
                <tbody>
                  {backups.data!.map((b) => {
                    const total = Object.values(b.record_counts).reduce((a, c) => a + c, 0);
                    return (
                      <tr key={b.id} className="border-t border-gray-100 dark:border-white/5">
                        <td className={TD}>
                          {b.label}
                          {b.trigger === "pre_restore" && <span className="ml-2 text-[11px] uppercase tracking-wide text-gray-400">safety</span>}
                        </td>
                        <td className={TD}><Pill status={b.status} /></td>
                        <td className={TD}>{fmtBytes(b.size_bytes)}</td>
                        <td className={TD}>{total}</td>
                        <td className={TD}>{fmtDT(b.created_at)}</td>
                        <td className={TD}>{b.expires_at ? new Date(b.expires_at).toLocaleDateString() : "never"}</td>
                        <td className={TD}>
                          <div className="flex flex-wrap gap-1.5">
                            <button onClick={() => verify.mutate(b.id)}
                              className="rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-gray-50 dark:border-white/10 dark:hover:bg-white/5">
                              {verifyResult[b.id] === "valid" ? "✓ Valid" : verifyResult[b.id] === "invalid" ? "✗ Corrupt" : "Verify"}
                            </button>
                            <button onClick={() => download.mutate(b)}
                              className="rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-gray-50 dark:border-white/10 dark:hover:bg-white/5">
                              Download
                            </button>
                            <button onClick={() => { setConfirmRestore(b); setDryRunResult(null); restore.mutate({ id: b.id, dryRun: true }); }}
                              disabled={b.status !== "success"}
                              className="rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-40 dark:border-white/10 dark:hover:bg-white/5">
                              Restore
                            </button>
                            <button onClick={() => remove.mutate(b.id)} aria-label="Delete backup"
                              className="rounded-lg border border-gray-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:border-white/10 dark:hover:bg-red-500/10">
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </ScrollX>
          )}
      </Card>

      {/* Restore is destructive, so the dry run is shown first and the real
          restore needs a second, explicit confirmation. */}
      {confirmRestore && (
        <Card title={`Restore — ${confirmRestore.label}`}>
          {restore.isPending && !dryRunResult && <Skeleton className="h-20 w-full" />}
          {dryRunResult && (
            <>
              <p className="mb-3 text-sm text-gray-600 dark:text-gray-300">
                Dry run complete. Checksum {dryRunResult.checksum_verified ? "verified" : "NOT verified"}. Nothing has been written.
              </p>
              <ScrollX>
                <table className="w-full min-w-[420px]">
                  <thead><tr><th className={TH}>Entity</th><th className={TH}>In backup</th><th className={TH}>Would create</th><th className={TH}>Already present</th></tr></thead>
                  <tbody>
                    {Object.entries(dryRunResult.summary).map(([entity, s]) => (
                      <tr key={entity} className="border-t border-gray-100 dark:border-white/5">
                        <td className={TD}>{cap(entity)}</td>
                        <td className={TD}>{s.in_backup ?? 0}</td>
                        <td className={TD}>{s.would_create ?? s.created ?? 0}</td>
                        <td className={TD}>{s.already_present ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollX>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={() => restore.mutate({ id: confirmRestore.id, dryRun: false })} disabled={restore.isPending}>
                  {restore.isPending ? "Restoring…" : "Apply restore"}
                </Button>
                <Button variant="secondary" onClick={() => { setConfirmRestore(null); setDryRunResult(null); }}>Cancel</Button>
              </div>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                A safety backup of current data is taken automatically before the restore is applied.
              </p>
            </>
          )}
          {restore.isError && (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400">
              {(restore.error as any)?.response?.data?.error?.message ?? "Restore failed."}
            </p>
          )}
        </Card>
      )}

      <Card title="Restore history">
        {restores.isLoading ? <Skeleton className="h-24 w-full" />
          : (restores.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">No restores have been run.</p>
          ) : (
            <ScrollX>
              <table className="w-full min-w-[560px]">
                <thead><tr><th className={TH}>When</th><th className={TH}>Mode</th><th className={TH}>Status</th><th className={TH}>Checksum</th><th className={TH}>Detail</th></tr></thead>
                <tbody>
                  {restores.data!.map((r) => (
                    <tr key={r.id} className="border-t border-gray-100 dark:border-white/5">
                      <td className={TD}>{fmtDT(r.created_at)}</td>
                      <td className={TD}>{r.dry_run ? "Dry run" : "Applied"}</td>
                      <td className={TD}><Pill status={r.status} /></td>
                      <td className={TD}>{r.checksum_verified ? "Verified" : "Failed"}</td>
                      <td className={`${TD} max-w-[280px] truncate`} title={r.error ?? ""}>{r.error ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollX>
          )}
      </Card>
    </div>
  );
}

// ── Imports ──────────────────────────────────────────────────────────────────

function ImportsPage({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [entity, setEntity] = useState("expenses");
  const [format, setFormat] = useState("csv");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportJobRow | null>(null);

  const entities = useQuery({ queryKey: ["production", "importEntities", farmId], queryFn: () => api.listImportEntities(farmId) });
  const history = useQuery({ queryKey: ["production", "imports", farmId], queryFn: () => api.listImports(farmId) });

  const run = useMutation({
    mutationFn: (dryRun: boolean) =>
      api.runImport(farmId, { file: file!, entity, source_format: format, dry_run: dryRun }),
    onSuccess: (job) => {
      setResult(job);
      qc.invalidateQueries({ queryKey: ["production", "imports", farmId] });
    },
  });

  const template = useMutation({
    mutationFn: async () => {
      const blob = await api.downloadImportTemplate(farmId, entity);
      api.saveBlob(blob, `${entity}_template.csv`);
    },
  });

  const spec = entities.data?.find((e) => e.entity === entity);
  const canApply = result && result.status === "success" && result.dry_run && result.valid_rows > 0;

  return (
    <div className="space-y-5">
      <Card title="Import data">
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Entity" value={entity} onChange={(e) => { setEntity(e.target.value); setResult(null); }}
            options={(entities.data ?? []).map((e) => ({ value: e.entity, label: cap(e.entity) }))} />
          <Select label="Format" value={format} onChange={(e) => setFormat(e.target.value)}
            options={[{ value: "csv", label: "CSV" }, { value: "excel", label: "Excel (.xlsx)" }, { value: "json", label: "JSON" }]} />
        </div>

        {spec && (
          <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
            Columns: <span className="font-mono">{spec.columns.join(", ")}</span>.
            {" "}Required: <span className="font-mono">{spec.required.join(", ")}</span>.
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.json" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); }}
            className="block w-full max-w-xs text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-700 dark:text-gray-300 dark:file:bg-brand-600/15 dark:file:text-brand-300" />
          <Button variant="secondary" onClick={() => template.mutate()}>
            <ArrowDownToLine className="mr-1.5 h-4 w-4" />Template
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => run.mutate(true)} disabled={!file || run.isPending}>
            {run.isPending ? "Checking…" : "Validate (dry run)"}
          </Button>
          <Button variant="secondary" onClick={() => run.mutate(false)} disabled={!canApply || run.isPending}>
            <Upload className="mr-1.5 h-4 w-4" />Apply import
          </Button>
        </div>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Every import is validated first. Nothing is written until the dry run passes and you apply it.
        </p>
      </Card>

      {result && (
        <Card title={`${result.dry_run ? "Dry run" : "Import"} result`}>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile label="Rows read" value={String(result.total_rows)} />
            <Tile label="Valid" value={String(result.valid_rows)} />
            <Tile label="Invalid" value={String(result.failed_rows)} tone={result.failed_rows ? "danger" : undefined} />
            <Tile label="Written" value={String(result.imported_rows)} />
          </div>

          {result.error && (
            <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">{result.error}</p>
          )}

          {result.errors.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-sm font-medium text-gray-900 dark:text-white">Row errors</p>
              <ScrollX>
                <table className="w-full min-w-[420px]">
                  <thead><tr><th className={TH}>File row</th><th className={TH}>Problem</th></tr></thead>
                  <tbody>
                    {result.errors.map((e, i) => (
                      <tr key={i} className="border-t border-gray-100 dark:border-white/5">
                        <td className={TD}>{e.row}</td>
                        <td className={`${TD} whitespace-normal`}>{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollX>
            </div>
          )}

          {!result.dry_run && result.status === "success" && (
            <p className="mt-3 flex items-center gap-2 text-sm text-brand-700 dark:text-brand-300">
              <CheckCircle2 className="h-4 w-4" />Imported {result.imported_rows} row(s).
            </p>
          )}
        </Card>
      )}

      <Card title="Import history">
        {history.isLoading ? <Skeleton className="h-24 w-full" />
          : (history.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">No imports have been run.</p>
          ) : (
            <ScrollX>
              <table className="w-full min-w-[680px]">
                <thead><tr>
                  <th className={TH}>When</th><th className={TH}>Entity</th><th className={TH}>File</th>
                  <th className={TH}>Mode</th><th className={TH}>Status</th><th className={TH}>Rows</th>
                </tr></thead>
                <tbody>
                  {history.data!.map((j) => (
                    <tr key={j.id} className="border-t border-gray-100 dark:border-white/5">
                      <td className={TD}>{fmtDT(j.created_at)}</td>
                      <td className={TD}>{cap(j.entity)}</td>
                      <td className={`${TD} max-w-[200px] truncate`}>{j.filename ?? "—"}</td>
                      <td className={TD}>{j.dry_run ? "Dry run" : "Applied"}</td>
                      <td className={TD}><Pill status={j.status} /></td>
                      <td className={TD}>{j.imported_rows}/{j.total_rows}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollX>
          )}
      </Card>
    </div>
  );
}

// ── Exports ──────────────────────────────────────────────────────────────────

function ExportsPage({ farmId }: { farmId: string }) {
  const qc = useQueryClient();
  const [dataset, setDataset] = useState("daily_logs");
  const [format, setFormat] = useState("csv");

  const datasets = useQuery({ queryKey: ["production", "exportDatasets", farmId], queryFn: () => api.listExportDatasets(farmId) });
  const history = useQuery({ queryKey: ["production", "exports", farmId], queryFn: () => api.listExports(farmId) });

  const run = useMutation({
    mutationFn: async () => {
      const { blob, filename } = await api.downloadExport(farmId, dataset, format);
      api.saveBlob(blob, filename);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["production", "exports", farmId] }),
  });

  return (
    <div className="space-y-5">
      <Card title="Export data">
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Dataset" value={dataset} onChange={(e) => setDataset(e.target.value)}
            options={(datasets.data ?? []).map((d) => ({ value: d.dataset, label: cap(d.dataset) }))} />
          <Select label="Format" value={format} onChange={(e) => setFormat(e.target.value)}
            options={[{ value: "csv", label: "CSV" }, { value: "excel", label: "Excel (.xlsx)" }, { value: "json", label: "JSON" }]} />
        </div>
        <div className="mt-4">
          <Button onClick={() => run.mutate()} disabled={run.isPending}>
            <ArrowUpFromLine className="mr-1.5 h-4 w-4" />{run.isPending ? "Preparing…" : "Download export"}
          </Button>
        </div>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Exports use the same columns as the import templates, so a file can be edited and imported straight back.
        </p>
      </Card>

      <Card title="Export history">
        {history.isLoading ? <Skeleton className="h-24 w-full" />
          : (history.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">No exports have been generated.</p>
          ) : (
            <ScrollX>
              <table className="w-full min-w-[560px]">
                <thead><tr>
                  <th className={TH}>When</th><th className={TH}>Dataset</th><th className={TH}>Format</th>
                  <th className={TH}>Status</th><th className={TH}>Rows</th><th className={TH}>Size</th>
                </tr></thead>
                <tbody>
                  {history.data!.map((j) => (
                    <tr key={j.id} className="border-t border-gray-100 dark:border-white/5">
                      <td className={TD}>{fmtDT(j.created_at)}</td>
                      <td className={TD}>{cap(j.dataset)}</td>
                      <td className={TD}>{j.export_format.toUpperCase()}</td>
                      <td className={TD}><Pill status={j.status} /></td>
                      <td className={TD}>{j.row_count}</td>
                      <td className={TD}>{fmtBytes(j.size_bytes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollX>
          )}
      </Card>
    </div>
  );
}

// ── Reports ──────────────────────────────────────────────────────────────────

const REPORT_TYPES = [
  "farm_summary", "production", "finance", "feed", "health", "inventory",
  "mortality", "vaccination", "sales", "purchases",
].map((v) => ({ value: v, label: cap(v) }));

const PERIODS = ["daily", "weekly", "monthly", "quarterly", "annual"].map((v) => ({ value: v, label: cap(v) }));

function ReportsPage({ farmId }: { farmId: string }) {
  const [reportType, setReportType] = useState("farm_summary");
  const [period, setPeriod] = useState("monthly");

  const params = useMemo(() => ({ report_type: reportType, period_type: period }), [reportType, period]);
  const report = useQuery({
    queryKey: ["production", "report", farmId, reportType, period],
    queryFn: () => generateReport(farmId, params),
  });

  const csv = useMutation({
    mutationFn: async () => {
      const blob = await downloadReportCsv(farmId, params);
      api.saveBlob(blob, `${reportType}_${period}.csv`);
    },
  });

  return (
    <div className="space-y-5">
      <Card title="Generate report" action={
        <Button variant="secondary" onClick={() => csv.mutate()} disabled={csv.isPending}>
          <ArrowDownToLine className="mr-1.5 h-4 w-4" />CSV
        </Button>
      }>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Report" value={reportType} onChange={(e) => setReportType(e.target.value)} options={REPORT_TYPES} />
          <Select label="Period" value={period} onChange={(e) => setPeriod(e.target.value)} options={PERIODS} />
        </div>
      </Card>

      {report.isLoading ? <Skeleton className="h-64 w-full" />
        : report.isError || !report.data ? (
          <EmptyState title="Report unavailable" description="Could not generate this report." />
        ) : (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{report.data.title}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {report.data.period_label} · generated {fmtDT(report.data.generated_at)}
              </p>
            </div>

            {report.data.sections.map((section, i) => (
              <Card key={i} title={section.heading}>
                {section.kind === "kpis" && (
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                    {section.kpis.map((k) => <Tile key={k.label} label={k.label} value={String(k.value)} sub={k.sub ?? undefined} />)}
                  </div>
                )}
                {section.kind === "table" && (
                  <ScrollX>
                    <table className="w-full min-w-[520px]">
                      <thead><tr>{section.table_columns.map((c) => <th key={c} className={TH}>{c}</th>)}</tr></thead>
                      <tbody>
                        {section.table_rows.map((row, ri) => (
                          <tr key={ri} className="border-t border-gray-100 dark:border-white/5">
                            {row.map((cell: any, ci: number) => <td key={ci} className={TD}>{String(cell ?? "—")}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ScrollX>
                )}
                {section.kind === "breakdown" && (
                  <ul className="space-y-2">
                    {section.breakdown.map((b) => (
                      <li key={b.label} className="flex items-center justify-between gap-3 text-sm">
                        <span className="min-w-0 truncate text-gray-700 dark:text-gray-200">{b.label}</span>
                        <span className="shrink-0 font-medium text-gray-900 dark:text-white">{b.value}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {section.kind === "note" && <p className="text-sm text-gray-600 dark:text-gray-300">{section.note}</p>}
                {section.kind === "series" && (
                  <p className="text-sm text-gray-500 dark:text-gray-400">{section.series.length} data point(s) over the period.</p>
                )}
              </Card>
            ))}
          </div>
        )}
    </div>
  );
}

// ── Workspace shell ──────────────────────────────────────────────────────────

type Tab = "status" | "diagnostics" | "backups" | "imports" | "exports" | "reports" | "release";

const TABS: { id: Tab; label: string; icon: typeof Activity }[] = [
  { id: "status", label: "System Status", icon: Activity },
  { id: "diagnostics", label: "Diagnostics", icon: Stethoscope },
  { id: "backups", label: "Backups", icon: Database },
  { id: "imports", label: "Imports", icon: ArrowDownToLine },
  { id: "exports", label: "Exports", icon: ArrowUpFromLine },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "release", label: "Release", icon: GitBranch },
];

export default function ProductionScreen() {
  const [tab, setTab] = useState<Tab>("status");
  const { currentFarm, isLoading } = useWorkspace();

  const farmId = currentFarm?.id;
  const needsFarm: Tab[] = ["backups", "imports", "exports", "reports"];

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300">
          <Rocket className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Production</h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">
            System health, data movement, backups and release readiness.
          </p>
        </div>
      </header>

      <div className="flex gap-1 overflow-x-auto border-b border-gray-200 dark:border-white/10">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
            className={`-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-brand-500 text-brand-600 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
            }`}>
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </div>

      {needsFarm.includes(tab) && !farmId ? (
        isLoading
          ? <Skeleton className="h-64 w-full" />
          : <EmptyState title="No farm selected" description="Choose a farm from the switcher to work with its data." />
      ) : (
        <>
          {tab === "status" && <SystemStatusPage />}
          {tab === "diagnostics" && <DiagnosticsPage />}
          {tab === "release" && <ReleasePage />}
          {tab === "backups" && <BackupsPage farmId={farmId!} />}
          {tab === "imports" && <ImportsPage farmId={farmId!} />}
          {tab === "exports" && <ExportsPage farmId={farmId!} />}
          {tab === "reports" && <ReportsPage farmId={farmId!} />}
        </>
      )}
    </div>
  );
}
