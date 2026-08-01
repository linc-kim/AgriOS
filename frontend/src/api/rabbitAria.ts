/**
 * Rabbit ARIA API (Module 17) — deterministic-first Q&A over the platform AI
 * router. Answers arrive honesty-labelled with cited sources; ARIA never edits data.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

const base = (farmId: string) => `/farms/${farmId}/rabbit/aria`;

export interface AriaAnswer {
  provider: string;
  engine: string;
  fact_type: string;
  answer: string;
  sources: string[];
  confidence: string;
  ai_enabled: boolean;
}

export async function askAria(farmId: string, question: string) {
  const { data } = await apiClient.post<APISuccess<AriaAnswer>>(
    `${base(farmId)}/ask`, { question }, { timeout: 60000 });
  return data.data;
}

export async function getAriaContext(farmId: string) {
  const { data } = await apiClient.get<APISuccess<Record<string, unknown>>>(`${base(farmId)}/context`);
  return data.data;
}
