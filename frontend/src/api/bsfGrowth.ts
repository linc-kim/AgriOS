/**
 * BSF Growth Planner API (Module 16) — a thin client over the platform Growth
 * Planner (module='bsf').
 *
 * Plans, goals, milestones and progress are recorded domain objects. Progress is
 * computed by the backend from recorded operational data; the frontend renders it
 * honesty-labelled and never recomputes. ARIA/Mission Control are advisory only —
 * only these explicit user actions mutate a plan.
 */
import apiClient from "./client";
import type { Figure } from "./bsf";

type APISuccess<T> = { data: T; success: true };
const base = (farmId: string) => `/farms/${farmId}/bsf/growth`;

export const MILESTONE_STATUSES = ["pending", "in_progress", "achieved", "blocked", "skipped"] as const;

export interface Goal {
  id: string;
  plan_id: string;
  metric_key: string;
  label: string;
  unit: string | null;
  baseline_value: string | null;
  target_value: string;
  target_date: string | null;
  status: string;
  is_primary: boolean;
}

export interface Milestone {
  id: string;
  plan_id: string;
  title: string;
  description: string | null;
  sequence: number;
  target_date: string | null;
  status: string;
  target_metric_key: string | null;
  target_metric_value: string | null;
  expected_impact: string | null;
  dependencies: unknown[];
}

export interface Plan {
  id: string;
  farm_id: string;
  module: string;
  title: string;
  description: string | null;
  status: string;
  is_primary: boolean;
  current_revision: number;
}

export interface GoalProgress {
  goal_id: string;
  metric_key: string;
  label: string;
  unit: string | null;
  is_primary: boolean;
  progress: Record<string, Figure>;
  run_rate: Record<string, Figure>;
}

export interface PlanProgress {
  overall_percent: Figure;
  goals: GoalProgress[];
  milestones: {
    total: Figure;
    by_status: Record<string, number>;
    completion_pct: Figure;
    next_milestone: Record<string, unknown> | null;
  };
}

export interface PlanDetail extends Plan {
  goals: Goal[];
  milestones: Milestone[];
  progress: PlanProgress;
}

export interface Revision {
  id: string;
  plan_id: string;
  revision_number: number;
  reason: string | null;
  trigger: string;
  snapshot: Record<string, unknown>;
  created_at: string;
}

export interface GoalInput {
  metric_key: string;
  label: string;
  unit?: string | null;
  baseline_value?: number | null;
  target_value: number;
  target_date?: string | null;
  is_primary?: boolean;
}
export interface MilestoneInput {
  title: string;
  sequence?: number;
  target_date?: string | null;
  expected_impact?: string | null;
}

export async function listPlans(farmId: string): Promise<Plan[]> {
  const { data } = await apiClient.get<APISuccess<Plan[]>>(`${base(farmId)}/plans`);
  return data.data;
}
export async function createPlan(
  farmId: string,
  body: { title: string; description?: string; is_primary?: boolean; goals?: GoalInput[]; milestones?: MilestoneInput[] },
): Promise<Plan> {
  const { data } = await apiClient.post<APISuccess<Plan>>(`${base(farmId)}/plans`, body);
  return data.data;
}
export async function getPlanDetail(farmId: string, planId: string): Promise<PlanDetail> {
  const { data } = await apiClient.get<APISuccess<PlanDetail>>(`${base(farmId)}/plans/${planId}`);
  return data.data;
}
export async function updateMilestoneStatus(farmId: string, planId: string, milestoneId: string, status: string, reason?: string): Promise<PlanDetail> {
  const { data } = await apiClient.patch<APISuccess<PlanDetail>>(`${base(farmId)}/plans/${planId}/milestones/${milestoneId}`, { status, reason });
  return data.data;
}
export async function listRevisions(farmId: string, planId: string): Promise<Revision[]> {
  const { data } = await apiClient.get<APISuccess<Revision[]>>(`${base(farmId)}/plans/${planId}/revisions`);
  return data.data;
}
export async function archivePlan(farmId: string, planId: string): Promise<Plan> {
  const { data } = await apiClient.post<APISuccess<Plan>>(`${base(farmId)}/plans/${planId}/archive`);
  return data.data;
}
