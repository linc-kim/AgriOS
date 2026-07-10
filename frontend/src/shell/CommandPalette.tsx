import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { Search, Moon, Sun, LogOut } from "lucide-react";

import { MODULES } from "@/shell/registry";
import { useShellStore } from "@/stores/shellStore";
import { useAuthStore } from "@/stores/authStore";
import { isSuperAdmin } from "@/lib/roles";
import { logout } from "@/lib/logout";
import { cn } from "@/lib/cn";

interface Command {
  id: string;
  label: string;
  hint?: string;
  icon: LucideIcon;
  run: () => void;
}

export function CommandPalette() {
  const open = useShellStore((s) => s.commandOpen);
  const setOpen = useShellStore((s) => s.setCommandOpen);
  const setTheme = useShellStore((s) => s.setTheme);
  const navigate = useNavigate();
  const admin = isSuperAdmin(useAuthStore((s) => s.user));
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useShellStore.getState().commandOpen);
      } else if (e.key === "Escape" && useShellStore.getState().commandOpen) {
        e.preventDefault();
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      const t = setTimeout(() => inputRef.current?.focus(), 20);
      return () => clearTimeout(t);
    }
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const mods: Command[] = MODULES.filter((m) => !m.adminOnly || admin).map((m) => ({
      id: m.id,
      label: m.label,
      hint: m.description,
      icon: m.icon,
      run: () => navigate(m.path),
    }));
    const actions: Command[] = [
      { id: "theme-dark", label: "Switch to dark theme", hint: "Appearance", icon: Moon, run: () => setTheme("dark") },
      { id: "theme-light", label: "Switch to light theme", hint: "Appearance", icon: Sun, run: () => setTheme("light") },
      {
        id: "logout",
        label: "Log out",
        hint: "Account",
        icon: LogOut,
        run: async () => {
          await logout();
          navigate("/login", { replace: true });
        },
      },
    ];
    return [...mods, ...actions];
  }, [admin, navigate, setTheme]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.hint?.toLowerCase().includes(q),
    );
  }, [commands, query]);

  if (!open) return null;

  const run = (c?: Command) => {
    if (!c) return;
    setOpen(false);
    c.run();
  };

  return (
    <div
      role="dialog"
      aria-modal
      aria-label="Command palette"
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]"
    >
      <div
        className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm animate-[ob-in_.12s_ease]"
        onClick={() => setOpen(false)}
      />
      <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl animate-[ob-in_.16s_cubic-bezier(.16,1,.3,1)] dark:border-white/10 dark:bg-[#161a20]">
        <div className="flex items-center gap-3 border-b border-gray-100 px-4 dark:border-white/10">
          <Search className="h-4 w-4 text-gray-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, filtered.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                run(filtered[active]);
              }
            }}
            placeholder="Search modules and actions…"
            className="h-12 w-full bg-transparent text-[15px] text-gray-900 outline-none placeholder:text-gray-400 dark:text-white"
          />
          <kbd className="rounded border border-gray-200 px-1.5 text-[11px] text-gray-400 dark:border-white/10">
            Esc
          </kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-1.5">
          {filtered.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-gray-400">
              No results for “{query}”
            </p>
          )}
          {filtered.map((c, i) => {
            const Icon = c.icon;
            return (
              <button
                key={c.id}
                onMouseEnter={() => setActive(i)}
                onClick={() => run(c)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left",
                  i === active ? "bg-brand-50 dark:bg-brand-600/15" : "",
                )}
              >
                <Icon
                  className={cn(
                    "h-[18px] w-[18px]",
                    i === active ? "text-brand-600 dark:text-brand-300" : "text-gray-400",
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-gray-900 dark:text-white">
                    {c.label}
                  </span>
                  {c.hint && <span className="block truncate text-xs text-gray-400">{c.hint}</span>}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
