/** Shared sub-navigation for the Small Ruminant workspaces. The same component
 *  serves goat and sheep; the production tab (Dairy / Wool) is species-driven. */
import { useNavigate } from "react-router-dom";

import { cn } from "@/lib/cn";
import { SPECIES_UI } from "./config";
import type { Species } from "@/api/smallRuminant";

export function SrSubnav({ species, active }: { species: Species; active: string }) {
  const navigate = useNavigate();
  const ui = SPECIES_UI[species];
  const root = `/${species}`;
  const links = [
    { to: root, label: "Directory" },
    { to: `${root}/dashboard`, label: "Dashboard" },
    { to: `${root}/${ui.productionPath}`, label: ui.productionLabel },
    { to: `${root}/reports`, label: "Reports" },
    { to: `${root}/aria`, label: "Ask ARIA" },
    { to: `${root}/mission`, label: "Mission Control" },
  ];
  return (
    <div className="mb-5 flex gap-2 overflow-x-auto" role="tablist" aria-label={`${ui.title} sections`}>
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
