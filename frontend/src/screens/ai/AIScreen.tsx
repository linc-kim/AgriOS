/**
 * Greena — ARIA AI workspace (Module 9).
 * Tabs: Dashboard (forecasts, mortality prediction, disease risk, explainable
 * factors) and Assistant (offline-safe natural-language chat grounded in real
 * farm data). Wired to the real backend.
 */
import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles, Send, TrendingUp, Activity, ShieldAlert, Bot, User as UserIcon } from "lucide-react";

import { getAIDashboard, askAI } from "@/api/aiPlatform";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import type { AIDashboard, AIExplainFactor, AIForecast } from "@/types";

type Tab = "dashboard" | "assistant";

const RISK_CLS: Record<string, string> = {
  critical: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  high: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  moderate: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  low: "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300",
};
const cap = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function Card({ title, icon: Icon, children }: { title: string; icon?: typeof TrendingUp; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">{Icon && <Icon className="h-4 w-4 text-brand-500" />}{title}</h3>
      {children}
    </section>
  );
}

function Factors({ factors }: { factors: AIExplainFactor[] }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {factors.map((f, i) => (
        <li key={i} className="flex items-start justify-between gap-3 text-sm">
          <span className="text-gray-600 dark:text-gray-300">{f.factor}{f.detail ? <span className="text-gray-400"> — {f.detail}</span> : null}</span>
          <span className="shrink-0 font-semibold text-gray-900 dark:text-white">{f.impact}</span>
        </li>
      ))}
    </ul>
  );
}

