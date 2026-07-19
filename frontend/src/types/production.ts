/**
 * Greena — Production Readiness types (Module 11).
 * Mirrors backend/app/schemas/production.py.
 */

// ── Version / release ────────────────────────────────────────────────────────

export interface VersionInfo {
  version: string;
  environment: string;
  git_sha: string | null;
  git_sha_short: string | null;
  build_time: string | null;
  python_version: string | null;
  started_at: string;
  uptime_seconds: number;
}

export interface ReleaseRow {
  id: string;
  version: string;
  environment: string;
  git_sha: string | null;
  migration_revision: string | null;
  previous_version: string | null;
  is_rollback: boolean;
  deployed_at: string;
  verified: boolean;
  verification: Record<string, unknown>;
  notes: string | null;
}

export interface ReleaseInfo {
  current: VersionInfo;
  migration_current: string | null;
  migration_expected: string | null;
  migrations_at_head: boolean;
  latest_release: ReleaseRow | null;
  history: ReleaseRow[];
}

// ── Diagnostics ──────────────────────────────────────────────────────────────

export type HealthStatus = "healthy" | "degraded" | "unhealthy";
export type Severity = "critical" | "warning" | "info";

export interface DiagnosticCheck {
  name: string;
  group: string;
  severity: Severity;
  passed: boolean;
  detail: string;
}

export interface DiagnosticsReport {
  status: HealthStatus;
  checked_at: string;
  duration_ms: number;
  version: string;
  environment: string;
  passed_count: number;
  failed_count: number;
  critical_failures: string[];
  checks: DiagnosticCheck[];
}

export interface VerificationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface VerificationResult {
  passed: boolean;
  checked_at: string;
  version: string;
  environment?: string | null;
  checks: VerificationCheck[];
}

export interface RollbackVerification {
  passed: boolean;
  is_rollback: boolean;
  version: string;
  previous_version: string | null;
  checked_at: string;
  checks: VerificationCheck[];
}

// ── Status / metrics ─────────────────────────────────────────────────────────

export interface RouteLatency {
  method: string;
  path: string;
  count: number;
  avg_ms: number;
}

export interface MetricsSummary {
  uptime_seconds: number;
  total_requests: number;
  server_errors: number;
  client_errors: number;
  error_rate: number;
  avg_latency_ms: number;
  exceptions: Record<string, number>;
  events: Record<string, number>;
  slowest_routes: RouteLatency[];
}

export interface SystemStatus {
  status: HealthStatus;
  version: string;
  environment: string;
  checked_at: string;
  metrics: MetricsSummary;
  entities: Record<string, number>;
  active_users_24h: number;
  diagnostics: DiagnosticsReport;
}

// ── Backups ──────────────────────────────────────────────────────────────────

export interface BackupRow {
  id: string;
  scope: string;
  farm_id: string | null;
  label: string;
  trigger: string;
  status: string;
  checksum: string | null;
  size_bytes: number;
  record_counts: Record<string, number>;
  schema_version: string;
  app_version: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface BackupVerification {
  backup_id: string;
  valid: boolean;
  detail: string;
  expected_checksum: string | null;
  actual_checksum: string | null;
  size_bytes: number | null;
  record_counts: Record<string, number>;
}

export interface RestoreRunRow {
  id: string;
  backup_id: string;
  farm_id: string | null;
  dry_run: boolean;
  status: string;
  summary: Record<string, Record<string, number>>;
  checksum_verified: boolean;
  safety_backup_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
  created_at: string;
}

export interface RetentionResult {
  expired_removed: number;
  pruned_over_limit: number;
  retention_days: number;
  max_per_farm: number;
  swept_at: string;
}

// ── Imports / exports ────────────────────────────────────────────────────────

export interface ImportRowError {
  row: number;
  message: string;
}

export interface ImportJobRow {
  id: string;
  farm_id: string;
  entity: string;
  source_format: string;
  filename: string | null;
  dry_run: boolean;
  status: string;
  total_rows: number;
  valid_rows: number;
  imported_rows: number;
  failed_rows: number;
  errors: ImportRowError[];
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
  created_at: string;
}

export interface ImportEntityInfo {
  entity: string;
  columns: string[];
  required: string[];
}

export interface ExportJobRow {
  id: string;
  farm_id: string;
  dataset: string;
  export_format: string;
  status: string;
  row_count: number;
  size_bytes: number;
  duration_ms: number | null;
  error: string | null;
  created_at: string;
}

export interface ExportDatasetInfo {
  dataset: string;
  formats: string[];
}
