/**
 * BSF Environment API (Module 16).
 *
 * Immutable environmental readings for a production unit, returned with a live,
 * deterministic threshold assessment against the species' recommended ranges.
 * Per-unit assessment + stability come straight from the backend engine.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/bsf/environment`;

export const ENV_SOURCES = ["manual", "sensor", "scheduled"] as const;

export interface EnvReading {
  id: string;
  farm_id: string;
  production_unit_id: string | null;
  batch_id: string | null;
  recorded_at: string;
  temperature_c: string | null;
  humidity_pct: string | null;
  moisture_pct: string | null;
  airflow_mps: string | null;
  source: string;
  notes: string | null;
}

export interface Violation {
  parameter: string;
  status: string;
  severity: "critical" | "warning";
  value: number;
  min: number | null;
  max: number | null;
  unit: string;
  detail: string;
}

export interface Assessment {
  overall: "ok" | "warning" | "critical";
  parameters: Record<string, { label: string; value: unknown; detail?: string }>;
  violations: Violation[];
}

export interface ReadingResult {
  reading: EnvReading;
  assessment: Assessment;
}

export interface UnitAssessment {
  unit_id: string;
  latest_recorded_at?: string | null;
  assessment: Assessment | null;
  stability: Record<string, { label: string; value: unknown; detail?: string }>;
  reading_count?: number;
}

export async function listReadings(
  farmId: string, params: { production_unit_id?: string; batch_id?: string; limit?: number } = {},
): Promise<EnvReading[]> {
  const { data } = await apiClient.get<APISuccess<EnvReading[]>>(`${base(farmId)}/readings`, { params });
  return data.data;
}

export async function recordReading(
  farmId: string,
  body: { production_unit_id?: string | null; batch_id?: string | null; temperature_c?: number | null; humidity_pct?: number | null; moisture_pct?: number | null; airflow_mps?: number | null; source?: string; notes?: string },
): Promise<ReadingResult> {
  const { data } = await apiClient.post<APISuccess<ReadingResult>>(`${base(farmId)}/readings`, body);
  return data.data;
}

export async function getUnitAssessment(farmId: string, unitId: string): Promise<UnitAssessment> {
  const { data } = await apiClient.get<APISuccess<UnitAssessment>>(`${base(farmId)}/units/${unitId}/assessment`);
  return data.data;
}
