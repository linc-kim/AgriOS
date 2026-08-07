/** Swine — Reports: the farm dashboard's composed sections + CSV exports. Every
 *  section is generated on demand from the deterministic engines (nothing stored). */
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";

import { csvUrl, getFarmDashboard } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { SwineSubnav } from "./SwineSubnav";

const SECTIONS = ["reproduction", "farrowing", "feed", "health", "growth", "finance", "housing"];

export default function SwineReportsScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const q = useQuery({
    queryKey: ["swine-report-farm", farmId], queryFn: () => getFarmDashboard(farmId as string), enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const d = q.data ?? {};

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <SwineSubnav active="/swine/reports" />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Reports</h1>
        <div className="flex gap-2">
          {(["registry", "sales", "mortality"] as const).map((name) => (
            <a key={name} href={csvUrl(farmId, name)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800">
              <Download className="h-4 w-4" /> {name} CSV
            </a>
          ))}
        </div>
      </div>

      {q.isLoading ? <Skeleton className="h-64 rounded-xl" /> : (
        <div className="space-y-3">
          {SECTIONS.map((key) => {
            const sec = d[key];
            if (!sec) return null;
            return (
              <div key={key} className="rounded-xl border border-gray-200 p-3 dark:border-gray-800">
                <div className="mb-1 flex items-center justify-between">
                  <h2 className="text-sm font-semibold capitalize text-gray-800 dark:text-gray-200">{key}</h2>
                  <span className="text-[11px] text-gray-400">{sec.meaning}</span>
                </div>
                <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-500 sm:grid-cols-3">
                  {Object.entries(sec)
                    .filter(([k, v]) => !["meaning", "source"].includes(k) && v && typeof v === "object" && "value" in (v as any))
                    .slice(0, 9)
                    .map(([k, v]: [string, any]) => (
                      <li key={k}>
                        <span className="capitalize">{k.replace(/_/g, " ")}: </span>
                        <span className="font-medium text-gray-800 dark:text-gray-200">{String(v.value ?? "—")}</span>
                      </li>
                    ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
