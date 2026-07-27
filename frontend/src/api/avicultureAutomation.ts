/**
 * Aviculture Automation API (Module 15, Part 9).
 *
 * Deterministic operational reminders/tasks (materialised into the platform
 * Reminder engine, tagged aviculture) and staged workflows. Each computed item
 * carries Priority / Reason / Evidence / Suggested-Due — the honesty contract.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T };

const base = (farmId: string) => `/farms/${farmId}/aviculture`;

export interface OperationalItem {
  kind: string;
  title: string;
  priority: string;
  reason: string;
  evidence: Record<string, unknown>;
  suggested_due_on: string | null;
  dedup_key: string;
}

export interface GenerateResult { created: number; skipped: number; notified: number; evaluated: number; }

export interface Task {
  id: string;
  farm_id: string;
  title: string;
  notes: string | null;
  due_at: string;
  priority: string;
  is_done: boolean;
  metadata: Record<string, unknown>;
}

export interface Workflow {
  id: string;
  bird_id: string | null;
  workflow_type: string;
  current_stage: string;
  status: string;
  started_on: string;
  completed_on: string | null;
  notes: string | null;
  stages: string[];
}

export interface WorkflowEvent {
  id: string; workflow_id: string; from_stage: string | null; to_stage: string; occurred_on: string; note: string | null;
}

export async function previewAutomation(farmId: string, horizonDays = 30): Promise<OperationalItem[]> {
  const { data } = await apiClient.get<APISuccess<OperationalItem[]>>(`${base(farmId)}/automation/preview`, { params: { horizon_days: horizonDays } });
  return data.data;
}
export async function generateReminders(farmId: string): Promise<GenerateResult> {
  const { data } = await apiClient.post<APISuccess<GenerateResult>>(`${base(farmId)}/automation/generate`, {});
  return data.data;
}
export async function listTasks(farmId: string, includeDone = false): Promise<Task[]> {
  const { data } = await apiClient.get<APISuccess<Task[]>>(`${base(farmId)}/tasks`, { params: { include_done: includeDone } });
  return data.data;
}
export async function completeTask(farmId: string, reminderId: string): Promise<Task> {
  const { data } = await apiClient.post<APISuccess<Task>>(`${base(farmId)}/tasks/${reminderId}/complete`, {});
  return data.data;
}
export async function listWorkflows(farmId: string, status?: string): Promise<Workflow[]> {
  const { data } = await apiClient.get<APISuccess<Workflow[]>>(`${base(farmId)}/workflows`, { params: status ? { status } : undefined });
  return data.data;
}
export async function startWorkflow(farmId: string, body: { workflow_type: string; bird_id?: string; notes?: string }): Promise<Workflow> {
  const { data } = await apiClient.post<APISuccess<Workflow>>(`${base(farmId)}/workflows`, body);
  return data.data;
}
export async function advanceWorkflow(farmId: string, workflowId: string, note?: string): Promise<Workflow> {
  const { data } = await apiClient.post<APISuccess<Workflow>>(`${base(farmId)}/workflows/${workflowId}/advance`, { note });
  return data.data;
}
