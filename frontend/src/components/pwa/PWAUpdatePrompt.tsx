/**
 * PWAUpdatePrompt — Shown when a new service worker version is waiting.
 * User can tap "Update" to activate the new version immediately.
 * Sprint 9: PWA update notification.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

export function PWAUpdatePrompt() {
  const { t } = useTranslation();
  const [needsUpdate, setNeedsUpdate] = useState(false);
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    navigator.serviceWorker.getRegistration().then((reg) => {
      if (!reg) return;
      setRegistration(reg);

      // Already a waiting worker (page loaded after update was downloaded)
      if (reg.waiting) {
        setNeedsUpdate(true);
      }

      // New worker installing and then waiting
      reg.addEventListener("updatefound", () => {
        const newWorker = reg.installing;
        if (!newWorker) return;
        newWorker.addEventListener("statechange", () => {
          if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
            setNeedsUpdate(true);
          }
        });
      });
    });
  }, []);

  if (!needsUpdate) return null;

  const handleUpdate = () => {
    if (registration?.waiting) {
      registration.waiting.postMessage({ type: "SKIP_WAITING" });
    }
    setNeedsUpdate(false);
    window.location.reload();
  };

  return (
    <div className="fixed bottom-24 left-4 right-4 z-50 bg-gray-900 text-white rounded-2xl shadow-xl p-4 flex items-center justify-between">
      <div>
        <p className="text-sm font-semibold">{t("pwa.update_title")}</p>
        <p className="text-xs text-gray-400 mt-0.5">{t("pwa.update_subtitle")}</p>
      </div>
      <button
        onClick={handleUpdate}
        className="ml-4 px-4 py-2 bg-brand-600 text-white text-xs font-semibold rounded-xl shrink-0 hover:bg-brand-700"
      >
        {t("pwa.update_btn")}
      </button>
    </div>
  );
}
