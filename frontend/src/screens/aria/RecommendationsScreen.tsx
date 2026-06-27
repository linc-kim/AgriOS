/**
 * AI-03 — Recommendations Screen
 * /farms/:farmId/aria/recommendations
 *
 * Pending ARIA recommendation cards.
 * - "Act" and "Dismiss" buttons per card
 * - Status chip (pending / acted / dismissed / expired)
 * - action_route deep link
 * - Filter tabs: pending | all
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { actionRecommendation, listRecommendations } from "@/api/aria";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { AIRecommendation, RecommendationStatus } from "@/types";

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<RecommendationStatus, string> = {
  pending:   "bg-brand-50 text-brand-700",
  acted:     "bg-green-100 text-green-700",
  dismissed: "bg-gray-100 text-gray-500",
  expired:   "bg-gray-50 text-gray-400",
};

function StatusChip({ status }: { status: RecommendationStatus }) {
  const { t } = useTranslation();
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLES[status]}`}>
      {t(`aria.recommendations.status.${status}`)}
    </span>
  );
}

// ── Recommendation Card ───────────────────────────────────────────────────────

function RecommendationCard({
  rec,
  onAct,
  onDismiss,
  acting,
  dismissing,
}: {
  rec: AIRecommendation;
  onAct: (id: string) => void;
  onDismiss: (id: string) => void;
  acting: boolean;
  dismissing: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { farmId } = useParams<{ farmId: string }>();
  const isPending = rec.status === "pending";

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0 mt-0.5">📋</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <StatusChip status={rec.status} />
            <span className="text-xs text-gray-400">{rec.recommendation_type.replace(/_/g, " ")}</span>
          </div>
          <h3 className="text-sm font-semibold text-gray-900 leading-snug">{rec.title}</h3>
          <p className="text-sm text-gray-600 mt-1 leading-relaxed">{rec.body}</p>

          {/* Expiry */}
          {rec.expires_at && (
            <p className="text-xs text-amber-500 mt-1.5">
              {t("aria.recommendations.expires")}{" "}
              {new Date(rec.expires_at).toLocaleDateString("en-KE", {
                day: "numeric",
                month: "short",
              })}
            </p>
          )}
        </div>
      </div>

      {/* Actions */}
      {isPending && (
        <div className="flex items-center gap-2 mt-4">
          {/* Primary action: navigate to action_route */}
          {rec.action_route ? (
            <button
              onClick={() => {
                onAct(rec.id);
                navigate(rec.action_route!.replace(":farmId", farmId ?? ""));
              }}
              disabled={acting}
              className="flex-1 bg-brand-600 text-white text-sm font-medium py-2.5 rounded-xl flex items-center justify-center gap-1.5 disabled:opacity-50"
            >
              {acting ? <Spinner size="xs" /> : null}
              {rec.action_label ?? t("aria.recommendations.act")}
            </button>
          ) : (
            <button
              onClick={() => onAct(rec.id)}
              disabled={acting}
              className="flex-1 bg-brand-600 text-white text-sm font-medium py-2.5 rounded-xl flex items-center justify-center gap-1.5 disabled:opacity-50"
            >
              {acting ? <Spinner size="xs" /> : null}
              {t("aria.recommendations.act")}
            </button>
          )}
          <button
            onClick={() => onDismiss(rec.id)}
            disabled={dismissing}
            className="flex-1 border border-gray-200 text-gray-600 text-sm font-medium py-2.5 rounded-xl flex items-center justify-center gap-1.5 disabled:opacity-40 hover:bg-gray-50"
          >
            {dismissing ? <Spinner size="xs" /> : null}
            {t("aria.recommendations.dismiss")}
          </button>
        </div>
      )}

      {/* Acted / dismissed timestamp */}
      {rec.acted_at && (
        <p className="text-xs text-green-500 mt-3 text-right">
          {t("aria.recommendations.acted_at")}{" "}
          {new Date(rec.acted_at).toLocaleDateString("en-KE")}
        </p>
      )}
      {rec.dismissed_at && (
        <p className="text-xs text-gray-400 mt-3 text-right">
          {t("aria.recommendations.dismissed_at")}{" "}
          {new Date(rec.dismissed_at).toLocaleDateString("en-KE")}
        </p>
      )}
    </div>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

type TabFilter = "pending" | "all";

export default function RecommendationsScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<TabFilter>("pending");
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [dismissingId, setDismissingId] = useState<string | null>(null);

  const statusFilter = tab === "pending" ? "pending" : undefined;

  const { data, isLoading, isError } = useQuery({
    queryKey: [...queryKeys.aiRecommendations(farmId!), tab],
    queryFn: () => listRecommendations(farmId!, statusFilter),
    enabled: !!farmId,
  });

  const actMutation = useMutation({
    mutationFn: (id: string) => actionRecommendation(farmId!, id, "acted"),
    onMutate: (id) => setActioningId(id),
    onSettled: () => setActioningId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.aiRecommendations(farmId!) });
    },
  });

  const dismissMutation = useMutation({
    mutationFn: (id: string) => actionRecommendation(farmId!, id, "dismissed"),
    onMutate: (id) => setDismissingId(id),
    onSettled: () => setDismissingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.aiRecommendations(farmId!) });
    },
  });

  const recs = data?.recommendations ?? [];
  const pendingCount = data?.pending_count ?? 0;

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={() => navigate(-1)} className="text-gray-500 text-lg">←</button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{t("aria.recommendations.title")}</h1>
            {pendingCount > 0 && (
              <p className="text-xs text-brand-600 mt-0.5">
                {pendingCount} {t("aria.recommendations.pending_count")}
              </p>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {(["pending", "all"] as TabFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setTab(f)}
              className={`flex-1 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                tab === f
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {t(`aria.recommendations.tab.${f}`)}
            </button>
          ))}
        </div>
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
            {t("aria.recommendations.load_error")}
          </div>
        )}

        {!isLoading && !isError && recs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <span className="text-5xl mb-4">🎯</span>
            <h2 className="text-gray-800 font-semibold">
              {tab === "pending"
                ? t("aria.recommendations.empty_pending_title")
                : t("aria.recommendations.empty_all_title")}
            </h2>
            <p className="text-gray-400 text-sm mt-1 max-w-xs">
              {t("aria.recommendations.empty_body")}
            </p>
          </div>
        )}

        {recs.map((rec) => (
          <RecommendationCard
            key={rec.id}
            rec={rec}
            onAct={(id) => actMutation.mutate(id)}
            onDismiss={(id) => dismissMutation.mutate(id)}
            acting={actioningId === rec.id}
            dismissing={dismissingId === rec.id}
          />
        ))}
      </div>
    </div>
  );
}
