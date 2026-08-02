/** Small Ruminant — Reports (shared): the computed P&L + a registry CSV export.
 *  Everything is composed from recorded facts by the deterministic engines. */
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";

import { getFinanceSummary, registryCsvUrl, type Figure, type Species } from "@/api/smallRuminant";
import { SPECIES_UI } from "./config";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SrSubnav } from "./SrSubnav";

export default function SrReportsScreen({ species }: { species: Species }) {
  const ui = SPECIES_UI[species];
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const q = useQuery({
    queryKey: ["sr-finance", species, farmId],
    queryFn: () => getFinanceSummary(farmId as string, species),
    enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const pnl = q.data?.pnl ?? {};
  const ue = q.data?.unit_economics ?? {};

  const rows: { label: string; fig?: Figure }[] = [
    { label: "Revenue", fig: pnl.revenue },
    { label: "Feed cost", fig: pnl.feed_cost },
    { label: "Operating cost", fig: pnl.operating_cost },
    { label: "Total cost", fig: pnl.total_cost },
    { label: "Gross margin", fig: pnl.gross_margin },
    { label: "Gross margin %", fig: pnl.gross_margin_pct },
    { label: "ROI %", fig: pnl.roi_pct },
    { label: "Cost per animal", fig: ue.cost_per_animal },
    { label: "Cost per kg sold", fig: ue.cost_per_kg_sold },
    ui.producesMilk ? { label: "Cost per litre milk", fig: ue.cost_per_litre_milk } : { label: "", fig: undefined },
    ui.producesWool ? { label: "Cost per kg wool", fig: ue.cost_per_kg_wool } : { label: "", fig: undefined },
  ].filter((r) => r.label);

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <SrSubnav species={species} active={`/${species}/reports`} />
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{ui.title} Reports</h1>
        <a
          href={registryCsvUrl(farmId, species)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
        >
          <Download className="h-4 w-4" /> Registry CSV
        </a>
      </div>

      <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Profit &amp; loss</h2>
      {q.isLoading ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
          <table className="min-w-full text-sm">
            <tbody>
              {rows.map((r) => (
                <tr key={r.label} className="border-t border-gray-100 first:border-t-0 dark:border-gray-800">
                  <td className="px-3 py-2 text-gray-500">{r.label}</td>
                  <td className="px-3 py-2 text-right"><LabelledValue figure={r.fig} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
