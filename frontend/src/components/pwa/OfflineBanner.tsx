/**
 * OfflineBanner — Shown at the top of AppLayout when the device is offline.
 * Data already fetched is still visible via TanStack Query cache.
 * Sprint 9: Offline-aware UI layer.
 */

import { useTranslation } from "react-i18next";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";

export function OfflineBanner() {
  const { t } = useTranslation();
  const { isOnline } = useNetworkStatus();

  if (isOnline) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-yellow-500 text-white text-xs font-medium text-center py-2 px-4 shadow-md">
      {t("offline.banner")}
    </div>
  );
}
