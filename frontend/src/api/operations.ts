/**
 * ARIA Operations Director API (Module 13 Part 7).
 *
 * The organization-scale view: aggregated organization facts, cross-farm
 * comparison, the unified operations dashboard, the merged timeline, performance
 * analytics, organization reports and task assignment. All deterministic — no
 * endpoint here reaches Gemini or Claude.
 *
 * Every aggregate carries its provenance (source farms, missing farms, method),
 * so the UI can render "not enough recorded data" honestly and never a
 * fabricated total.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export type Severity = "normal" | "watch" | "warning" | "critical";

export interface OpsAggregate {
  key: string;
  label: string;
  value: string | null;
  unit: string;
  available: boolean;
  source_farms: string[];
  missing_farms: string[];
  method: string;
}

export interface OpsOrgPriority {
  rank: number;
  label: string;
  why: string;
  farm_id: string;
  farm_name: string;
  severity: Severity;
  source: string;
}

export interface OpsOrganizationFacts {
  organization_name: string;
  as_of: string;
  farm_count: number;
  farm_names: string[];
  overall: Severity;
  health: OpsAggregate;
  production: OpsAggregate;
  mortality: OpsAggregate;
  feed_usage: OpsAggregate;
  water_usage: OpsAggregate;
  inventory: OpsAggregate;
  financial: OpsAggregate;
  priorities: OpsOrgPriority[];
  silent_farms: string[];
}

export interface OpsFarmRank {
  farm_id: string;
  farm_name: string;
  value: number | null;
  display: string;
  available: boolean;
}

export interface OpsRanking {
  key: string;
  label: string;
  unit: string;
  higher_is_better: boolean;
  ranked: OpsFarmRank[];
  missing: OpsFarmRank[];
  best: OpsFarmRank | null;
  needs_attention: OpsFarmRank | null;
  average: string | null;
  method: string;
}

export interface OpsComparison {
  farm_count: number;
  rankings: OpsRanking[];
}

export interface OpsWorker {
  user_id: string;
  name: string;
  role: string;
  role_label: string;
  farm_ids: string[];
  farm_names: string[];
}

export interface OpsTaskHistoryEvent {
  at: string;
  action: string;
  actor: string;
  detail: string;
}

export type TaskStatus = "open" | "overdue" | "done";

export interface OpsTask {
  task_id: string;
  farm_id: string;
  farm_name: string;
  title: string;
  status: TaskStatus;
  priority: string;
  owner_id: string | null;
  owner_name: string | null;
  due_at: string | null;
  created_at: string | null;
  completed_at: string | null;
  history: OpsTaskHistoryEvent[];
}

export interface OpsFarmSummary {
  farm_id: string;
  farm_name: string;
  overall: Severity;
  health_score: number;
  open_tasks: number;
  overdue_tasks: number;
  alert_count: number;
  silent: boolean;
}

export interface OpsAlert {
  at: string;
  farm_id: string;
  farm_name: string;
  kind: string;
  title: string;
  detail: string;
  severity: Severity;
}

export interface OpsNotification {
  at: string;
  farm_id: string;
  farm_name: string;
  title: string;
  body: string;
  severity: string;
}

export interface OpsDashboard {
  as_of: string;
  tier: string;
  sections: string[];
  organization: OpsOrganizationFacts;
  farms: OpsFarmSummary[];
  alerts: OpsAlert[];
  priorities: OpsOrgPriority[];
  tasks: OpsTask[];
  workers: OpsWorker[];
  notifications: OpsNotification[];
  operational_status: string;
}

export interface OpsTimelineEvent {
  at: string;
  farm_id: string;
  farm_name: string;
  kind: string;
  title: string;
  detail: string;
  worker: string | null;
  severity: Severity;
}

export interface OpsWorkerPerformance {
  user_id: string;
  name: string;
  assigned: number;
  completed: number;
  overdue: number;
  completion_rate: string | null;
  avg_completion_hours: string | null;
  method: string;
}

export interface OpsMetric {
  key: string;
  label: string;
  value: string | null;
  unit: string;
  available: boolean;
  method: string;
  detail: string;
}

export interface OpsAnalytics {
  workers: OpsWorkerPerformance[];
  farm_productivity: OpsMetric[];
  org_metrics: OpsMetric[];
  trends: OpsMetric[];
}

export interface OpsReportSection {
  label: string;
  value: string;
  available: boolean;
  method: string;
}

export interface OpsReport {
  period: string;
  label: string;
  as_of: string;
  organization_name: string;
  farm_count: number;
  sections: OpsReportSection[];
  risks: string[];
  priorities: string[];
  notes: string[];
}

export interface DashboardParams {
  farm_id?: string;
  worker_id?: string;
  severity?: Severity;
  since?: string;
  until?: string;
}

const base = (orgId: string) => `/organizations/${orgId}/operations`;

export async function getDashboard(orgId: string, params: DashboardParams = {}): Promise<OpsDashboard> {
  const { data } = await apiClient.get<APISuccess<OpsDashboard>>(`${base(orgId)}/dashboard`, { params });
  return data.data;
}

export async function getOrganizationFacts(orgId: string): Promise<OpsOrganizationFacts> {
  const { data } = await apiClient.get<APISuccess<OpsOrganizationFacts>>(`${base(orgId)}/organization`);
  return data.data;
}

export async function getComparison(orgId: string): Promise<OpsComparison> {
  const { data } = await apiClient.get<APISuccess<OpsComparison>>(`${base(orgId)}/farms`);
  return data.data;
}

export async function getWorkers(orgId: string): Promise<OpsWorker[]> {
  const { data } = await apiClient.get<APISuccess<OpsWorker[]>>(`${base(orgId)}/workers`);
  return data.data;
}

export async function getTasks(
  orgId: string,
  params: { farm_id?: string; worker_id?: string; include_done?: boolean } = {},
): Promise<OpsTask[]> {
  const { data } = await apiClient.get<APISuccess<OpsTask[]>>(`${base(orgId)}/tasks`, { params });
  return data.data;
}

export async function getTimeline(
  orgId: string,
  params: { days?: number; limit?: number; farm_id?: string; worker?: string; severity?: Severity } = {},
): Promise<OpsTimelineEvent[]> {
  const { data } = await apiClient.get<APISuccess<OpsTimelineEvent[]>>(`${base(orgId)}/timeline`, { params });
  return data.data;
}

export async function getAnalytics(orgId: string): Promise<OpsAnalytics> {
  const { data } = await apiClient.get<APISuccess<OpsAnalytics>>(`${base(orgId)}/analytics`);
  return data.data;
}

export async function getReport(orgId: string, period: "daily" | "weekly" | "monthly"): Promise<OpsReport> {
  const { data } = await apiClient.get<APISuccess<OpsReport>>(`${base(orgId)}/reports`, { params: { period } });
  return data.data;
}

export async function assignTask(orgId: string, taskId: string, ownerId: string): Promise<OpsTask> {
  const { data } = await apiClient.post<APISuccess<OpsTask>>(
    `${base(orgId)}/tasks/${taskId}/assign`,
    { owner_id: ownerId },
  );
  return data.data;
}

export async function completeTask(orgId: string, taskId: string): Promise<OpsTask> {
  const { data } = await apiClient.post<APISuccess<OpsTask>>(`${base(orgId)}/tasks/${taskId}/complete`, {});
  return data.data;
}
