/**
 * OfflineScreen — Shown when the app detects it cannot reach the server.
 * Instructs the user to check their connection. Cached data is still browsable.
 * Blueprint: Shared/Utility screen group — "Offline".
 */

import { useTranslation } from "react-i18next";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { useNavigate } from "react-router-dom";

export default function OfflineScreen() {
  const { t } = useTranslation();
  const { isOnline } = useNetworkStatus();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8 text-center">
      {/* Icon */}
      <div className="w-20 h-20 rounded-full bg-yellow-100 flex items-center justify-center mb-6">
        <svg className="w-10 h-10 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z"
          />
        </svg>
      </div>

      <h1 className="text-xl font-bold text-gray-900 mb-2">{t("offline.title")}</h1>
      <p className="text-sm text-gray-500 mb-8 max-w-xs">{t("offline.subtitle")}</p>

      {/* Status indicator */}
      <div className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium mb-8 ${
        isOnline ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
      }`}>
        <div className={`w-2 h-2 rounded-full ${isOnline ? "bg-green-500" : "bg-red-400"}`} />
        {isOnline ? t("offline.connected") : t("offline.disconnected")}
      </div>

      <div className="space-y-3 w-full max-w-xs">
        {isOnline && (
          <button
            onClick={() => navigate("/")}
            className="w-full py-3 bg-brand-600 text-white rounded-2xl text-sm font-semibold"
          >
            {t("offline.go_home")}
          </button>
        )}
        <button
          onClick={() => window.location.reload()}
          className="w-full py-3 border border-gray-200 text-gray-700 rounded-2xl text-sm font-medium"
        >
          {t("offline.retry")}
        </button>
      </div>

      <p className="text-xs text-gray-400 mt-8">{t("offline.cached_note")}</p>
    </div>
  );
}
