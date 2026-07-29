/**
 * Aviculture ARIA API (Module 15, Part 10).
 *
 * The aviculture assistant. Deterministic-first: factual questions are answered
 * from recorded facts (provider="deterministic"); open questions are explained by
 * the AI with a grounded offline fallback. ARIA never diagnoses disease. Every
 * answer is honesty-labelled (provider + fact_type + sources + confidence).
 */
import apiClient from "./client";

type APISuccess<T> = { data: T };

const base = (farmId: string) => `/farms/${farmId}/aviculture/aria`;

export interface AskResponse {
  provider: string;    // deterministic | gemini | claude | offline
  engine: string;
  fact_type: string;   // recorded_fact | calculated | ai_suggestion | unavailable
  answer: string;
  sources: string[];
  safety: string[];    // e.g. ["no_diagnosis"]
  confidence: string;
  ai_enabled: boolean;
}

export interface SpeciesKnowledge {
  species: string;
  scientific_name: string | null;
  group: string;
  conservation_status: string | null;
  profile: Record<string, unknown>;
  label: string;
  detail: string;
  disclaimer: string;
}

export async function askAria(farmId: string, question: string): Promise<AskResponse> {
  const { data } = await apiClient.post<APISuccess<AskResponse>>(`${base(farmId)}/ask`, { question });
  return data.data;
}
export async function getAriaContext(farmId: string): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get<APISuccess<{ context: Record<string, unknown> }>>(`${base(farmId)}/context`);
  return data.data.context;
}
export async function getSpeciesKnowledge(farmId: string, speciesId: string): Promise<SpeciesKnowledge> {
  const { data } = await apiClient.get<APISuccess<SpeciesKnowledge>>(`${base(farmId)}/species/${speciesId}/knowledge`);
  return data.data;
}
