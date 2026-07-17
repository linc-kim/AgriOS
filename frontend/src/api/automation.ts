/**
 * Greena — Automation & Notifications API Client (Module 8).
 */
import apiClient from "./client";
import type {
  APISuccess, ActivityNotification, AutomationRule, EngineRunResult, Reminder,
} from "@/types";

const base = (farmId: string) => `/farms/${farmId}/automation`;

// Rules
export async function listRules(farmId: string): Promise<AutomationRule[]> {
  const { data } = await apiClient.get<APISuccess<AutomationRule[]>>(`${base(farmId)}/rules`);
  return data.data;
}
export async function createRule(farmId: string, input: { name: string; trigger_type: string; conditions?: Record<string, any>; actions?: Record<string, any>[]; priority?: string; description?: string }): Promise<AutomationRule> {
  const { data } = await apiClient.post<APISuccess<AutomationRule>>(`${base(farmId)}/rules`, input);
  return data.data;
}
export async function updateRule(farmId: string, id: string, input: Record<string, any>): Promise<AutomationRule> {
  const { data } = await apiClient.patch<APISuccess<AutomationRule>>(`${base(farmId)}/rules/${id}`, input);
  return data.data;
}
export async function deleteRule(farmId: string, id: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/rules/${id}`);
}

// Reminders
export async function listReminders(farmId: string, includeDone = false): Promise<Reminder[]> {
  const { data } = await apiClient.get<APISuccess<Reminder[]>>(`${base(farmId)}/reminders`, { params: { include_done: includeDone } });
  return data.data;
}
export async function createReminder(farmId: string, input: { title: string; due_at: string; notes?: string; recurrence?: string; priority?: string }): Promise<Reminder> {
  const { data } = await apiClient.post<APISuccess<Reminder>>(`${base(farmId)}/reminders`, input);
  return data.data;
}
export async function updateReminder(farmId: string, id: string, input: Record<string, any>): Promise<Reminder> {
  const { data } = await apiClient.patch<APISuccess<Reminder>>(`${base(farmId)}/reminders/${id}`, input);
  return data.data;
}
export async function deleteReminder(farmId: string, id: string): Promise<void> {
  await apiClient.delete(`${base(farmId)}/reminders/${id}`);
}

// Engine + triggers
export async function runEngine(farmId: string): Promise<EngineRunResult> {
  const { data } = await apiClient.post<APISuccess<EngineRunResult>>(`${base(farmId)}/run`);
  return data.data;
}
export async function listTriggers(farmId: string): Promise<string[]> {
  const { data } = await apiClient.get<APISuccess<string[]>>(`${base(farmId)}/triggers`);
  return data.data;
}

// Activity
export async function listActivity(farmId: string, params?: { status?: string; q?: string; priority?: string }): Promise<ActivityNotification[]> {
  const { data } = await apiClient.get<APISuccess<ActivityNotification[]>>(`${base(farmId)}/activity`, { params });
  return data.data;
}
export async function archiveNotification(farmId: string, id: string, archived = true): Promise<ActivityNotification> {
  const { data } = await apiClient.post<APISuccess<ActivityNotification>>(`${base(farmId)}/activity/${id}/archive`, null, { params: { archived } });
  return data.data;
}
