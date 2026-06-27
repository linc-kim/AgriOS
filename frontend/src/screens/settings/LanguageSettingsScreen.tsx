/**
 * S-03 — Language Settings Screen
 * /settings/language
 * Toggle between English and Kiswahili. Persisted via PATCH /auth/me.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { authAPI } from "@/api/auth";
import { queryKeys } from "@/lib/queryClient";
import { useAuthStore } from "@/stores/authStore";

const LANGUAGES: { code: "en" | "sw"; label: string; native: string; flag: string }[] = [
  { code: "en", label: "English", native: "English", flag: "🇬🇧" },
  { code: "sw", label: "Swahili", native: "Kiswahili", flag: "🇰🇪" },
];

export default function LanguageSettingsScreen() {
  const { t, i18n } = useTranslation();
  const { user, setUser } = useAuthStore();
  const qc = useQueryClient();

  const current = (user?.language ?? "en") as "en" | "sw";

  const updateMut = useMutation({
    mutationFn: (lang: "en" | "sw") => authAPI.updateMe({ language: lang }),
    onSuccess: (updated, lang) => {
      setUser(updated);
      i18n.changeLanguage(lang);
      qc.invalidateQueries({ queryKey: queryKeys.settingsProfile() });
    },
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100 px-4 py-4">
        <h1 className="text-lg font-bold text-gray-900">{t("settings.language.title")}</h1>
        <p className="text-xs text-gray-400 mt-0.5">{t("settings.language.subtitle")}</p>
      </div>

      <div className="p-4">
        <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
          {LANGUAGES.map((lang, idx) => {
            const isSelected = current === lang.code;
            const isLast = idx === LANGUAGES.length - 1;

            return (
              <button
                key={lang.code}
                onClick={() => !isSelected && updateMut.mutate(lang.code)}
                disabled={updateMut.isPending}
                className={`w-full flex items-center justify-between px-4 py-4 text-left transition-colors ${
                  isSelected ? "bg-brand-50" : "hover:bg-gray-50"
                } ${!isLast ? "border-b border-gray-50" : ""}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{lang.flag}</span>
                  <div>
                    <p className={`text-sm font-semibold ${isSelected ? "text-brand-700" : "text-gray-900"}`}>
                      {lang.native}
                    </p>
                    <p className="text-xs text-gray-400">{lang.label}</p>
                  </div>
                </div>

                {isSelected && (
                  <div className="w-5 h-5 rounded-full bg-brand-600 flex items-center justify-center shrink-0">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        <p className="text-xs text-gray-400 mt-4 px-1">{t("settings.language.note")}</p>
      </div>
    </div>
  );
}
