/**
 * ARIA supervisor API (Module 13 Part 5).
 *
 * Monitors, alerts, ranked priorities, timeline and reports — all deterministic,
 * none of it touching Gemini or Claude.
 *
 * `getSupervisor` is read-only by default. Passing `sync` also persists alerts
 * as notifications and creates auto-reminders, so the dashboard never calls it
 * that way on a refresh: a page load must not have side effects.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

export type MonitorState = "normal" | "watch" | "warning" | "critical";

export interface AriaMonitor {
  key: string;
  label: string;
  state: MonitorState;
  why: string;
  evidence: string[];
  /** True when the state is normal only because nothing has been recorded. */
  unmeasured: boolean;
}

export interface AriaAlert {
  key: string;
  severity: MonitorState;
  title: string;
  reason: string;
  evidence: string[];
  action: string;
  monitor: string;
  raised_at: string;
}

export interface AriaPriorityItem {
  key: string;
  rank: number;
  label: string;
  why: string;
  source: "alert" | "vaccination" | "reminder" | "routine";
  severity: MonitorState;
}

export interface AriaReportSection {
  label: string;
  value: string;
  available: boolean;
}

export interface AriaSupervisorBriefing {
  farm_name: string;
  as_of: string;
  greeting: string;
  overall: MonitorState;
  health_score: number;
  sections: AriaReportSection[];
  priorities: string[];
  suggested_actions: string[];
  notes: string[];
}

export interface AriaSupervisorSnapshot {
  briefing: AriaSupervisorBriefing;
  overall: MonitorState;
  health_score: number;
  monitors: AriaMonitor[];
  alerts: AriaAlert[];
  priorities: AriaPriorityItem[];
}

export interface AriaTimelineEvent {
  at: string;
  kind: "vaccination" | "production" | "feed" | "mortality" | "reminder" | "weighin";
  title: string;
  detail: string;
}

export interface AriaReport {
  period: string;
  label: string;
  sections: AriaReportSection[];
  notes: string[];
}

export async function getSupervisor(
  farmId: string,
  opts: { sync?: boolean } = {},
): Promise<AriaSupervisorSnapshot> {
  const { data } = await apiClient.get<APISuccess<AriaSupervisorSnapshot>>(
    `/farms/${farmId}/aria/supervisor`,
    { params: opts.sync ? { sync: true } : undefined },
  );
  return data.data;
}

export async function getTimeline(
  farmId: string,
  params: { days?: number; limit?: number } = {},
): Promise<AriaTimelineEvent[]> {
  const { data } = await apiClient.get<APISuccess<AriaTimelineEvent[]>>(
    `/farms/${farmId}/aria/timeline`,
    { params },
  );
  return data.data;
}

export async function getReport(farmId: string, period: "today" | "7d" | "30d"): Promise<AriaReport> {
  const { data } = await apiClient.get<APISuccess<AriaReport>>(
    `/farms/${farmId}/aria/reports`,
    { params: { period } },
  );
  return data.data;
}
