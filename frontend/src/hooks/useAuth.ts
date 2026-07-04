/**
 * AGRIOS — useAuth Hook
 * Wraps auth store and React Query for components.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authAPI } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";
import { queryKeys } from "@/lib/queryClient";

export function useAuth() {
  const { user, isAuthenticated, isLoading } = useAuthStore();
  const { setAuth, clearAuth } = useAuthStore();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // ── Current User ──────────────────────────────────────────────────────────

  const { data: currentUser } = useQuery({
    queryKey: queryKeys.me,
    queryFn: authAPI.getMe,
    enabled: isAuthenticated,
    staleTime: 1000 * 60 * 5,   // User profile is stable for 5 minutes
  });

  // ── OTP Flow ──────────────────────────────────────────────────────────────

  const requestOTP = useMutation({
    mutationFn: authAPI.requestOTP,
  });

  const verifyOTP = useMutation({
    mutationFn: authAPI.verifyOTP,
    onSuccess: async (data) => {
      // Store access token in-memory
      useAuthStore.getState().setAccessToken(data.access_token);
      // Fetch user profile
      const user = await authAPI.getMe();
      setAuth(data.access_token, user);
      // Navigate based on user state
      if (data.is_new_user || !data.has_pin) {
        navigate("/onboarding/name");
      } else {
        navigate("/");
      }
    },
  });

  // ── PIN Flow ──────────────────────────────────────────────────────────────

  const setPIN = useMutation({
    mutationFn: authAPI.setPIN,
    onSuccess: () => {
      navigate("/onboarding/farm");
    },
  });

  const verifyPIN = useMutation({
    mutationFn: authAPI.verifyPIN,
    onSuccess: async (data) => {
      useAuthStore.getState().setAccessToken(data.access_token);
      const user = await authAPI.getMe();
      setAuth(data.access_token, user);
      navigate("/");
    },
  });

  // ── Logout ────────────────────────────────────────────────────────────────

  const logout = useMutation({
    mutationFn: authAPI.logout,
    onSettled: () => {
      // Clear regardless of whether API call succeeded
      clearAuth();
      queryClient.clear();
      navigate("/login");
    },
  });

  return {
    user: currentUser ?? user,
    isAuthenticated,
    isLoading,
    requestOTP,
    verifyOTP,
    setPIN,
    verifyPIN,
    logout,
  };
}
