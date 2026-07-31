/**
 * BSF ARIA API (Module 16). ARIA explains, summarises, recommends and answers —
 * advisory only, read-only, never mutating a plan or record. Every answer carries
 * a fact_type honesty label and the sources it rests on.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/bsf/aria`;

export interface AriaAnswer {
  provider: string;
  engine: string;
  fact_type: string; // recorded | calculated | forecast | ai_suggestion | unavailable
  answer: string;
  sources: string[];
  confidence: string;
  ai_enabled: boolean;
}

export async function askAria(farmId: string, question: string): Promise<AriaAnswer> {
  const { data } = await apiClient.post<APISuccess<AriaAnswer>>(`${base(farmId)}/ask`, { question });
  return data.data;
}

export async function getAriaContext(farmId: string): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get<APISuccess<Record<string, unknown>>>(`${base(farmId)}/context`);
  return data.data;
}
