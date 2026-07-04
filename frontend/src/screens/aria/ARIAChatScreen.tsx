/**
 * AI-01 — ARIA Chat Screen
 * /farms/:farmId/aria
 *
 * Conversational interface with ARIA.
 * - Message bubbles (user right, ARIA left)
 * - Live typing indicator while awaiting response
 * - Quota badge in header
 * - Optional flock context via ?flockId=
 * - Auto-scroll to latest message
 * - New conversation / history drawer
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  deleteConversation,
  getConversation,
  listConversations,
  sendARIAMessage,
} from "@/api/aria";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { AIMessage, AIConversationSummary } from "@/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-KE", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: AIMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-white text-xs font-bold mr-2 flex-shrink-0 mt-0.5">
          A
        </div>
      )}
      <div className={`max-w-[80%] ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-brand-600 text-white rounded-br-sm"
              : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-sm"
          }`}
        >
          {message.content}
        </div>
        <div className="flex items-center gap-1.5 mt-1 px-1">
          <span className="text-xs text-gray-400">{fmtTime(message.created_at)}</span>
          {!isUser && message.provider === "claude" && (
            <span className="text-xs text-amber-400">· fallback</span>
          )}
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-3">
      <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-white text-xs font-bold mr-2 flex-shrink-0">
        A
      </div>
      <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-sm shadow-sm px-4 py-3 flex items-center gap-1">
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  );
}

function HistoryDrawer({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onClose,
}: {
  conversations: AIConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/40" onClick={onClose} />
      {/* Drawer */}
      <div className="w-72 bg-white h-full flex flex-col shadow-xl">
        <div className="px-4 pt-12 pb-3 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-bold text-gray-900">{t("aria.history.title")}</h2>
          <button onClick={onNew} className="text-brand-600 text-sm font-medium">
            {t("aria.history.new")}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              {t("aria.history.empty")}
            </p>
          )}
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`px-4 py-3 border-b border-gray-50 cursor-pointer flex items-center justify-between group ${
                conv.id === activeId ? "bg-brand-50" : "hover:bg-gray-50"
              }`}
              onClick={() => onSelect(conv.id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {conv.title || t("aria.history.untitled")}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {conv.message_count} {t("aria.history.messages")}
                </p>
              </div>
              <button
                className="text-gray-300 hover:text-red-400 ml-2 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conv.id);
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

export default function ARIAChatScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const [searchParams] = useSearchParams();
  const flockId = searchParams.get("flockId") ?? undefined;
  const navigate = useNavigate();
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [quotaRemaining, setQuotaRemaining] = useState<number | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load conversation history list
  const { data: conversations = [] } = useQuery({
    queryKey: queryKeys.aiConversations(farmId!),
    queryFn: () => listConversations(farmId!),
    enabled: !!farmId,
  });

  // Load existing conversation when one is selected
  const { data: convDetail } = useQuery({
    queryKey: queryKeys.aiConversation(farmId!, conversationId!),
    queryFn: () => getConversation(farmId!, conversationId!),
    enabled: !!farmId && !!conversationId,
    staleTime: 0,
  });

  useEffect(() => {
    if (convDetail) {
      setMessages(convDetail.messages);
    }
  }, [convDetail]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      sendARIAMessage(farmId!, {
        content,
        conversation_id: conversationId ?? undefined,
        flock_id: flockId,
      }),
    onMutate: async (content) => {
      setIsTyping(true);
      // Optimistically add user message
      const optimisticUser: AIMessage = {
        id: crypto.randomUUID(),
        conversation_id: conversationId ?? "",
        role: "user",
        content,
        language: "en",
        provider: null,
        total_tokens: null,
        latency_ms: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticUser]);
    },
    onSuccess: (response) => {
      setIsTyping(false);
      if (!conversationId) {
        setConversationId(response.conversation_id);
      }
      if (response.quota_remaining !== null) {
        setQuotaRemaining(response.quota_remaining);
      }
      setMessages((prev) => {
        // Replace optimistic user message + append assistant response
        const withoutLast = prev.slice(0, -1); // remove optimistic
        const userMsg: AIMessage = {
          ...prev[prev.length - 1],
          conversation_id: response.conversation_id,
        };
        return [...withoutLast, userMsg, response.message];
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.aiConversations(farmId!) });
    },
    onError: () => {
      setIsTyping(false);
      const errorMsg: AIMessage = {
        id: crypto.randomUUID(),
        conversation_id: conversationId ?? "",
        role: "assistant",
        content: t("aria.chat.error_fallback"),
        language: "en",
        provider: null,
        total_tokens: null,
        latency_ms: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(farmId!, id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.aiConversations(farmId!) });
      if (deletedId === conversationId) {
        setConversationId(null);
        setMessages([]);
      }
    },
  });

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || sendMutation.isPending) return;
    setInput("");
    sendMutation.mutate(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    setShowHistory(false);
  };

  const handleSelectConversation = (id: string) => {
    setConversationId(id);
    setShowHistory(false);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-3 border-b border-gray-100 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-500 text-lg">←</button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-white text-sm font-bold">
              A
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900">ARIA</h1>
              <p className="text-xs text-gray-400">{t("aria.chat.subtitle")}</p>
            </div>
          </div>
        </div>
        {quotaRemaining !== null && (
          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
            {quotaRemaining} {t("aria.chat.queries_left")}
          </span>
        )}
        <button
          onClick={() => setShowHistory(true)}
          className="text-gray-400 hover:text-gray-600 text-lg"
          title={t("aria.history.title")}
        >
          ☰
        </button>
        <button
          onClick={handleNewConversation}
          className="text-brand-600 text-sm font-medium"
        >
          + {t("aria.history.new_short")}
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center pb-16">
            <div className="w-16 h-16 rounded-full bg-brand-50 flex items-center justify-center text-3xl mb-4">
              🤖
            </div>
            <h2 className="text-gray-800 font-semibold text-lg">{t("aria.chat.welcome_title")}</h2>
            <p className="text-gray-400 text-sm mt-2 max-w-xs">
              {t("aria.chat.welcome_body")}
            </p>
            {/* Suggested prompts */}
            <div className="flex flex-col gap-2 mt-6 w-full max-w-xs">
              {(t("aria.chat.suggestions", { returnObjects: true }) as string[]).map((s, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setInput(s);
                  }}
                  className="bg-white border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-700 text-left hover:border-brand-300 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-100 px-4 py-3 pb-8">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("aria.chat.placeholder")}
            rows={1}
            className="flex-1 resize-none rounded-2xl border border-gray-200 px-4 py-2.5 text-sm text-gray-800 focus:outline-none focus:border-brand-400 max-h-32 leading-relaxed"
            style={{ height: "auto" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
            }}
            disabled={sendMutation.isPending}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sendMutation.isPending}
            className="w-10 h-10 rounded-full bg-brand-600 text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
          >
            {sendMutation.isPending ? <Spinner size="sm" /> : "↑"}
          </button>
        </div>
        <p className="text-xs text-gray-300 text-center mt-2">{t("aria.chat.disclaimer")}</p>
      </div>

      {/* History Drawer */}
      {showHistory && (
        <HistoryDrawer
          conversations={conversations}
          activeId={conversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={(id) => deleteMutation.mutate(id)}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  );
}
