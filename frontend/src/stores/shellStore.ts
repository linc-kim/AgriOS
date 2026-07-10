/**
 * Greena — Application shell state (theme, sidebar, current org/farm).
 * Persisted to localStorage; theme is applied to <html> as a `dark` class.
 */
import { create } from "zustand";

type Theme = "light" | "dark" | "system";

interface ShellStore {
  theme: Theme;
  sidebarCollapsed: boolean;
  commandOpen: boolean;
  currentOrgId: string | null;
  currentFarmId: string | null;

  setTheme: (t: Theme) => void;
  toggleSidebar: () => void;
  setCommandOpen: (open: boolean) => void;
  setCurrentOrg: (id: string | null) => void;
  setCurrentFarm: (id: string | null) => void;
}

const read = <T,>(key: string, fallback: T): T => {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
};

export function applyTheme(theme: Theme) {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const dark = theme === "dark" || (theme === "system" && prefersDark);
  document.documentElement.classList.toggle("dark", dark);
}

export const useShellStore = create<ShellStore>((set, get) => ({
  theme: read<Theme>("greena.theme", "light"),
  sidebarCollapsed: read<boolean>("greena.sidebarCollapsed", false),
  commandOpen: false,
  currentOrgId: read<string | null>("greena.orgId", null),
  currentFarmId: read<string | null>("greena.farmId", null),

  setTheme: (theme) => {
    localStorage.setItem("greena.theme", JSON.stringify(theme));
    applyTheme(theme);
    set({ theme });
  },
  toggleSidebar: () => {
    const next = !get().sidebarCollapsed;
    localStorage.setItem("greena.sidebarCollapsed", JSON.stringify(next));
    set({ sidebarCollapsed: next });
  },
  setCommandOpen: (commandOpen) => set({ commandOpen }),
  setCurrentOrg: (id) => {
    localStorage.setItem("greena.orgId", JSON.stringify(id));
    set({ currentOrgId: id });
  },
  setCurrentFarm: (id) => {
    localStorage.setItem("greena.farmId", JSON.stringify(id));
    set({ currentFarmId: id });
  },
}));
