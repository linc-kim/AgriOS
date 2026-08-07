/** Swine — Pig Profile: identity + life-history timeline + computed growth analysis
 *  and the explainable market-readiness assessment. */
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { getGrowthAnalysis, getPig, getReadiness, getTimeline } from "@/api/swine";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { LabelledValue } from "@/components/common/FactBadge";

export default function SwineProfileScreen() {
  const { pigId } = useParams();
  const navigate = useNavigate();
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const pigQ = useQuery({
    queryKey: ["swine-pig", farmId, pigId],
    queryFn: () => getPig(farmId as string, pigId as string), enabled: !!farmId && !!pigId,
  });
  const timelineQ = useQuery({
    queryKey: ["swine-timeline", farmId, pigId],
    queryFn: () => getTimeline(farmId as string, pigId as string), enabled: !!farmId && !!pigId,
  });
  const growthQ = useQuery({
    queryKey: ["swine-pig-growth", farmId, pigId],
    queryFn: () => getGrowthAnalysis(farmId as string, pigId as string), enabled: !!farmId && !!pigId,
  });
  const readyQ = useQuery({
    queryKey: ["swine-pig-ready", farmId, pigId],
    queryFn: () => getReadiness(farmId as string, pigId as string), enabled: !!farmId && !!pigId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  if (pigQ.isLoading) return <div className="mx-auto max-w-3xl px-4 py-6"><Skeleton className="h-64 rounded-xl" /></div>;
  const p = pigQ.data;
  if (!p) return <p className="py-16 text-center text-sm text-gray-400">Not found.</p>;
  const ready = readyQ.data;

  const facts: [string, string | null][] = [
    ["Ref", p.internal_ref], ["Name", p.name], ["Ear tag", p.ear_tag],
    ["Sex / class", p.sex], ["Birth sex", p.birth_sex], ["Purpose", p.purpose.replace(/_/g, " ")],
    ["Stage", p.production_stage.replace(/_/g, " ")], ["Status", p.status],
    ["Reproductive status", p.reproductive_status.replace(/_/g, " ")], ["Market status", p.market_status],
    ["Date of birth", p.date_of_birth], ["Current weight (kg)", p.current_weight_kg],
    ["Breed", p.breed_name ?? null], ["Sire", p.sire_ref ?? null], ["Dam", p.dam_ref ?? null],
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <button onClick={() => navigate("/swine")}
        className="mb-4 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft className="h-4 w-4" /> Pig Directory
      </button>
      <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
        {p.name ?? p.internal_ref} <span className="text-gray-400">· {p.internal_ref}</span>
      </h1>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 rounded-xl border border-gray-200 p-4 text-sm dark:border-gray-800 sm:grid-cols-3">
        {facts.map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs uppercase tracking-wide text-gray-400">{k}</dt>
            <dd className="capitalize text-gray-900 dark:text-gray-100">{v ?? "—"}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
          <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Growth</h2>
          <div className="space-y-1 text-sm">
            <Row label="Current weight (kg)" fig={growthQ.data?.current_weight_kg} />
            <Row label="Total gain (kg)" fig={growthQ.data?.total_gain_kg} />
            <Row label="Average daily gain (kg)" fig={growthQ.data?.average_daily_gain_kg} />
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
          <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Market readiness</h2>
          {readyQ.isLoading ? <Skeleton className="h-16 rounded-lg" /> : (
            <>
              <p className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">{ready?.status ?? "—"}</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-gray-500">
                {(ready?.reasons ?? []).map((r: string, i: number) => <li key={i}>{r}</li>)}
              </ul>
            </>
          )}
        </div>
      </div>

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">Timeline</h2>
      {timelineQ.isLoading ? <Skeleton className="h-40 rounded-xl" /> : (
        <ol className="space-y-2">
          {(timelineQ.data ?? []).map((e) => (
            <li key={e.id} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
              <span className="font-medium capitalize text-gray-800 dark:text-gray-200">{e.event_type.replace(/_/g, " ")}</span>
              {e.summary && <span className="text-gray-500"> — {e.summary}</span>}
              {e.occurred_at && <span className="ml-1 text-xs text-gray-400">{e.occurred_at.slice(0, 10)}</span>}
            </li>
          ))}
          {(timelineQ.data ?? []).length === 0 && <li className="text-sm text-gray-400">No events recorded yet.</li>}
        </ol>
      )}
    </div>
  );
}

function Row({ label, fig }: { label: string; fig?: any }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-500">{label}</span>
      <LabelledValue figure={fig} />
    </div>
  );
}
