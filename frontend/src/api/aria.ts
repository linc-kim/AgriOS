/**
 * Greena — ARIA AI API Client
 * Sprint 6: Conversations, insights, recommendations, usage/quota.
 * All functions unwrap APISuccess<T> before returning.
 */

import apiClient from "./client";
import type {
  AIConversationDetail,
  AIConversationSummary,
  AIInsightListResponse,
  AIRecommendationListResponse,
  ARIAMessageCreate,
  ARIAResponse,
  AIUsageResponse,
  AIInsight,
  AIRecommendation,
} from "@/types";

type APISuccess<T> = { data: T; success: true };

// ── Conversations ─────────────────────────────────────────────────────────────

export async function sendARIAMessage(
  farmId: string,
  payload: ARIAMessageCreate
): Promise<ARIAResponse> {
  const res = await apiClient.post<APISuccess<ARIAResponse>>(
    `/farms/${farmId}/aria/chat`,
    payload
  );
  return res.data.data;
}

export async function listConversations(
  farmId: string,
  params?: { limit?: number; offset?: number }
): Promise<AIConversationSummary[]> {
  const res = await apiClient.get<APISuccess<AIConversationSummary[]>>(
    `/farms/${farmId}/aria/conversations`,
    { params }
  );
  return res.data.data;
}

export async function getConversation(
  farmId: string,
  conversationId: string
): Promise<AIConversationDetail> {
  const res = await apiClient.get<APISuccess<AIConversationDetail>>(
    `/farms/${farmId}/aria/conversations/${conversationId}`
  );
  return res.data.data;
}

export async function deleteConversation(
  farmId: string,
  conversationId: string
): Promise<void> {
  await apiClient.delete(`/farms/${farmId}/aria/conversations/${conversationId}`);
}

// ── Insights ──────────────────────────────────────────────────────────────────

export async function listInsights(
  farmId: string,
  params?: { include_dismissed?: boolean }
): Promise<AIInsightListResponse> {
  const res = await apiClient.get<APISuccess<AIInsightListResponse>>(
    `/farms/${farmId}/aria/insights`,
    { params }
  );
  return res.data.data;
}

export async function dismissInsight(
  farmId: string,
  insightId: string
): Promise<AIInsight> {
  const res = await apiClient.patch<APISuccess<AIInsight>>(
    `/farms/${farmId}/aria/insights/${insightId}/dismiss`,
    {}
  );
  return res.data.data;
}

// ── Recommendations ───────────────────────────────────────────────────────────

export async function listRecommendations(
  farmId: string,
  params?: { status?: string }
): Promise<AIRecommendationListResponse> {
  const res = await apiClient.get<APISuccess<AIRecommendationListResponse>>(
    `/farms/${farmId}/aria/recommendations`,
    { params }
  );
  return res.data.data;
}

export async function actionRecommendation(
  farmId: string,
  recommendationId: string,
  action: "acted" | "dismissed"
): Promise<AIRecommendation> {
  const res = await apiClient.patch<APISuccess<AIRecommendation>>(
    `/farms/${farmId}/aria/recommendations/${recommendationId}/action`,
    { action }
  );
  return res.data.data;
}

// ── Usage / Quota ─────────────────────────────────────────────────────────────

export async function getARIAUsage(farmId: string): Promise<AIUsageResponse> {
  const res = await apiClient.get<APISuccess<AIUsageResponse>>(
    `/farms/${farmId}/aria/usage`
  );
  return res.data.data;
}
