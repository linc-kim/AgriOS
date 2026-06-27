/**
 * N-01 — Notifications Screen
 * /notifications  (farm-context resolved from authStore)
 * /farms/:farmId/notifications
 *
 * Lists user notifications for the active farm.
 * - Unread badge in header
 * - Mark individual or all as read
 * - Soft-delete per notification
 * - Empty state when inbox is clear
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { notificationsAPI } from "@/api/notifications";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { Notification } from "@/types";

// ── Notification type → icon map ──────────────────────────────────────────────

const TYPE_ICONS: Record<string, string> = {
  vaccination_reminder: "💉",
  vaccination_overdue:  "⚠️",
  daily_log_reminder:   "📋",
  disease_alert:        "🚨",
  weekly_summary:       "📊",
  farm_invite:          "🤝",
};

function notifIcon(type: string): string {
  return TYPE_ICONS[type] ?? "🔔";
}

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1)  return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ── Notification Card ─────────────────────────────────────────────────────────

function NotificationCard({
  notification,
  farmId,
  onMarkRead,
  onDelete,
  markingRead,
  deleting,
}: {
  notification: Notification;
  farmId: string;
  onMarkRead: (id: string) => void;
  onDelete: (id: string) => void;
  markingRead: boolean;
  deleting: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div
      className={`bg-white rounded-2xl border p-4 shadow-sm transition-opacity ${
        notification.is_read ? "border-gray-100 opacity-75" : "border-brand-200"
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Unread dot */}
        <div className="flex-shrink-0 mt-1">
          <span className="text-2xl">{notifIcon(notification.notification_type)}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                {!notification.is_read && (
                  <span className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0" />
                )}
                <h3
                  className={`text-sm leading-snug ${
                    notification.is_read
                      ? "font-normal text-gray-700"
                      : "font-semibold text-gray-900"
                  }`}
                >
                  {notification.title}
                </h3>
              </div>
              <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                {notification.body}
              </p>

              {/* Action link */}
              {notification.action_route && (
                <button
                  onClick={() =>
                    navigate(
                      notification.action_route!.replace(":farmId", farmId),
                    )
                  }
                  className="text-brand-600 text-sm font-medium mt-1 hover:underline"
                >
                  {t("notifications.view_details")} →
                </button>
              )}
            </div>

            {/* Timestamp */}
            <span className="text-xs text-gray-400 flex-shrink-0">
              {timeAgo(notification.created_at)}
            </span>
          </div>

          {/* Actions row */}
          <div className="flex items-center gap-3 mt-3 pt-2 border-t border-gray-50">
            {!notification.is_read && (
              <button
                onClick={() => onMarkRead(notification.id)}
                disabled={markingRead}
                className="text-xs text-brand-600 font-medium hover:text-brand-700 disabled:opacity-50"
              >
                {t("notifications.mark_read")}
              </button>
            )}
            <button
              onClick={() => onDelete(notification.id)}
              disabled={deleting}
              className="text-xs text-red-500 font-medium hover:text-red-600 disabled:opacity-50 ml-auto"
            >
              {t("common.delete")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function NotificationsScreen() {
  const { t } = useTranslation();
  const { farmId } = useParams<{ farmId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);

  const farm = farmId ?? "";

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.notifications(farm),
    queryFn: () => notificationsAPI.list(farm, { unread_only: unreadOnly }),
    enabled: !!farm,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsAPI.markRead(farm, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.notifications(farm) });
      qc.invalidateQueries({ queryKey: queryKeys.unreadCount(farm) });
    },
  });

  const markAllMutation = useMutation({
    mutationFn: () => notificationsAPI.markAllRead(farm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.notifications(farm) });
      qc.invalidateQueries({ queryKey: queryKeys.unreadCount(farm) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => notificationsAPI.delete(farm, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.notifications(farm) });
      qc.invalidateQueries({ queryKey: queryKeys.unreadCount(farm) });
    },
  });

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // ── Error ───────────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-gray-500 text-sm">{t("common.error_loading")}</p>
          <button
            onClick={() => navigate(-1)}
            className="mt-3 text-brand-600 text-sm font-medium hover:underline"
          >
            {t("common.go_back")}
          </button>
        </div>
      </div>
    );
  }

  const notifications = data.items;
  const unreadCount   = data.unread_count;

  // ── Empty state ─────────────────────────────────────────────────────────────
  const isEmpty = notifications.length === 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-lg mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-gray-900">
                {t("notifications.title")}
              </h1>
              {unreadCount > 0 && (
                <span className="bg-brand-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                  {unreadCount}
                </span>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                onClick={() => markAllMutation.mutate()}
                disabled={markAllMutation.isPending}
                className="text-sm text-brand-600 font-medium hover:text-brand-700 disabled:opacity-50"
              >
                {markAllMutation.isPending
                  ? t("common.saving")
                  : t("notifications.mark_all_read")}
              </button>
            )}
          </div>

          {/* Filter toggle */}
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => setUnreadOnly(false)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                !unreadOnly
                  ? "bg-brand-600 text-white"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {t("notifications.filter_all")}
            </button>
            <button
              onClick={() => setUnreadOnly(true)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                unreadOnly
                  ? "bg-brand-600 text-white"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {t("notifications.filter_unread")}
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-lg mx-auto px-4 py-4 space-y-3">
        {isEmpty ? (
          // ── Empty state ───────────────────────────────────────────────────
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <span className="text-5xl mb-4">🔔</span>
            <h2 className="text-lg font-semibold text-gray-900 mb-1">
              {t("notifications.empty_title")}
            </h2>
            <p className="text-sm text-gray-500 max-w-xs">
              {unreadOnly
                ? t("notifications.empty_unread_body")
                : t("notifications.empty_body")}
            </p>
          </div>
        ) : (
          notifications.map((n) => (
            <NotificationCard
              key={n.id}
              notification={n}
              farmId={farm}
              onMarkRead={(id) => markReadMutation.mutate(id)}
              onDelete={(id) => deleteMutation.mutate(id)}
              markingRead={
                markReadMutation.isPending &&
                markReadMutation.variables === n.id
              }
              deleting={
                deleteMutation.isPending &&
                deleteMutation.variables === n.id
              }
            />
          ))
        )}
      </div>
    </div>
  );
}
