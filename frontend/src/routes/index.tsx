/**
 * AGRIOS — Route Configuration
 * React Router v6 with lazy-loaded screen components.
 * Route groups:
 *   /auth/* — Public auth screens (Login, OTP, PIN)
 *   /onboarding/* — First-time setup (Name, Farm, First Flock)
 *   /* — Protected app screens (Home, Flock, Health, Finance, ARIA)
 *   /admin/* — Admin-only screens (separate layout)
 *
 * Lazy loading: each screen is a separate bundle.
 * Screens are loaded on-demand — initial bundle stays small.
 */

import { lazy, Suspense, useEffect } from "react";
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
} from "react-router-dom";

import AuthLayout from "@/layouts/AuthLayout";
import AppLayout from "@/layouts/AppLayout";
import AdminLayout from "@/layouts/AdminLayout";
import { useAuthStore } from "@/stores/authStore";
import { authAPI } from "@/api/auth";
import { isSuperAdmin } from "@/lib/roles";
import { Spinner } from "@/components/ui/Spinner";

// ── Lazy Screen Imports ───────────────────────────────────────────────────────

// Auth
const LoginScreen = lazy(() => import("@/screens/auth/LoginScreen"));
const OTPScreen = lazy(() => import("@/screens/auth/OTPScreen"));
const PINSetupScreen = lazy(() => import("@/screens/auth/PINSetupScreen"));
const PINLoginScreen = lazy(() => import("@/screens/auth/PINLoginScreen"));

// Onboarding
const OnboardingNameScreen = lazy(
  () => import("@/screens/onboarding/OnboardingNameScreen"),
);
const FarmSetupScreen = lazy(
  () => import("@/screens/onboarding/FarmSetupScreen"),
);

// Farm management (Sprint 2)
const FarmManagementScreen = lazy(
  () => import("@/screens/farms/FarmManagementScreen"),
);
const FarmEditScreen = lazy(
  () => import("@/screens/farms/FarmEditScreen"),
);
const FarmMembersScreen = lazy(
  () => import("@/screens/farms/FarmMembersScreen"),
);
const InviteMemberScreen = lazy(
  () => import("@/screens/farms/InviteMemberScreen"),
);
const FarmStructureScreen = lazy(
  () => import("@/screens/farms/FarmStructureScreen"),
);
const AddUnitScreen = lazy(
  () => import("@/screens/farms/AddUnitScreen"),
);
const AddHouseScreen = lazy(
  () => import("@/screens/farms/AddHouseScreen"),
);

// App (placeholders for Sprint 1+)
const DashboardScreen = lazy(() => import("@/screens/DashboardScreen"));
const ComingSoonScreen = lazy(() => import("@/screens/ComingSoonScreen"));

// ARIA screens (Sprint 6)
const ARIAChatScreen = lazy(() => import("@/screens/aria/ARIAChatScreen"));
const InsightsScreen = lazy(() => import("@/screens/aria/InsightsScreen"));
const RecommendationsScreen = lazy(
  () => import("@/screens/aria/RecommendationsScreen"),
);
const ARIASettingsScreen = lazy(
  () => import("@/screens/aria/ARIASettingsScreen"),
);

// Platform screens (Sprint 7)
const NotificationsScreen = lazy(
  () => import("@/screens/notifications/NotificationsScreen"),
);
const MarketPricesScreen = lazy(
  () => import("@/screens/market/MarketPricesScreen"),
);
const PriceHistoryScreen = lazy(
  () => import("@/screens/market/PriceHistoryScreen"),
);

// Admin screens (Sprint 8)
const AdminOverviewScreen = lazy(() => import("@/screens/admin/AdminOverviewScreen"));
const AdminUsersScreen = lazy(() => import("@/screens/admin/AdminUsersScreen"));
const AdminFarmsScreen = lazy(() => import("@/screens/admin/AdminFarmsScreen"));
const AdminPlansScreen = lazy(() => import("@/screens/admin/AdminPlansScreen"));
const AdminAlertsScreen = lazy(() => import("@/screens/admin/AdminAlertsScreen"));
const AdminMarketScreen = lazy(() => import("@/screens/admin/AdminMarketScreen"));
const AdminAIUsageScreen = lazy(() => import("@/screens/admin/AdminAIUsageScreen"));
const AdminSettingsScreen = lazy(() => import("@/screens/admin/AdminSettingsScreen"));

// Settings screens (Sprint 9)
const SettingsScreen = lazy(() => import("@/screens/settings/SettingsScreen"));
const ProfileSettingsScreen = lazy(() => import("@/screens/settings/ProfileSettingsScreen"));
const NotificationSettingsScreen = lazy(() => import("@/screens/settings/NotificationSettingsScreen"));
const LanguageSettingsScreen = lazy(() => import("@/screens/settings/LanguageSettingsScreen"));
const AboutScreen = lazy(() => import("@/screens/settings/AboutScreen"));

// Utility screens (Sprint 9)
const OfflineScreen = lazy(() => import("@/screens/utility/OfflineScreen"));
const NotFoundScreen = lazy(() => import("@/screens/utility/NotFoundScreen"));

