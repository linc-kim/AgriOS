/**
 * Rabbit Mission Control API (Module 17) — the strategic briefing composed by the
 * deterministic engines. Read-only; every insight cites recorded/calculated evidence.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export interface InsightEvidence {
  source: string;
  value: string | null;
  fact_type: string;
}

export interface Insight {
  category: string;
  severity: string;
  title: string;
  detail: string;
  evidence: InsightEvidence[];
  confidence: string;
  limitations: string;
}

export interface Briefing {
  headline: string;
  summaries: Record<string, unknown>;
  insights: Insight[];
  priorities: string[];
  counts: Record<string, number>;
}

export async function getRabbitBriefing(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Briefing>>(`/farms/${farmId}/mission/rabbit/briefing`);
  return data.data;
}
