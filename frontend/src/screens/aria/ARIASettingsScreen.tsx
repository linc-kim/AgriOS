/**
 * AI-04 — ARIA Settings Screen
 * /farms/:farmId/aria/settings
 *
 * Quota progress bar (used/limit), plan name badge,
 * conversation history list with individual delete,
 * and navigation shortcuts to chat / insights / recommendations.
 */

import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { deleteConversation, getARIAUsage, listConversations } from "@/api/aria";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { AIConversationSummary } from "@/types";

// ── Quota Progress Bar ────────────────────────────────────────────────────────

function QuotaBar({
  used,
  limit,
  planName,
}: {
  used: number;
  limit: number | null;
  planName: string;
}) {
  const { t } = useTranslation();
  const isUnlimited = limit === null;
  const pct = isUnlimited ? 0 : Math.min(100, Math.round((used / limit!) * 100));
  const barColor =
    pct >= 90 ? "bg-red-400" : pct >= 70 ? "bg-amber-400" : "bg-brand-500";

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-gray-900">{t("aria.settings.quota_title")}</h2>
        <span className="text-xs font-medium bg-brand-50 text-brand-700 px-2.5 py-1 rounded-full capitalize">
          {planName}
        </span>
      </div>

      {isUnlimited ? (
        <div className="flex items-center gap-2">
          <span className="text-3xl font-bold text-brand-600">∞</span>
          <div>
            <p className="text-sm font-medium text-gray-800">{t("aria.settings.unlimited")}</p>
            <p className="text-xs text-gray-400">
              {used} {t("aria.settings.queries_this_month")}
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-end justify-between mb-2">
            <span className="text-3xl font-bold text-gray-900">{used}</span>
            <span className="text-sm text-gray-400">/ {limit} {t("aria.settings.this_month")}</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {limit! - used > 0
              ? `${limit! - used} ${t("aria.settings.queries_remaining")}`
              : t("aria.settings.quota_exhausted")}
          </p>
        </>
      )}
    </div>
  );
}

// ── Conversation Row ──────────────────────────────────────────────────────────

function ConversationRow({
  conv,
  farmId,
  onDelete,
  deleting,
}: {
  conv: AIConversationSummary;
  farmId: string;
  onDelete: (id: string) => void;
  deleting: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="flex items-center gap-3 py-3 border-b border-gray-50 last:border-0">
      <button
        onClick={() => navigate(`/farms/${farmId}/aria?conv=${conv.id}`)}
        className="flex-1 text-left min-w-0"
      >
        <p className="text-sm font-medium text-gray-800 truncate">
          {conv.title || t("aria.history.untitled")}
        </p>
        <p className="text-xs text-gray-400 mt-0.5">
          {conv.message_count} {t("aria.history.messages")} ·{" "}
          {new Date(conv.created_at).toLocaleDateString("en-KE", {
            day: "numeric",
            month: "short",
          })}
        </p>
      </button>
      <button
        onClick={() => onDelete(conv.id)}
        disabled={deleting}
        className="text-gray-300 hover:text-red-400 disabled:opacity-40 text-lg flex-shrink-0 w-8 h-8 flex items-center justify-center"
      >
        {deleting ? <Spinner size="xs" /> : "×"}
      </button>
    </div>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

export default function ARIASettingsScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: usageData, isLoading: usageLoading } = useQuery({
    queryKey: queryKeys.aiQuota(farmId!),
    queryFn: () => getARIAUsage(farmId!),
    enabled: !!farmId,
  });

  const { data: conversations = [], isLoading: convsLoading } = useQuery({
    queryKey: queryKeys.aiConversations(farmId!),
    queryFn: () => listConversations(farmId!),
    enabled: !!farmId,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(farmId!, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.aiConversations(farmId!) });
    },
  });

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-4 border-b border-gray-100 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-500 text-lg">←</button>
        <h1 className="text-xl font-bold text-gray-900">{t("aria.settings.title")}</h1>
      </div>

      <div className="flex-1 px-4 py-4 space-y-4">
        {/* Quota */}
        {usageLoading ? (
          <div className="bg-white rounded-2xl border border-gray-100 p-5 flex justify-center">
            <Spinner />
          </div>
        ) : usageData ? (
          <QuotaBar
            used={usageData.queries_used_this_month}
            limit={usageData.monthly_limit}
            planName={usageData.plan_name}
          />
        ) : null}

        {/* Quick links */}
        <div className="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50 shadow-sm overflow-hidden">
          <button
            onClick={() => navigate(`/farms/${farmId}/aria`)}
            className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-gray-50 active:bg-gray-100"
          >
            <div className="flex items-center gap-3">
              <span className="text-xl">💬</span>
              <span className="text-sm font-medium text-gray-800">{t("aria.settings.go_chat")}</span>
            </div>
            <span className="text-gray-300">›</span>
          </button>
          <button
            onClick={() => navigate(`/farms/${farmId}/aria/insights`)}
            className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-gray-50 active:bg-gray-100"
          >
            <div className="flex items-center gap-3">
              <span className="text-xl">💡</span>
              <span className="text-sm font-medium text-gray-800">{t("aria.settings.go_insights")}</span>
            </div>
            <span className="text-gray-300">›</span>
          </button>
          <button
            onClick={() => navigate(`/farms/${farmId}/aria/recommendations`)}
            className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-gray-50 active:bg-gray-100"
          >
            <div className="flex items-center gap-3">
              <span className="text-xl">📋</span>
              <span className="text-sm font-medium text-gray-800">{t("aria.settings.go_recommendations")}</span>
            </div>
            <span className="text-gray-300">›</span>
          </button>
        </div>

        {/* Conversation history */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-50">
            <h2 className="text-sm font-bold text-gray-900">{t("aria.settings.conversations_title")}</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              {conversations.length} {t("aria.settings.total_conversations")}
            </p>
          </div>

          {convsLoading && (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          )}

          {!convsLoading && conversations.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              {t("aria.settings.no_conversations")}
            </p>
          )}

          <div className="px-4">
            {conversations.map((conv) => (
              <ConversationRow
                key={conv.id}
                conv={conv}
                farmId={farmId!}
                onDelete={(id) => deleteMutation.mutate(id)}
                deleting={deleteMutation.isPending && deleteMutation.variables === conv.id}
              />
            ))}
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-300 text-center pb-4">
          {t("aria.settings.disclaimer")}
        </p>
      </div>
    </div>
  );
}
