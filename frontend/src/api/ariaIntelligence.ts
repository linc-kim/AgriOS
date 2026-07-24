/**
 * ARIA farm intelligence — the deterministic operations-manager API (Part 4).
 *
 * Briefing, checklist, insights, trends and health score, plus the deterministic
 * answer path (knowledge base + decision support). None of it touches Gemini or
 * Claude, so the whole surface works with no AI provider configured.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export interface AriaInsight {
  key: string;
  title: string;
  problem: string;
  reason: string;
  action: string;
  benefit: string;
  confidence: string;
  sources: string[];
  priority: "high" | "medium" | "low";
}

export interface AriaChecklistItem {
  key: string;
  label: string;
  done: boolean;
  reason: string;
  priority: "high" | "medium" | "low";
}

export interface AriaTrend {
  metric: string;
  direction: "up" | "down" | "steady";
  change_pct: number | null;
  explanation: string;
  grounded: boolean;
  sources: string[];
}

export interface AriaHealthFactor {
  key: string;
  label: string;
  score: number;
  max_score: number;
  status: "ok" | "warn" | "fail";
  explanation: string;
}

export interface AriaHealthScore {
  score: number;
  max_score: number;
  grade: "excellent" | "good" | "fair" | "poor";
  factors: AriaHealthFactor[];
}

export interface AriaBriefing {
  farm_name: string;
  as_of: string;
  greeting: string;
  lines: string[];
  priorities: string[];
  health_score: number;
  notes: string[];
}

export interface AriaIntelligence {
  briefing: AriaBriefing;
  health: AriaHealthScore;
  insights: AriaInsight[];
  checklist: AriaChecklistItem[];
  trends: AriaTrend[];
}

export interface AriaKnowledgeAnswer {
  key: string;
  title: string;
  category: string;
  explanation: string;
  best_practices: string[];
  warnings: string[];
  source: string;
  vet_now: boolean;
  confidence: string;
}

export interface AriaDecisionAnswer {
  question: string;
  lean: "consider" | "caution" | "hold" | "need_info";
  headline: string;
  pros: string[];
  cons: string[];
  assumptions: string[];
  risks: string[];
  missing: string[];
  sources: string[];
}

export interface AriaAnswer {
  type: "knowledge" | "decision" | "none";
  knowledge: AriaKnowledgeAnswer | null;
  decision: AriaDecisionAnswer | null;
}

export async function getIntelligence(farmId: string): Promise<AriaIntelligence> {
  const { data } = await apiClient.get<APISuccess<AriaIntelligence>>(
    `/farms/${farmId}/aria/intelligence`,
  );
  return data.data;
}

/**
 * Deterministic answer to a question — knowledge or decision. `type: "none"`
 * means neither applied and the caller should fall back to its own snapshot
 * answers rather than invent one.
 */
export async function askDeterministic(farmId: string, question: string): Promise<AriaAnswer> {
  const { data } = await apiClient.post<APISuccess<AriaAnswer>>(
    `/farms/${farmId}/aria/answer`,
    { question },
  );
  return data.data;
}
