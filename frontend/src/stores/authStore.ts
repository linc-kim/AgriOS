/**
 * AGRIOS — Auth Zustand Store
 * Manages: access token (in-memory), current user, auth state.
 * Access token is NEVER persisted to localStorage or sessionStorage.
 * Refresh token lives in httpOnly cookie (managed by the browser).
 */

import { create } from "zustand";
import type { User } from "@/types";

interface AuthStore {
  // State
  accessToken: string | null;
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  // Actions
  setAuth: (accessToken: string, user: User) => void;
  setAccessToken: (token: string) => void;
  setUser: (user: User) => void;
  clearAuth: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  // Initial state — user must re-auth on page load via refresh token cookie
  accessToken: null,
  user: null,
  isLoading: true,    // True on startup while we check refresh token
  isAuthenticated: false,

  setAuth: (accessToken, user) =>
    set({
      accessToken,
      user,
      isAuthenticated: true,
      isLoading: false,
    }),

  setAccessToken: (token) =>
    set({ accessToken: token }),

  setUser: (user) =>
    set({ user }),

  clearAuth: () =>
    set({
      accessToken: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
    }),

  setLoading: (loading) =>
    set({ isLoading: loading }),
}));
