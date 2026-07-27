/**
 * Mission Control API (Module 14).
 *
 * The strategic layer: create a mission, then read the roadmap, living business
 * plan, daily mission, progress, manual, reports and CEO dashboard — all computed
 * live from the mission plus recorded facts, so nothing goes stale. The CEO
 * advisor is grounded in the deterministic engines; Gemini only explains.
 *
 * Every figure carries a `fact_type` so the UI can show the honesty distinction —
 * recorded fact, calculated forecast, strategic recommendation, or AI suggestion —
 * rather than presenting every number as equally certain.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export type FactType =
  | "recorded_fact"
  | "calculated_forecast"
  | "strategic_recommendation"
  | "ai_suggestion";

export interface MValue {
  label: string;
  value: string | null;
  fact_type: FactType;
  detail: string;
  unit: string;
  available: boolean;
}

export interface Metric {
  kind: string;
  label: string;
  target: number | null;
  unit: string;
  primary: boolean;
}

export interface Mission {
  id: string;
  farm_id: string;
  name: string;
  description: string | null;
  target_date: string | null;
  status: string;
  is_primary: boolean;
  success_metrics: Metric[];
  constraints: string[];
  priorities: string[];
  assumptions: { key: string; label?: string; value: unknown; unit?: string; source?: string }[];
  policies: { key: string; statement: string; category?: string; value?: unknown }[];
  baseline: Record<string, number>;
  created_at: string;
}

export interface DiscoveryQuestion {
  key: string;
  prompt: string;
  kind: string;
  unit: string;
  options: string[];
  why: string;
}

export interface Phase {
  index: number;
  name: string;
  objectives: string[];
  infrastructure: string[];
  bird_target: number | null;
  financial_target: MValue;
  operational_targets: string[];
  start_date: string | null;
  end_date: string | null;
  duration_days: number | null;
  completion_criteria: string[];
  dependencies: string[];
  risks: string[];
  fact_type: FactType;
}

export interface Roadmap {
  mission_name: string;
  metric_kind: string;
  baseline_value: number | null;
  target_value: number | null;
  phases: Phase[];
  method: string;
  notes: string[];
}

export interface Milestone {
  name: string;
  target: string;
  done: boolean;
  detail: string;
}

export interface HealthFactor {
  label: string;
  score: number;
  max_score: number;
  explanation: string;
}
export interface MissionHealth {
  score: number;
  grade: string;
  factors: HealthFactor[];
}

export interface DailyMission {
  on: string;
  headline: string;
  phase: string;
  critical_tasks: MValue[];
  risks: MValue[];
  opportunities: MValue[];
  budget: MValue;
  purchases: MValue[];
  records_required: MValue[];
  kpis: MValue[];
}

export interface Dashboard {
  mission_name: string;
  status: string;
  completion_pct: number;
  current_phase: string;
  daily: DailyMission;
  upcoming_milestones: Milestone[];
  risks: MValue[];
  cash_runway: MValue;
  budget_status: MValue;
  population: MValue;
  revenue: MValue;
  profit: MValue;
  operations_health: MValue;
  health: MissionHealth;
  time_remaining_days: number | null;
}

export interface Progress {
  completion_pct: number;
  completion_explanation: string;
  current_phase_name: string;
  current_phase_index: number;
  milestones: Milestone[];
  financial: MValue;
  population: MValue;
  infrastructure: MValue;
  profit: MValue;
  cash_reserve: MValue;
  time_remaining_days: number | null;
  time_elapsed_pct: number | null;
  forecasted_completion: MValue;
  on_track: boolean;
  metrics: MValue[];
}

export interface PlanSection {
  heading: string;
  body: MValue[];
  fact_type: FactType;
}
export interface BusinessPlan {
  mission_name: string;
  as_of: string;
  sections: PlanSection[];
  notes: string[];
}

export interface ManualSection {
  heading: string;
  items: string[];
}
export interface Manual {
  mission_name: string;
  as_of: string;
  sections: ManualSection[];
}

export interface Report {
  period: string;
  label: string;
  as_of: string;
  mission_name: string;
  health: MissionHealth;
  progress_vs_plan: MValue[];
  budget_vs_plan: MValue[];
  growth_vs_plan: MValue[];
  upcoming_decisions: string[];
  recommended_actions: string[];
  notes: string[];
}

export interface Adaptation {
  needed: boolean;
  trigger: string;
  reasons: string[];
  recommendations: string[];
  detail: MValue[];
}

export interface Revision {
  id: string;
  revision_number: number;
  reason: string | null;
  trigger: string;
  snapshot: Record<string, unknown>;
  created_at: string;
}

export interface AdvisorAnswer {
  question: string;
  answer: string;
  provider: string;
  grounded_context: string;
  fact_type: FactType;
  sources: string[];
}

export interface MissionCreate {
  name: string;
  description?: string;
  target_date?: string | null;
  is_primary?: boolean;
  success_metrics: Metric[];
  constraints?: string[];
  priorities?: string[];
  assumptions?: Mission["assumptions"];
  policies?: Mission["policies"];
}

const base = (farmId: string) => `/farms/${farmId}/mission`;

export async function listMissions(farmId: string): Promise<Mission[]> {
  const { data } = await apiClient.get<APISuccess<Mission[]>>(base(farmId));
  return data.data;
}
export async function createMission(farmId: string, body: MissionCreate): Promise<Mission> {
  const { data } = await apiClient.post<APISuccess<Mission>>(base(farmId), body);
  return data.data;
}
export async function getDiscovery(farmId: string): Promise<DiscoveryQuestion[]> {
  const { data } = await apiClient.get<APISuccess<DiscoveryQuestion[]>>(`${base(farmId)}/discovery`);
  return data.data;
}
export async function getDashboard(farmId: string, missionId: string): Promise<Dashboard> {
  const { data } = await apiClient.get<APISuccess<Dashboard>>(`${base(farmId)}/${missionId}/dashboard`);
  return data.data;
}
export async function getRoadmap(farmId: string, missionId: string): Promise<Roadmap> {
  const { data } = await apiClient.get<APISuccess<Roadmap>>(`${base(farmId)}/${missionId}/roadmap`);
  return data.data;
}
export async function getPlan(farmId: string, missionId: string): Promise<BusinessPlan> {
  const { data } = await apiClient.get<APISuccess<BusinessPlan>>(`${base(farmId)}/${missionId}/plan`);
  return data.data;
}
export async function getProgress(farmId: string, missionId: string): Promise<Progress> {
  const { data } = await apiClient.get<APISuccess<Progress>>(`${base(farmId)}/${missionId}/progress`);
  return data.data;
}
export async function getManual(farmId: string, missionId: string): Promise<Manual> {
  const { data } = await apiClient.get<APISuccess<Manual>>(`${base(farmId)}/${missionId}/manual`);
  return data.data;
}
export async function getReport(
  farmId: string, missionId: string, period: "weekly" | "monthly" | "quarterly" | "annual",
): Promise<Report> {
  const { data } = await apiClient.get<APISuccess<Report>>(`${base(farmId)}/${missionId}/reports`, { params: { period } });
  return data.data;
}
export async function getAdaptation(farmId: string, missionId: string): Promise<Adaptation> {
  const { data } = await apiClient.get<APISuccess<Adaptation>>(`${base(farmId)}/${missionId}/adaptation`);
  return data.data;
}
export async function listRevisions(farmId: string, missionId: string): Promise<Revision[]> {
  const { data } = await apiClient.get<APISuccess<Revision[]>>(`${base(farmId)}/${missionId}/revisions`);
  return data.data;
}
export async function replan(
  farmId: string, missionId: string, body: { assumptions?: unknown[]; target_date?: string } = {},
): Promise<{ revision_number: number; applied: boolean; evaluation: Adaptation }> {
  const { data } = await apiClient.post<APISuccess<{ revision_number: number; applied: boolean; evaluation: Adaptation }>>(
    `${base(farmId)}/${missionId}/replan`, body);
  return data.data;
}
export async function askAdvisor(farmId: string, missionId: string, question: string): Promise<AdvisorAnswer> {
  const { data } = await apiClient.post<APISuccess<AdvisorAnswer>>(`${base(farmId)}/${missionId}/advisor`, { question });
  return data.data;
}
