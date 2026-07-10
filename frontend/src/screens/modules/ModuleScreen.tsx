import { useLocation } from "react-router-dom";
import { moduleByPath } from "@/shell/registry";
import { EmptyState } from "@/components/ui/EmptyState";

/**
 * Generic screen for a registered module that has no bespoke screen yet.
 * Renders the module's purpose as a calm empty state — the shell already treats
 * it as a first-class destination (nav, breadcrumbs, command palette).
 */
export default function ModuleScreen() {
  const { pathname } = useLocation();
  const mod = moduleByPath("/" + pathname.split("/")[1]);
  const Icon = mod?.icon;

  return (
    <div className="space-y-7">
      <header>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
          {mod?.label ?? "Module"}
        </h1>
        <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">{mod?.description}</p>
      </header>
      <EmptyState
        icon={Icon ? <Icon className="h-6 w-6" /> : undefined}
        title={`Your ${(mod?.label ?? "workspace").toLowerCase()} lives here`}
        description="Your workspace is set up and ready. This space fills in as you add data and as new tools come online."
      />
    </div>
  );
}
