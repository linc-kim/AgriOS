/**
 * Aviculture — Ask ARIA (Module 15, Part 10).
 *
 * This is NOT a second assistant. It is the aviculture surface of the existing
 * platform ARIA: questions go to the shared AI provider and settings, answered
 * deterministic-first from the collection's recorded facts and only routed to the
 * AI for open explanation — always with a grounded offline fallback. ARIA never
 * diagnoses disease and never invents a figure; every answer is honesty-labelled
 * (provider · fact_type · sources), exactly as the platform honesty framework
 * requires.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Send, Sparkles } from "lucide-react";

import { askAria, type AskResponse } from "@/api/avicultureAria";
import { useWorkspace } from "@/shell/useWorkspace";
import { AriaAvatar } from "@/components/aria";
import { cn } from "@/lib/cn";
import { AviSubnav } from "./AviSubnav";

// Honesty labels ARIA returns, mapped to the shared badge palette.
const FACT_BADGE: Record<string, { label: string; cls: string }> = {
  recorded_fact: { label: "recorded", cls: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300" },
  calculated: { label: "calculated", cls: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" },
  ai_suggestion: { label: "AI", cls: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" },
  unavailable: { label: "unavailable", cls: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400" },
};

const SUGGESTIONS = [
  "How many birds do I have?",
  "How many breeding pairs are active?",
  "What is my collection worth?",
  "Explain incubation schedules",
  "What tasks are due?",
];

type Turn = { role: "user"; text: string } | { role: "aria"; res: AskResponse };

export default function AvicultureAriaScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [q, setQ] = useState("");
  const [thread, setThread] = useState<Turn[]>([]);

  const ask = useMutation({
    mutationFn: (question: string) => askAria(farmId as string, question),
    onSuccess: (res) => setThread((t) => [...t, { role: "aria", res }]),
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  const send = (text: string) => {
    if (!text.trim() || ask.isPending) return;
    setThread((t) => [...t, { role: "user", text }]);
    setQ("");
    ask.mutate(text);
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <div className="mb-4 flex items-center gap-3">
        <AriaAvatar size={44} state="idle" animated />
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Ask ARIA</h1>
          <p className="text-[13px] text-gray-500 dark:text-gray-400">
            Answers from your recorded aviculture data — never a guess, never a diagnosis.
          </p>
        </div>
      </div>
      <AviSubnav farmId={farmId} active="/aviculture/aria" />

      {thread.length === 0 && (
        <div className="mb-4 rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
          <p className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-gray-100">
            <Sparkles className="h-4 w-4 text-brand-500" aria-hidden /> Try asking
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" onClick={() => send(s)}
                className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 dark:border-white/10 dark:text-gray-300 dark:hover:bg-white/[0.04]">
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mb-4 space-y-3">
        {thread.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-600 px-3.5 py-2 text-sm text-white">{m.text}</div>
            </div>
          ) : (
            <AriaTurn key={i} res={m.res} />
          ),
        )}
        {ask.isPending && (
          <div className="flex items-center gap-2 text-sm text-gray-400"><Loader2 className="h-4 w-4 animate-spin" /> Thinking…</div>
        )}
      </div>

      <div className="flex items-end gap-2">
        <textarea
          value={q} onChange={(e) => setQ(e.target.value)} rows={1}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(q); } }}
          placeholder="Ask about breeding, incubation, health, valuation, tasks…" aria-label="Ask ARIA"
          className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
        />
        <button type="button" onClick={() => send(q)} disabled={!q.trim() || ask.isPending} aria-label="Send"
          className="rounded-xl bg-brand-600 p-2.5 text-white hover:bg-brand-700 disabled:opacity-40">
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

function AriaTurn({ res }: { res: AskResponse }) {
  const badge = FACT_BADGE[res.fact_type] ?? FACT_BADGE.unavailable;
  return (
    <div className="max-w-[92%] space-y-1">
      <div className="rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-800 dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-100">
        {res.answer}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 px-1">
        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", badge.cls)}>{badge.label}</span>
        <span className="text-[10px] text-gray-400">{res.provider}</span>
        {res.safety.includes("no_diagnosis") && (
          <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-600 dark:bg-red-500/15 dark:text-red-300">
            no diagnosis
          </span>
        )}
        {res.sources.length > 0 && (
          <span className="text-[10px] text-gray-400">· {res.sources.join(", ")}</span>
        )}
      </div>
    </div>
  );
}
