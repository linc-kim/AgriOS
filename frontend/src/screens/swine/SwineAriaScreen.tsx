/** Swine — Ask ARIA: deterministic-first, honesty-labelled Q&A plus explainable
 *  recommendations. ARIA explains from recorded data; it never changes a record. */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { askAria, getRecommendations, type AriaAnswer } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { FactBadge } from "@/components/common/FactBadge";
import { SwineSubnav } from "./SwineSubnav";

const SUGGESTIONS = [
  "How many pigs do I have?",
  "What is my conception rate?",
  "What is my cost per pig?",
  "What is my gross margin?",
  "Any pigs under withdrawal?",
];

const SEV: Record<string, string> = {
  critical: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  watch: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  info: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300",
};

export default function SwineAriaScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<{ q: string; a: AriaAnswer }[]>([]);

  const askM = useMutation({
    mutationFn: (q: string) => askAria(farmId as string, q),
    onSuccess: (a, q) => { setHistory((h) => [{ q, a }, ...h]); setQuestion(""); },
  });
  const recQ = useQuery({
    queryKey: ["swine-recs", farmId], queryFn: () => getRecommendations(farmId as string), enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const recs: any[] = recQ.data?.recommendations ?? [];

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <SwineSubnav active="/swine/aria" />
      <h1 className="mb-1 text-xl font-semibold text-gray-900 dark:text-gray-100">Ask ARIA · Swine</h1>
      <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
        Answers come from your recorded data and the deterministic engines. ARIA never invents data, never
        diagnoses disease, and never changes your records.
      </p>

      <div className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && question.trim()) askM.mutate(question.trim()); }}
          placeholder="Ask about your herd…"
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
              <FactBadge label={h.a.fact_type} /><span>{h.a.answer}</span>
            </p>
            <p className="mt-1 text-[11px] text-gray-400">
              {h.a.provider} · confidence {h.a.confidence} · sources: {h.a.sources.join(", ")}
            </p>
          </div>
        ))}
      </div>

      <h2 className="mb-2 mt-8 text-sm font-semibold text-gray-700 dark:text-gray-300">Recommendations</h2>
      {recQ.isLoading ? <Skeleton className="h-32 rounded-xl" /> : recs.length === 0 ? (
        <p className="text-sm text-gray-400">No recommendations — operations look steady.</p>
      ) : (
        <ul className="space-y-2">
          {recs.map((r, i) => (
            <li key={i} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
              <div className="flex items-center gap-2">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${SEV[r.severity] ?? SEV.info}`}>
                  {r.severity}
                </span>
                <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{r.recommendation}</span>
                <span className="ml-auto text-[11px] text-gray-400">confidence {r.confidence}</span>
              </div>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{r.reason}</p>
              {(r.supporting_data ?? []).length > 0 && (
                <p className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-gray-400">
                  evidence:
                  {r.supporting_data.map((e: any, k: number) => (
                    <span key={k} className="inline-flex items-center gap-1">
                      {e.source}={e.value ?? "—"} <FactBadge label={e.fact_type} />
                    </span>
                  ))}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
