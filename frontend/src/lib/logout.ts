import { authAPI } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";
import { queryClient } from "@/lib/queryClient";

/** Revoke the session server-side (best effort), clear local state + cache. */
export async function logout() {
  try {
    await authAPI.logout();
  } catch {
    /* ignore — clear locally regardless */
  }
  useAuthStore.getState().clearAuth();
  queryClient.clear();
}
