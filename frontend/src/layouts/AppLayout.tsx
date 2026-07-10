/**
 * Greena — Main App Layout (Farmer PWA)
 * Structure:
 *   - Fixed top bar (56px)
 *   - Scrollable content area
 *   - Fixed bottom navigation (64px) with 5 tabs
 *
 * Engineering Constitution: 5-tab bottom navigation
 * Tab order: Home / Flock / Health / Finance / ARIA
 * Minimum touch target: 48x48px
 */

import { Link, Outlet, useLocation } from "react-router-dom";
import { PWAUpdatePrompt } from "@/components/pwa/PWAUpdatePrompt";
import { useUIStore, type BottomTab } from "@/stores/uiStore";
import { useAuthStore } from "@/stores/authStore";

const NAV_TABS: Array<{
  key: BottomTab;
  label: string;
  path: string;
  icon: string;
}> = [
  { key: "home", label: "Home", path: "/", icon: "🏠" },
  { key: "flock", label: "Flock", path: "/flock", icon: "🐓" },
  { key: "health", label: "Health", path: "/health", icon: "💊" },
  { key: "finance", label: "Finance", path: "/finance", icon: "💰" },
  { key: "aria", label: "ARIA", path: "/aria", icon: "🤖" },
];

export default function AppLayout() {
  const location = useLocation();
  const { isOnline, lastSyncedAt } = useUIStore();
  const { user } = useAuthStore();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* ── Top Bar ─────────────────────────────────────────── */}
      <header
        className="fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-100"
        style={{ height: "56px" }}
      >
        <div className="flex items-center justify-between h-full px-4">
          <div>
            <p className="text-sm font-semibold text-gray-900 leading-tight">
              {user?.full_name ?? "My Farm"}
            </p>
            {!isOnline && (
              <p className="text-xs text-amber-600">
                Offline
                {lastSyncedAt
                  ? ` · Last synced ${formatRelativeTime(lastSyncedAt)}`
                  : ""}
              </p>
            )}
          </div>
          <button
            className="relative min-h-touch min-w-touch flex items-center justify-center"
            aria-label="Notifications"
          >
            <span className="text-xl">🔔</span>
          </button>
        </div>
      </header>

      {/* ── Scroll Content ───────────────────────────────────── */}
      <main
        className="flex-1 overflow-y-auto"
        style={{ paddingTop: "56px", paddingBottom: "64px" }}
      >
        <Outlet />
      </main>

      {/* ── PWA Update Prompt ───────────────────────────────── */}
      <PWAUpdatePrompt />

      {/* ── Bottom Navigation ────────────────────────────────── */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-100"
        style={{ height: "64px" }}
      >
        <div className="grid grid-cols-5 h-full">
          {NAV_TABS.map((tab) => {
            const isActive =
              tab.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(tab.path);

            return (
              <Link
                key={tab.key}
                to={tab.path}
                className={`flex flex-col items-center justify-center gap-0.5 min-h-touch transition-colors ${
                  isActive
                    ? "text-brand-600"
                    : "text-gray-400 hover:text-gray-600"
                }`}
                aria-label={tab.label}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="text-xl leading-none">{tab.icon}</span>
                <span
                  className={`text-[10px] font-medium leading-none ${
                    isActive ? "text-brand-600" : "text-gray-400"
                  }`}
                >
                  {tab.label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

function formatRelativeTime(date: Date): string {
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}
