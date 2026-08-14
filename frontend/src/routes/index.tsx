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
const HelpScreen = lazy(() => import("@/screens/public/HelpScreen"));
const InstallScreen = lazy(() => import("@/screens/public/InstallScreen"));
const EnterprisesScreen = lazy(() => import("@/screens/public/EnterprisesScreen"));
const EnterpriseScreen = lazy(() => import("@/screens/public/EnterpriseScreen"));
const PrivacyScreen = lazy(() => import("@/screens/public/PrivacyScreen"));
const TermsScreen = lazy(() => import("@/screens/public/TermsScreen"));
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
const BillingCheckoutScreen = lazy(() => import("@/screens/billing/BillingCheckoutScreen"));
const PaymentCallbackScreen = lazy(() => import("@/screens/billing/PaymentCallbackScreen"));
const ReferralDashboardScreen = lazy(() => import("@/screens/billing/ReferralDashboardScreen"));
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
const AriaPlanningScreen = lazy(() => import("@/screens/ai/AriaPlanningScreen"));
const OperationsCenterScreen = lazy(() => import("@/screens/ai/OperationsCenterScreen"));
const AriaAssistantScreen = lazy(() => import("@/screens/ai/AriaAssistantScreen"));
const AriaSettingsScreen = lazy(() => import("@/screens/ai/AriaSettingsScreen"));
const MissionControlScreen = lazy(() => import("@/screens/ai/MissionControlScreen"));
const AvicultureCollectionScreen = lazy(() => import("@/screens/aviculture/AvicultureCollectionScreen"));
const BirdProfileScreen = lazy(() => import("@/screens/aviculture/BirdProfileScreen"));
const AviariesScreen = lazy(() => import("@/screens/aviculture/AviariesScreen"));
const AviaryDetailScreen = lazy(() => import("@/screens/aviculture/AviaryDetailScreen"));
const BreedingScreen = lazy(() => import("@/screens/aviculture/BreedingScreen"));
const IncubationScreen = lazy(() => import("@/screens/aviculture/IncubationScreen"));
const AvicultureHealthScreen = lazy(() => import("@/screens/aviculture/HealthScreen"));
const AvicultureDashboardScreen = lazy(() => import("@/screens/aviculture/AvicultureDashboardScreen"));
const AvicultureAutomationScreen = lazy(() => import("@/screens/aviculture/AutomationScreen"));
const AvicultureAriaScreen = lazy(() => import("@/screens/aviculture/AvicultureAriaScreen"));

