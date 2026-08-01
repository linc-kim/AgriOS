/**
 * Rabbit — Growth Workspace (Module 17, Frontend Increment 2).
 *
 * Per-rabbit weight history, deterministic growth analysis (ADG, deviation,
 * percentile) and the feed summary with FCR. All growth/FCR math is the backend's;
 * feed consumption reuses the platform Inventory module.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LineChart } from "lucide-react";

import { listWeights, recordWeight, getGrowthAnalysis, getFeedSummary, recordFeed } from "@/api/rabbitGrowth";
import { listRabbits } from "@/api/rabbit";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { LabelledValue } from "@/components/common/FactBadge";
import { RabbitSubnav } from "./RabbitSubnav";

const inputCls = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900";
const today = () => new Date().toISOString().slice(0, 10);

export default function RabbitGrowthScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [rabbitId, setRabbitId] = useState("");
  const [modal, setModal] = useState<"weight" | "feed" | null>(null);

  const rabbitsQ = useQuery({ queryKey: ["rabbits-active", farmId], queryFn: () => listRabbits(farmId as string, { status: "active", limit: 200 }), enabled: !!farmId });
  const effId = rabbitId || rabbitsQ.data?.data[0]?.id || "";

  const weightsQ = useQuery({ queryKey: ["rabbit-weights", farmId, effId], queryFn: () => listWeights(farmId as string, effId), enabled: !!farmId && !!effId });
  const growthQ = useQuery({ queryKey: ["rabbit-growth", farmId, effId], queryFn: () => getGrowthAnalysis(farmId as string, effId), enabled: !!farmId && !!effId });
  const feedQ = useQuery({ queryKey: ["rabbit-feed-summary", farmId, effId], queryFn: () => getFeedSummary(farmId as string, effId), enabled: !!farmId && !!effId });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["rabbit-weights", farmId, effId] });
    qc.invalidateQueries({ queryKey: ["rabbit-growth", farmId, effId] });
    qc.invalidateQueries({ queryKey: ["rabbit-feed-summary", farmId, effId] });
  };
  const weightM = useMutation({ mutationFn: (w: number) => recordWeight(farmId as string, effId, { recorded_on: today(), weight_g: w }), onSuccess: () => { invalidate(); setModal(null); } });
  const feedM = useMutation({ mutationFn: (v: { kg: number; cost?: number }) => recordFeed(farmId as string, { rabbit_id: effId, quantity_kg: v.kg, fed_on: today(), cost: v.cost ?? null }), onSuccess: () => { invalidate(); setModal(null); } });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  const analysis = growthQ.data?.analysis;
  const feedSum = feedQ.data?.summary;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <RabbitSubnav active="/rabbit/growth" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <LineChart className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Growth &amp; Feed</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Weights, growth analysis &amp; feed efficiency</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={!effId} onClick={() => setModal("weight")}>Record weight</Button>
          <Button variant="secondary" disabled={!effId} onClick={() => setModal("feed")}>Record feed</Button>
        </div>
      </div>

      <div className="mb-4">
        <select value={effId} onChange={(e) => setRabbitId(e.target.value)} className={inputCls}>
          {(rabbitsQ.data?.data ?? []).map((r) => <option key={r.id} value={r.id}>{r.internal_ref}{r.name ? ` · ${r.name}` : ""}</option>)}
        </select>
      </div>

      {!effId ? <p className="text-sm text-gray-400">No active rabbits to analyse.</p> : (
        <div className="space-y-6">
          <section>
            <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Growth analysis</h2>
            {growthQ.isLoading || !analysis ? <Skeleton className="h-20 rounded-xl" /> : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Tile label="Latest weight (g)" figure={analysis.latest_weight_g} />
                <Tile label="Total gain (g)" figure={analysis.total_gain_g} />
                <Tile label="ADG (g/day)" figure={analysis.average_daily_gain} />
                <Tile label="Deviation (g)" figure={analysis.deviation_g} />
                <Tile label="Expected wt (g)" figure={analysis.expected_weight_g} />
                <Tile label="Herd percentile" figure={growthQ.data!.herd_percentile_pct} suffix="%" />
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Feed efficiency</h2>
            {feedQ.isLoading || !feedSum ? <Skeleton className="h-20 rounded-xl" /> : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Tile label="Feed events" figure={feedSum.feeding_events} />
                <Tile label="Total feed (kg)" figure={feedSum.total_feed_kg} />
                <Tile label="Total cost" figure={feedSum.total_cost} />
                <Tile label="FCR" figure={feedSum.feed_conversion_ratio} />
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Weight history</h2>
            {weightsQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (weightsQ.data ?? []).length === 0 ? (
              <p className="text-sm text-gray-400">No weights recorded.</p>
            ) : (
              <ul className="space-y-1">
                {weightsQ.data!.map((w) => (
                  <li key={w.id} className="flex justify-between rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-800 dark:bg-gray-900">
                    <span>{w.recorded_on}{w.age_days != null ? ` · ${w.age_days}d` : ""}</span>
                    <span className="font-medium">{w.weight_g} g</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {modal === "weight" && (
        <NumberModal title="Record weight (g)" submitting={weightM.isPending} onCancel={() => setModal(null)} onSubmit={(v) => weightM.mutate(v)} />
      )}
      {modal === "feed" && (
        <FeedModal submitting={feedM.isPending} onCancel={() => setModal(null)} onSubmit={(kg, cost) => feedM.mutate({ kg, cost })} />
      )}
    </div>
  );
}

function Tile({ label, figure, suffix }: { label: string; figure?: { label: string; value: unknown; detail?: string }; suffix?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100"><LabelledValue figure={figure} format={(v) => `${v}${suffix ?? ""}`} /></p>
    </div>
  );
}

function NumberModal({ title, onSubmit, onCancel, submitting }: { title: string; onSubmit: (v: number) => void; onCancel: () => void; submitting: boolean }) {
  const [val, setVal] = useState("");
  return (
    <Modal open onClose={onCancel} title={title}>
      <div className="space-y-3">
        <input type="number" min={0} value={val} onChange={(e) => setVal(e.target.value)} className={inputCls} />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button loading={submitting} disabled={!val} onClick={() => onSubmit(Number(val))}>Save</Button>
        </div>
      </div>
    </Modal>
  );
}

function FeedModal({ onSubmit, onCancel, submitting }: { onSubmit: (kg: number, cost?: number) => void; onCancel: () => void; submitting: boolean }) {
  const [kg, setKg] = useState("");
  const [cost, setCost] = useState("");
  return (
    <Modal open onClose={onCancel} title="Record feed">
      <div className="space-y-3">
        <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Quantity (kg)</span>
          <input type="number" min={0} step="0.001" value={kg} onChange={(e) => setKg(e.target.value)} className={inputCls} /></label>
        <label className="block"><span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">Cost (optional)</span>
          <input type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} className={inputCls} /></label>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button loading={submitting} disabled={!kg} onClick={() => onSubmit(Number(kg), cost ? Number(cost) : undefined)}>Save</Button>
        </div>
      </div>
    </Modal>
  );
}
