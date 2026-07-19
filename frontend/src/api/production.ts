/**
 * Greena — Production Readiness API client (Module 11).
 *
 * Platform routes live under /production; farm-scoped data operations under
 * /farms/{farmId}/data.
 */
import apiClient from "./client";
import type { APISuccess } from "@/types";
import type {
  BackupRow, BackupVerification, DiagnosticsReport, ExportDatasetInfo, ExportJobRow,
  ImportEntityInfo, ImportJobRow, ReleaseInfo, ReleaseRow, RestoreRunRow, RetentionResult,
  RollbackVerification, SystemStatus, VerificationResult, VersionInfo,
} from "@/types/production";

// ── Platform ─────────────────────────────────────────────────────────────────

export async function getVersion(): Promise<VersionInfo> {
  const { data } = await apiClient.get<APISuccess<VersionInfo>>("/production/version");
  return data.data;
}

export async function getDiagnostics(): Promise<DiagnosticsReport> {
  const { data } = await apiClient.get<APISuccess<DiagnosticsReport>>("/production/diagnostics");
  return data.data;
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const { data } = await apiClient.get<APISuccess<SystemStatus>>("/production/status");
  return data.data;
}

export async function getReleaseInfo(): Promise<ReleaseInfo> {
  const { data } = await apiClient.get<APISuccess<ReleaseInfo>>("/production/release");
  return data.data;
}

export async function recordRelease(notes?: string): Promise<ReleaseRow> {
  const { data } = await apiClient.post<APISuccess<ReleaseRow>>(
    "/production/release/record", null, { params: notes ? { notes } : undefined },
  );
  return data.data;
}

export async function verifyDeployment(): Promise<VerificationResult> {
  const { data } = await apiClient.post<APISuccess<VerificationResult>>("/production/deployment/verify");
  return data.data;
}

export async function verifyRollback(): Promise<RollbackVerification> {
  const { data } = await apiClient.post<APISuccess<RollbackVerification>>("/production/rollback/verify");
  return data.data;
}

// ── Backups ──────────────────────────────────────────────────────────────────

const dataBase = (farmId: string) => `/farms/${farmId}/data`;

export async function listBackups(farmId: string): Promise<BackupRow[]> {
  const { data } = await apiClient.get<APISuccess<BackupRow[]>>(`${dataBase(farmId)}/backups`);
  return data.data;
}

export async function createBackup(
  farmId: string, input: { label?: string; retention_days?: number },
): Promise<BackupRow> {
  const { data } = await apiClient.post<APISuccess<BackupRow>>(`${dataBase(farmId)}/backups`, input);
  return data.data;
}

export async function verifyBackup(farmId: string, backupId: string): Promise<BackupVerification> {
  const { data } = await apiClient.get<APISuccess<BackupVerification>>(
    `${dataBase(farmId)}/backups/${backupId}/verify`,
  );
  return data.data;
}

export async function deleteBackup(farmId: string, backupId: string): Promise<void> {
  await apiClient.delete(`${dataBase(farmId)}/backups/${backupId}`);
}

export async function restoreBackup(
  farmId: string, input: { backup_id: string; dry_run: boolean; overwrite?: boolean },
): Promise<RestoreRunRow> {
  const { data } = await apiClient.post<APISuccess<RestoreRunRow>>(`${dataBase(farmId)}/restore`, input);
  return data.data;
}

export async function listRestores(farmId: string): Promise<RestoreRunRow[]> {
  const { data } = await apiClient.get<APISuccess<RestoreRunRow[]>>(`${dataBase(farmId)}/restores`);
  return data.data;
}

export async function applyRetention(farmId: string): Promise<RetentionResult> {
  const { data } = await apiClient.post<APISuccess<RetentionResult>>(
    `${dataBase(farmId)}/backups/retention`,
  );
  return data.data;
}

// ── Imports ──────────────────────────────────────────────────────────────────

export async function listImportEntities(farmId: string): Promise<ImportEntityInfo[]> {
  const { data } = await apiClient.get<APISuccess<ImportEntityInfo[]>>(
    `${dataBase(farmId)}/imports/entities`,
  );
  return data.data;
}

export async function listImports(farmId: string): Promise<ImportJobRow[]> {
  const { data } = await apiClient.get<APISuccess<ImportJobRow[]>>(`${dataBase(farmId)}/imports`);
  return data.data;
}

export async function runImport(
  farmId: string,
  params: { file: File; entity: string; source_format: string; dry_run: boolean; skip_invalid?: boolean },
): Promise<ImportJobRow> {
  const form = new FormData();
  form.append("file", params.file);
  const { data } = await apiClient.post<APISuccess<ImportJobRow>>(
    `${dataBase(farmId)}/imports`, form,
    {
      params: {
        entity: params.entity,
        source_format: params.source_format,
        dry_run: params.dry_run,
        skip_invalid: params.skip_invalid ?? false,
      },
      // Let the browser set multipart/form-data with its own boundary; the
      // client's JSON default would produce an unparseable body.
      headers: { "Content-Type": undefined as unknown as string },
    },
  );
  return data.data;
}

// ── Exports ──────────────────────────────────────────────────────────────────

export async function listExportDatasets(farmId: string): Promise<ExportDatasetInfo[]> {
  const { data } = await apiClient.get<APISuccess<ExportDatasetInfo[]>>(
    `${dataBase(farmId)}/exports/datasets`,
  );
  return data.data;
}

export async function listExports(farmId: string): Promise<ExportJobRow[]> {
  const { data } = await apiClient.get<APISuccess<ExportJobRow[]>>(`${dataBase(farmId)}/exports`);
  return data.data;
}

/** Streams a file back; the caller triggers the download. */
export async function downloadExport(
  farmId: string, dataset: string, exportFormat: string,
): Promise<{ blob: Blob; filename: string }> {
  const res = await apiClient.get(`${dataBase(farmId)}/exports/download`, {
    params: { dataset, export_format: exportFormat },
    responseType: "blob",
  });
  return { blob: res.data as Blob, filename: filenameFrom(res.headers, `${dataset}.${exportFormat}`) };
}

export async function downloadImportTemplate(farmId: string, entity: string): Promise<Blob> {
  const res = await apiClient.get(`${dataBase(farmId)}/imports/template`, {
    params: { entity }, responseType: "blob",
  });
  return res.data as Blob;
}

export async function downloadBackup(farmId: string, backupId: string): Promise<Blob> {
  const res = await apiClient.get(`${dataBase(farmId)}/backups/${backupId}/download`, {
    responseType: "blob",
  });
  return res.data as Blob;
}

// ── Download helpers ─────────────────────────────────────────────────────────

/** Pull the server-supplied filename out of Content-Disposition. */
function filenameFrom(headers: unknown, fallback: string): string {
  const raw = (headers as Record<string, string> | undefined)?.["content-disposition"];
  const match = raw?.match(/filename="?([^"]+)"?/);
  return match?.[1] ?? fallback;
}

/** Save a blob to disk under the given name. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoking immediately can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
