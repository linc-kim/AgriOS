/**
 * ARIA workspace — conversation history.
 *
 * The recording endpoint (/aria/record) is stateless, and the server-side
 * conversation store is wired to the Gemini/Claude chat path, which Part 3
 * forbids here. So workspace history lives on the device, keyed by farm. This
 * is real persistence from the farmer's point of view — conversations survive
 * reloads, can be searched, pinned, renamed, archived and deleted — without
 * putting an LLM anywhere near the record path.
 *
 * A deliberate boundary: only the conversation *transcript* is stored, never
 * in-flight dialogue state. A half-finished, unconfirmed record is not history
 * and must not resurrect on reload — the farmer would have no idea a pending
 * write was still lurking.
 */

export interface StoredMessage {
  id: string;
  role: "user" | "aria";
  text: string;
  /** Present on ARIA answers — the modules the answer drew on. */
  sources?: string[];
  /** Present when this message recorded something. */
  saved?: { module: string; summary: string };
  ts: number;
}

export interface StoredConversation {
  id: string;
  title: string;
  messages: StoredMessage[];
  pinned: boolean;
  archived: boolean;
  createdAt: number;
  updatedAt: number;
}

const KEY = (farmId: string) => `greena.aria.conversations.${farmId}`;
const MAX = 100; // plenty of history without letting localStorage grow unbounded

function read(farmId: string): StoredConversation[] {
  try {
    const raw = localStorage.getItem(KEY(farmId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // Corrupt or unavailable storage must never take the workspace down.
    return [];
  }
}

function write(farmId: string, list: StoredConversation[]): void {
  try {
    localStorage.setItem(KEY(farmId), JSON.stringify(list.slice(0, MAX)));
  } catch {
    // Quota or private-mode failures are non-fatal; history is a convenience,
    // not the source of truth for any recorded data.
  }
}

export const conversationStore = {
  list(farmId: string): StoredConversation[] {
    // Pinned first, then most-recently-updated. Archived drop to the bottom.
    return read(farmId).sort((a, b) => {
      if (a.archived !== b.archived) return a.archived ? 1 : -1;
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return b.updatedAt - a.updatedAt;
    });
  },

  get(farmId: string, id: string): StoredConversation | undefined {
    return read(farmId).find((c) => c.id === id);
  },

  save(farmId: string, conversation: StoredConversation): void {
    const list = read(farmId);
    const idx = list.findIndex((c) => c.id === conversation.id);
    const next = { ...conversation, updatedAt: Date.now() };
    if (idx >= 0) list[idx] = next;
    else list.unshift(next);
    write(farmId, list);
  },

  remove(farmId: string, id: string): void {
    write(farmId, read(farmId).filter((c) => c.id !== id));
  },

  update(farmId: string, id: string, patch: Partial<StoredConversation>): void {
    const list = read(farmId);
    const idx = list.findIndex((c) => c.id === id);
    if (idx < 0) return;
    list[idx] = { ...list[idx], ...patch, updatedAt: Date.now() };
    write(farmId, list);
  },

  /** Case-insensitive search across titles and message text. */
  search(farmId: string, query: string): StoredConversation[] {
    const q = query.trim().toLowerCase();
    if (!q) return this.list(farmId);
    return this.list(farmId).filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.messages.some((m) => m.text.toLowerCase().includes(q)),
    );
  },
};

/** A blank conversation. Title is derived from the first message when it lands. */
export function newConversation(): StoredConversation {
  const now = Date.now();
  return {
    id: `c${now}-${Math.random().toString(36).slice(2, 8)}`,
    title: "New conversation",
    messages: [],
    pinned: false,
    archived: false,
    createdAt: now,
    updatedAt: now,
  };
}

/** First user message, trimmed, makes a serviceable title. */
export function deriveTitle(messages: StoredMessage[]): string {
  const first = messages.find((m) => m.role === "user");
  if (!first) return "New conversation";
  const t = first.text.trim();
  return t.length > 40 ? `${t.slice(0, 40)}…` : t;
}
