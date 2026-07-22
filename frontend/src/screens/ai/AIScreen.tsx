/**
 * Greena — ARIA workspace (Module 9).
 *
 * Two tabs over one body of intelligence: Dashboard is ARIA volunteering what
 * it noticed, Assistant is ARIA answering what you asked. They share the same
 * card components deliberately — when a farmer asks "what's my disease risk?"
 * the answer arrives as the *same card* they saw on the dashboard, so the two
 * halves read as one assistant rather than two features.
 *
 * Everything on screen is grounded: every number comes from the farm's own
 * records, and every answer shows which records it used.
 */
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Lightbulb, TrendingUp } from "lucide-react";

import { getAIDashboard, askAI } from "@/api/aiPlatform";
import { useWorkspace } from "@/shell/useWorkspace";
import { queryKeys } from "@/lib/queryClient";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  AriaAvatar,
  AriaCard,
  AriaComposer,
  AriaDiseaseCard,
  AriaEmptyState,
  AriaForecastCard,
  AriaHeadline,
  AriaInsightCard,
  AriaMark,
  AriaMessageBubble,
  AriaPredictionCard,
  AriaQuickActions,
  AriaRecommendation,
  AriaStatus,
  AriaThinking,
  AriaTranscript,
  OPENING_ACTIONS,
  suggestFollowUps,
  type AriaMessage,
} from "@/components/aria";
import type { AIDashboard } from "@/types";

type Tab = "dashboard" | "assistant";

export default function AIScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [tab, setTab] = useState<Tab>("dashboard");

  // Fetched once at this level so the assistant can render the same cards the
  // dashboard shows without a second request.
  const dash = useQuery({
    queryKey: queryKeys.aiDashboard(farmId ?? ""),
    queryFn: () => getAIDashboard(farmId as string),
    enabled: !!farmId,
  });

  const providers = dash.data?.providers;
  const status = !providers
    ? "ready"
    : providers.gemini || providers.claude
      ? "ready"
      : "offline";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <AriaAvatar size={44} state="idle" animated />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
            ARIA
          </h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">
            Predictions, forecasts and an assistant grounded in your farm data.
          </p>
        </div>
        <AriaStatus
          kind={status as "ready" | "offline"}
          detail={
            status === "offline"
              ? "Offline model"
              : providers?.gemini
                ? "Ready · Gemini"
                : providers?.claude
                  ? "Ready · Claude"
                  : undefined
          }
        />
      </header>

      <div
        className="flex gap-1 border-b border-gray-200 dark:border-white/10"
        role="tablist"
        aria-label="ARIA sections"
      >
        {(["dashboard", "assistant"] as Tab[]).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "border-brand-600 text-brand-700 dark:border-brand-400 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {!farmId ? (
        <AriaEmptyState
          title="No farm selected"
          description="Choose a farm and ARIA will start reading its records."
        />
      ) : tab === "dashboard" ? (
        <DashboardTab query={dash} />
      ) : (
        <AssistantTab farmId={farmId} dashboard={dash.data} />
      )}
    </div>
  );
}

/* ── Dashboard ─────────────────────────────────────────────────────────────── */

