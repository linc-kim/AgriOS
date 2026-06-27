/**
 * S-02 — Notification Settings Screen
 * /settings/notifications
 * Toggle SMS notification preferences. Stored in user.metadata_.
 */

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { authAPI } from "@/api/auth";
import { queryKeys } from "@/lib/queryClient";
import { useAuthStore } from "@/stores/authStore";

interface ToggleRowProps {
  label: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}

function ToggleRow({ label, description, value, onChange, disabled }: ToggleRowProps) {
  return (
    <div className="flex items-start justify-between py-4 border-b border-gray-50 last:border-0">
      <div className="flex-1 pr-4">
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-400 mt-0.5">{description}</p>
      </div>
      <button
        role="switch"
        aria-checked={value}
        onClick={() => !disabled && onChange(!value)}
        disabled={disabled}
        className={`relative w-11 h-6 rounded-full transition-colors shrink-0 mt-0.5 ${
          value ? "bg-brand-600" : "bg-gray-200"
        } ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
      >
        <span
          className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
            value ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

export default function NotificationSettingsScreen() {
  const { t } = useTranslation();
  const { user, setUser } = useAuthStore();
  const qc = useQueryClient();

  const [smsEnabled, setSmsEnabled] = useState(
    user?.sms_notifications_enabled ?? true
  );
  const [saved, setSaved] = useState(false);

  // Keep local state in sync if user object changes
  useEffect(() => {
    setSmsEnabled(user?.sms_notifications_enabled ?? true);
  }, [user?.sms_notifications_enabled]);

  const updateMut = useMutation({
    mutationFn: (enabled: boolean) =>
      authAPI.updateMe({ sms_notifications_enabled: enabled }),
    onSuccess: (updated) => {
      setUser(updated);
      qc.invalidateQueries({ queryKey: queryKeys.settingsProfile() });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const handleToggle = (enabled: boolean) => {
    setSmsEnabled(enabled);
    updateMut.mutate(enabled);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100 px-4 py-4">
        <h1 className="text-lg font-bold text-gray-900">{t("settings.notifications.title")}</h1>
        <p className="text-xs text-gray-400 mt-0.5">{t("settings.notifications.subtitle")}</p>
      </div>

      <div className="p-4">
        <div className="bg-white rounded-2xl border border-gray-100 px-4">
          <ToggleRow
            label={t("settings.notifications.sms_toggle")}
            description={t("settings.notifications.sms_desc")}
            value={smsEnabled}
            onChange={handleToggle}
            disabled={updateMut.isPending}
          />
          <ToggleRow
            label={t("settings.notifications.vaccination")}
            description={t("settings.notifications.vaccination_desc")}
            value={smsEnabled}
            onChange={() => {}}
            disabled
          />
          <ToggleRow
            label={t("settings.notifications.daily_log")}
            description={t("settings.notifications.daily_log_desc")}
            value={smsEnabled}
            onChange={() => {}}
            disabled
          />
          <ToggleRow
            label={t("settings.notifications.disease_alert")}
            description={t("settings.notifications.disease_alert_desc")}
            value={smsEnabled}
            onChange={() => {}}
            disabled
          />
        </div>

        <p className="text-xs text-gray-400 mt-4 px-1">
          {t("settings.notifications.master_note")}
        </p>

        {saved && (
          <div className="mt-4 py-2.5 bg-green-50 text-green-700 text-xs font-medium text-center rounded-xl">
            {t("common.saved")}
          </div>
        )}
      </div>
    </div>
  );
}
