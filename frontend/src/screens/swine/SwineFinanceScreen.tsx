/** Swine — Finance: the computed P&L + unit economics, recent sales, and CSV export.
 *  Everything is composed from recorded facts by the deterministic finance engine. */
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";

import { csvUrl, getFinanceSummary, listSales, type Figure } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";
import { SwineSubnav } from "./SwineSubnav";

export default function SwineFinanceScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const finQ = useQuery({
    queryKey: ["swine-finance", farmId], queryFn: () => getFinanceSummary(farmId as string), enabled: !!farmId,
  });
  const salesQ = useQuery({
    queryKey: ["swine-sales", farmId], queryFn: () => listSales(farmId as string), enabled: !!farmId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const pnl = finQ.data?.pnl ?? {};
  const ue = finQ.data?.unit_economics ?? {};
  const rows: { label: string; fig?: Figure }[] = [
    { label: "Revenue", fig: pnl.revenue },
    { label: "Feed cost", fig: pnl.feed_cost },
    { label: "Operating cost", fig: pnl.operating_cost },
    { label: "Total cost", fig: pnl.total_cost },
    { label: "Gross margin", fig: pnl.gross_margin },
    { label: "Gross margin %", fig: pnl.gross_margin_pct },
    { label: "ROI %", fig: pnl.roi_pct },
    { label: "Cost per pig", fig: ue.cost_per_pig },
    { label: "Cost per kg sold", fig: ue.cost_per_kg_sold },
    { label: "Feed cost %", fig: ue.feed_cost_pct },
    { label: "Health cost %", fig: ue.health_cost_pct },
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <SwineSubnav active="/swine/finance" />
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Finance</h1>
        <a href={csvUrl(farmId, "sales")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800">
          <Download className="h-4 w-4" /> Sales CSV
        </a>
      </div>

      <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Profit &amp; loss</h2>
      {finQ.isLoading ? <Skeleton className="h-64 rounded-xl" /> : (
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

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">Recent sales</h2>
      {salesQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (salesQ.data?.data ?? []).length === 0 ? (
        <p className="text-sm text-gray-400">No sales recorded.</p>
      ) : (
        <ul className="space-y-1.5">
          {(salesQ.data?.data ?? []).slice(0, 15).map((s: any) => (
            <li key={s.id} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
              <span className="capitalize font-medium text-gray-800 dark:text-gray-200">{s.sale_type.replace(/_/g, " ")}</span>
              <span className="ml-2 text-gray-500">{s.sale_date}</span>
              <span className="ml-2 text-gray-500">· {s.total_price} {s.currency ?? ""}</span>
              {s.buyer_name && <span className="ml-2 text-gray-400">→ {s.buyer_name}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
