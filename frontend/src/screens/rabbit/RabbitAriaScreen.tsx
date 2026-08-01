/**
 * Rabbit — Ask ARIA (Module 17, Frontend).
 *
 * Deterministic-first Q&A. Answers arrive honesty-labelled (recorded / calculated
 * / forecast / ai_suggestion / unavailable) with cited sources. ARIA explains and
 * recommends — it never edits data.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";

import { askAria, type AriaAnswer } from "@/api/rabbitAria";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { FactBadge } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

const SUGGESTIONS = [
  "How many rabbits do I have?",
  "What is my kindling rate?",
  "What is my mortality rate?",
  "What is my top bottleneck?",
];

export default function RabbitAriaScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Array<{ q: string; a: AriaAnswer }>>([]);

  const askM = useMutation({
    mutationFn: (q: string) => askAria(farmId as string, q),
    onSuccess: (a, q) => {
      setHistory((h) => [{ q, a }, ...h]);
      setQuestion("");
    },
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  function submit(q: string) {
    if (q.trim()) askM.mutate(q.trim());
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <RabbitSubnav active="/rabbit/aria" />
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300">
          <Sparkles className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Ask ARIA</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Grounded in your recorded data — never a guess</p>
        </div>
      </div>

      <div className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit(question)}
          placeholder="Ask about your rabbits…"
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <Button loading={askM.isPending} onClick={() => submit(question)}>Ask</Button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => submit(s)}
            className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="mt-6 space-y-4">
        {history.map((item, i) => (
          <div key={i} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{item.q}</p>
            <div className="mt-2 flex items-start justify-between gap-3">
              <p className="text-sm text-gray-700 dark:text-gray-300">{item.a.answer}</p>
              <FactBadge label={item.a.fact_type} />
            </div>
            {item.a.sources.length > 0 && (
              <p className="mt-2 text-[11px] text-gray-400">
                Sources: {item.a.sources.join(", ")} · confidence {item.a.confidence}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
