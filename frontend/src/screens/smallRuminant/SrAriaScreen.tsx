/** Small Ruminant — Ask ARIA (shared): deterministic-first, honesty-labelled Q&A.
 *  ARIA explains from recorded data; it never changes a plan or record. */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { askAria, type AriaAnswer, type Species } from "@/api/smallRuminant";
import { SPECIES_UI } from "./config";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { FactBadge } from "@/components/common/FactBadge";
import { SrSubnav } from "./SrSubnav";

const SUGGESTIONS = [
  "How many animals do I have?",
  "What is my birth rate?",
  "What is my mortality rate?",
  "What is my gross margin?",
  "What is the top bottleneck?",
];

export default function SrAriaScreen({ species }: { species: Species }) {
  const ui = SPECIES_UI[species];
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<{ q: string; a: AriaAnswer }[]>([]);

  const askM = useMutation({
    mutationFn: (q: string) => askAria(farmId as string, species, q),
    onSuccess: (a, q) => { setHistory((h) => [{ q, a }, ...h]); setQuestion(""); },
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <SrSubnav species={species} active={`/${species}/aria`} />
      <h1 className="mb-1 text-xl font-semibold text-gray-900 dark:text-gray-100">Ask ARIA · {ui.title}</h1>
      <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
        Answers come from your recorded data and the deterministic engines. ARIA never invents data and
        never changes your plans.
      </p>

      <div className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && question.trim()) askM.mutate(question.trim()); }}
          placeholder={`Ask about your ${ui.collective}…`}
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
        />
        <Button loading={askM.isPending} onClick={() => question.trim() && askM.mutate(question.trim())}>Ask</Button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => askM.mutate(s)}
            className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300">
            {s}
          </button>
        ))}
      </div>

      <div className="mt-5 space-y-3">
        {history.map((h, i) => (
          <div key={i} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
            <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{h.q}</p>
            <p className="mt-1 flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
              <FactBadge label={h.a.fact_type} />
              <span>{h.a.answer}</span>
            </p>
            <p className="mt-1 text-[11px] text-gray-400">
              {h.a.provider} · confidence {h.a.confidence} · sources: {h.a.sources.join(", ")}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
