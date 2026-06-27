/**
 * S-01 — Profile Settings Screen
 * /settings/profile
 * Update display name. Phone number is read-only (auth identifier).
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { authAPI } from "@/api/auth";
import { queryKeys } from "@/lib/queryClient";
import { useAuthStore } from "@/stores/authStore";
import { Spinner } from "@/components/ui/Spinner";

export default function ProfileSettingsScreen() {
  const { t } = useTranslation();
  const { user, setUser } = useAuthStore();
  const qc = useQueryClient();
  const [name, setName] = useState(user?.full_name ?? "");
  const [saved, setSaved] = useState(false);

  const updateMut = useMutation({
    mutationFn: () => authAPI.updateMe({ full_name: name.trim() || null }),
    onSuccess: (updated) => {
      setUser(updated);
      qc.invalidateQueries({ queryKey: queryKeys.settingsProfile() });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const isDirty = name !== (user?.full_name ?? "");

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100 px-4 py-4">
        <h1 className="text-lg font-bold text-gray-900">{t("settings.profile.title")}</h1>
        <p className="text-xs text-gray-400 mt-0.5">{t("settings.profile.subtitle")}</p>
      </div>

      <div className="p-4 space-y-4">
        {/* Phone — read-only */}
        <div className="bg-white rounded-2xl border border-gray-100 p-4">
          <label className="block text-xs font-medium text-gray-500 mb-1">
            {t("settings.profile.phone")}
          </label>
          <p className="text-sm font-semibold text-gray-900">{user?.phone}</p>
          <p className="text-xs text-gray-400 mt-1">{t("settings.profile.phone_note")}</p>
        </div>

        {/* Display name */}
        <div className="bg-white rounded-2xl border border-gray-100 p-4">
          <label className="block text-xs font-medium text-gray-500 mb-1.5">
            {t("settings.profile.name")}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("settings.profile.name_placeholder")}
            maxLength={80}
            className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Save button */}
        <button
          onClick={() => updateMut.mutate()}
          disabled={!isDirty || updateMut.isPending}
          className="w-full py-3 bg-brand-600 text-white rounded-2xl text-sm font-semibold disabled:opacity-40"
        >
          {updateMut.isPending ? (
            <span className="flex items-center justify-center gap-2">
              <Spinner size="sm" /> {t("common.saving")}
            </span>
          ) : saved ? (
            t("common.saved")
          ) : (
            t("settings.profile.save")
          )}
        </button>
      </div>
    </div>
  );
}
