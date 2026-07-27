/** Shared sub-navigation across the Aviculture surfaces (Module 15). */
import { useNavigate } from "react-router-dom";

import { cn } from "@/lib/cn";

const LINKS = [
  { to: "/aviculture", label: "Collection" },
  { to: "/aviculture/aviaries", label: "Aviaries" },
  { to: "/aviculture/breeding", label: "Breeding" },
  { to: "/aviculture/incubation", label: "Incubation" },
  { to: "/aviculture/health", label: "Health" },
];

export function AviSubnav({ active }: { farmId?: string; active: string }) {
  const navigate = useNavigate();
  return (
    <div className="mb-5 flex gap-2 overflow-x-auto">
      {LINKS.map((l) => (
        <button
          key={l.to}
          type="button"
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
