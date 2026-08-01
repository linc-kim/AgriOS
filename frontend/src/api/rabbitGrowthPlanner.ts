/**
 * Rabbit Growth Planner API (Module 17) — a thin client over the PLATFORM Growth
 * Planner (module='rabbit'). No rabbit-specific planner exists: plans/goals/
 * milestones/progress are the platform's, computed by the backend from recorded
 * data. The frontend renders progress honesty-labelled and never recomputes.
 */
import apiClient from "./client";
import type { Figure } from "./rabbit";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/rabbit/growth`;

export interface Goal {
  id: string; plan_id: string; metric_key: string; label: string; unit: string | null;
  baseline_value: string | null; target_value: string; target_date: string | null; status: string; is_primary: boolean;
}
export interface Milestone {
  id: string; plan_id: string; title: string; description: string | null; sequence: number;
  target_date: string | null; status: string; target_metric_key: string | null;
  target_metric_value: string | null; expected_impact: string | null; dependencies: unknown[];
}
export interface Plan {
  id: string; farm_id: string; module: string; title: string; description: string | null;
  status: string; is_primary: boolean; current_revision: number;
}
export interface GoalProgress {
  goal_id: string; metric_key: string; label: string; unit: string | null;
  is_primary: boolean; progress: Record<string, Figure>; run_rate: Record<string, Figure>;
}
export interface PlanProgress {
  overall_percent: Figure;
  goals: GoalProgress[];
  milestones: { total: Figure; by_status: Record<string, number>; completion_pct: Figure; next_milestone: Record<string, unknown> | null };
}
export interface PlanDetail extends Plan {
  goals: Goal[];
  milestones: Milestone[];
  progress: PlanProgress;
}
export interface GoalInput {
  metric_key: string; label: string; unit?: string | null; baseline_value?: number | null;
  target_value: number; target_date?: string | null; is_primary?: boolean;
}

/** Metric keys the rabbit provider resolves from recorded facts. */
export const RABBIT_METRIC_KEYS = [
  "herd_size", "breeding_does", "monthly_kits", "total_kits",
  "monthly_litters", "monthly_revenue", "total_revenue",
] as const;

export async function listPlans(farmId: string): Promise<Plan[]> {
  const { data } = await apiClient.get<APISuccess<Plan[]>>(`${base(farmId)}/plans`);
  return data.data;
}
export async function createPlan(
  farmId: string,
  body: { title: string; description?: string; is_primary?: boolean; goals?: GoalInput[] },
): Promise<Plan> {
  const { data } = await apiClient.post<APISuccess<Plan>>(`${base(farmId)}/plans`, body);
  return data.data;
}
export async function getPlanDetail(farmId: string, planId: string): Promise<PlanDetail> {
  const { data } = await apiClient.get<APISuccess<PlanDetail>>(`${base(farmId)}/plans/${planId}`);
  return data.data;
}
