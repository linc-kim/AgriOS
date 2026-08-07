/** Shared sub-navigation for the Swine workspace. */
import { useNavigate } from "react-router-dom";

import { cn } from "@/lib/cn";

export function SwineSubnav({ active }: { active: string }) {
  const navigate = useNavigate();
  const links = [
    { to: "/swine", label: "Directory" },
    { to: "/swine/dashboard", label: "Dashboard" },
    { to: "/swine/breeding", label: "Breeding" },
    { to: "/swine/health", label: "Health" },
    { to: "/swine/growth", label: "Growth" },
    { to: "/swine/finance", label: "Finance" },
    { to: "/swine/reports", label: "Reports" },
    { to: "/swine/aria", label: "Ask ARIA" },
    { to: "/swine/mission", label: "Mission Control" },
  ];
  return (
    <div className="mb-5 flex gap-2 overflow-x-auto" role="tablist" aria-label="Swine sections">
      {links.map((l) => (
        <button
          key={l.to}
          type="button"
          role="tab"
          aria-selected={l.to === active}
          onClick={() => navigate(l.to)}
          className={cn(
            "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium",
            l.to === active
              ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
              : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800",
          )}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
