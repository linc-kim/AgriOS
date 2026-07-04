/**
 * A-08 — Admin Settings Screen
 * /admin/settings
 * Platform-level config: contact info, feature flags, branding.
 * V1: read-only display of platform metadata. No editable settings stored server-side.
 */

import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/authStore";
import { platformRole } from "@/lib/roles";

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3.5 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden mb-4">
      <div className="px-5 py-4 border-b border-gray-50 bg-gray-50">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</h2>
      </div>
      <div className="px-5">{children}</div>
    </div>
  );
}

export default function AdminSettingsScreen() {
  const { t } = useTranslation();
  const { user } = useAuthStore();

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.settings.title")}</h1>
        <p className="text-sm text-gray-400">{t("admin.settings.subtitle")}</p>
      </div>

      <Section title={t("admin.settings.section_platform")}>
        <SettingRow label={t("admin.settings.platform_name")} value="AGRIOS" />
        <SettingRow label={t("admin.settings.platform_version")} value="1.0.0" />
        <SettingRow label={t("admin.settings.platform_region")} value="East Africa (Nairobi)" />
        <SettingRow label={t("admin.settings.platform_currency")} value="KES (Kenyan Shilling)" />
        <SettingRow label={t("admin.settings.platform_timezone")} value="Africa/Nairobi (UTC+3)" />
        <SettingRow label={t("admin.settings.platform_language")} value="English / Kiswahili" />
      </Section>

      <Section title={t("admin.settings.section_session")}>
        <SettingRow label={t("admin.settings.session_role")} value={platformRole(user) ?? "super_admin"} />
        <SettingRow label={t("admin.settings.session_phone")} value={user?.phone ?? "—"} />
        <SettingRow label={t("admin.settings.session_name")} value={user?.full_name ?? t("admin.settings.not_set")} />
      </Section>

      <Section title={t("admin.settings.section_integrations")}>
        <SettingRow label={t("admin.settings.integration_sms")} value="Africa's Talking" />
        <SettingRow label={t("admin.settings.integration_ai_primary")} value="Google Gemini" />
        <SettingRow label={t("admin.settings.integration_ai_fallback")} value="Anthropic Claude" />
        <SettingRow label={t("admin.settings.integration_auth")} value="JWT (RS256)" />
      </Section>

      <Section title={t("admin.settings.section_db")}>
        <SettingRow label={t("admin.settings.db_migrations")} value="030 (Frozen — DB-10)" />
        <SettingRow label={t("admin.settings.db_engine")} value="PostgreSQL + SQLAlchemy" />
        <SettingRow label={t("admin.settings.db_audit")} value={t("admin.settings.db_audit_value")} />
      </Section>

      <p className="text-xs text-center text-gray-300 mt-6">
        {t("admin.settings.readonly_notice")}
      </p>
    </div>
  );
}
