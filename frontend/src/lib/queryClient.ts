/**
 * Greena — TanStack Query Client Configuration
 * Handles: caching, background refetch, stale-while-revalidate, offline awareness.
 */

import { QueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Show stale data immediately, refetch in background
      staleTime: 1000 * 60,           // 1 minute
      gcTime: 1000 * 60 * 10,         // Keep in cache for 10 minutes
      retry: (failureCount, error) => {
        // Don't retry auth errors
        if (error instanceof AxiosError) {
          const status = error.response?.status;
          if (status === 401 || status === 403 || status === 404) return false;
        }
        return failureCount < 2;
      },
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,       // Refetch when connection is restored
    },
    mutations: {
      retry: false,                   // Never retry mutations automatically
    },
  },
});

// ── Cache Invalidation Keys ───────────────────────────────────────────────────
// Centralised query keys prevent typos and make invalidation explicit.

export const queryKeys = {
  // Auth
  me: ["auth", "me"] as const,

  // Farms (Sprint 2+)
  farms: () => ["farms"] as const,
  farm: (id: string) => ["farms", id] as const,
  farmSummary: (id: string) => ["farms", id, "summary"] as const,
  farmMembers: (id: string) => ["farms", id, "members"] as const,

  // Flocks (Sprint 3+)
  flocks: (farmId: string) => ["farms", farmId, "flocks"] as const,
  flock: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId] as const,
  flockPerformance: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId, "performance"] as const,

  // Farm Structure (Sprint 2 — dedicated keys)
  farmUnits: (farmId: string) => ["farms", farmId, "units"] as const,
  farmHouses: (farmId: string) => ["farms", farmId, "houses"] as const,

  // Daily Logs (Sprint 3)
  flockLogs: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId, "logs"] as const,
  flockLog: (farmId: string, flockId: string, logDate: string) =>
    ["farms", farmId, "flocks", flockId, "logs", logDate] as const,

  // Production Records (Sprint 3)
  flockProduction: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId, "production"] as const,

  // Weigh-Ins (Sprint 3)
  flockWeighins: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId, "weighins"] as const,

  // Feed Purchases (Sprint 3)
  feedPurchases: (farmId: string) => ["farms", farmId, "feed-purchases"] as const,

  // Feed Management (Phase 3, Module 4)
  feedDashboard: (farmId: string) => ["farms", farmId, "feed", "dashboard"] as const,
  feedInventory: (farmId: string) => ["farms", farmId, "feed", "inventory"] as const,
  feedSuppliers: (farmId: string) => ["farms", farmId, "feed", "suppliers"] as const,
  feedTransactions: (farmId: string) => ["farms", farmId, "feed", "transactions"] as const,
  feedAnalytics: (farmId: string) => ["farms", farmId, "feed", "analytics"] as const,
  feedForecast: (farmId: string) => ["farms", farmId, "feed", "forecast"] as const,
  flockFeedConsumption: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId, "feed-consumption"] as const,

  // Inventory & Assets (Module 6)
  invDashboard: (farmId: string) => ["farms", farmId, "inv", "dashboard"] as const,
  invItems: (farmId: string) => ["farms", farmId, "inv", "items"] as const,
  invMovements: (farmId: string) => ["farms", farmId, "inv", "movements"] as const,
  invAssets: (farmId: string) => ["farms", farmId, "inv", "assets"] as const,
  invMaintenance: (farmId: string) => ["farms", farmId, "inv", "maintenance"] as const,
  invSuppliers: (farmId: string) => ["farms", farmId, "inv", "suppliers"] as const,
  invAlerts: (farmId: string) => ["farms", farmId, "inv", "alerts"] as const,
  invAnalytics: (farmId: string) => ["farms", farmId, "inv", "analytics"] as const,

  // Health (Sprint 4)
  flockVaccinations: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId, "vaccinations"] as const,
  flockVaccination: (farmId: string, flockId: string, recordId: string) =>
    ["farms", farmId, "flocks", flockId, "vaccinations", recordId] as const,
  healthSchedule: (farmId: string) => ["farms", farmId, "health", "schedule"] as const,
  farmAlerts: (farmId: string) => ["farms", farmId, "health", "alerts"] as const,
  activeAlertBanner: (farmId: string) =>
    ["farms", farmId, "health", "alerts", "active"] as const,

  // Finance (Sprint 5)
  expenseCategories: (farmId: string) =>
    ["farms", farmId, "finance", "categories"] as const,
  expenses: (farmId: string) => ["farms", farmId, "expenses"] as const,
  expense: (farmId: string, expenseId: string) =>
    ["farms", farmId, "expenses", expenseId] as const,
  revenue: (farmId: string) => ["farms", farmId, "revenue"] as const,
  revenueRecord: (farmId: string, recordId: string) =>
    ["farms", farmId, "revenue", recordId] as const,
  flockSnapshot: (farmId: string, flockId: string) =>
    ["farms", farmId, "flocks", flockId, "finance"] as const,
  financeDashboard: (farmId: string) =>
    ["farms", farmId, "finance", "dashboard"] as const,
  categoryBreakdown: (farmId: string) =>
    ["farms", farmId, "finance", "categories", "breakdown"] as const,
  // Finance analytics (Module 5)
  financeOverview: (farmId: string) => ["farms", farmId, "finance", "overview"] as const,
  financeAnalytics: (farmId: string) => ["farms", farmId, "finance", "analytics"] as const,
  financeTransactions: (farmId: string) => ["farms", farmId, "finance", "transactions"] as const,
  financeCashflow: (farmId: string) => ["farms", farmId, "finance", "cashflow"] as const,
  financeReport: (farmId: string) => ["farms", farmId, "finance", "report"] as const,

  // AI / ARIA (Sprint 6)
  aiConversations: (farmId: string) =>
    ["farms", farmId, "ai", "conversations"] as const,
  aiConversation: (farmId: string, conversationId: string) =>
    ["farms", farmId, "ai", "conversations", conversationId] as const,
  aiInsights: (farmId: string) =>
    ["farms", farmId, "ai", "insights"] as const,
  aiRecommendations: (farmId: string) =>
    ["farms", farmId, "ai", "recommendations"] as const,
  aiQuota: (farmId: string) =>
    ["farms", farmId, "ai", "quota"] as const,

  // Notifications (Sprint 7)
  notifications: (farmId: string) =>
    ["farms", farmId, "notifications"] as const,
  unreadCount: (farmId: string) =>
    ["farms", farmId, "notifications", "unread-count"] as const,

  // Market Prices (Sprint 7) — platform-wide, not farm-scoped
  marketPrices: () => ["market", "prices"] as const,
  marketPriceHistory: (commodity: string) =>
    ["market", "prices", "history", commodity] as const,
  marketCommodities: () => ["market", "commodities"] as const,
  // Admin (Sprint 8) — platform-wide, not farm-scoped
  adminStats: () => ["admin", "stats"] as const,
  adminUsers: () => ["admin", "users"] as const,
  adminUser: (userId: string) => ["admin", "users", userId] as const,
  adminFarms: () => ["admin", "farms"] as const,
  adminPlans: () => ["admin", "plans"] as const,
  adminAIUsage: (period?: number) => ["admin", "ai", "usage", period] as const,

  // Sprint 9 — Settings
  settingsProfile: () => ["auth", "me"] as const,
};
