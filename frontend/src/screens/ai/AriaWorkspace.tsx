/**
 * ARIA workspace — the farmer's operational assistant (Module 13, Part 3).
 *
 * Three panes over one deterministic engine. The centre is a conversation, but
 * it is not a chatbot: it records farm activity by talking, asks for what's
 * missing as a confirmation card rather than a bubble, and answers questions
 * from the farm's own data. The left rail is history; the right is today's
 * snapshot.
 *
 * The one rule that shapes everything: no Gemini, no Claude. Recording goes
 * through /aria/record (the deterministic aria_nlu → aria_dialogue → aria_actions
 * pipeline). Questions that come back unhandled are answered from the snapshot
 * data already on screen. So the whole workspace works with no AI provider
 * configured, and never puts a model in the write path.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/cn";
import { Menu } from "lucide-react";

import { recordTurn, type AriaDialogueState, type AriaRecordStage } from "@/api/ariaRecord";
import { getProductionDashboard } from "@/api/flocks";
import { getVaccinationSchedule } from "@/api/health";
import { getFinanceDashboard } from "@/api/finance";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";

import {
  AriaAvatar,
  AriaComposer,
  AriaMessageBubble,
  AriaSourceBadge,
  AriaThinking,
  AriaTranscript,
  type AriaMessage,
} from "@/components/aria";
import { AriaConfirmationCard } from "@/components/aria/AriaConfirmationCard";
import { AriaRecordedCard } from "@/components/aria/AriaRecordedCard";
import { AriaSnapshotPanel } from "@/components/aria/AriaSnapshotPanel";
import { AriaIntelligencePanel } from "@/components/aria/AriaIntelligencePanel";
import { AriaKnowledgeCard, AriaDecisionCard } from "@/components/aria/AriaAnswerCards";
import { AriaWorkspaceSidebar } from "@/components/aria/AriaWorkspaceSidebar";
import { askDeterministic, type AriaDecisionAnswer, type AriaKnowledgeAnswer } from "@/api/ariaIntelligence";
import {
  AriaQuickActions,
  AriaSuggestedPrompts,
} from "@/components/aria/AriaQuickBar";
import {
  answerFromSnapshot,
  type SnapshotData,
} from "@/components/aria/deterministicAnswers";
import {
  conversationStore,
  deriveTitle,
  newConversation,
  type StoredConversation,
  type StoredMessage,
} from "@/components/aria/conversationStore";

/* ── Live turn model (in-memory; only the transcript persists) ─────────────── */

interface PendingTurn {
  stage: AriaRecordStage;
  prompt: string;
  options: string[];
  understood: string | null;
  note: string | null;
  state: AriaDialogueState | null;
}

interface TurnMessage extends AriaMessage {
  /** Set when this message is a saved-record card. */
  recorded?: { module: string; summary: string };
  /** Deterministic knowledge/decision answers, rendered as rich cards. */
  knowledge?: AriaKnowledgeAnswer;
  decision?: AriaDecisionAnswer;
}

