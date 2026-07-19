/**
 * Greena — Axios HTTP Client
 * Configured with:
 * - Base URL from environment
 * - JWT Bearer token injection from Zustand auth store
 * - Automatic token refresh on 401
 * - Standard error handling
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { APIError } from "@/types";
import { useAuthStore } from "@/stores/authStore";

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
    // Access token is stored in Zustand authStore (in-memory, not localStorage).
    // authStore imports only zustand + types, so this static import is not circular.
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
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

/**
 * The refresh call must never go through the refresh-on-401 recovery below.
 *
 * If it did, a 401 from /auth/refresh would trigger a second /auth/refresh;
 * that inner call sees isRefreshing === true, parks itself on
 * failedRequestQueue, and returns a promise that only settles once the outer
 * refresh settles — while the outer refresh is awaiting the inner one. The two
 * deadlock, the promise never resolves, and the app hangs on its loading
 * spinner instead of redirecting to login. Users with an expired refresh token
 * saw a permanent spinner.
 */
const isRefreshRequest = (config?: InternalAxiosRequestConfig): boolean =>
  Boolean(config?.url?.includes("/auth/refresh"));

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<APIError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // A failed refresh is terminal: clear auth and let the caller redirect.
    if (error.response?.status === 401 && isRefreshRequest(originalRequest)) {
      failedRequestQueue.forEach(({ reject }) => reject(error));
      failedRequestQueue = [];
      isRefreshing = false;

      const { useAuthStore } = await import("@/stores/authStore");
      useAuthStore.getState().clearAuth();

      return Promise.reject(error);
    }

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
