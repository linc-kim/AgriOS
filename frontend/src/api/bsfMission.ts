/**
 * BSF Mission Control API (Module 16). The strategic briefing composed by Mission
 * Control from the deterministic engines + Growth Planner. Read-only; Mission
 * Control orchestrates and never owns business logic. Every insight cites the
 * recorded/calculated/forecast evidence it rests on.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export interface InsightEvidence { source: string; value: string | null; fact_type: string }
export interface Insight {
  category: string;
  severity: "critical" | "warning" | "watch" | "info";
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

export async function getBsfBriefing(farmId: string): Promise<Briefing> {
  const { data } = await apiClient.get<APISuccess<Briefing>>(`/farms/${farmId}/mission/bsf/briefing`);
  return data.data;
}
