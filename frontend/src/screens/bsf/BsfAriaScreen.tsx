/**
 * BSF — ARIA Workspace (Module 16, Frontend Milestone 9).
 *
 * A conversational surface where ARIA explains and answers from the farm's
 * recorded data and the deterministic engines. ARIA is ADVISORY ONLY — it never
 * changes a plan or record. Every answer shows its honesty fact-type and the
 * sources it rests on; uncertainty is surfaced, never hidden.
 */
import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Send, Sparkles } from "lucide-react";

import { askAria, type AriaAnswer } from "@/api/bsfAria";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { FactBadge } from "@/components/common/FactBadge";
import { BsfSubnav } from "./BsfSubnav";

type Turn = { role: "user"; text: string } | { role: "aria"; res: AriaAnswer };

const SUGGESTIONS = [
  "How much have I harvested in total?",
  "What is my biggest bottleneck?",
  "How is my growth goal progressing?",
  "How much feedstock is on hand?",
];

export default function BsfAriaScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [thread, setThread] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: (q: string) => askAria(farmId as string, q),
    onSuccess: (res) => { setThread((t) => [...t, { role: "aria", res }]); setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50); },
    onError: () => setThread((t) => [...t, { role: "aria", res: { provider: "offline", engine: "deterministic", fact_type: "unavailable", answer: "I couldn’t reach the assistant just now.", sources: [], confidence: "low", ai_enabled: false } }]),
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  function submit(q: string) {
    const question = q.trim();
    if (!question) return;
    setThread((t) => [...t, { role: "user", text: question }]);
    setInput("");
    ask.mutate(question);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <BsfSubnav active="/bsf/aria" />
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <Sparkles className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Ask ARIA</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Explains from your recorded data — advisory only</p>
        </div>
      </div>

      <div className="mb-4 min-h-[40vh] space-y-3">
        {thread.length === 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <p className="mb-2 text-sm text-gray-500">Try asking:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => submit(s)}
                  className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">{s}</button>
              ))}
            </div>
          </div>
        )}
        {thread.map((turn, i) => turn.role === "user" ? (
          <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2 text-sm text-white">{turn.text}</div>
        ) : (
          <div key={i} className="max-w-[90%] rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-4 py-3 text-sm dark:border-gray-800 dark:bg-gray-900">
            <p className="text-gray-800 dark:text-gray-200">{turn.res.answer}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-400">
              <FactBadge label={turn.res.fact_type} />
              <span>confidence: {turn.res.confidence}</span>
              {turn.res.sources.length > 0 && <span>· sources: {turn.res.sources.join(", ")}</span>}
              {!turn.res.ai_enabled && <span>· offline</span>}
            </div>
          </div>
        ))}
        {ask.isPending && <div className="max-w-[60%] rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-4 py-3 text-sm text-gray-400 dark:border-gray-800 dark:bg-gray-900">ARIA is thinking…</div>}
        <div ref={endRef} />
      </div>

      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); submit(input); }}>
        <input
          className="flex-1 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm dark:border-gray-700 dark:bg-gray-900"
          placeholder="Ask about production, feed, harvest, growth…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          aria-label="Ask ARIA a question"
        />
        <Button type="submit" leftIcon={<Send className="h-4 w-4" />} loading={ask.isPending} disabled={!input.trim()}>Ask</Button>
      </form>
    </div>
  );
}
