/**
 * Greena — Auth API Functions
 * All auth HTTP calls. Used by React Query mutations.
 */

import apiClient from "./client";
import type {
  APISuccess,
  TokenResponse,
  User,
} from "@/types";

// ── Types ──────────────────────────────────────────────────────────────────

export interface OTPRequestPayload {
  phone: string;
}

export interface OTPVerifyPayload {
  phone: string;
  code: string;
}

export interface PINSetPayload {
  pin: string;
  pin_confirm: string;
}

export interface PINVerifyPayload {
  phone: string;
  pin: string;
}

export interface UserUpdatePayload {
  full_name?: string | null;
  language?: "en" | "sw";
  sms_notifications_enabled?: boolean;
}

export interface EmailSignupPayload {
  email: string;
  password: string;
  full_name?: string;
  remember_me?: boolean;
}

export interface EmailLoginPayload {
  email: string;
  password: string;
  remember_me?: boolean;
}

// ── API Calls ──────────────────────────────────────────────────────────────

export const authAPI = {
  signup: async (payload: EmailSignupPayload) => {
    const response = await apiClient.post<APISuccess<TokenResponse>>(
      "/auth/signup",
      payload,
    );
    return response.data.data;
  },

  login: async (payload: EmailLoginPayload) => {
    const response = await apiClient.post<APISuccess<TokenResponse>>(
      "/auth/login",
      payload,
    );
    return response.data.data;
  },

  logoutAll: async () => {
    await apiClient.post("/auth/logout-all");
  },

  requestOTP: async (payload: OTPRequestPayload) => {
    const response = await apiClient.post<
      APISuccess<{ phone: string; message: string; expires_in_minutes: number }>
    >("/auth/request-otp", payload);
    return response.data.data;
  },

  verifyOTP: async (payload: OTPVerifyPayload) => {
    const response = await apiClient.post<APISuccess<TokenResponse>>(
      "/auth/verify-otp",
      payload,
    );
    return response.data.data;
  },

  setPIN: async (payload: PINSetPayload) => {
    const response = await apiClient.post<APISuccess<{ message: string }>>(
      "/auth/set-pin",
      payload,
    );
    return response.data.data;
  },

  verifyPIN: async (payload: PINVerifyPayload) => {
    const response = await apiClient.post<APISuccess<TokenResponse>>(
      "/auth/verify-pin",
      payload,
    );
    return response.data.data;
  },

  refresh: async () => {
    const response = await apiClient.post<
      APISuccess<{ access_token: string; expires_in: number }>
    >("/auth/refresh");
    return response.data.data;
  },

  logout: async () => {
    await apiClient.post("/auth/logout");
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<APISuccess<User>>("/auth/me");
    return response.data.data;
  },

  updateMe: async (payload: UserUpdatePayload): Promise<User> => {
    const response = await apiClient.patch<APISuccess<User>>("/auth/me", payload);
    return response.data.data;
  },
};