// ── Module 16 — Black Soldier Fly ──────────────────────────────────────────────
const BsfProductionBoardScreen = lazy(() => import("@/screens/bsf/ProductionBoardScreen"));
const BsfBatchWorkspaceScreen = lazy(() => import("@/screens/bsf/BatchWorkspaceScreen"));
const BsfDashboardScreen = lazy(() => import("@/screens/bsf/BsfDashboardScreen"));
const BsfFeedstockScreen = lazy(() => import("@/screens/bsf/BsfFeedstockScreen"));
const BsfHarvestScreen = lazy(() => import("@/screens/bsf/BsfHarvestScreen"));
const BsfEnvironmentScreen = lazy(() => import("@/screens/bsf/BsfEnvironmentScreen"));
const BsfGrowthScreen = lazy(() => import("@/screens/bsf/BsfGrowthScreen"));
const BsfReportsScreen = lazy(() => import("@/screens/bsf/BsfReportsScreen"));
const BsfAriaScreen = lazy(() => import("@/screens/bsf/BsfAriaScreen"));
const BsfMissionScreen = lazy(() => import("@/screens/bsf/BsfMissionScreen"));
const RabbitDirectoryScreen = lazy(() => import("@/screens/rabbit/RabbitDirectoryScreen"));
const RabbitProfileScreen = lazy(() => import("@/screens/rabbit/RabbitProfileScreen"));
const RabbitDashboardScreen = lazy(() => import("@/screens/rabbit/RabbitDashboardScreen"));
const RabbitReportsScreen = lazy(() => import("@/screens/rabbit/RabbitReportsScreen"));
const RabbitAriaScreen = lazy(() => import("@/screens/rabbit/RabbitAriaScreen"));
const RabbitMissionScreen = lazy(() => import("@/screens/rabbit/RabbitMissionScreen"));
const RabbitBreedingScreen = lazy(() => import("@/screens/rabbit/RabbitBreedingScreen"));
const RabbitHealthScreen = lazy(() => import("@/screens/rabbit/RabbitHealthScreen"));
const RabbitHousingScreen = lazy(() => import("@/screens/rabbit/RabbitHousingScreen"));
const RabbitGrowthScreen = lazy(() => import("@/screens/rabbit/RabbitGrowthScreen"));
const RabbitGrowthPlannerScreen = lazy(() => import("@/screens/rabbit/RabbitGrowthPlannerScreen"));
// Small Ruminant (Modules 18/19) — one shared screen set for goat & sheep.
const SrDirectoryScreen = lazy(() => import("@/screens/smallRuminant/SrDirectoryScreen"));
const SrProfileScreen = lazy(() => import("@/screens/smallRuminant/SrProfileScreen"));
const SrDashboardScreen = lazy(() => import("@/screens/smallRuminant/SrDashboardScreen"));
const SrProductionScreen = lazy(() => import("@/screens/smallRuminant/SrProductionScreen"));
const SrReportsScreen = lazy(() => import("@/screens/smallRuminant/SrReportsScreen"));
const SrAriaScreen = lazy(() => import("@/screens/smallRuminant/SrAriaScreen"));
const SrMissionScreen = lazy(() => import("@/screens/smallRuminant/SrMissionScreen"));
// Swine (Module 20) — single-species pig workspace.
const SwineDirectoryScreen = lazy(() => import("@/screens/swine/SwineDirectoryScreen"));
const SwineProfileScreen = lazy(() => import("@/screens/swine/SwineProfileScreen"));
const SwineDashboardScreen = lazy(() => import("@/screens/swine/SwineDashboardScreen"));
const SwineBreedingScreen = lazy(() => import("@/screens/swine/SwineBreedingScreen"));
const SwineHealthScreen = lazy(() => import("@/screens/swine/SwineHealthScreen"));
const SwineGrowthScreen = lazy(() => import("@/screens/swine/SwineGrowthScreen"));
const SwineFinanceScreen = lazy(() => import("@/screens/swine/SwineFinanceScreen"));
const SwineReportsScreen = lazy(() => import("@/screens/swine/SwineReportsScreen"));
const SwineAriaScreen = lazy(() => import("@/screens/swine/SwineAriaScreen"));
const SwineMissionScreen = lazy(() => import("@/screens/swine/SwineMissionScreen"));
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
      { path: "/farming", element: <EnterprisesScreen /> },
      { path: "/farming/:slug", element: <EnterpriseScreen /> },
      // /aria-ai, not /aria — /ai is the in-app assistant module.
      { path: "/aria-ai", element: <AriaScreen /> },
      { path: "/pricing", element: <PricingScreen /> },
      { path: "/learning", element: <LearningScreen /> },
      { path: "/about", element: <AboutScreen /> },
      { path: "/contact", element: <ContactScreen /> },
      { path: "/help", element: <HelpScreen /> },
      { path: "/install", element: <InstallScreen /> },
      { path: "/privacy", element: <PrivacyScreen /> },
      { path: "/terms", element: <TermsScreen /> },
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
          { path: "/billing", element: <BillingCheckoutScreen /> },
          { path: "/billing/callback", element: <PaymentCallbackScreen /> },
          { path: "/billing/referral", element: <ReferralDashboardScreen /> },
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
          { path: "/ai/planning", element: <AriaPlanningScreen /> },
          { path: "/ai/operations", element: <OperationsCenterScreen /> },
          { path: "/ai/assistant", element: <AriaAssistantScreen /> },
          { path: "/ai/settings", element: <AriaSettingsScreen /> },
          { path: "/ai/mission", element: <MissionControlScreen /> },
          { path: "/ai/insights", element: <AIScreen /> },
          { path: "/aviculture", element: <AvicultureCollectionScreen /> },
          { path: "/aviculture/aviaries", element: <AviariesScreen /> },
          { path: "/aviculture/aviaries/:aviaryId", element: <AviaryDetailScreen /> },
          { path: "/aviculture/breeding", element: <BreedingScreen /> },
          { path: "/aviculture/incubation", element: <IncubationScreen /> },
          { path: "/aviculture/health", element: <AvicultureHealthScreen /> },
          { path: "/aviculture/dashboard", element: <AvicultureDashboardScreen /> },
          { path: "/aviculture/automation", element: <AvicultureAutomationScreen /> },
          { path: "/aviculture/aria", element: <AvicultureAriaScreen /> },
          { path: "/aviculture/:birdId", element: <BirdProfileScreen /> },
          // ── Module 16 — Black Soldier Fly ──────────────────────────────────
          { path: "/bsf", element: <BsfProductionBoardScreen /> },
          { path: "/bsf/batches/:batchId", element: <BsfBatchWorkspaceScreen /> },
          { path: "/bsf/dashboard", element: <BsfDashboardScreen /> },
          { path: "/bsf/feedstock", element: <BsfFeedstockScreen /> },
          { path: "/bsf/harvest", element: <BsfHarvestScreen /> },
          { path: "/bsf/environment", element: <BsfEnvironmentScreen /> },
          { path: "/bsf/growth", element: <BsfGrowthScreen /> },
          { path: "/bsf/reports", element: <BsfReportsScreen /> },
          { path: "/bsf/aria", element: <BsfAriaScreen /> },
          { path: "/bsf/mission", element: <BsfMissionScreen /> },
          { path: "/rabbit", element: <RabbitDirectoryScreen /> },
          { path: "/rabbit/dashboard", element: <RabbitDashboardScreen /> },
          { path: "/rabbit/breeding", element: <RabbitBreedingScreen /> },
          { path: "/rabbit/health", element: <RabbitHealthScreen /> },
          { path: "/rabbit/housing", element: <RabbitHousingScreen /> },
          { path: "/rabbit/growth", element: <RabbitGrowthScreen /> },
          { path: "/rabbit/planner", element: <RabbitGrowthPlannerScreen /> },
          { path: "/rabbit/reports", element: <RabbitReportsScreen /> },
          { path: "/rabbit/aria", element: <RabbitAriaScreen /> },
          { path: "/rabbit/mission", element: <RabbitMissionScreen /> },
          { path: "/rabbit/:rabbitId", element: <RabbitProfileScreen /> },
          // ── Small Ruminant — Goat workspace (Module 18) ──────────────────
          { path: "/goat", element: <SrDirectoryScreen species="goat" /> },
          { path: "/goat/dashboard", element: <SrDashboardScreen species="goat" /> },
          { path: "/goat/dairy", element: <SrProductionScreen species="goat" /> },
          { path: "/goat/reports", element: <SrReportsScreen species="goat" /> },
          { path: "/goat/aria", element: <SrAriaScreen species="goat" /> },
          { path: "/goat/mission", element: <SrMissionScreen species="goat" /> },
          { path: "/goat/:animalId", element: <SrProfileScreen species="goat" /> },
          // ── Small Ruminant — Sheep workspace (Module 19) ─────────────────
          { path: "/sheep", element: <SrDirectoryScreen species="sheep" /> },
          { path: "/sheep/dashboard", element: <SrDashboardScreen species="sheep" /> },
          { path: "/sheep/wool", element: <SrProductionScreen species="sheep" /> },
          { path: "/sheep/reports", element: <SrReportsScreen species="sheep" /> },
          { path: "/sheep/aria", element: <SrAriaScreen species="sheep" /> },
          { path: "/sheep/mission", element: <SrMissionScreen species="sheep" /> },
          { path: "/sheep/:animalId", element: <SrProfileScreen species="sheep" /> },
          // ── Swine — Pig workspace (Module 20) ────────────────────────────
          { path: "/swine", element: <SwineDirectoryScreen /> },
          { path: "/swine/dashboard", element: <SwineDashboardScreen /> },
          { path: "/swine/breeding", element: <SwineBreedingScreen /> },
          { path: "/swine/health", element: <SwineHealthScreen /> },
          { path: "/swine/growth", element: <SwineGrowthScreen /> },
          { path: "/swine/finance", element: <SwineFinanceScreen /> },
          { path: "/swine/reports", element: <SwineReportsScreen /> },
          { path: "/swine/aria", element: <SwineAriaScreen /> },
          { path: "/swine/mission", element: <SwineMissionScreen /> },
          { path: "/swine/:pigId", element: <SwineProfileScreen /> },
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
