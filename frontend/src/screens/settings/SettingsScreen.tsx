/**
 * S-00 — Settings Hub Screen
 * /settings
 * Entry point listing all settings categories.
 */

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { authAPI } from "@/api/auth";
import { useNavigate } from "react-router-dom";

interface SettingsLinkProps {
  to: string;
  icon: string;
  label: string;
  sub?: string;
}

function SettingsLink({ to, icon, label, sub }: SettingsLinkProps) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between px-4 py-4 border-b border-gray-50 last:border-0 active:bg-gray-50"
    >
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gray-100 flex items-center justify-center text-lg shrink-0">
          {icon}
        </div>
        <div>
          <p className="text-sm font-medium text-gray-900">{label}</p>
          {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
        </div>
      </div>
      <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </Link>
  );
}

export default function SettingsScreen() {
  const { t } = useTranslation();
  const { user, clearAuth } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await authAPI.logout();
    } finally {
      clearAuth();
      navigate("/login", { replace: true });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* User card */}
      <div className="bg-white border-b border-gray-100 px-4 py-5">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-brand-100 flex items-center justify-center">
            <span className="text-xl font-bold text-brand-600">
              {(user?.full_name ?? user?.phone ?? "?")[0].toUpperCase()}
            </span>
          </div>
          <div>
            <p className="text-sm font-bold text-gray-900">
              {user?.full_name ?? t("settings.hub.no_name")}
            </p>
            <p className="text-xs text-gray-400">{user?.phone}</p>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
          <SettingsLink
            to="/settings/profile"
            icon="👤"
            label={t("settings.hub.profile")}
            sub={t("settings.hub.profile_sub")}
          />
          <SettingsLink
            to="/settings/notifications"
            icon="🔔"
            label={t("settings.hub.notifications")}
            sub={t("settings.hub.notifications_sub")}
          />
          <SettingsLink
            to="/settings/language"
            icon="🌐"
            label={t("settings.hub.language")}
            sub={user?.language === "sw" ? "Kiswahili" : "English"}
          />
          <SettingsLink
            to="/settings/about"
            icon="ℹ️"
            label={t("settings.hub.about")}
            sub="AGRIOS v1.0.0"
          />
        </div>

        <button
          onClick={handleLogout}
          className="w-full py-3.5 bg-white border border-red-100 text-red-500 rounded-2xl text-sm font-semibold"
        >
          {t("settings.hub.logout")}
        </button>
      </div>
    </div>
  );
}