function ForecastCard({ f }: { f: AIForecast }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{f.metric}</p>
      <p className="mt-1.5 text-lg font-semibold text-gray-900 dark:text-white">{f.projected_value} <span className="text-sm font-normal text-gray-400">{f.unit}</span></p>
      <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${RISK_CLS[f.confidence === "high" ? "low" : f.confidence === "medium" ? "moderate" : "high"]}`}>{cap(f.confidence)} confidence</span>
      {f.factors.length > 0 && <ul className="mt-2 space-y-1 text-xs text-gray-500 dark:text-gray-400">{f.factors.map((x, i) => <li key={i}>· {x}</li>)}</ul>}
    </div>
  );
}

export default function AIScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300"><Sparkles className="h-5 w-5" /></span>
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">ARIA</h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">Predictions, forecasts and an assistant grounded in your farm data.</p>
        </div>
      </header>

      <div className="flex gap-1 border-b border-gray-200 dark:border-white/10">
        {(["dashboard", "assistant"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium capitalize transition-colors ${tab === t ? "border-brand-500 text-brand-600 dark:text-brand-300" : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "dashboard" && farmId && <DashboardTab farmId={farmId} />}
      {tab === "assistant" && farmId && <AssistantTab farmId={farmId} />}
    </div>
  );
}

function DashboardTab({ farmId }: { farmId: string }) {
  const query = useQuery({ queryKey: queryKeys.aiDashboard(farmId), queryFn: () => getAIDashboard(farmId), enabled: !!farmId });
  if (query.isLoading) return <Skeleton className="h-64 rounded-2xl" />;
  const d: AIDashboard | undefined = query.data;
  if (!d) return null;
  const providerLabel = d.providers.gemini ? "Gemini" : d.providers.claude ? "Claude" : "Offline model";

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-900 dark:border-brand-600/30 dark:bg-brand-600/10 dark:text-brand-100">
        <span className="flex items-center gap-2"><Sparkles className="h-4 w-4" /> {d.headline}</span>
        <p className="mt-1 text-xs text-brand-700/70 dark:text-brand-200/60">Model: {providerLabel} · explainable & grounded in your data.</p>
      </div>

      {/* Predictions */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Mortality prediction (next 7 days)" icon={Activity}>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-semibold text-gray-900 dark:text-white">{d.mortality.predicted_next_7d}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${d.mortality.trend === "rising" ? RISK_CLS.high : d.mortality.trend === "falling" ? RISK_CLS.low : RISK_CLS.moderate}`}>{cap(d.mortality.trend)}</span>
            <span className="text-xs text-gray-400">{cap(d.mortality.confidence)} confidence</span>
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{d.mortality.explanation}</p>
          <Factors factors={d.mortality.factors} />
        </Card>

        <Card title="Disease risk" icon={ShieldAlert}>
          <div className="flex items-center gap-3">
            <span className="text-3xl font-semibold text-gray-900 dark:text-white">{d.disease_risk.score}<span className="text-base text-gray-400">/100</span></span>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${RISK_CLS[d.disease_risk.level] ?? RISK_CLS.low}`}>{cap(d.disease_risk.level)}</span>
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{d.disease_risk.recommendation}</p>
          <Factors factors={d.disease_risk.factors} />
        </Card>
      </div>

      {/* Forecasts */}
      <Card title="Forecasts" icon={TrendingUp}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {d.forecasts.financial && <ForecastCard f={d.forecasts.financial} />}
          {d.forecasts.feed && <ForecastCard f={d.forecasts.feed} />}
          {d.forecasts.production && <ForecastCard f={d.forecasts.production} />}
          {d.forecasts.inventory && <ForecastCard f={d.forecasts.inventory} />}
        </div>
      </Card>

      {(d.recommendations.length > 0 || d.insights.length > 0) && (
        <div className="grid gap-5 lg:grid-cols-2">
          {d.recommendations.length > 0 && (
            <Card title="Recommendations"><ul className="space-y-1.5 text-sm">{d.recommendations.map((r, i) => <li key={i} className="text-gray-700 dark:text-gray-200">· {r.title}</li>)}</ul></Card>
          )}
          {d.insights.length > 0 && (
            <Card title="Insights"><ul className="space-y-1.5 text-sm">{d.insights.map((r, i) => <li key={i} className="text-gray-700 dark:text-gray-200">· {r.title}</li>)}</ul></Card>
          )}
        </div>
      )}
    </div>
  );
}

interface ChatMsg { role: "user" | "aria"; text: string; sources?: string[]; provider?: string; }

function AssistantTab({ farmId }: { farmId: string }) {
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: "aria", text: "Hi, I'm ARIA. Ask me about your feed, finances, mortality, disease risk, inventory or egg production." },
  ]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: (q: string) => askAI(farmId, q),
    onSuccess: (r) => {
      setMessages((m) => [...m, { role: "aria", text: r.answer, sources: r.sources, provider: r.provider }]);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    },
    onError: (e: any) => setMessages((m) => [...m, { role: "aria", text: e?.response?.data?.error?.message ?? "Sorry, I couldn't answer that right now." }]),
  });

  const submit = () => {
    const q = input.trim();
    if (!q || ask.isPending) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    ask.mutate(q);
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const suggestions = ["How is my feed stock?", "What's my profit this month?", "What is my disease risk?", "Predict mortality"];

  return (
    <div className="flex h-[calc(100dvh-16rem)] min-h-[420px] flex-col rounded-2xl border border-gray-200 dark:border-white/10">
      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${m.role === "user" ? "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300" : "bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300"}`}>
              {m.role === "user" ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </span>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${m.role === "user" ? "bg-brand-500 text-white" : "bg-gray-50 text-gray-800 dark:bg-white/[0.04] dark:text-gray-200"}`}>
              <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
              {m.sources && m.sources.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {m.sources.map((s) => <span key={s} className="rounded-md bg-white/60 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 dark:bg-white/10 dark:text-gray-400">{s}</span>)}
                  {m.provider && <span className="rounded-md px-1.5 py-0.5 text-[10px] text-gray-400">via {m.provider}</span>}
                </div>
              )}
            </div>
          </div>
        ))}
        {ask.isPending && (
          <div className="flex gap-3"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300"><Bot className="h-4 w-4" /></span>
            <div className="rounded-2xl bg-gray-50 px-4 py-2.5 text-sm text-gray-400 dark:bg-white/[0.04]">ARIA is thinking…</div></div>
        )}
        <div ref={endRef} />
      </div>

      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-2 px-5 pb-2">
          {suggestions.map((s) => (
            <button key={s} onClick={() => { setInput(s); setTimeout(submit, 0); }} className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-white/10 dark:text-gray-300">{s}</button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 border-t border-gray-200 p-3 dark:border-white/10">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          placeholder="Ask ARIA about your farm…"
          className="flex-1 rounded-xl border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white"
        />
        <Button onClick={submit} disabled={!input.trim() || ask.isPending} leftIcon={<Send className="h-4 w-4" />}>Send</Button>
      </div>
    </div>
  );
}
