/**
 * AGRIOS — Axios HTTP Client
 * Configured with:
 * - Base URL from environment
 * - JWT Bearer token injection from Zustand auth store
 * - Automatic token refresh on 401
 * - Standard error handling
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { APIError } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,       // Required for httpOnly refresh token cookie
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,              // 30s default; AI endpoints get their own timeout
});

// ── Request Interceptor — Inject Bearer Token ──────────────────────────────

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Access token is stored in Zustand authStore (in-memory, not localStorage)
    // We import lazily to avoid circular deps
    try {
      const { useAuthStore } = require("@/stores/authStore");
      const token = useAuthStore.getState().accessToken;
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // Store not yet initialised — first request before app loads
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ── Response Interceptor — Handle 401 with Token Refresh ──────────────────

let isRefreshing = false;
let failedRequestQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<APIError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue requests while refresh is in progress
        return new Promise((resolve, reject) => {
          failedRequestQueue.push({ resolve, reject });
        }).then(() => apiClient(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Attempt token refresh using the httpOnly cookie
        const refreshResponse = await apiClient.post("/auth/refresh");
        const { access_token } = refreshResponse.data.data;

        // Update token in auth store
        const { useAuthStore } = await import("@/stores/authStore");
        useAuthStore.getState().setAccessToken(access_token);

        // Retry all queued requests
        failedRequestQueue.forEach(({ resolve }) => resolve(undefined));
        failedRequestQueue = [];

        // Retry the original failed request
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed — clear auth state and redirect to login
        failedRequestQueue.forEach(({ reject }) => reject(refreshError));
        failedRequestQueue = [];

        const { useAuthStore } = await import("@/stores/authStore");
        useAuthStore.getState().clearAuth();

        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
