import { useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Menu,
  Search,
  Bell,
  Sun,
  Moon,
  ChevronRight,
  Settings,
  LogOut,
} from "lucide-react";

import { moduleByPath } from "@/shell/registry";
import { useShellStore } from "@/stores/shellStore";
import { useAuthStore } from "@/stores/authStore";
import { useClickOutside } from "@/hooks/useClickOutside";
import { Avatar } from "@/components/ui/Avatar";
import { logout } from "@/lib/logout";

function Breadcrumbs() {
  const { pathname } = useLocation();
  const mod = moduleByPath(pathname === "/" ? "/" : "/" + pathname.split("/")[1]);
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm">
      <Link to="/" className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
        Greena
      </Link>
      <ChevronRight className="h-3.5 w-3.5 text-gray-300 dark:text-gray-600" />
      <span className="font-medium text-gray-900 dark:text-white">
        {mod?.label ?? "Page"}
      </span>
    </nav>
  );
}

function ThemeToggle() {
  const setTheme = useShellStore((s) => s.setTheme);
  const isDark = document.documentElement.classList.contains("dark");
  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
    >
      {isDark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
    </button>
  );
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
      >
        <Bell className="h-[18px] w-[18px]" />
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-gray-200 bg-white p-4 shadow-xl shadow-black/5 animate-[ob-in_.14s_ease] dark:border-white/10 dark:bg-[#161a20] dark:shadow-black/40">
          <p className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Notifications</p>
          <div className="flex flex-col items-center py-6 text-center">
            <Bell className="mb-2 h-6 w-6 text-gray-300 dark:text-gray-600" />
            <p className="text-sm text-gray-500 dark:text-gray-400">You're all caught up.</p>
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileMenu() {
  const user = useAuthStore((s) => s.user);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);
  const navigate = useNavigate();

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Account menu"
        aria-haspopup="menu"
        className="flex items-center rounded-full outline-none focus-visible:ring-4 focus-visible:ring-brand-500/25"
      >
        <Avatar name={user?.full_name} email={user?.email} className="h-9 w-9" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-60 rounded-xl border border-gray-200 bg-white p-1.5 shadow-xl shadow-black/5 animate-[ob-in_.14s_ease] dark:border-white/10 dark:bg-[#161a20] dark:shadow-black/40"
        >
          <div className="flex items-center gap-2.5 px-2.5 py-2">
            <Avatar name={user?.full_name} email={user?.email} className="h-9 w-9" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                {user?.full_name || "Your account"}
              </p>
              <p className="truncate text-xs text-gray-500 dark:text-gray-400">{user?.email}</p>
            </div>
          </div>
          <div className="my-1 h-px bg-gray-100 dark:bg-white/10" />
          <button
            onClick={() => {
              setOpen(false);
              navigate("/settings");
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/[0.06]"
          >
            <Settings className="h-4 w-4 text-gray-400" /> Settings
          </button>
          <button
            onClick={async () => {
              setOpen(false);
              await logout();
              navigate("/login", { replace: true });
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}

export function Topbar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const setCommandOpen = useShellStore((s) => s.setCommandOpen);
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-gray-200 bg-white/85 px-4 backdrop-blur dark:border-white/10 dark:bg-[#0f1216]/85 sm:px-6">
      <button
        onClick={onOpenSidebar}
        aria-label="Open navigation"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 lg:hidden dark:text-gray-400 dark:hover:bg-white/[0.06]"
      >
        <Menu className="h-5 w-5" />
      </button>

      <Breadcrumbs />

      <div className="ml-auto flex items-center gap-1.5">
        <button
          onClick={() => setCommandOpen(true)}
          className="hidden items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-100 sm:flex dark:border-white/10 dark:bg-white/[0.03] dark:hover:bg-white/[0.06]"
        >
          <Search className="h-4 w-4" />
          <span>Search</span>
          <kbd className="ml-2 rounded border border-gray-200 bg-white px-1.5 text-[11px] font-medium text-gray-400 dark:border-white/10 dark:bg-white/[0.04]">
            ⌘K
          </kbd>
        </button>
        <button
          onClick={() => setCommandOpen(true)}
          aria-label="Search"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 sm:hidden dark:text-gray-400 dark:hover:bg-white/[0.06]"
        >
          <Search className="h-[18px] w-[18px]" />
        </button>
        <NotificationBell />
        <ThemeToggle />
        <div className="mx-1 h-6 w-px bg-gray-200 dark:bg-white/10" />
        <ProfileMenu />
      </div>
    </header>
  );
}
