/**
 * Greena — ARIA AI Platform API Client (Module 9).
 */
import apiClient from "./client";
import type {
  AIAskResponse, AIDashboard, AIDiseaseRisk, AIForecasts, AIMortalityPrediction, APISuccess,
} from "@/types";

const base = (farmId: string) => `/farms/${farmId}/ai`;

export async function getAIDashboard(farmId: string): Promise<AIDashboard> {
  const { data } = await apiClient.get<APISuccess<AIDashboard>>(`${base(farmId)}/dashboard`);
  return data.data;
}
export async function getAIForecasts(farmId: string): Promise<AIForecasts> {
  const { data } = await apiClient.get<APISuccess<AIForecasts>>(`${base(farmId)}/forecasts`);
  return data.data;
}
export async function getMortalityPrediction(farmId: string): Promise<AIMortalityPrediction> {
  const { data } = await apiClient.get<APISuccess<AIMortalityPrediction>>(`${base(farmId)}/predictions/mortality`);
  return data.data;
}
export async function getDiseaseRisk(farmId: string): Promise<AIDiseaseRisk> {
  const { data } = await apiClient.get<APISuccess<AIDiseaseRisk>>(`${base(farmId)}/predictions/disease-risk`);
  return data.data;
}
export async function askAI(farmId: string, question: string): Promise<AIAskResponse> {
  const { data } = await apiClient.post<APISuccess<AIAskResponse>>(`${base(farmId)}/ask`, { question });
  return data.data;
}
