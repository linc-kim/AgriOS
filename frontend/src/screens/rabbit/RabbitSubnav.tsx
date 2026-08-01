/** Shared sub-navigation across the Rabbit Management surfaces (Module 17).
 *  Links are added as each frontend screen ships. */
import { useNavigate } from "react-router-dom";

import { cn } from "@/lib/cn";

const LINKS = [
  { to: "/rabbit", label: "Directory" },
  { to: "/rabbit/dashboard", label: "Dashboard" },
  { to: "/rabbit/breeding", label: "Breeding" },
  { to: "/rabbit/health", label: "Health" },
  { to: "/rabbit/housing", label: "Housing" },
  { to: "/rabbit/growth", label: "Growth" },
  { to: "/rabbit/planner", label: "Planner" },
  { to: "/rabbit/reports", label: "Reports" },
  { to: "/rabbit/aria", label: "Ask ARIA" },
  { to: "/rabbit/mission", label: "Mission Control" },
];

export function RabbitSubnav({ active }: { active: string }) {
  const navigate = useNavigate();
  return (
    <div className="mb-5 flex gap-2 overflow-x-auto" role="tablist" aria-label="Rabbit sections">
      {LINKS.map((l) => (
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
