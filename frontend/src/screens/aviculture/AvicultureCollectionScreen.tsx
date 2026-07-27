/**
 * Aviculture — Collection Management (Module 15, Part 2).
 *
 * "Every bird has a complete digital identity." This is the collection home:
 * search and filter the flock of individuals, add a bird (with its data-driven
 * species), and open any bird's full life history. Individual-first, not
 * flock-first — the philosophy that separates aviculture from commercial poultry.
 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bird as BirdIcon, Feather, Plus, Search } from "lucide-react";

import {
  createBird,
  createSpecies,
  listBirds,
  listSpecies,
  type Bird,
  type Species,
} from "@/api/aviculture";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "./badges";
import { AviModal } from "./AviModal";
import { AviSubnav } from "./AviSubnav";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "sold", label: "Sold" },
  { value: "transferred", label: "Transferred" },
  { value: "deceased", label: "Deceased" },
  { value: "archived", label: "Archived" },
];

const SEX_OPTIONS = [
  { value: "unknown", label: "Unknown sex" },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
];

const SPECIES_GROUPS = [
  "parrot", "finch", "canary", "softbill", "pigeon", "dove", "quail",
  "pheasant", "peafowl", "waterfowl", "ornamental_chicken", "other",
];

export default function AvicultureCollectionScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [addOpen, setAddOpen] = useState(false);

  const birdsQ = useQuery({
    queryKey: ["avi-birds", farmId, status, search],
    queryFn: () => listBirds(farmId as string, { status: status || undefined, search: search || undefined }),
    enabled: !!farmId,
  });

  const speciesQ = useQuery({
    queryKey: ["avi-species", farmId],
    queryFn: () => listSpecies(farmId as string),
    enabled: !!farmId,
  });

  if (!farmId) {
    return <p className="py-16 text-center text-sm text-gray-500">Select a farm to open the collection.</p>;
  }

  const birds = birdsQ.data?.birds ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
            <Feather className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Aviculture Collection</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {birdsQ.data ? `${birdsQ.data.total} bird${birdsQ.data.total === 1 ? "" : "s"}` : "Ornamental & specialty birds"}
            </p>
          </div>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>
          Add bird
        </Button>
      </div>

      {/* Aviculture sub-navigation */}
      <AviSubnav farmId={farmId} active="/aviculture" />

      {/* Filters */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row">
        <TextField
          placeholder="Search name, ring, microchip, reference…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          leftIcon={<Search className="h-4 w-4" />}
          className="sm:flex-1"
          aria-label="Search birds"
        />
        <Select
          options={STATUS_OPTIONS}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
          className="sm:w-52"
        />
      </div>

      {/* Body */}
      {birdsQ.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : birds.length === 0 ? (
        <EmptyState
          icon={<BirdIcon className="h-8 w-8" />}
          title={search || status ? "No birds match your filters" : "No birds yet"}
          description={
            search || status
              ? "Try clearing the search or status filter."
              : "Add your first bird to start building its digital identity."
          }
          action={
            !search && !status ? (
              <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>
                Add bird
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {birds.map((bird) => (
            <BirdCard key={bird.id} bird={bird} onClick={() => navigate(`/aviculture/${bird.id}`)} />
          ))}
        </div>
      )}

      <AddBirdModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        farmId={farmId}
        species={speciesQ.data ?? []}
        onCreated={() => {
          qc.invalidateQueries({ queryKey: ["avi-birds", farmId] });
          qc.invalidateQueries({ queryKey: ["avi-species", farmId] });
        }}
      />
    </div>
  );
}

function BirdCard({ bird, onClick }: { bird: Bird; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col rounded-xl border border-gray-200 bg-white p-4 text-left transition hover:border-brand-300 hover:shadow-sm dark:border-gray-800 dark:bg-gray-900 dark:hover:border-brand-500/40"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900 dark:text-gray-100">
            {bird.name || bird.internal_ref}
          </p>
          <p className="truncate text-xs text-gray-500 dark:text-gray-400">
            {bird.species_name ?? "Unknown species"}
            {bird.breed_name ? ` · ${bird.breed_name}` : ""}
          </p>
        </div>
        <StatusBadge status={bird.status} />
      </div>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
        <span className="font-mono">{bird.internal_ref}</span>
        {bird.ring_number && <span>Ring {bird.ring_number}</span>}
        <span className="capitalize">{bird.sex}</span>
        {bird.lifecycle_stage !== "unknown" && <span className="capitalize">{bird.lifecycle_stage}</span>}
      </div>
    </button>
  );
}

function AddBirdModal({
  open,
  onClose,
  farmId,
  species,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  farmId: string;
  species: Species[];
  onCreated: () => void;
}) {
  const qc = useQueryClient();
  const [speciesId, setSpeciesId] = useState("");
  const [name, setName] = useState("");
  const [ring, setRing] = useState("");
  const [sex, setSex] = useState("unknown");
  const [error, setError] = useState<string | null>(null);

  // Inline species creation when the catalog is empty.
  const [newSpecies, setNewSpecies] = useState("");
  const [newGroup, setNewGroup] = useState("parrot");

  const speciesOptions = useMemo(
    () => [{ value: "", label: "Select species…" }, ...species.map((s) => ({ value: s.id, label: s.common_name }))],
    [species],
  );

  const createSpeciesM = useMutation({
    mutationFn: () => createSpecies(farmId, { common_name: newSpecies.trim(), species_group: newGroup }),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["avi-species", farmId] });
      setSpeciesId(s.id);
      setNewSpecies("");
    },
    onError: () => setError("Could not add species."),
  });

  const createBirdM = useMutation({
    mutationFn: () =>
      createBird(farmId, {
        species_id: speciesId,
        name: name.trim() || undefined,
        ring_number: ring.trim() || undefined,
        sex,
      }),
    onSuccess: () => {
      onCreated();
      reset();
      onClose();
    },
    onError: (e: unknown) => {
      const msg =
        (e as { response?: { data?: { error?: { message?: string }; detail?: { message?: string } } } })?.response
          ?.data?.error?.message ?? "Could not add bird. Check the details and try again.";
      setError(msg);
    },
  });

  function reset() {
    setSpeciesId("");
    setName("");
    setRing("");
    setSex("unknown");
    setError(null);
  }

  const canSubmit = !!speciesId && !createBirdM.isPending;

  return (
    <AviModal open={open} onClose={onClose} title="Add bird">
      <div className="space-y-4">
        {species.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 p-3 dark:border-gray-700">
            <p className="mb-2 text-sm text-gray-600 dark:text-gray-300">
              Your species catalog is empty. Add a species first (it becomes reusable across the collection).
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <TextField
                placeholder="e.g. African Grey"
                value={newSpecies}
                onChange={(e) => setNewSpecies(e.target.value)}
                className="sm:flex-1"
                aria-label="New species name"
              />
              <Select
                options={SPECIES_GROUPS.map((g) => ({ value: g, label: g.replace("_", " ") }))}
                value={newGroup}
                onChange={(e) => setNewGroup(e.target.value)}
                aria-label="Species group"
                className="sm:w-40"
              />
              <Button
                variant="secondary"
                loading={createSpeciesM.isPending}
                disabled={!newSpecies.trim()}
                onClick={() => createSpeciesM.mutate()}
              >
                Add
              </Button>
            </div>
          </div>
        ) : (
          <Select
            label="Species"
            options={speciesOptions}
            value={speciesId}
            onChange={(e) => setSpeciesId(e.target.value)}
          />
        )}

        <TextField label="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Apollo" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField label="Ring number (optional)" value={ring} onChange={(e) => setRing(e.target.value)} />
          <Select
            label="Sex"
            options={SEX_OPTIONS}
            value={sex}
            onChange={(e) => setSex(e.target.value)}
          />
        </div>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={createBirdM.isPending} disabled={!canSubmit} onClick={() => { setError(null); createBirdM.mutate(); }}>
            Add bird
          </Button>
        </div>
      </div>
    </AviModal>
  );
}