export default function AriaWorkspace() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const qc = useQueryClient();

  // Conversation history (client-side; see conversationStore for why).
  const [conversations, setConversations] = useState<StoredConversation[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);

  const [messages, setMessages] = useState<TurnMessage[]>([]);
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [input, setInput] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [rightView, setRightView] = useState<"snapshot" | "briefing">("snapshot");
  const seq = useRef(0);
  // Monotonic counter plus a per-mount salt, so an id can never collide with a
  // stored one from a previous session even before a conversation is loaded.
  const salt = useRef(Math.random().toString(36).slice(2, 6));
  const nextId = () => `m${salt.current}-${++seq.current}`;

  const refresh = () => farmId && setConversations(conversationStore.list(farmId));
  useEffect(() => {
    if (farmId) setConversations(conversationStore.list(farmId));
  }, [farmId]);

  // Snapshot data, also used to answer questions deterministically.
  const production = useQuery({
    queryKey: [...queryKeys.flocks(farmId ?? ""), "production-dashboard"],
    queryFn: () => getProductionDashboard(farmId as string),
    enabled: !!farmId,
    staleTime: 60_000,
  });
  const vaccinations = useQuery({
    queryKey: queryKeys.healthSchedule(farmId ?? ""),
    queryFn: () => getVaccinationSchedule(farmId as string),
    enabled: !!farmId,
    staleTime: 60_000,
  });
  const finance = useQuery({
    queryKey: queryKeys.financeDashboard(farmId ?? ""),
    queryFn: () => getFinanceDashboard(farmId as string),
    enabled: !!farmId,
    staleTime: 60_000,
  });

  const snapshot: SnapshotData = {
    production: production.data,
    finance: finance.data,
    vaccinations: vaccinations.data,
  };

  const dueVaccinations =
    (vaccinations.data?.overdue.length ?? 0) +
    (vaccinations.data?.due_today.length ?? 0) +
    (vaccinations.data?.due_this_week.length ?? 0);

  /* ── Persistence helpers ─────────────────────────────────────────────── */

  const persist = (msgs: TurnMessage[]) => {
    if (!farmId) return;
    const stored: StoredMessage[] = msgs.map((m) => ({
      id: m.id,
      role: m.role,
      text: m.text,
      sources: m.sources,
      saved: m.recorded,
      knowledge: m.knowledge,
      decision: m.decision,
      ts: Date.now(),
    }));
    let convo = activeId ? conversationStore.get(farmId, activeId) : undefined;
    if (!convo) {
      convo = newConversation();
      setActiveId(convo.id);
    }
    convo = { ...convo, messages: stored, title: deriveTitle(stored) || convo.title };
    conversationStore.save(farmId, convo);
    refresh();
  };

  const loadConversation = (id: string) => {
    if (!farmId) return;
    const convo = conversationStore.get(farmId, id);
    if (!convo) return;
    setActiveId(id);
    setPending(null);
    setInput("");
    // Continue the id sequence past the loaded messages. The salt already
    // prevents cross-session collisions; this keeps the counter monotonic for
    // this mount. Parse the numeric suffix after the last dash.
    seq.current = convo.messages.reduce((max, m) => {
      const n = Number(m.id.slice(m.id.lastIndexOf("-") + 1));
      return Number.isFinite(n) && n > max ? n : max;
    }, 0);
    setMessages(
      convo.messages.map((m) => ({
        id: m.id,
        role: m.role,
        text: m.text,
        sources: m.sources,
        recorded: m.saved,
        knowledge: m.knowledge as AriaKnowledgeAnswer | undefined,
        decision: m.decision as AriaDecisionAnswer | undefined,
      })),
    );
    setSidebarOpen(false);
  };

  const startNew = () => {
    setActiveId(null);
    setMessages([]);
    setPending(null);
    setInput("");
    seq.current = 0;
    setSidebarOpen(false);
  };

  /* ── The turn engine ─────────────────────────────────────────────────── */

  const turn = useMutation({
    mutationFn: (vars: { text: string; state: AriaDialogueState | null }) =>
      recordTurn(farmId as string, { text: vars.text, state: vars.state }),
    onSuccess: (res, vars) => {
      // Not a record → a question. Answer deterministically: first the backend
      // knowledge base and decision engine, then the local snapshot. No LLM at
      // any step.
      if (!res.handled) {
        setPending(null);
        void answerQuestion(vars.text);
        return;
      }

      // A save just completed → recorded card, and refresh the snapshot.
      if (res.saved && res.module) {
        setMessages((prev) => {
          const next: TurnMessage[] = [
            ...prev,
            {
              id: nextId(),
              role: "aria",
              text: res.summary ?? res.reply,
              recorded: { module: res.module as string, summary: res.summary ?? res.reply },
            },
          ];
          persist(next);
          return next;
        });
        setPending(null);
        invalidateSnapshot();
        return;
      }

      // Terminal non-save (cancelled / abandoned) → plain reply, clear pending.
      if (res.stage === "cancelled" || res.stage === "abandoned" || !res.state) {
        setMessages((prev) => {
          const next: TurnMessage[] = [...prev, { id: nextId(), role: "aria", text: res.reply }];
          persist(next);
          return next;
        });
        setPending(null);
        return;
      }

      // Mid-record → a confirmation card carries the turn.
      setPending({
        stage: res.stage,
        prompt: res.reply,
        options: res.options,
        understood: extractUnderstood(res.reply, res.stage),
        note: extractNote(res.reply, res.stage),
        state: res.state,
      });
    },
    onError: () => {
      setMessages((prev) => {
        const next: TurnMessage[] = [
          ...prev,
          {
            id: nextId(),
            role: "aria",
            text: "Something went wrong reaching your records. Nothing was saved — please try again.",
            error: true,
          },
        ];
        return next;
      });
      setPending(null);
    },
  });

  const invalidateSnapshot = () => {
    if (!farmId) return;
    qc.invalidateQueries({ queryKey: [...queryKeys.flocks(farmId), "production-dashboard"] });
    qc.invalidateQueries({ queryKey: queryKeys.healthSchedule(farmId) });
    qc.invalidateQueries({ queryKey: queryKeys.financeDashboard(farmId) });
  };

  // Answering (as opposed to recording) has its own pending flag so the
  // thinking indicator shows while the deterministic answer is fetched.
  const [answering, setAnswering] = useState(false);

  /**
   * Answer a question with no LLM: the backend knowledge base and decision
   * engine first, then the local snapshot. If the backend returns type "none"
   * and the snapshot can't help either, that falls through to an honest
   * "here's where that lives" — never a fabricated answer.
   */
  const answerQuestion = async (question: string) => {
    if (!farmId) return;
    setAnswering(true);
    try {
      const det = await askDeterministic(farmId, question);
      if (det.type === "knowledge" && det.knowledge) {
        appendAria({ text: det.knowledge.title, knowledge: det.knowledge });
        return;
      }
      if (det.type === "decision" && det.decision) {
        appendAria({ text: det.decision.headline, decision: det.decision });
        return;
      }
      // Neither — fall back to a snapshot-grounded answer.
      const local = answerFromSnapshot(question, snapshot);
      appendAria({ text: local.text, sources: local.sources });
    } catch {
      const local = answerFromSnapshot(question, snapshot);
      appendAria({ text: local.text, sources: local.sources });
    } finally {
      setAnswering(false);
    }
  };

  const appendAria = (msg: Omit<TurnMessage, "id" | "role">) => {
    setMessages((prev) => {
      const next: TurnMessage[] = [...prev, { id: nextId(), role: "aria", ...msg }];
      persist(next);
      return next;
    });
  };

  /** Send a farmer message — either a fresh utterance or an answer to a card. */
  const send = (raw?: string) => {
    const text = (raw ?? input).trim();
    if (!text || turn.isPending || !farmId) return;

    setMessages((prev) => [...prev, { id: nextId(), role: "user", text }]);
    setInput("");
    turn.mutate({ text, state: pending?.state ?? null });
  };

  /** A tapped option on the confirmation card. */
  const pickOption = (option: string) => {
    if (!pending) return;
    setMessages((prev) => [...prev, { id: nextId(), role: "user", text: option }]);
    turn.mutate({ text: option, state: pending.state });
  };

  const seedComposer = (seed: string) => {
    setInput(seed);
    // Focus is handled by the composer's own effect on value change.
  };

  const fresh = messages.length === 0 && !pending;

  if (!farmId) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Select a farm to talk to ARIA.
        </p>
      </div>
    );
  }

  return (
    // Fills the shell's content area: 100dvh minus the sticky 4rem topbar and
    // the main's 3.5rem vertical padding.
    <div className="flex h-[calc(100dvh-8rem)] min-h-[520px] gap-0 overflow-hidden rounded-2xl border border-gray-200 dark:border-white/10">
      {/* ── Left rail ────────────────────────────────────────────────── */}
      <div className="hidden w-64 shrink-0 border-r border-gray-200 dark:border-white/10 lg:block">
        <AriaWorkspaceSidebar
          conversations={searchQuery ? conversationStore.search(farmId, searchQuery) : conversations}
          activeId={activeId}
          dueVaccinations={dueVaccinations}
          onSelect={loadConversation}
          onNew={startNew}
          onSearch={setSearchQuery}
          onRename={(id, title) => {
            conversationStore.update(farmId, id, { title });
            refresh();
          }}
          onTogglePin={(id) => {
            const c = conversationStore.get(farmId, id);
            if (c) conversationStore.update(farmId, id, { pinned: !c.pinned });
            refresh();
          }}
          onToggleArchive={(id) => {
            const c = conversationStore.get(farmId, id);
            if (c) conversationStore.update(farmId, id, { archived: !c.archived });
            refresh();
          }}
          onDelete={(id) => {
            conversationStore.remove(farmId, id);
            if (id === activeId) startNew();
            refresh();
          }}
          onVaccinationsClick={() => navigate("/health")}
        />
      </div>

      {/* Mobile sidebar drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-72 border-r border-gray-200 bg-white dark:border-white/10 dark:bg-gray-900">
            <AriaWorkspaceSidebar
              conversations={searchQuery ? conversationStore.search(farmId, searchQuery) : conversations}
              activeId={activeId}
              dueVaccinations={dueVaccinations}
              onSelect={loadConversation}
              onNew={startNew}
              onSearch={setSearchQuery}
              onRename={(id, title) => {
                conversationStore.update(farmId, id, { title });
                refresh();
              }}
              onTogglePin={(id) => {
                const c = conversationStore.get(farmId, id);
                if (c) conversationStore.update(farmId, id, { pinned: !c.pinned });
                refresh();
              }}
              onToggleArchive={(id) => {
                const c = conversationStore.get(farmId, id);
                if (c) conversationStore.update(farmId, id, { archived: !c.archived });
                refresh();
              }}
              onDelete={(id) => {
                conversationStore.remove(farmId, id);
                if (id === activeId) startNew();
                refresh();
              }}
              onVaccinationsClick={() => navigate("/health")}
            />
          </div>
        </div>
      )}

      {/* ── Centre: conversation ─────────────────────────────────────── */}
      <div className="flex min-w-0 flex-1 flex-col bg-[#fbfcfb] dark:bg-transparent">
        <header className="flex items-center gap-2.5 border-b border-gray-200 px-4 py-3 dark:border-white/10">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open conversations"
            className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-white/[0.06] lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <AriaAvatar size={34} state={turn.isPending ? "thinking" : "idle"} animated />
          <span className="order-last flex shrink-0 gap-1">
            <button
              type="button"
              onClick={() => navigate("/ai/supervisor")}
              className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-50 dark:text-brand-300 dark:hover:bg-brand-500/10"
            >
              Supervisor
            </button>
            <button
              type="button"
              onClick={() => navigate("/ai/planning")}
              className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-50 dark:text-brand-300 dark:hover:bg-brand-500/10"
            >
              Planning
            </button>
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm font-semibold text-gray-900 dark:text-white">ARIA</h1>
            <p className="truncate text-[11px] text-gray-400 dark:text-gray-500">
              Your farm operations manager · records &amp; answers offline
            </p>
          </div>
        </header>

        <AriaTranscript
          dependency={messages.length + (pending ? 0.5 : 0) + (turn.isPending ? 0.25 : 0)}
          className="space-y-4 p-4"
        >
          {fresh && <Welcome key="welcome" />}
          {/* The right-rail briefing is desktop-only; on a phone the farmer
              still needs their morning brief, so it opens inline on the fresh
              screen where the right rail can't reach. */}
          {fresh && (
            <div key="mobile-briefing" className="xl:hidden">
              <AriaIntelligencePanel farmId={farmId} />
            </div>
          )}
          {messages.map((m, i) =>
            m.recorded ? (
              <AriaRecordedCard key={m.id} module={m.recorded.module} summary={m.recorded.summary} index={i} />
            ) : m.knowledge ? (
              <AriaKnowledgeCard key={m.id} answer={m.knowledge} />
            ) : m.decision ? (
              <AriaDecisionCard key={m.id} answer={m.decision} />
            ) : (
              <AriaMessageBubble key={m.id} message={m} index={i} onFollowUp={(q) => send(q)} />
            ),
          )}
          {pending && !turn.isPending && (
            <AriaConfirmationCard
              key="pending-card"
              stage={pending.stage}
              prompt={pending.prompt}
              options={pending.options}
              understood={pending.understood}
              note={pending.note}
              onPick={pickOption}
              disabled={turn.isPending}
            />
          )}
          {(turn.isPending || answering) && (
            <AriaThinking key="thinking" label={answering ? "ARIA is thinking" : "ARIA is working"} />
          )}
        </AriaTranscript>

        {/* Quick actions on a fresh conversation only. */}
        {fresh && (
          <div className="border-t border-gray-200 px-4 py-3 dark:border-white/10">
            <AriaQuickActions
              onSeed={seedComposer}
              onUpload={() => setInput("")}
              onNavigate={(href) => navigate(href)}
            />
          </div>
        )}

        {/* Composer */}
        <div className="border-t border-gray-200 p-3 dark:border-white/10">
          <AriaSuggestedPrompts onPick={(p) => send(p)} className="mb-2" />
          <AriaComposer
            value={input}
            onChange={setInput}
            onSubmit={() => send()}
            disabled={turn.isPending}
            placeholder="Tell ARIA what happened, or ask about your farm…"
          />
          <p className="mt-2 flex flex-wrap items-center gap-1.5 px-1 text-[11px] text-gray-400 dark:text-gray-500">
            <AriaSourceBadge source="Offline Knowledge" />
            Deterministic — ARIA records and answers from your data without Gemini or Claude.
          </p>
        </div>
      </div>

      {/* ── Right: snapshot / briefing ───────────────────────────────── */}
      <div className="hidden w-80 shrink-0 flex-col border-l border-gray-200 xl:flex dark:border-white/10">
        <div
          className="flex gap-1 border-b border-gray-200 p-2 dark:border-white/10"
          role="tablist"
          aria-label="Right panel view"
        >
          {(["snapshot", "briefing"] as const).map((v) => (
            <button
              key={v}
              role="tab"
              aria-selected={rightView === v}
              onClick={() => setRightView(v)}
              className={cn(
                "flex-1 rounded-lg px-3 py-1.5 text-sm font-medium capitalize transition-colors",
                rightView === v
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                  : "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/[0.06]",
              )}
            >
              {v}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {rightView === "snapshot" ? (
            <AriaSnapshotPanel farmId={farmId} />
          ) : (
            <AriaIntelligencePanel farmId={farmId} />
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Welcome (empty state) ─────────────────────────────────────────────── */

function Welcome() {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <AriaAvatar size={52} />
      <div>
        <p className="text-base font-semibold text-gray-900 dark:text-white">
          Talk to ARIA about your farm
        </p>
        <p className="mx-auto mt-1 max-w-md text-sm leading-relaxed text-gray-500 dark:text-gray-400">
          Tell me what happened — "three birds died", "collected 12 trays", "we vaccinated
          Newcastle" — and I'll record it. I'll ask before saving, and answer questions from your
          own data.
        </p>
      </div>
    </div>
  );
}

/* ── Reply parsing ─────────────────────────────────────────────────────── */

/**
 * Split the server reply into a read-back and the actual question. The
 * confirmation reply is shaped "Ready to record: X. <assumptions> Shall I save
 * it?"; pull the middle out so the card can show "I'll record: X" as its header.
 */
function extractUnderstood(reply: string, stage: AriaRecordStage): string | null {
  if (stage !== "confirming") return null;
  const m = reply.match(/ready to record:\s*(.+?)\.\s/i);
  return m ? m[1].trim() : null;
}

function extractNote(reply: string, stage: AriaRecordStage): string | null {
  if (stage !== "confirming") return null;
  // Everything between the read-back sentence and the final "Shall I save it?".
  const m = reply.match(/ready to record:[^.]+\.\s*(.+?)\s*shall i save it\?/i);
  const note = m?.[1]?.trim();
  return note && note.length > 0 ? note : null;
}
