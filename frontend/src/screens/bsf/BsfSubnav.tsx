/** Shared sub-navigation across the Black Soldier Fly surfaces (Module 16).
 *  Links are added as each frontend milestone ships its screen. */
import { useNavigate } from "react-router-dom";

import { cn } from "@/lib/cn";

const LINKS = [
  { to: "/bsf", label: "Production" },
  // Added per milestone: dashboard, feedstock, harvest, environment, growth,
  // reports, aria, mission.
];

export function BsfSubnav({ active }: { active: string }) {
  const navigate = useNavigate();
  return (
    <div className="mb-5 flex gap-2 overflow-x-auto" role="tablist" aria-label="BSF sections">
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
