/**
 * NotFoundScreen — 404 page for unmatched routes.
 * Blueprint: Shared/Utility screen group — "Error".
 */

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

export default function NotFoundScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8 text-center">
      <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-6">
        <svg className="w-10 h-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"
          />
        </svg>
      </div>

      <p className="text-5xl font-black text-gray-200 mb-4">404</p>
      <h1 className="text-xl font-bold text-gray-900 mb-2">{t("error.not_found_title")}</h1>
      <p className="text-sm text-gray-500 mb-8 max-w-xs">{t("error.not_found_subtitle")}</p>

      <button
        onClick={() => navigate("/")}
        className="px-6 py-3 bg-brand-600 text-white rounded-2xl text-sm font-semibold"
      >
        {t("error.go_home")}
      </button>
    </div>
  );
}
