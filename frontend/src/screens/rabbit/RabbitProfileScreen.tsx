/**
 * Rabbit — Profile (Module 17, Frontend).
 *
 * Identity, classification, biology and the append-only timeline for a single
 * rabbit. Presentation-only; the backend owns every fact and transition.
 */
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { getRabbit, getTimeline, STAGE_LABELS } from "@/api/rabbit";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { RabbitSubnav } from "./RabbitSubnav";

export default function RabbitProfileScreen() {
  const { rabbitId } = useParams<{ rabbitId: string }>();
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();

  const rabbitQ = useQuery({
    queryKey: ["rabbit", farmId, rabbitId],
    queryFn: () => getRabbit(farmId as string, rabbitId as string),
    enabled: !!farmId && !!rabbitId,
  });
  const timelineQ = useQuery({
    queryKey: ["rabbit-timeline", farmId, rabbitId],
    queryFn: () => getTimeline(farmId as string, rabbitId as string),
    enabled: !!farmId && !!rabbitId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <RabbitSubnav active="/rabbit" />
      <button
        onClick={() => navigate("/rabbit")}
        className="mb-4 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
      >
        <ArrowLeft className="h-4 w-4" /> Directory
      </button>

      {rabbitQ.isLoading || !rabbitQ.data ? (
        <Skeleton className="h-48 rounded-xl" />
      ) : (
        <>
          <div className="mb-5">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              {rabbitQ.data.name ?? rabbitQ.data.internal_ref}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {rabbitQ.data.internal_ref} · <span className="capitalize">{rabbitQ.data.sex}</span> ·{" "}
              <span className="capitalize">{rabbitQ.data.status}</span>
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Field label="Breed" value={rabbitQ.data.breed_name} />
            <Field label="Bloodline" value={rabbitQ.data.bloodline_name} />
            <Field label="Cage" value={rabbitQ.data.cage_name} />
            <Field label="Stage" value={STAGE_LABELS[rabbitQ.data.lifecycle_stage] ?? rabbitQ.data.lifecycle_stage} />
            <Field label="Purpose" value={rabbitQ.data.purpose} />
            <Field label="Ear tag" value={rabbitQ.data.ear_tag} />
            <Field label="Reproductive" value={rabbitQ.data.reproductive_status} />
            <Field label="DOB" value={rabbitQ.data.date_of_birth} />
            <Field label="Current weight (g)" value={rabbitQ.data.current_weight_g} />
            <Field label="Sire" value={rabbitQ.data.sire_ref} />
            <Field label="Dam" value={rabbitQ.data.dam_ref} />
          </div>
        </>
      )}

      <section className="mt-8">
        <h2 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Timeline</h2>
        {timelineQ.isLoading ? (
          <Skeleton className="h-32 rounded-xl" />
        ) : (timelineQ.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-400">No events recorded yet.</p>
        ) : (
          <ul className="space-y-2">
            {timelineQ.data!.map((e) => (
              <li key={e.id} className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">
                    {e.event_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-gray-400">{new Date(e.occurred_at).toLocaleDateString()}</span>
                </div>
                {e.summary && <p className="text-sm text-gray-600 dark:text-gray-400">{e.summary}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-medium capitalize text-gray-900 dark:text-gray-100">{value ?? "—"}</p>
    </div>
  );
}
