/**
 * AI-02 — Insights Screen
 * /farms/:farmId/aria/insights
 *
 * Proactive ARIA insights for the farm.
 * - Severity badges: alert=red, warning=amber, info=brand, reminder=gray
 * - Dismiss button per card
 * - Empty state when no active insights
 * - Count chips in header per severity
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { dismissInsight, listInsights } from "@/api/aria";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { AIInsight, InsightSeverity } from "@/types";

// ── Severity helpers ───────────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<InsightSeverity, { badge: string; border: string; icon: string }> = {
  alert:    { badge: "bg-red-100 text-red-700",    border: "border-red-200",    icon: "🚨" },
  warning:  { badge: "bg-amber-100 text-amber-700", border: "border-amber-200",  icon: "⚠️" },
  info:     { badge: "bg-brand-50 text-brand-700",  border: "border-brand-100",  icon: "💡" },
  reminder: { badge: "bg-gray-100 text-gray-600",   border: "border-gray-200",   icon: "🔔" },
};

function SeverityBadge({ severity }: { severity: InsightSeverity }) {
  const { t } = useTranslation();
  const s = SEVERITY_STYLES[severity];
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${s.badge}`}>
      {t(`aria.insights.severity.${severity}`)}
    </span>
  );
}

// ── Insight Card ──────────────────────────────────────────────────────────────

function InsightCard({
  insight,
  onDismiss,
  dismissing,
}: {
  insight: AIInsight;
  onDismiss: (id: string) => void;
  dismissing: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { farmId } = useParams<{ farmId: string }>();
  const s = SEVERITY_STYLES[insight.severity];

  return (
    <div className={`bg-white rounded-2xl border ${s.border} p-4 shadow-sm`}>
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0 mt-0.5">{s.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <SeverityBadge severity={insight.severity} />
            <span className="text-xs text-gray-400">{insight.insight_type.replace(/_/g, " ")}</span>
          </div>
          <h3 className="text-sm font-semibold text-gray-900 leading-snug">{insight.title}</h3>
          <p className="text-sm text-gray-600 mt-1 leading-relaxed">{insight.body}</p>

          {/* Action link */}
          {insight.action_route && insight.action_label && (
            <button
              onClick={() => navigate(insight.action_route!.replace(":farmId", farmId ?? ""))}
              className="text-brand-600 text-sm font-medium mt-2 hover:underline"
            >
              {insight.action_label} →
            </button>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-50">
        <span className="text-xs text-gray-400">
          {new Date(insight.generated_at).toLocaleDateString("en-KE", {
            day: "numeric",
            month: "short",
          })}
        </span>
        <button
          onClick={() => onDismiss(insight.id)}
          disabled={dismissing}
          className="text-xs text-gray-400 hover:text-gray-600 disabled:opacity-40 flex items-center gap-1"
        >
          {dismissing ? <Spinner size="xs" /> : null}
          {t("aria.insights.dismiss")}
        </button>
      </div>
    </div>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

export default function InsightsScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [showDismissed, setShowDismissed] = useState(false);
  const [dismissingId, setDismissingId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.aiInsights(farmId!),
    queryFn: () => listInsights(farmId!, showDismissed),
    enabled: !!farmId,
  });

  const dismissMutation = useMutation({
    mutationFn: (insightId: string) => dismissInsight(farmId!, insightId),
    onMutate: (id) => setDismissingId(id),
    onSettled: () => setDismissingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.aiInsights(farmId!) });
    },
  });

  const insights = data?.insights ?? [];
  const counts = data?.severity_counts ?? { alert: 0, warning: 0, info: 0, reminder: 0 };

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3 mb-3">
          <button onClick={() => navigate(-1)} className="text-gray-500 text-lg">←</button>
          <h1 className="text-xl font-bold text-gray-900">{t("aria.insights.title")}</h1>
        </div>

        {/* Severity counts */}
        <div className="flex items-center gap-2 flex-wrap">
          {(["alert", "warning", "info", "reminder"] as InsightSeverity[]).map((sev) =>
            counts[sev] > 0 ? (
              <span
                key={sev}
                className={`text-xs font-medium px-2.5 py-1 rounded-full ${SEVERITY_STYLES[sev].badge}`}
              >
                {counts[sev]} {t(`aria.insights.severity.${sev}`)}
              </span>
            ) : null
          )}
          {Object.values(counts).every((c) => c === 0) && (
            <span className="text-sm text-gray-400">{t("aria.insights.all_clear")}</span>
          )}
        </div>

        {/* Show dismissed toggle */}
        <button
          onClick={() => setShowDismissed((v) => !v)}
          className="mt-3 text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
        >
          <span>{showDismissed ? "▼" : "▶"}</span>
          {showDismissed ? t("aria.insights.hide_dismissed") : t("aria.insights.show_dismissed")}
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 px-4 py-4 space-y-3">
        {isLoading && (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        )}

        {isError && (
          <div className="bg-red-50 border border-red-100 rounded-2xl p-4 text-sm text-red-600 text-center">
            {t("aria.insights.load_error")}
          </div>
        )}

        {!isLoading && !isError && insights.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <span className="text-5xl mb-4">✅</span>
            <h2 className="text-gray-800 font-semibold">{t("aria.insights.empty_title")}</h2>
            <p className="text-gray-400 text-sm mt-1 max-w-xs">{t("aria.insights.empty_body")}</p>
          </div>
        )}

        {insights.map((insight) => (
          <InsightCard
            key={insight.id}
            insight={insight}
            onDismiss={(id) => dismissMutation.mutate(id)}
            dismissing={dismissingId === insight.id}
          />
        ))}
      </div>
    </div>
  );
}
