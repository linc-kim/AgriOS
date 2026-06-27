/**
 * AGRIOS — UI State Zustand Store
 * Manages: active tab, toast queue, modal states.
 */

import { create } from "zustand";

export type BottomTab = "home" | "flock" | "health" | "finance" | "aria";

export type ToastType = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface UIStore {
  // Bottom navigation
  activeTab: BottomTab;
  setActiveTab: (tab: BottomTab) => void;

  // Toast queue
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;

  // Offline state
  isOnline: boolean;
  setOnline: (online: boolean) => void;
  lastSyncedAt: Date | null;
  setLastSyncedAt: (date: Date) => void;
}

let toastId = 0;

export const useUIStore = create<UIStore>((set) => ({
  // Bottom navigation — starts on Home
  activeTab: "home",
  setActiveTab: (tab) => set({ activeTab: tab }),

  // Toasts
  toasts: [],
  addToast: (toast) =>
    set((state) => ({
      toasts: [
        ...state.toasts,
        { ...toast, id: String(++toastId) },
      ],
    })),
  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  // Connectivity
  isOnline: navigator.onLine,
  setOnline: (online) => set({ isOnline: online }),
  lastSyncedAt: null,
  setLastSyncedAt: (date) => set({ lastSyncedAt: date }),
}));