// Finance screens (Sprint 5)
const FinanceDashboardScreen = lazy(
  () => import("@/screens/finance/FinanceDashboardScreen"),
);
const ExpenseListScreen = lazy(
  () => import("@/screens/finance/ExpenseListScreen"),
);
const LogExpenseScreen = lazy(
  () => import("@/screens/finance/LogExpenseScreen"),
);
const RevenueListScreen = lazy(
  () => import("@/screens/finance/RevenueListScreen"),
);
const LogRevenueScreen = lazy(
  () => import("@/screens/finance/LogRevenueScreen"),
);
const FlockPnLScreen = lazy(
  () => import("@/screens/finance/FlockPnLScreen"),
);
const FinancialSummaryScreen = lazy(
  () => import("@/screens/finance/FinancialSummaryScreen"),
);
const BreakEvenCalculatorScreen = lazy(
  () => import("@/screens/finance/BreakEvenCalculatorScreen"),
);

// Health screens (Sprint 4)
const HealthDashboardScreen = lazy(
  () => import("@/screens/health/HealthDashboardScreen"),
);
const VaccinationScheduleScreen = lazy(
  () => import("@/screens/health/VaccinationScheduleScreen"),
);
const LogVaccinationScreen = lazy(
  () => import("@/screens/health/LogVaccinationScreen"),
);
const VaccinationHistoryScreen = lazy(
  () => import("@/screens/health/VaccinationHistoryScreen"),
);
const DiseaseAlertsScreen = lazy(
  () => import("@/screens/health/DiseaseAlertsScreen"),
);

// Flock screens (Sprint 3)
const FlockListScreen = lazy(() => import("@/screens/flocks/FlockListScreen"));
const FlockDetailScreen = lazy(
  () => import("@/screens/flocks/FlockDetailScreen"),
);
const CreateFlockScreen = lazy(
  () => import("@/screens/flocks/CreateFlockScreen"),
);
const CloseFlockScreen = lazy(
  () => import("@/screens/flocks/CloseFlockScreen"),
);
const DailyLogScreen = lazy(() => import("@/screens/flocks/DailyLogScreen"));
const DailyLogHistoryScreen = lazy(
  () => import("@/screens/flocks/DailyLogHistoryScreen"),
);
const WeighInScreen = lazy(() => import("@/screens/flocks/WeighInScreen"));
const FeedPurchaseScreen = lazy(
  () => import("@/screens/flocks/FeedPurchaseScreen"),
);

// ── Auth Guard ────────────────────────────────────────────────────────────────

