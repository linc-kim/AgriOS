/**
 * Greena — Notifications API Client (Sprint 7)
 * Wraps /api/v1/farms/{farmId}/notifications endpoints.
 */

import { apiClient } from "./client";
import type { APISuccess, Notification, NotificationListResponse } from "@/types";

export interface NotificationListParams {
  unread_only?: boolean;
  limit?: number;
  offset?: number;
}

export const notificationsAPI = {
  /**
   * List notifications for the current user on this farm.
   */
  list: async (
    farmId: string,
    params?: NotificationListParams,
  ): Promise<NotificationListResponse> => {
    const res = await apiClient.get<APISuccess<NotificationListResponse>>(
      `/farms/${farmId}/notifications`,
      { params },
    );
    return res.data.data;
  },

  /**
   * Mark a single notification as read.
   */
  markRead: async (farmId: string, notificationId: string): Promise<Notification> => {
    const res = await apiClient.patch<APISuccess<Notification>>(
      `/farms/${farmId}/notifications/${notificationId}/read`,
    );
    return res.data.data;
  },

  /**
   * Mark all notifications as read for this user + farm.
   * Returns the count of notifications updated.
   */
  markAllRead: async (farmId: string): Promise<number> => {
    const res = await apiClient.post<APISuccess<{ updated: number }>>(
      `/farms/${farmId}/notifications/read-all`,
    );
    return res.data.data.updated;
  },

  /**
   * Soft-delete a notification.
   */
  delete: async (farmId: string, notificationId: string): Promise<void> => {
    await apiClient.delete(`/farms/${farmId}/notifications/${notificationId}`);
  },
};
