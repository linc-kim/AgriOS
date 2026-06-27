/**
 * ErrorScreen — Generic error boundary fallback screen.
 * Blueprint: Shared/Utility screen group — "Error".
 */

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

interface Props {
  message?: string;
  onRetry?: () => void;
}

export default function ErrorScreen({ message, onRetry }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8 text-center">
      <div className="w-20 h-20 rounded-full bg-red-100 flex items-center justify-center mb-6">
        <svg className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
      </div>

      <h1 className="text-xl font-bold text-gray-900 mb-2">{t("error.generic_title")}</h1>
      <p className="text-sm text-gray-500 mb-2 max-w-xs">{t("error.generic_subtitle")}</p>
      {message && (
        <p className="text-xs text-red-400 bg-red-50 rounded-xl px-3 py-2 mb-6 max-w-xs font-mono">
          {message}
        </p>
      )}

      <div className="space-y-3 w-full max-w-xs mt-4">
        {onRetry && (
          <button
            onClick={onRetry}
            className="w-full py-3 bg-brand-600 text-white rounded-2xl text-sm font-semibold"
          >
            {t("error.retry")}
          </button>
        )}
        <button
          onClick={() => navigate("/")}
          className="w-full py-3 border border-gray-200 text-gray-700 rounded-2xl text-sm font-medium"
        >
          {t("error.go_home")}
        </button>
      </div>
    </div>
  );
}
