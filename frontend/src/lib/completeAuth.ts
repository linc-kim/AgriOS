/**
 * Shared post-authentication routine used by Login and Sign Up.
 * Sets the access token (so the API client authenticates), loads the user and
 * their organizations, updates the auth store, and decides where to land:
 * a user with no organization goes to onboarding, otherwise the dashboard.
 */
import { authAPI } from "@/api/auth";
import { organizationsAPI } from "@/api/organizations";
import { useAuthStore } from "@/stores/authStore";

export async function completeAuthAndRoute(accessToken: string): Promise<string> {
  const store = useAuthStore.getState();
  // Set the token first so the axios interceptor attaches it to the next calls.
  store.setAccessToken(accessToken);

  const user = await authAPI.getMe();
  store.setAuth(accessToken, user);

  const organizations = await organizationsAPI.list();
  return organizations.length === 0 ? "/onboarding" : "/";
}
