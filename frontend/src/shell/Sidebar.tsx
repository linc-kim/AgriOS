import { NavLink } from "react-router-dom";

import { MODULES, SECTIONS } from "@/shell/registry";
import { OrgFarmSwitcher } from "@/shell/OrgFarmSwitcher";
import { Logo } from "@/components/ui/Logo";
import { useAuthStore } from "@/stores/authStore";
import { isSuperAdmin } from "@/lib/roles";
import { cn } from "@/lib/cn";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const user = useAuthStore((s) => s.user);
  const admin = isSuperAdmin(user);

  return (
    <div className="flex h-full flex-col border-r border-gray-200 bg-white dark:border-white/10 dark:bg-[#0f1216]">
      <div className="px-4 pb-3 pt-5">
        <Logo variant="lockup" className="h-7 w-auto dark:hidden" />
        <Logo variant="lockup" tone="white" className="hidden h-7 w-auto dark:block" />
      </div>

      <div className="px-3 pb-3">
        <OrgFarmSwitcher />
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        {SECTIONS.map((sec) => {
          const items = MODULES.filter(
            (m) => m.section === sec.id && (!m.adminOnly || admin),
          );
          if (!items.length) return null;
          return (
            <div key={sec.id}>
              <p className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                {sec.label}
              </p>
              <div className="space-y-0.5">
                {items.map((m) => {
                  const Icon = m.icon;
                  return (
                    <NavLink
                      key={m.id}
                      to={m.path}
                      end={m.path === "/"}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          "group flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300"
                            : "text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-white/[0.06] dark:hover:text-white",
                        )
                      }
                    >
                      <Icon className="h-[18px] w-[18px] shrink-0" />
                      <span className="truncate">{m.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <div className="border-t border-gray-100 px-4 py-3 dark:border-white/10">
        <p className="text-[11px] text-gray-400">Greena — farm operating system</p>
      </div>
    </div>
  );
}
