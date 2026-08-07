/** Swine — Breeding: reproduction summary + recent services and confirmed
 *  pregnancies. All figures are computed by the deterministic breeding engine. */
import { useQuery } from "@tanstack/react-query";

import { getReproductionSummary, listBreedings, listPregnancies, type Figure } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SwineSubnav } from "./SwineSubnav";

export default function SwineBreedingScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const sumQ = useQuery({
    queryKey: ["swine-repro", farmId], queryFn: () => getReproductionSummary(farmId as string), enabled: !!farmId,
  });
  const breedQ = useQuery({
    queryKey: ["swine-breedings", farmId], queryFn: () => listBreedings(farmId as string), enabled: !!farmId,
  });
  const pregQ = useQuery({
    queryKey: ["swine-pregnancies", farmId], queryFn: () => listPregnancies(farmId as string), enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const s = sumQ.data ?? {};
  const tiles: { label: string; fig?: Figure }[] = [
    { label: "Services", fig: s.total_services },
    { label: "Pregnancies", fig: s.total_pregnancies },
    { label: "Conception rate", fig: s.conception_rate_pct },
    { label: "Pregnancy rate", fig: s.pregnancy_rate_pct },
    { label: "Natural", fig: s.natural_services },
    { label: "AI", fig: s.ai_services },
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <SwineSubnav active="/swine/breeding" />
      <h1 className="mb-4 text-xl font-semibold text-gray-900 dark:text-gray-100">Breeding &amp; Pregnancy</h1>

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

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">Confirmed pregnancies</h2>
      {pregQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (pregQ.data ?? []).length === 0 ? (
        <p className="text-sm text-gray-400">No active pregnancies.</p>
      ) : (
        <ul className="space-y-1.5">
          {(pregQ.data ?? []).map((p: any) => (
            <li key={p.id} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
              <span className="capitalize text-gray-800 dark:text-gray-200">{p.status}</span>
              <span className="ml-2 text-gray-500">due {p.expected_farrowing_date ?? "—"}</span>
              <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] uppercase text-gray-500 dark:bg-gray-800">
                risk {p.risk_level}
              </span>
            </li>
          ))}
        </ul>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">Recent services</h2>
      {breedQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (breedQ.data ?? []).length === 0 ? (
        <p className="text-sm text-gray-400">No breeding services recorded.</p>
      ) : (
        <ul className="space-y-1.5">
          {(breedQ.data ?? []).slice(0, 15).map((b: any) => (
            <li key={b.id} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
              <span className="capitalize font-medium text-gray-800 dark:text-gray-200">{b.method}</span>
              <span className="ml-2 text-gray-500">{b.service_date ?? "—"}</span>
              <span className="ml-2 capitalize text-gray-500">· {b.status} · {b.outcome}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
