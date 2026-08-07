/** Swine — Health: the deterministic health summary (a pattern, never a diagnosis)
 *  and recent disease cases. */
import { useQuery } from "@tanstack/react-query";

import { getHealthSummary, listDiseaseCases, type Figure } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SwineSubnav } from "./SwineSubnav";

export default function SwineHealthScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const sumQ = useQuery({
    queryKey: ["swine-health", farmId], queryFn: () => getHealthSummary(farmId as string), enabled: !!farmId,
  });
  const caseQ = useQuery({
    queryKey: ["swine-diseases", farmId], queryFn: () => listDiseaseCases(farmId as string), enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const s = sumQ.data ?? {};
  const tiles: { label: string; fig?: Figure }[] = [
    { label: "Open cases", fig: s.open_disease_cases },
    { label: "Mortality rate", fig: s.mortality_rate_pct },
    { label: "Vaccinations", fig: s.vaccinations },
    { label: "Treatments", fig: s.treatments },
    { label: "Active withdrawals", fig: s.active_withdrawals },
    { label: "Active isolations", fig: s.active_isolations },
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <SwineSubnav active="/swine/health" />
      <h1 className="mb-1 text-xl font-semibold text-gray-900 dark:text-gray-100">Health &amp; Biosecurity</h1>
      <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">{s.disclaimer ?? "A pattern of recorded facts — not a veterinary diagnosis."}</p>

      {sumQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
          {tiles.map((t) => (
            <div key={t.label} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
              <div className="text-xs uppercase tracking-wide text-gray-400">{t.label}</div>
              <div className="mt-1 text-sm font-medium"><LabelledValue figure={t.fig} /></div>
            </div>
          ))}
        </div>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">Recent disease cases</h2>
      {caseQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (caseQ.data ?? []).length === 0 ? (
        <p className="text-sm text-gray-400">No disease cases recorded.</p>
      ) : (
        <ul className="space-y-1.5">
          {(caseQ.data ?? []).slice(0, 15).map((c: any) => (
            <li key={c.id} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
              <span className="font-medium text-gray-800 dark:text-gray-200">{c.disease_name}</span>
              <span className="ml-2 capitalize text-gray-500">· {c.scope} · {c.status} · {c.severity}</span>
              {c.affected_count > 1 && <span className="ml-2 text-gray-400">{c.affected_count} affected</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
