/**
 * A-05 — Admin Disease Alerts Screen
 * /admin/alerts
 * Create, publish, update, and deactivate platform disease alerts.
 * Uses the existing health API endpoints (/health/alerts — admin section).
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { apiClient } from "@/api/client";
import { Spinner } from "@/components/ui/Spinner";

// Inline types for disease alerts (admin view)
interface DiseaseAlert {
  id: string;
  title: string;
  disease_name: string;
  severity: string;
  status: string;
  affected_counties: string[];
  affected_species: string[];
  published_at: string | null;
  created_at: string;
}

interface DiseaseAlertCreate {
  title: string;
  disease_name: string;
  severity: "low" | "medium" | "high" | "critical";
  description: string;
  affected_counties: string[];
  affected_species: string[];
  guidance: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  low:      "bg-gray-100 text-gray-600",
  medium:   "bg-amber-100 text-amber-700",
  high:     "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

const STATUS_COLORS: Record<string, string> = {
  draft:    "bg-gray-100 text-gray-500",
  active:   "bg-green-100 text-green-700",
  inactive: "bg-red-100 text-red-500",
};

export default function AdminAlertsScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<DiseaseAlertCreate>({
    title: "",
    disease_name: "",
    severity: "medium",
    description: "",
    affected_counties: [],
    affected_species: ["broiler", "layer"],
    guidance: "",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "alerts"],
    queryFn: async () => {
      const res = await apiClient.get("/health/alerts");
      return res.data.data as DiseaseAlert[];
    },
  });

  const createMut = useMutation({
    mutationFn: (body: DiseaseAlertCreate) => apiClient.post("/health/alerts", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "alerts"] });
      setShowForm(false);
      setForm({ title: "", disease_name: "", severity: "medium", description: "", affected_counties: [], affected_species: ["broiler", "layer"], guidance: "" });
    },
  });

  const publishMut = useMutation({
    mutationFn: (alertId: string) => apiClient.post(`/health/alerts/${alertId}/publish`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "alerts"] }),
  });

  const deactivateMut = useMutation({
    mutationFn: (alertId: string) => apiClient.post(`/health/alerts/${alertId}/deactivate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "alerts"] }),
  });

  const alerts: DiseaseAlert[] = data ?? [];

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.alerts.title")}</h1>
          <p className="text-sm text-gray-400">{t("admin.alerts.subtitle")}</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-brand-600 text-white rounded-xl text-sm font-medium hover:bg-brand-700"
        >
          + {t("admin.alerts.create_alert")}
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : (
        <div className="space-y-3">
          {alerts.length === 0 ? (
            <div className="text-center py-20 text-gray-400 text-sm">{t("admin.alerts.empty")}</div>
          ) : (
            alerts.map((alert) => (
              <div key={alert.id} className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_COLORS[alert.status] ?? ""}`}>
                        {alert.status}
                      </span>
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SEVERITY_COLORS[alert.severity] ?? ""}`}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-gray-900">{alert.title}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{alert.disease_name}</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {alert.status === "draft" && (
                      <button
                        onClick={() => publishMut.mutate(alert.id)}
                        disabled={publishMut.isPending}
                        className="text-xs px-3 py-1.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
                      >
                        {t("admin.alerts.action_publish")}
                      </button>
                    )}
                    {alert.status === "active" && (
                      <button
                        onClick={() => deactivateMut.mutate(alert.id)}
                        disabled={deactivateMut.isPending}
                        className="text-xs px-3 py-1.5 bg-red-100 text-red-600 rounded-lg font-medium hover:bg-red-200 disabled:opacity-50"
                      >
                        {t("admin.alerts.action_deactivate")}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create form modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-base font-bold text-gray-900 mb-4">{t("admin.alerts.create_alert")}</h2>

            {[
              { key: "title", label: t("admin.alerts.field_title") },
              { key: "disease_name", label: t("admin.alerts.field_disease") },
              { key: "guidance", label: t("admin.alerts.field_guidance") },
            ].map(({ key, label }) => (
              <div key={key} className="mb-3">
                <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                <input
                  value={(form as any)[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
              </div>
            ))}

            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-600 mb-1">{t("admin.alerts.field_description")}</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
            </div>

            <div className="mb-4">
              <label className="block text-xs font-medium text-gray-600 mb-1">{t("admin.alerts.field_severity")}</label>
              <select
                value={form.severity}
                onChange={(e) => setForm({ ...form, severity: e.target.value as any })}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm"
              >
                {["low", "medium", "high", "critical"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setShowForm(false)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={() => createMut.mutate(form)}
                disabled={createMut.isPending || !form.title || !form.disease_name}
                className="flex-1 py-2 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {createMut.isPending ? t("common.saving") : t("admin.alerts.save_draft")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
