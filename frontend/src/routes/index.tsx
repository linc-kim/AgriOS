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

// Public marketing site (Module 12). Lazy so the app bundle is not paid for by
// a visitor who only reads the homepage, and vice versa.
const MarketingLayout = lazy(() => import("@/layouts/MarketingLayout"));
const HomeScreen = lazy(() => import("@/screens/public/HomeScreen"));
const FeaturesScreen = lazy(() => import("@/screens/public/FeaturesScreen"));
const SolutionsScreen = lazy(() => import("@/screens/public/SolutionsScreen"));
const AriaScreen = lazy(() => import("@/screens/public/AriaScreen"));
const PricingScreen = lazy(() => import("@/screens/public/PricingScreen"));
const LearningScreen = lazy(() => import("@/screens/public/LearningScreen"));
const AboutScreen = lazy(() => import("@/screens/public/AboutScreen"));
const ContactScreen = lazy(() => import("@/screens/public/ContactScreen"));
const BrandAriaScreen = lazy(() => import("@/screens/public/BrandAriaScreen"));

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
const FeedScreen = lazy(() => import("@/screens/inventory/InventoryScreen"));
const StoreScreen = lazy(() => import("@/screens/store/StoreScreen"));
const FinanceScreen = lazy(() => import("@/screens/finance/FinanceScreen"));
const ReportsScreen = lazy(() => import("@/screens/reports/ReportsScreen"));
const AutomationScreen = lazy(() => import("@/screens/automation/AutomationScreen"));
const AIScreen = lazy(() => import("@/screens/ai/AIScreen"));
const AriaWorkspace = lazy(() => import("@/screens/ai/AriaWorkspace"));
const AriaSupervisorScreen = lazy(() => import("@/screens/ai/AriaSupervisorScreen"));
const AdminScreen = lazy(() => import("@/screens/admin/AdminScreen"));
const ProductionScreen = lazy(() => import("@/screens/production/ProductionScreen"));

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
const BESPOKE_PATHS = new Set(["/livestock", "/inventory", "/feed", "/finance", "/reports", "/automation", "/ai", "/admin", "/production"]);
const moduleRoutes = MODULES.filter(
  (m) => m.path !== "/" && !BESPOKE_PATHS.has(m.path),
).map((m) => ({
  path: m.path,
  element: <ModuleScreen />,
}));

const router = createBrowserRouter([
  // Public marketing site. "/" is the homepage for everyone — the app's
  // dashboard moved to /dashboard so a visitor is not met with a login wall.
  {
    element: <MarketingLayout />,
    children: [
      { path: "/", element: <HomeScreen /> },
      { path: "/features", element: <FeaturesScreen /> },
      { path: "/solutions", element: <SolutionsScreen /> },
      // /aria-ai, not /aria — /ai is the in-app assistant module.
      { path: "/aria-ai", element: <AriaScreen /> },
      { path: "/pricing", element: <PricingScreen /> },
      { path: "/learning", element: <LearningScreen /> },
      { path: "/about", element: <AboutScreen /> },
      { path: "/contact", element: <ContactScreen /> },
      // Living brand documentation — rendered from the same component the
      // product uses, so the spec cannot drift from the real mark.
      { path: "/brand/aria", element: <BrandAriaScreen /> },
    ],
  },

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
          { path: "/dashboard", element: <DashboardScreen /> },
          { path: "/livestock", element: <LivestockScreen /> },
          { path: "/livestock/:flockId", element: <FlockDetailScreen /> },
          { path: "/feed", element: <FeedScreen /> },
          { path: "/inventory", element: <StoreScreen /> },
          { path: "/finance", element: <FinanceScreen /> },
          { path: "/reports", element: <ReportsScreen /> },
          { path: "/automation", element: <AutomationScreen /> },
          // The workspace is ARIA's primary surface (Module 13). The analytical
          // dashboard/assistant tabs stay reachable at /ai/insights.
          { path: "/ai", element: <AriaWorkspace /> },
          { path: "/ai/supervisor", element: <AriaSupervisorScreen /> },
          { path: "/ai/insights", element: <AIScreen /> },
          { path: "/admin", element: <AdminScreen /> },
          { path: "/production", element: <ProductionScreen /> },
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