function RequireAuth() {
  const { isAuthenticated, isLoading, setAuth, clearAuth } =
    useAuthStore();

  useEffect(() => {
    // On app load, attempt to restore session using the refresh token cookie
    const restoreSession = async () => {
      try {
        const { access_token } = await authAPI.refresh();
        const user = await authAPI.getMe();
        setAuth(access_token, user);
      } catch {
        // No valid refresh token — user must log in
        clearAuth();
      }
    };

    if (!isAuthenticated && isLoading) {
      restoreSession();
    }
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

// ── Admin Guard ───────────────────────────────────────────────────────────────

function RequireAdmin() {
  const { isAuthenticated, isLoading, user } = useAuthStore();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated || !isSuperAdmin(user)) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

// ── Router Configuration ──────────────────────────────────────────────────────

const router = createBrowserRouter([
  // ── Auth Routes (public) ──────────────────────────────────────────────────
  {
    element: <AuthLayout />,
    children: [
      { path: "/login", element: <LoginScreen /> },
      { path: "/verify-otp", element: <OTPScreen /> },
      { path: "/set-pin", element: <PINSetupScreen /> },
      { path: "/pin-login", element: <PINLoginScreen /> },
    ],
  },

  // ── Onboarding Routes (protected — user exists but hasn't finished setup) ──
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          { path: "/onboarding/name", element: <OnboardingNameScreen /> },
          { path: "/onboarding/farm", element: <FarmSetupScreen /> },
          // Sprint 3: /onboarding/flock
          // Sprint 3: /onboarding/complete
        ],
      },
    ],
  },

  // ── Protected App Routes ──────────────────────────────────────────────────
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <DashboardScreen /> },
          // ── Flock Tab (Sprint 3) ──────────────────────────────────────────
          { path: "/flock", element: <Navigate to="/farms" replace /> },
          { path: "/farms/:farmId/flocks", element: <FlockListScreen /> },
          { path: "/farms/:farmId/flocks/new", element: <CreateFlockScreen /> },
          { path: "/farms/:farmId/flocks/:flockId", element: <FlockDetailScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/close", element: <CloseFlockScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/log", element: <DailyLogScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/logs", element: <DailyLogHistoryScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/weighin", element: <WeighInScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/production", element: <ComingSoonScreen /> },
          { path: "/farms/:farmId/feed-purchases/new", element: <FeedPurchaseScreen /> },
          // ── Health Tab (Sprint 4) ─────────────────────────────────────────────
          { path: "/health", element: <Navigate to="/farms" replace /> },
          { path: "/farms/:farmId/health", element: <HealthDashboardScreen /> },
          { path: "/farms/:farmId/health/schedule", element: <VaccinationScheduleScreen /> },
          { path: "/farms/:farmId/health/alerts", element: <DiseaseAlertsScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/vaccinations", element: <VaccinationHistoryScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/vaccinations/new", element: <LogVaccinationScreen /> },
          // ── Finance Tab (Sprint 5) ────────────────────────────────────────────
          { path: "/finance", element: <Navigate to="/farms" replace /> },
          { path: "/farms/:farmId/finance", element: <FinanceDashboardScreen /> },
          { path: "/farms/:farmId/finance/summary", element: <FinancialSummaryScreen /> },
          { path: "/farms/:farmId/finance/calculators", element: <BreakEvenCalculatorScreen /> },
          { path: "/farms/:farmId/expenses", element: <ExpenseListScreen /> },
          { path: "/farms/:farmId/expenses/new", element: <LogExpenseScreen /> },
          { path: "/farms/:farmId/revenue", element: <RevenueListScreen /> },
          { path: "/farms/:farmId/revenue/new", element: <LogRevenueScreen /> },
          { path: "/farms/:farmId/flocks/:flockId/finance", element: <FlockPnLScreen /> },
                    // ── ARIA Tab (Sprint 6) ────────────────────────────────────────────────
          { path: "/aria", element: <Navigate to="/farms" replace /> },
          { path: "/farms/:farmId/aria", element: <ARIAChatScreen /> },
          { path: "/farms/:farmId/aria/insights", element: <InsightsScreen /> },
          { path: "/farms/:farmId/aria/recommendations", element: <RecommendationsScreen /> },
          { path: "/farms/:farmId/aria/settings", element: <ARIASettingsScreen /> },
          // ── Notifications (Sprint 7) ──────────────────────────────────────────
          { path: "/notifications", element: <Navigate to="/farms" replace /> },
          { path: "/farms/:farmId/notifications", element: <NotificationsScreen /> },
          // ── Market Prices (Sprint 7) ───────────────────────────────────────────
          { path: "/market/prices", element: <MarketPricesScreen /> },
          { path: "/market/prices/history", element: <PriceHistoryScreen /> },
          // ── Settings (Sprint 9) ───────────────────────────────────────────
          { path: "/settings", element: <SettingsScreen /> },
          { path: "/settings/profile", element: <ProfileSettingsScreen /> },
          { path: "/settings/notifications", element: <NotificationSettingsScreen /> },
          { path: "/settings/language", element: <LanguageSettingsScreen /> },
          { path: "/settings/about", element: <AboutScreen /> },
          // ── Offline / Error (Sprint 9) ────────────────────────────────────
          { path: "/offline", element: <OfflineScreen /> },

          // ── Farm Management Routes (Sprint 2) ─────────────────────────
          { path: "/farms/:farmId", element: <FarmManagementScreen /> },
          { path: "/farms/:farmId/edit", element: <FarmEditScreen /> },
          { path: "/farms/:farmId/members", element: <FarmMembersScreen /> },
          { path: "/farms/:farmId/members/invite", element: <InviteMemberScreen /> },
          { path: "/farms/:farmId/structure", element: <FarmStructureScreen /> },
          { path: "/farms/:farmId/units/new", element: <AddUnitScreen /> },
          { path: "/farms/:farmId/units/:unitId/edit", element: <AddUnitScreen /> },
          { path: "/farms/:farmId/units/:unitId/houses/new", element: <AddHouseScreen /> },
          { path: "/farms/:farmId/units/:unitId/houses/:houseId/edit", element: <AddHouseScreen /> },
        ],
      },
    ],
  },

  // ── Admin Routes (super_admin only) ─────────────────────────────────────────
  {
    element: <RequireAdmin />,
    children: [
      {
        element: <AdminLayout />,
        children: [
          { path: "/admin", element: <AdminOverviewScreen /> },
          { path: "/admin/users", element: <AdminUsersScreen /> },
          { path: "/admin/farms", element: <AdminFarmsScreen /> },
          { path: "/admin/plans", element: <AdminPlansScreen /> },
          { path: "/admin/alerts", element: <AdminAlertsScreen /> },
          { path: "/admin/market", element: <AdminMarketScreen /> },
          { path: "/admin/ai-usage", element: <AdminAIUsageScreen /> },
          { path: "/admin/settings", element: <AdminSettingsScreen /> },
        ],
      },
    ],
  },

  // ── Catch-all ─────────────────────────────────────────────────────────────
  { path: "*", element: <NotFoundScreen /> },
]);

// ── Screen Fallback ───────────────────────────────────────────────────────────

function ScreenFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Spinner size="md" />
    </div>
  );
}

// ── App Router Provider ───────────────────────────────────────────────────────

export function AppRouter() {
  return (
    <Suspense fallback={<ScreenFallback />}>
      <RouterProvider router={router} />
    </Suspense>
  );
}
