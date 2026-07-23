/**
 * ARIA conversational recording — the deterministic write path (Module 13).
 *
 * This talks only to POST /aria/record, which is the deterministic pipeline:
 * aria_nlu → aria_dialogue → aria_actions. No Gemini, no Claude, no quota. The
 * workspace is built entirely on this and on the existing read endpoints
 * (production dashboard, vaccination schedule, finance), so the whole surface
 * works with no AI provider configured.
 *
 * The turn model is stateless on the server: each call carries the `state` the
 * previous call returned, and the client holds it for the length of a
 * recording. That is why a half-finished mortality never outlives its
 * conversation.
 */
import apiClient from "./client";

type APISuccess<T> = { data: T; success: true };

/** Where a recording conversation has got to. Mirrors the server's Stage enum. */
export type AriaRecordStage =
  | "collecting"
  | "probing"
  | "confirming"
  | "ready"
  | "cancelled"
  | "abandoned"
  | "";

/** Opaque dialogue state — round-tripped verbatim, never inspected client-side. */
export type AriaDialogueState = Record<string, unknown>;

export interface AriaRecordTurn {
  /**
   * False means this was not a recording utterance at all. The workspace then
   * answers it deterministically from loaded snapshot data rather than routing
   * to an LLM — Part 3 forbids Gemini and Claude here.
   */
  handled: boolean;
  reply: string;
  stage: AriaRecordStage;
  /** Tappable answers (flock names, "Skip", "Yes, save it"). Never the only way to answer. */
  options: string[];
  /** Pass back on the next turn to continue. Null when the turn is terminal. */
  state: AriaDialogueState | null;
  saved: boolean;
  summary: string | null;
  /** Which module the record landed in: livestock | production | health | feed. */
  module: string | null;
  resource_id: string | null;
}

export interface AriaRecordRequest {
  text: string;
  state?: AriaDialogueState | null;
}

export async function recordTurn(
  farmId: string,
  req: AriaRecordRequest,
): Promise<AriaRecordTurn> {
  const res = await apiClient.post<APISuccess<AriaRecordTurn>>(
    `/farms/${farmId}/aria/record`,
    { text: req.text, state: req.state ?? null },
  );
  return res.data.data;
}
