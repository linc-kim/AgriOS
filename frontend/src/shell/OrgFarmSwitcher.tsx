import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronsUpDown, Check, Plus, Building2, Sprout } from "lucide-react";

import { useWorkspace } from "@/shell/useWorkspace";
import { useClickOutside } from "@/hooks/useClickOutside";
import { cn } from "@/lib/cn";

function Row({
  active,
  icon,
  label,
  onClick,
}: {
  active?: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm",
        "text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/[0.06]",
      )}
    >
      <span className="text-gray-400">{icon}</span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {active && <Check className="h-4 w-4 text-brand-600" />}
    </button>
  );
}

export function OrgFarmSwitcher() {
  const { orgs, farms, currentOrg, currentFarm, setCurrentOrg, setCurrentFarm } =
    useWorkspace();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false), open);
  const navigate = useNavigate();

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-2.5 rounded-xl border px-2.5 py-2 text-left transition-colors",
          "border-gray-200 bg-white hover:bg-gray-50",
          "dark:border-white/10 dark:bg-white/[0.03] dark:hover:bg-white/[0.06]",
        )}
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-sm font-semibold text-white">
          {(currentOrg?.name?.[0] ?? "G").toUpperCase()}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-gray-900 dark:text-white">
            {currentOrg?.name ?? "Your organization"}
          </span>
          <span className="block truncate text-xs text-gray-500 dark:text-gray-400">
            {currentFarm?.name ?? "No farm yet"}
          </span>
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-gray-400" />
      </button>

      {open && (
        <div
          role="menu"
          className={cn(
            "absolute left-0 right-0 z-40 mt-2 origin-top rounded-xl border p-1.5 shadow-xl",
            "border-gray-200 bg-white shadow-black/5",
            "dark:border-white/10 dark:bg-[#161a20] dark:shadow-black/40",
            "animate-[ob-in_.14s_ease]",
          )}
        >
          <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
            Organizations
          </p>
          {orgs.map((o) => (
            <Row
              key={o.id}
              active={o.id === currentOrg?.id}
              icon={<Building2 className="h-4 w-4" />}
              label={o.name}
              onClick={() => {
                setCurrentOrg(o.id);
                setOpen(false);
              }}
            />
          ))}

          {farms.length > 0 && (
            <>
              <p className="px-2.5 pb-1 pt-2.5 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                Farms
              </p>
              {farms.map((f) => (
                <Row
                  key={f.id}
                  active={f.id === currentFarm?.id}
                  icon={<Sprout className="h-4 w-4" />}
                  label={f.name}
                  onClick={() => {
                    setCurrentFarm(f.id);
                    setOpen(false);
                  }}
                />
              ))}
            </>
          )}

          <div className="my-1.5 h-px bg-gray-100 dark:bg-white/10" />
          <Row
            icon={<Plus className="h-4 w-4" />}
            label="New organization"
            onClick={() => {
              setOpen(false);
              navigate("/onboarding");
            }}
          />
        </div>
      )}
    </div>
  );
}
