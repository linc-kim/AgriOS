/**
 * Greena — Connectivity Watcher
 * Monitors online/offline state and updates UIStore.
 * Shows offline banner when connection is lost.
 */

import { useEffect } from "react";
import { useUIStore } from "@/stores/uiStore";

export function ConnectivityWatcher() {
  const { isOnline, setOnline, setLastSyncedAt } = useUIStore();

  useEffect(() => {
    function handleOnline() {
      setOnline(true);
      setLastSyncedAt(new Date());
    }

    function handleOffline() {
      setOnline(false);
    }

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [setOnline, setLastSyncedAt]);

  if (isOnline) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] bg-amber-500 text-white text-xs text-center py-1 px-4">
      You're offline — data will sync when connected
    </div>
  );
}
