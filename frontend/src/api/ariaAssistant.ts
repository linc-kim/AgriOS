/**
 * ARIA AI Assistant API (Module 13 Part 8).
 *
 * The final ARIA surface: the deterministic-first router (made transparent), the
 * multimodal assistant (text, transcribed voice, images, documents), retrieval
 * over uploaded documents, and AI settings + the cost dashboard.
 *
 * Everything is deterministic-first — the assistant reaches Gemini only when the
 * router says a deterministic engine can't answer, and falls back to a grounded
 * offline reply when no provider is configured. The `engine`/`provider` fields on
 * every reply say which path actually ran, so the UI can show it honestly.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export type Engine = "deterministic" | "gemini" | "hybrid";
export type Provider = "deterministic" | "gemini" | "claude" | "offline";

export interface RouteDecision {
  target: string;
  engine: Engine;
  modality: string;
  needs_gemini: boolean;
  deterministic_first: boolean;
  reason: string;
  language: string;
  mixed_language: boolean;
  safety: string[];
  confidence: number;
}

export interface AssistResponse {
  handled: boolean;
  route: string;
  engine: string;
  provider: Provider;
  answer: string;
  language: string;
  mixed_language: boolean;
  safety: string[];
  sources: string[];
  needs_confirmation: boolean;
  data: Record<string, unknown>;
}

export interface AISettings {
  farm_id: string;
  ai_enabled: boolean;
  model: "gemini-flash" | "gemini-pro" | "offline";
  temperature: number;
  max_output_tokens: number;
  allow_vision: boolean;
  allow_documents: boolean;
  monthly_budget_usd: number | null;
  providers: Record<string, boolean>;
}

export interface AIUsage {
  total: { tokens: number; cost_usd: number; calls: number };
  this_month: { tokens: number; cost_usd: number; calls: number };
  by_provider: { provider: string; calls: number; cost_usd: number; tokens: number }[];
  monthly_budget_usd: number | null;
}

export interface DocumentTable {
  kind: string;
  headers: string[];
  row_count: number;
  preview: string[][];
}

export interface DocumentIngest {
  stored: boolean;
  document_id?: string;
  filename?: string;
  kind?: string;
  deterministic?: boolean;
  table_count?: number;
  tables: DocumentTable[];
  note: string;
  reason: string;
}

export interface AIDocument {
  id: string;
  filename: string;
  kind: string;
  table_count: number;
  size_bytes: number;
  created_at: string;
}

export interface Citation {
  doc_id: string;
  filename: string;
  snippet: string;
  score: number;
}

const base = (farmId: string) => `/farms/${farmId}/aria`;

export async function routePreview(
  farmId: string,
  text: string,
  attachments: { filename: string; mime: string; size_bytes: number }[] = [],
): Promise<RouteDecision> {
  const { data } = await apiClient.post<APISuccess<RouteDecision>>(
    `${base(farmId)}/route`, { text, attachments });
  return data.data;
}

export async function assist(
  farmId: string,
  text: string,
  state?: Record<string, unknown> | null,
): Promise<AssistResponse> {
  const { data } = await apiClient.post<APISuccess<AssistResponse>>(
    `${base(farmId)}/assistant`, { text, state: state ?? null });
  return data.data;
}

export async function assistImage(
  farmId: string,
  file: File,
  caption = "",
): Promise<AssistResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("caption", caption);
  const { data } = await apiClient.post<APISuccess<AssistResponse>>(
    `${base(farmId)}/assistant/image`, form);
  return data.data;
}

export async function uploadDocument(farmId: string, file: File): Promise<DocumentIngest> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<APISuccess<DocumentIngest>>(
    `${base(farmId)}/assistant/document`, form);
  return data.data;
}

export async function listDocuments(farmId: string): Promise<AIDocument[]> {
  const { data } = await apiClient.get<APISuccess<AIDocument[]>>(`${base(farmId)}/documents`);
  return data.data;
}

export async function searchDocuments(farmId: string, q: string): Promise<Citation[]> {
  const { data } = await apiClient.get<APISuccess<{ query: string; citations: Citation[] }>>(
    `${base(farmId)}/documents/search`, { params: { q } });
  return data.data.citations;
}

export async function getSettings(farmId: string): Promise<AISettings> {
  const { data } = await apiClient.get<APISuccess<AISettings>>(`${base(farmId)}/settings`);
  return data.data;
}

export async function updateSettings(farmId: string, changes: Partial<AISettings>): Promise<AISettings> {
  const { data } = await apiClient.put<APISuccess<AISettings>>(`${base(farmId)}/settings`, changes);
  return data.data;
}

export async function getUsage(farmId: string): Promise<AIUsage> {
  const { data } = await apiClient.get<APISuccess<AIUsage>>(`${base(farmId)}/settings/usage`);
  return data.data;
}
