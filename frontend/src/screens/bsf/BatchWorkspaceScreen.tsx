/**
 * BSF — Batch Workspace (Module 16, Frontend Milestone 2).
 *
 * The operational workspace for a single production batch: overview with
 * honesty-labelled metrics + lifecycle pacing, immutable lifecycle history and
 * event timeline, and the deterministic lifecycle actions (advance / move /
 * split / terminate). Every calculation, validation and lineage rule lives in
 * the backend — this screen presents and triggers, it never computes.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, GitBranch, MoveRight, Octagon, TrendingUp } from "lucide-react";

import {
  LIFECYCLE_STAGES, STAGE_LABELS,
  advanceBatch, getBatch, listLifecycle, listTimeline, listUnits,
  moveBatch, splitBatch, terminateBatch,
  type BatchDetail, type Figure,
} from "@/api/bsf";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { TextField } from "@/components/ui/TextField";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { LabelledValue } from "@/components/common/FactBadge";
import { BatchStatusBadge, StageBadge } from "./badges";

const TERMINAL = ["harvested", "completed", "split", "merged", "terminated", "archived"];
const fmtNum = (v: unknown) => (v == null ? "—" : Number(v).toLocaleString());

export default function BatchWorkspaceScreen() {
  const { batchId } = useParams<{ batchId: string }>();
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [action, setAction] = useState<null | "advance" | "move" | "split" | "terminate">(null);

  const batchQ = useQuery({
    queryKey: ["bsf-batch", farmId, batchId],
    queryFn: () => getBatch(farmId as string, batchId as string),
    enabled: !!farmId && !!batchId,
  });
  const lifeQ = useQuery({
    queryKey: ["bsf-batch-life", farmId, batchId],
    queryFn: () => listLifecycle(farmId as string, batchId as string),
    enabled: !!farmId && !!batchId,
  });
  const timelineQ = useQuery({
    queryKey: ["bsf-batch-timeline", farmId, batchId],
    queryFn: () => listTimeline(farmId as string, batchId as string),
    enabled: !!farmId && !!batchId,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["bsf-batch", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["bsf-batch-life", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["bsf-batch-timeline", farmId, batchId] });
    qc.invalidateQueries({ queryKey: ["bsf-batches", farmId] });
  };

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <button
        type="button"
        onClick={() => navigate("/bsf")}
        className="mb-4 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
      >
        <ArrowLeft className="h-4 w-4" /> Production Board
      </button>

      {batchQ.isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-500/30 dark:bg-red-500/10">
          <p className="text-sm text-red-700 dark:text-red-300">Couldn’t load this batch.</p>
          <Button variant="ghost" className="mt-2" onClick={() => batchQ.refetch()}>Try again</Button>
        </div>
      ) : batchQ.isLoading || !batchQ.data ? (
        <div className="space-y-3">
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-40 rounded-xl" />
        </div>
      ) : (
        <BatchView
          batch={batchQ.data}
          life={lifeQ.data ?? []}
          timeline={timelineQ.data ?? []}
          onAction={setAction}
        />
      )}

      {batchQ.data && action && (
        <ActionModals
          action={action}
          onClose={() => setAction(null)}
          farmId={farmId}
          batch={batchQ.data}
          onDone={() => { invalidate(); setAction(null); }}
        />
      )}
    </div>
  );
}

function BatchView({
  batch, life, timeline, onAction,
}: {
  batch: BatchDetail;
  life: Awaited<ReturnType<typeof listLifecycle>>;
  timeline: Awaited<ReturnType<typeof listTimeline>>;
  onAction: (a: "advance" | "move" | "split" | "terminate") => void;
}) {
  const terminal = TERMINAL.includes(batch.status);
  const m = batch.metrics ?? {};
  const pacing = batch.pacing ?? {};

  return (
    <>
      {/* Header */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{batch.batch_number}</h1>
            <BatchStatusBadge status={batch.status} />
          </div>
          {batch.name && <p className="text-sm text-gray-500 dark:text-gray-400">{batch.name}</p>}
          <div className="mt-2 flex items-center gap-2">
            <StageBadge stage={batch.lifecycle_stage} />
            {pacing.status && (
              <span className="text-xs text-gray-500" title={(pacing.status as Figure).detail}>
                {String((pacing.status as Figure).value)}
              </span>
            )}
          </div>
        </div>
        {!terminal && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" leftIcon={<TrendingUp className="h-4 w-4" />} onClick={() => onAction("advance")}>Advance</Button>
            <Button size="sm" variant="ghost" leftIcon={<MoveRight className="h-4 w-4" />} onClick={() => onAction("move")}>Move</Button>
            <Button size="sm" variant="ghost" leftIcon={<GitBranch className="h-4 w-4" />} onClick={() => onAction("split")}>Split</Button>
            <Button size="sm" variant="ghost" leftIcon={<Octagon className="h-4 w-4" />} onClick={() => onAction("terminate")}>Terminate</Button>
          </div>
        )}
      </div>

      {/* Metrics — every figure carries the engine's honesty label */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <MetricTile label="Population" figure={{ label: "recorded", value: batch.population_estimate }} format={fmtNum} />
        <MetricTile label="Avg weight (mg)" figure={m.average_weight_mg} />
        <MetricTile label="Survival" figure={m.survival_rate_pct} suffix="%" />
        <MetricTile label="Capacity used" figure={m.capacity_utilisation_pct} suffix="%" />
        <MetricTile label="Production velocity" figure={m.production_velocity_g_per_day} suffix=" g/day" />
        <MetricTile label="Days in production" figure={m.days_in_production} />
        <MetricTile label="Days in stage" figure={pacing.days_in_stage} />
        <MetricTile label="Expected days" figure={pacing.expected_days} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Lifecycle history (immutable) */}
        <section>
          <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Lifecycle history</h2>
          {life.length === 0 ? (
            <p className="text-sm text-gray-400">No lifecycle events yet.</p>
          ) : (
            <ol className="space-y-2">
              {life.map((e) => (
                <li key={e.id} className="rounded-lg border border-gray-200 bg-white p-3 text-sm dark:border-gray-800 dark:bg-gray-900">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-800 dark:text-gray-200">
                      {e.previous_stage ? `${STAGE_LABELS[e.previous_stage] ?? e.previous_stage} → ` : ""}
                      {STAGE_LABELS[e.new_stage] ?? e.new_stage}
                    </span>
                    <span className="text-xs text-gray-400">{e.occurred_on}</span>
                  </div>
                  {e.observations && <p className="mt-1 text-xs text-gray-500">{e.observations}</p>}
                </li>
              ))}
            </ol>
          )}
        </section>

        {/* Event timeline */}
        <section>
          <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Timeline</h2>
          {timeline.length === 0 ? (
            <p className="text-sm text-gray-400">No events yet.</p>
          ) : (
            <ol className="space-y-2">
              {timeline.map((e) => (
                <li key={e.id} className="flex items-start gap-2 text-sm">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                  <div>
                    <p className="text-gray-800 dark:text-gray-200">{e.summary ?? e.event_type}</p>
                    <p className="text-xs text-gray-400">{new Date(e.created_at).toLocaleDateString()}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  );
}

function MetricTile({ label, figure, format, suffix }: { label: string; figure?: Figure | null; format?: (v: unknown) => string; suffix?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
        <LabelledValue figure={figure} format={(v) => `${format ? format(v) : v}${suffix ?? ""}`} />
      </p>
    </div>
  );
}

// ── Action modals ─────────────────────────────────────────────────────────────

function ActionModals({
  action, onClose, farmId, batch, onDone,
}: {
  action: "advance" | "move" | "split" | "terminate";
  onClose: () => void;
  farmId: string;
  batch: BatchDetail;
  onDone: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const fail = (msg: string) => (e: unknown) => {
    const detail = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
    setError(detail || msg);
  };

  // Advance
  const [toStage, setToStage] = useState("");
  const [allowPremature, setAllowPremature] = useState(false);
  const advanceM = useMutation({
    mutationFn: () => advanceBatch(farmId, batch.id, { to_stage: toStage, allow_premature: allowPremature }),
    onSuccess: onDone,
    onError: fail("Could not advance the batch."),
  });

  // Move
  const unitsQ = useQuery({ queryKey: ["bsf-units", farmId], queryFn: () => listUnits(farmId), enabled: action === "move" });
  const [unitId, setUnitId] = useState<string>(batch.production_unit_id ?? "");
  const moveM = useMutation({
    mutationFn: () => moveBatch(farmId, batch.id, { production_unit_id: unitId || null }),
    onSuccess: onDone,
    onError: fail("Could not move the batch."),
  });

  // Split
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const splitM = useMutation({
    mutationFn: () => splitBatch(farmId, batch.id, { parts: [{ population_estimate: Number(p1) }, { population_estimate: Number(p2) }] }),
    onSuccess: onDone,
    onError: fail("Could not split the batch."),
  });

  // Terminate
  const [reason, setReason] = useState("");
  const terminateM = useMutation({
    mutationFn: () => terminateBatch(farmId, batch.id, { reason: reason || undefined }),
    onSuccess: onDone,
    onError: fail("Could not terminate the batch."),
  });

  const titles = { advance: "Advance lifecycle stage", move: "Move batch", split: "Split batch", terminate: "Terminate batch" };
  const forwardStages = LIFECYCLE_STAGES.filter(
    (s) => LIFECYCLE_STAGES.indexOf(s) > LIFECYCLE_STAGES.indexOf(batch.lifecycle_stage as typeof LIFECYCLE_STAGES[number]),
  );

  return (
    <Modal open onClose={onClose} title={titles[action]}>
      <div className="space-y-4">
        {action === "advance" && (
          <>
            <Select
              label="To stage" value={toStage} onChange={(e) => setToStage(e.target.value)}
              options={[{ value: "", label: "Select…" }, ...forwardStages.map((s) => ({ value: s, label: STAGE_LABELS[s] }))]}
            />
            <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
              <input type="checkbox" checked={allowPremature} onChange={(e) => setAllowPremature(e.target.checked)} />
              Acknowledge advancing before the expected stage duration
            </label>
          </>
        )}
        {action === "move" && (
          <Select
            label="Production unit" value={unitId} onChange={(e) => setUnitId(e.target.value)}
            options={[{ value: "", label: "Unassigned" }, ...(unitsQ.data ?? []).map((u) => ({ value: u.id, label: u.name }))]}
          />
        )}
        {action === "split" && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Part A population" inputMode="numeric" value={p1} onChange={(e) => setP1(e.target.value)} />
            <TextField label="Part B population" inputMode="numeric" value={p2} onChange={(e) => setP2(e.target.value)} />
          </div>
        )}
        {action === "terminate" && (
          <TextField label="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. contamination" />
        )}

        {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          {action === "advance" && <Button loading={advanceM.isPending} disabled={!toStage} onClick={() => { setError(null); advanceM.mutate(); }}>Advance</Button>}
          {action === "move" && <Button loading={moveM.isPending} onClick={() => { setError(null); moveM.mutate(); }}>Move</Button>}
          {action === "split" && <Button loading={splitM.isPending} disabled={!p1 || !p2} onClick={() => { setError(null); splitM.mutate(); }}>Split</Button>}
          {action === "terminate" && <Button loading={terminateM.isPending} onClick={() => { setError(null); terminateM.mutate(); }}>Terminate</Button>}
        </div>
      </div>
    </Modal>
  );
}
