/** Small Ruminant — Animal Profile (shared): identity + life-history timeline. */
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { getAnimal, getTimeline, type Species } from "@/api/smallRuminant";
import { SPECIES_UI } from "./config";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";

export default function SrProfileScreen({ species }: { species: Species }) {
  const ui = SPECIES_UI[species];
  const { animalId } = useParams();
  const navigate = useNavigate();
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;

  const animalQ = useQuery({
    queryKey: ["sr-animal", species, farmId, animalId],
    queryFn: () => getAnimal(farmId as string, species, animalId as string),
    enabled: !!farmId && !!animalId,
  });
  const timelineQ = useQuery({
    queryKey: ["sr-timeline", species, farmId, animalId],
    queryFn: () => getTimeline(farmId as string, species, animalId as string),
    enabled: !!farmId && !!animalId,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  if (animalQ.isLoading) return <div className="mx-auto max-w-3xl px-4 py-6"><Skeleton className="h-64 rounded-xl" /></div>;
  const a = animalQ.data;
  if (!a) return <p className="py-16 text-center text-sm text-gray-400">Not found.</p>;

  const facts: [string, string | null][] = [
    ["Ref", a.internal_ref], ["Name", a.name], ["Ear tag", a.ear_tag],
    ["Sex", a.sex], ["Purpose", a.purpose.replace(/_/g, " ")], ["Horn status", a.horn_status],
    ["Stage", a.lifecycle_stage.replace(/_/g, " ")], ["Status", a.status],
    ["Reproductive status", a.reproductive_status.replace(/_/g, " ")],
    ["Date of birth", a.date_of_birth], ["Current weight (kg)", a.current_weight_kg],
    ["Breed", a.breed_name ?? null], ["Sire", a.sire_ref ?? null], ["Dam", a.dam_ref ?? null],
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <button onClick={() => navigate(`/${species}`)}
        className="mb-4 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft className="h-4 w-4" /> {ui.title} Directory
      </button>
      <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
        {a.name ?? a.internal_ref} <span className="text-gray-400">· {a.internal_ref}</span>
      </h1>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 rounded-xl border border-gray-200 p-4 text-sm dark:border-gray-800 sm:grid-cols-3">
        {facts.map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs uppercase tracking-wide text-gray-400">{k}</dt>
            <dd className="capitalize text-gray-900 dark:text-gray-100">{v ?? "—"}</dd>
          </div>
        ))}
      </dl>

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700 dark:text-gray-300">Timeline</h2>
      {timelineQ.isLoading ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : (
        <ol className="space-y-2">
          {(timelineQ.data ?? []).map((e) => (
            <li key={e.id} className="rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800">
              <span className="font-medium capitalize text-gray-800 dark:text-gray-200">
                {e.event_type.replace(/_/g, " ")}
              </span>
              {e.summary && <span className="text-gray-500"> — {e.summary}</span>}
              {e.occurred_at && (
                <span className="ml-1 text-xs text-gray-400">{e.occurred_at.slice(0, 10)}</span>
              )}
            </li>
          ))}
          {(timelineQ.data ?? []).length === 0 && (
            <li className="text-sm text-gray-400">No events recorded yet.</li>
          )}
        </ol>
      )}
    </div>
  );
}
