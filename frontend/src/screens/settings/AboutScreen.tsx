/**
 * S-04 — About Screen
 * /settings/about
 * App version, AGRIOS info, support contact, open-source notices.
 */

import { useTranslation } from "react-i18next";

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3.5 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

export default function AboutScreen() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100 px-4 py-4">
        <h1 className="text-lg font-bold text-gray-900">{t("settings.about.title")}</h1>
        <p className="text-xs text-gray-400 mt-0.5">{t("settings.about.subtitle")}</p>
      </div>

      <div className="p-4 space-y-4">
        {/* App identity */}
        <div className="bg-white rounded-2xl border border-gray-100 p-5 text-center">
          <div className="w-16 h-16 rounded-2xl bg-brand-600 flex items-center justify-center mx-auto mb-3">
            <span className="text-3xl">🌾</span>
          </div>
          <h2 className="text-base font-bold text-gray-900">AGRIOS</h2>
          <p className="text-xs text-gray-400 mt-0.5">{t("settings.about.tagline")}</p>
        </div>

        {/* Version info */}
        <div className="bg-white rounded-2xl border border-gray-100 px-4">
          <InfoRow label={t("settings.about.version")} value="1.0.0" />
          <InfoRow label={t("settings.about.platform")} value="PWA (Android Chrome)" />
          <InfoRow label={t("settings.about.region")} value="Kenya" />
          <InfoRow label={t("settings.about.currency")} value="KES" />
          <InfoRow label={t("settings.about.languages")} value="English / Kiswahili" />
        </div>

        {/* Support */}
        <div className="bg-white rounded-2xl border border-gray-100 px-4">
          <div className="py-3.5 border-b border-gray-50">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              {t("settings.about.support_header")}
            </p>
            <p className="text-sm text-gray-900">support@agrios.app</p>
          </div>
          <div className="py-3.5">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              {t("settings.about.website_header")}
            </p>
            <p className="text-sm text-gray-900">agrios.app</p>
          </div>
        </div>

        {/* Legal */}
        <p className="text-xs text-gray-300 text-center px-4">
          {t("settings.about.legal")}
        </p>
      </div>
    </div>
  );
}
