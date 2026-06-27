/**
 * AGRIOS — Admin Layout
 * Desktop-first layout for the Admin Dashboard (admin.agrios.app / /admin/*).
 * Left sidebar navigation + main content area.
 * Access: super_admin only.
 */

import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/authStore";

interface NavItem {
  path: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: "/admin",            label: "admin.nav.overview",      icon: "📊" },
  { path: "/admin/users",      label: "admin.nav.users",         icon: "👥" },
  { path: "/admin/farms",      label: "admin.nav.farms",         icon: "🌾" },
  { path: "/admin/plans",      label: "admin.nav.plans",         icon: "📋" },
  { path: "/admin/alerts",     label: "admin.nav.alerts",        icon: "🚨" },
  { path: "/admin/market",     label: "admin.nav.market",        icon: "📈" },
  { path: "/admin/ai-usage",   label: "admin.nav.ai_usage",      icon: "🤖" },
  { path: "/admin/settings",   label: "admin.nav.settings",      icon: "⚙️" },
];

export default function AdminLayout() {
  const { t } = useTranslation();
  const { clearAuth } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    clearAuth();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className="w-56 bg-gray-900 text-white flex flex-col shrink-0 sticky top-0 h-screen">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-800">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest">AGRIOS</p>
          <p className="text-sm font-bold text-white mt-0.5">{t("admin.title")}</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/admin"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {t(item.label)}
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <div className="px-5 py-4 border-t border-gray-800">
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            {t("admin.logout")}
          </button>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