function DashboardTab({
  query,
}: {
  query: ReturnType<typeof useQuery<AIDashboard>>;
}) {
  if (query.isLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-20 rounded-2xl" />
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-56 rounded-2xl" />
          <Skeleton className="h-56 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (query.isError) {
    return (
      <AriaEmptyState
        title="ARIA could not reach your data"
        description="The farm records are temporarily unavailable. Predictions will return once the connection recovers."
      />
    );
  }

  const d = query.data;
  if (!d) return <AriaEmptyState />;

  const providerLabel = d.providers.gemini
    ? "Gemini"
    : d.providers.claude
      ? "Claude"
      : "Offline model";

  const forecasts = [
    d.forecasts.financial,
    d.forecasts.feed,
    d.forecasts.production,
    d.forecasts.inventory,
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      {d.headline && (
        <AriaHeadline
          headline={d.headline}
          meta={`${providerLabel} · explainable and grounded in your records`}
        />
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <AriaPredictionCard prediction={d.mortality} index={0} />
        <AriaDiseaseCard risk={d.disease_risk} index={1} />
      </div>

      {forecasts.length > 0 && (
        <AriaCard title="Forecasts" icon={TrendingUp} index={2}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {forecasts.map((f, i) => (
              <AriaForecastCard key={f!.metric} forecast={f!} index={i} />
            ))}
          </div>
        </AriaCard>
      )}

      {(d.recommendations.length > 0 || d.insights.length > 0) && (
        <div className="grid gap-5 lg:grid-cols-2">
          {d.recommendations.length > 0 && (
            <AriaCard title="Recommendations" icon={Lightbulb} index={3}>
              <div className="-mx-2 space-y-0.5">
                {d.recommendations.map((r, i) => (
                  <AriaRecommendation key={i} item={r} index={i} />
                ))}
              </div>
            </AriaCard>
          )}
          {d.insights.length > 0 && (
            <AriaCard title="Insights" attribution index={4}>
              <div className="-mx-2 space-y-0.5">
                {d.insights.map((r, i) => (
                  <AriaInsightCard key={i} item={r} index={i} />
                ))}
              </div>
            </AriaCard>
          )}
        </div>
      )}

      {forecasts.length === 0 &&
        d.recommendations.length === 0 &&
        d.insights.length === 0 && (
          <AriaEmptyState
            compact
            title="ARIA is still learning your farm"
            description="Forecasts and recommendations appear once there are enough days of records to find a pattern."
          />
        )}
    </div>
  );
}

/* ── Assistant ─────────────────────────────────────────────────────────────── */

const GREETING: AriaMessage = {
  id: "greeting",
  role: "aria",
  text: "Hi, I'm ARIA. Ask me about your feed, finances, mortality, disease risk, inventory or egg production — I answer from your own records.",
};

function AssistantTab({
  farmId,
  dashboard,
}: {
  farmId: string;
  dashboard?: AIDashboard;
}) {
  const [messages, setMessages] = useState<AriaMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const seq = useRef(0);
  const nextId = () => `m${++seq.current}`;

  /**
   * Attach the matching dashboard card when an answer is clearly about one of
   * them. Keyed off the question rather than the answer text, because the
   * question is what the farmer was looking for — and because matching on the
   * answer would attach a disease card to any reply that happened to mention
   * the word.
   */
  const cardFor = useMemo(
    () =>
      (question: string): React.ReactNode => {
        if (!dashboard) return null;
        const q = question.toLowerCase();
        if (/disease|sick|infection|outbreak|risk/.test(q)) {
          return <AriaDiseaseCard risk={dashboard.disease_risk} />;
        }
        if (/mortalit|death|dying|die|cull/.test(q)) {
          return <AriaPredictionCard prediction={dashboard.mortality} />;
        }
        return null;
      },
    [dashboard],
  );

  const ask = useMutation({
    mutationFn: (q: string) => askAI(farmId, q),
    onSuccess: (r, question) => {
      setMessages((m) => [
        ...m,
        {
          id: nextId(),
          role: "aria",
          text: r.answer,
          sources: r.sources,
          provider: r.provider,
          cards: cardFor(question),
          followUps: suggestFollowUps(r.answer, r.sources),
        },
      ]);
    },
    onError: (e: unknown) => {
      const message =
        (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data
          ?.error?.message ?? "Sorry, I couldn't answer that right now. Please try again.";
      setMessages((m) => [...m, { id: nextId(), role: "aria", text: message, error: true }]);
    },
  });

  const send = (raw?: string) => {
    const q = (raw ?? input).trim();
    if (!q || ask.isPending) return;
    setMessages((m) => [...m, { id: nextId(), role: "user", text: q }]);
    setInput("");
    ask.mutate(q);
  };

  const fresh = messages.length <= 1;

  return (
    <div
      className={[
        "flex flex-col rounded-2xl border border-gray-200 dark:border-white/10",
        // Fills the viewport minus the shell chrome, with a floor so it never
        // collapses on a short window. dvh, not vh — mobile browser toolbars.
        "h-[calc(100dvh-18rem)] min-h-[440px]",
      ].join(" ")}
    >
      <AriaTranscript
        dependency={messages.length + (ask.isPending ? 0.5 : 0)}
        className="space-y-4 p-4 sm:p-5"
      >
        {messages.map((m, i) => (
          <AriaMessageBubble key={m.id} message={m} index={i} onFollowUp={(q) => send(q)} />
        ))}
        {ask.isPending && <AriaThinking />}
      </AriaTranscript>

      {fresh && (
        <div className="px-4 pb-3 sm:px-5">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
            Try asking
          </p>
          <AriaQuickActions actions={OPENING_ACTIONS} onPick={(q) => send(q)} />
        </div>
      )}

      <div className="border-t border-gray-200 p-3 dark:border-white/10">
        <AriaComposer
          value={input}
          onChange={setInput}
          onSubmit={() => send()}
          disabled={ask.isPending}
          bare
        />
        <p className="mt-2 flex items-center gap-1.5 px-1 text-[11px] text-gray-400 dark:text-gray-500">
          <AriaMark size={11} detail="simple" />
          ARIA answers from your farm records. Check anything critical before acting.
        </p>
      </div>
    </div>
  );
}
