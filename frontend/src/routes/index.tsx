/**
 * Greena — Route configuration.
 * Auth (public) · Onboarding (protected wizard) · App shell (protected, driven
 * by the module registry). Each registered module gets a route automatically —
 * modules without a bespoke screen render a calm empty state.
 */
import { lazy, Suspense, useEffect } from "react";
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
} from "react-router-dom";

import AuthLayout from "@/layouts/AuthLayout";
import AppShell from "@/layouts/AppShell";
import { useAuthStore } from "@/stores/authStore";
import { authAPI } from "@/api/auth";
import { Spinner } from "@/components/ui/Spinner";
import { MODULES } from "@/shell/registry";

// Auth
const EmailLoginScreen = lazy(() => import("@/screens/auth/EmailLoginScreen"));
const SignUpScreen = lazy(() => import("@/screens/auth/SignUpScreen"));
const LoginScreen = lazy(() => import("@/screens/auth/LoginScreen"));
const OTPScreen = lazy(() => import("@/screens/auth/OTPScreen"));
const PINSetupScreen = lazy(() => import("@/screens/auth/PINSetupScreen"));
const PINLoginScreen = lazy(() => import("@/screens/auth/PINLoginScreen"));

// Onboarding
const OnboardingScreen = lazy(() => import("@/screens/onboarding/OnboardingScreen"));

// App
const DashboardScreen = lazy(() => import("@/screens/DashboardScreen"));
const ModuleScreen = lazy(() => import("@/screens/modules/ModuleScreen"));

// Modules with bespoke screens
const LivestockScreen = lazy(() => import("@/screens/livestock/LivestockScreen"));
const FlockDetailScreen = lazy(() => import("@/screens/livestock/FlockDetailScreen"));
const InventoryScreen = lazy(() => import("@/screens/inventory/InventoryScreen"));

// Utility / status
const UnauthorizedScreen = lazy(() => import("@/screens/utility/UnauthorizedScreen"));
const SessionExpiredScreen = lazy(() => import("@/screens/utility/SessionExpiredScreen"));
const OfflineScreen = lazy(() => import("@/screens/utility/OfflineScreen"));
const NotFoundScreen = lazy(() => import("@/screens/utility/NotFoundScreen"));

// ── Guards ────────────────────────────────────────────────────────────────────

function RequireAuth() {
  const { isAuthenticated, isLoading, setAuth, clearAuth } = useAuthStore();

  useEffect(() => {
    const restoreSession = async () => {
      try {
        const { access_token } = await authAPI.refresh();
        const user = await authAPI.getMe();
        setAuth(access_token, user);
      } catch {
        clearAuth();
      }
    };
    if (!isAuthenticated && isLoading) restoreSession();
  }, []);

  if (isLoading) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[#f6f8f6] dark:bg-[#0b0e12]">
        <Spinner size="lg" />
      </div>
    );
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}

// ── Module routes (from the registry) ─────────────────────────────────────────

// Modules that have their own screens are routed explicitly below; the rest
// fall back to the calm empty-state ModuleScreen.
const BESPOKE_PATHS = new Set(["/livestock", "/inventory"]);
const moduleRoutes = MODULES.filter(
  (m) => m.path !== "/" && !BESPOKE_PATHS.has(m.path),
).map((m) => ({
  path: m.path,
  element: <ModuleScreen />,
}));

const router = createBrowserRouter([
  // Public auth
  {
    element: <AuthLayout />,
    children: [
      { path: "/login", element: <EmailLoginScreen /> },
      { path: "/signup", element: <SignUpScreen /> },
      { path: "/phone-login", element: <LoginScreen /> },
      { path: "/verify-otp", element: <OTPScreen /> },
      { path: "/set-pin", element: <PINSetupScreen /> },
      { path: "/pin-login", element: <PINLoginScreen /> },
    ],
  },

  // Status (public)
  { path: "/session-expired", element: <SessionExpiredScreen /> },

  // Onboarding (protected, full-screen)
  {
    element: <RequireAuth />,
    children: [{ path: "/onboarding", element: <OnboardingScreen /> }],
  },

  // Protected application shell
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: <DashboardScreen /> },
          { path: "/livestock", element: <LivestockScreen /> },
          { path: "/livestock/:flockId", element: <FlockDetailScreen /> },
          { path: "/inventory", element: <InventoryScreen /> },
          ...moduleRoutes,
          { path: "/unauthorized", element: <UnauthorizedScreen /> },
          { path: "/offline", element: <OfflineScreen /> },
        ],
      },
    ],
  },

  { path: "*", element: <NotFoundScreen /> },
]);

function ScreenFallback() {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-[#f6f8f6] dark:bg-[#0b0e12]">
      <Spinner size="md" />
    </div>
  );
}

export function AppRouter() {
  return (
    <Suspense fallback={<ScreenFallback />}>
      <RouterProvider router={router} />
    </Suspense>
  );
}
