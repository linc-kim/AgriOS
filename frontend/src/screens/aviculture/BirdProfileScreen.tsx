/**
 * Aviculture — Bird Profile (Module 15, Part 2).
 *
 * A bird's complete digital identity and permanent life history: overview,
 * timeline (append-only events), ownership chain, and attachments. Lifecycle
 * actions (edit, archive, transfer, sell, death) each record history rather than
 * overwrite it — a sold or deceased bird stays in the record forever.
 */
import { useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight, ArrowLeft, Archive, ArchiveRestore, FileText, GitBranch, HeartPulse,
  ImagePlus, Pencil, Plus, ScrollText, ShoppingCart, Skull, Stethoscope, Users,
} from "lucide-react";

import { getOffspring, getPedigree, type PedigreeNode } from "@/api/breeding";
import { addHealthRecord, getWeightTrend, listHealthRecords } from "@/api/avicultureHealth";

import {
  addDocument, addMedia, archiveBird, getBird, getDocuments, getMedia,
  getOwnership, getTimeline, recordDeath, restoreBird, sellBird, transferBird, updateBird,
} from "@/api/aviculture";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/cn";
import { FactBadge, StatusBadge, eventLabel, eventDot } from "./badges";
import { AviModal } from "./AviModal";

type Tab = "overview" | "pedigree" | "health" | "timeline" | "ownership" | "media" | "documents";
const TABS: { key: Tab; label: string; icon: typeof Users }[] = [
  { key: "overview", label: "Overview", icon: HeartPulse },
  { key: "pedigree", label: "Pedigree", icon: GitBranch },
  { key: "health", label: "Health", icon: Stethoscope },
  { key: "timeline", label: "Timeline", icon: ScrollText },
  { key: "ownership", label: "Ownership", icon: Users },
  { key: "media", label: "Media", icon: ImagePlus },
  { key: "documents", label: "Documents", icon: FileText },
];

const TERMINAL = new Set(["sold", "transferred", "deceased"]);

export default function BirdProfileScreen() {
  const { birdId = "" } = useParams();
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [action, setAction] = useState<null | "edit" | "transfer" | "sell" | "death">(null);

  const birdQ = useQuery({
    queryKey: ["avi-bird", farmId, birdId],
    queryFn: () => getBird(farmId as string, birdId),
    enabled: !!farmId && !!birdId,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["avi-bird", farmId, birdId] });
    qc.invalidateQueries({ queryKey: ["avi-birds", farmId] });
    qc.invalidateQueries({ queryKey: ["avi-timeline", farmId, birdId] });
    qc.invalidateQueries({ queryKey: ["avi-ownership", farmId, birdId] });
  };

  const archiveM = useMutation({
    mutationFn: () => archiveBird(farmId as string, birdId),
    onSuccess: invalidate,
  });
  const restoreM = useMutation({
    mutationFn: () => restoreBird(farmId as string, birdId),
    onSuccess: invalidate,
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;
  if (birdQ.isLoading) return <div className="mx-auto max-w-4xl px-4 py-6"><Skeleton className="h-40 rounded-xl" /></div>;
  if (birdQ.isError || !birdQ.data) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <EmptyState title="Bird not found" description="It may have been removed or belongs to another farm."
          action={<Button variant="secondary" onClick={() => navigate("/aviculture")}>Back to collection</Button>} />
      </div>
    );
  }

  const bird = birdQ.data;
  const isTerminal = TERMINAL.has(bird.status);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <button
        type="button"
        onClick={() => navigate("/aviculture")}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
      >
        <ArrowLeft className="h-4 w-4" /> Collection
      </button>

      {/* Header */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {bird.name || bird.internal_ref}
              </h1>
              <StatusBadge status={bird.status} />
            </div>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {bird.species_name ?? "Unknown species"}
              {bird.breed_name ? ` · ${bird.breed_name}` : ""} · <span className="font-mono">{bird.internal_ref}</span>
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!isTerminal && (
              <Button variant="secondary" leftIcon={<Pencil className="h-4 w-4" />} onClick={() => setAction("edit")}>
                Edit
              </Button>
            )}
            {bird.status === "active" && (
              <>
                <Button variant="ghost" leftIcon={<ArrowLeftRight className="h-4 w-4" />} onClick={() => setAction("transfer")}>
                  Transfer
                </Button>
                <Button variant="ghost" leftIcon={<ShoppingCart className="h-4 w-4" />} onClick={() => setAction("sell")}>
                  Sell
                </Button>
                <Button variant="ghost" leftIcon={<Skull className="h-4 w-4" />} onClick={() => setAction("death")}>
                  Death
                </Button>
                <Button variant="ghost" leftIcon={<Archive className="h-4 w-4" />} loading={archiveM.isPending}
                  onClick={() => archiveM.mutate()}>
                  Archive
                </Button>
              </>
            )}
            {bird.status === "archived" && (
              <Button variant="secondary" leftIcon={<ArchiveRestore className="h-4 w-4" />} loading={restoreM.isPending}
                onClick={() => restoreM.mutate()}>
                Restore
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mt-5 flex gap-1 overflow-x-auto border-b border-gray-200 dark:border-gray-800">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition",
              tab === t.key
                ? "border-brand-500 text-brand-700 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300",
            )}
          >
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </div>

      <div className="py-5">
        {tab === "overview" && <Overview bird={bird} />}
        {tab === "pedigree" && <PedigreeTab farmId={farmId} birdId={birdId} />}
        {tab === "health" && <HealthTab farmId={farmId} birdId={birdId} />}
        {tab === "timeline" && <Timeline farmId={farmId} birdId={birdId} />}
        {tab === "ownership" && <OwnershipTab farmId={farmId} birdId={birdId} />}
        {tab === "media" && <MediaTab farmId={farmId} birdId={birdId} onChange={invalidate} />}
        {tab === "documents" && <DocumentsTab farmId={farmId} birdId={birdId} onChange={invalidate} />}
      </div>

      {/* Action modals */}
      {action === "edit" && <EditModal bird={bird} farmId={farmId} onClose={() => setAction(null)} onSaved={invalidate} />}
      {action === "transfer" && <TransferModal farmId={farmId} birdId={birdId} onClose={() => setAction(null)} onDone={invalidate} />}
      {action === "sell" && <SellModal farmId={farmId} birdId={birdId} onClose={() => setAction(null)} onDone={invalidate} />}
      {action === "death" && <DeathModal farmId={farmId} birdId={birdId} onClose={() => setAction(null)} onDone={invalidate} />}
    </div>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-900 dark:text-gray-100">{value || <span className="text-gray-400">—</span>}</dd>
    </div>
  );
}

function Overview({ bird }: { bird: import("@/api/aviculture").BirdDetail }) {
  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Field label="Reference" value={<span className="font-mono">{bird.internal_ref}</span>} />
        <Field label="Ring number" value={bird.ring_number} />
        <Field label="Microchip" value={bird.microchip} />
        <Field label="Sex" value={<span className="capitalize">{bird.sex}</span>} />
        <Field label="Sex method" value={<span className="capitalize">{bird.sex_method}</span>} />
        <Field label="DNA status" value={<span className="capitalize">{bird.dna_status}</span>} />
        <Field label="Lifecycle stage" value={<span className="capitalize">{bird.lifecycle_stage}</span>} />
        <Field label="Colour" value={bird.colour_description} />
        <Field label="Hatch date" value={bird.hatch_date} />
        <Field label="Acquisition" value={<span className="capitalize">{bird.acquisition_type}</span>} />
        <Field label="Current owner" value={bird.current_owner?.owner_name} />
      </dl>

      {bird.mutations.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">Genetics</h3>
          <div className="flex flex-wrap gap-2">
            {bird.mutations.map((m) => (
              <span key={m.id} className="rounded-full bg-amber-50 px-2.5 py-1 text-xs text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                {m.mutation_name} · {m.zygosity}
              </span>
            ))}
          </div>
        </div>
      )}

      {bird.tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {bird.tags.map((t) => (
            <span key={t} className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">#{t}</span>
          ))}
        </div>
      )}

      {bird.notes && <p className="whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">{bird.notes}</p>}
    </div>
  );
}

function Timeline({ farmId, birdId }: { farmId: string; birdId: string }) {
  const q = useQuery({ queryKey: ["avi-timeline", farmId, birdId], queryFn: () => getTimeline(farmId, birdId) });
  if (q.isLoading) return <Skeleton className="h-40 rounded-xl" />;
  const events = q.data ?? [];
  if (events.length === 0) return <EmptyState title="No events yet" />;
  return (
    <ol className="relative space-y-4 border-l border-gray-200 pl-5 dark:border-gray-800">
      {events.map((e) => (
        <li key={e.id} className="relative">
          <span className={cn("absolute -left-[26px] top-1 h-3 w-3 rounded-full ring-4 ring-white dark:ring-gray-900", eventDot(e.event_type))} />
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{e.title || eventLabel(e.event_type)}</p>
            <time className="text-xs text-gray-400">{e.occurred_on}</time>
          </div>
          {e.description && <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">{e.description}</p>}
        </li>
      ))}
    </ol>
  );
}

const HEALTH_TYPES = [
  "observation", "exam", "weight", "treatment", "medication", "vaccination", "deworming",
  "supplement", "vet_visit", "lab_report", "surgery", "injury", "necropsy", "preventive",
];

function HealthTab({ farmId, birdId }: { farmId: string; birdId: string }) {
  const qc = useQueryClient();
  const recordsQ = useQuery({ queryKey: ["avi-health", farmId, birdId], queryFn: () => listHealthRecords(farmId, birdId) });
  const trendQ = useQuery({ queryKey: ["avi-weight-trend", farmId, birdId], queryFn: () => getWeightTrend(farmId, birdId) });

  const [type, setType] = useState("observation");
  const [title, setTitle] = useState("");
  const [weight, setWeight] = useState("");
  const add = useMutation({
    mutationFn: () => addHealthRecord(farmId, birdId, {
      record_type: type, title: title.trim() || undefined,
      weight_grams: type === "weight" && weight ? weight : undefined,
    }),
    onSuccess: () => {
      setTitle(""); setWeight("");
      qc.invalidateQueries({ queryKey: ["avi-health", farmId, birdId] });
      qc.invalidateQueries({ queryKey: ["avi-weight-trend", farmId, birdId] });
      qc.invalidateQueries({ queryKey: ["avi-timeline", farmId, birdId] });
    },
  });

  const t = trendQ.data?.trend;
  return (
    <div className="space-y-5">
      {t && t.count.value > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <div className="flex items-center justify-between"><p className="text-xs uppercase tracking-wide text-gray-400">Latest weight</p><FactBadge label={t.latest.label} /></div>
            <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{t.latest.value != null ? `${t.latest.value} g` : "—"}</p>
          </div>
          <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <div className="flex items-center justify-between"><p className="text-xs uppercase tracking-wide text-gray-400">Change</p><FactBadge label={t.change_grams.label} /></div>
            <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{t.change_grams.value != null ? `${t.change_grams.value} g` : "—"}</p>
          </div>
          <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <p className="text-xs uppercase tracking-wide text-gray-400">Direction</p>
            <p className="mt-1 text-lg font-semibold capitalize text-gray-900 dark:text-gray-100">{t.direction.value ?? "—"}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800 sm:flex-row">
        <Select options={HEALTH_TYPES.map((x) => ({ value: x, label: x.replace(/_/g, " ") }))} value={type} onChange={(e) => setType(e.target.value)} aria-label="Record type" className="sm:w-40" />
        {type === "weight"
          ? <TextField placeholder="Weight (g)" inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} className="sm:flex-1" aria-label="Weight grams" />
          : <TextField placeholder="Title / note" value={title} onChange={(e) => setTitle(e.target.value)} className="sm:flex-1" aria-label="Title" />}
        <Button leftIcon={<Plus className="h-4 w-4" />} loading={add.isPending}
          disabled={type === "weight" ? !weight : !title.trim()} onClick={() => add.mutate()}>Add</Button>
      </div>

      {recordsQ.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (recordsQ.data ?? []).length === 0 ? (
        <EmptyState title="No health records yet" />
      ) : (
        <div className="space-y-2">
          {(recordsQ.data ?? []).map((r) => (
            <div key={r.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">
                  {r.title || r.record_type.replace(/_/g, " ")}
                  {r.weight_grams ? ` — ${r.weight_grams} g` : ""}
                </p>
                <span className="text-xs text-gray-400">{r.recorded_on}</span>
              </div>
              <p className="text-xs capitalize text-gray-500 dark:text-gray-400">
                {r.record_type.replace(/_/g, " ")}{r.severity ? ` · ${r.severity}` : ""}{r.status !== "recorded" ? ` · ${r.status}` : ""}
              </p>
              {Boolean((r.details as Record<string, unknown> | null)?._disclaimer) && (
                <p className="mt-1 text-xs italic text-amber-600 dark:text-amber-400">⚕ {String((r.details as Record<string, unknown>)._disclaimer)}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PedigreeTab({ farmId, birdId }: { farmId: string; birdId: string }) {
  const ped = useQuery({ queryKey: ["avi-pedigree", farmId, birdId], queryFn: () => getPedigree(farmId, birdId) });
  const off = useQuery({ queryKey: ["avi-offspring", farmId, birdId], queryFn: () => getOffspring(farmId, birdId) });
  if (ped.isLoading) return <Skeleton className="h-40 rounded-xl" />;
  const p = ped.data;
  if (!p) return <EmptyState title="No pedigree" />;
  const f = p.inbreeding_coefficient;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-wide text-gray-400">Inbreeding coefficient (F)</p>
            <FactBadge label={f.label} />
          </div>
          <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">{f.value.toFixed(3)}</p>
          {f.detail && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{f.detail}</p>}
        </div>
        <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
          <p className="text-xs uppercase tracking-wide text-gray-400">Founder lines</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">{p.founders.length}</p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Lineage roots with unknown parents.</p>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">Ancestry</h3>
        <PedigreeTree node={p.ancestry} />
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
          Offspring ({off.data?.offspring.length ?? 0})
        </h3>
        {(off.data?.offspring ?? []).length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">No recorded offspring.</p>
        ) : (
          <div className="space-y-1">
            {(off.data?.offspring ?? []).map((o) => (
              <div key={o.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-2 text-sm dark:border-gray-800">
                <span className="text-gray-900 dark:text-gray-100">{o.name || o.internal_ref}</span>
                <span className="text-xs capitalize text-gray-400">{o.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PedigreeTree({ node, depth = 0 }: { node: PedigreeNode; depth?: number }) {
  if (node.unknown || !node.id) {
    return <span className="text-xs italic text-gray-400">unknown</span>;
  }
  return (
    <div className={cn("text-sm", depth > 0 && "border-l border-gray-200 pl-3 dark:border-gray-800")}>
      <span className="font-mono text-gray-700 dark:text-gray-300">{String(node.id).slice(0, 8)}</span>
      {node.has_more && <span className="ml-1 text-xs text-gray-400">…</span>}
      {(node.sire || node.dam) && (
        <div className="mt-1 space-y-1">
          {node.sire && <div className="flex gap-2"><span className="text-xs text-sky-500">♂</span><PedigreeTree node={node.sire} depth={depth + 1} /></div>}
          {node.dam && <div className="flex gap-2"><span className="text-xs text-pink-500">♀</span><PedigreeTree node={node.dam} depth={depth + 1} /></div>}
        </div>
      )}
    </div>
  );
}

function OwnershipTab({ farmId, birdId }: { farmId: string; birdId: string }) {
  const q = useQuery({ queryKey: ["avi-ownership", farmId, birdId], queryFn: () => getOwnership(farmId, birdId) });
  if (q.isLoading) return <Skeleton className="h-40 rounded-xl" />;
  const rows = q.data ?? [];
  if (rows.length === 0) return <EmptyState title="No ownership records" />;
  return (
    <div className="space-y-2">
      {rows.map((o) => (
        <div key={o.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-800">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {o.owner_name} <span className="font-normal capitalize text-gray-400">· {o.owner_type}</span>
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {o.from_date ?? "—"} → {o.to_date ?? "present"} · <span className="capitalize">{o.acquisition}</span>
            </p>
          </div>
          {o.is_current && (
            <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
              Current
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function MediaTab({ farmId, birdId, onChange }: { farmId: string; birdId: string; onChange: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["avi-media", farmId, birdId], queryFn: () => getMedia(farmId, birdId) });
  const [url, setUrl] = useState("");
  const [caption, setCaption] = useState("");
  const m = useMutation({
    mutationFn: () => addMedia(farmId, birdId, { media_type: "photo", url: url.trim(), caption: caption.trim() || undefined }),
    onSuccess: () => { setUrl(""); setCaption(""); qc.invalidateQueries({ queryKey: ["avi-media", farmId, birdId] }); onChange(); },
  });
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800 sm:flex-row">
        <TextField placeholder="Image URL" value={url} onChange={(e) => setUrl(e.target.value)} className="sm:flex-1" aria-label="Image URL" />
        <TextField placeholder="Caption (optional)" value={caption} onChange={(e) => setCaption(e.target.value)} className="sm:w-48" aria-label="Caption" />
        <Button leftIcon={<ImagePlus className="h-4 w-4" />} loading={m.isPending} disabled={!url.trim()} onClick={() => m.mutate()}>Add</Button>
      </div>
      {q.isLoading ? <Skeleton className="h-32 rounded-xl" /> : (q.data ?? []).length === 0 ? <EmptyState title="No media yet" /> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {(q.data ?? []).map((md) => (
            <figure key={md.id} className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
              {md.url && <img src={md.url} alt={md.caption ?? "Bird media"} className="aspect-square w-full object-cover" loading="lazy" />}
              {md.caption && <figcaption className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">{md.caption}</figcaption>}
            </figure>
          ))}
        </div>
      )}
    </div>
  );
}

const DOC_TYPES = [
  "dna_certificate", "health_certificate", "import_permit", "export_permit",
  "lab_report", "ownership", "invoice", "contract", "other",
];

function DocumentsTab({ farmId, birdId, onChange }: { farmId: string; birdId: string; onChange: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["avi-docs", farmId, birdId], queryFn: () => getDocuments(farmId, birdId) });
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("dna_certificate");
  const m = useMutation({
    mutationFn: () => addDocument(farmId, birdId, { document_type: docType, url: url.trim(), title: title.trim() || undefined }),
    onSuccess: () => { setUrl(""); setTitle(""); qc.invalidateQueries({ queryKey: ["avi-docs", farmId, birdId] }); onChange(); },
  });
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Select options={DOC_TYPES.map((d) => ({ value: d, label: d.replace(/_/g, " ") }))} value={docType}
            onChange={(e) => setDocType(e.target.value)} aria-label="Document type" className="sm:w-48" />
          <TextField placeholder="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} className="sm:flex-1" aria-label="Document title" />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <TextField placeholder="Document URL" value={url} onChange={(e) => setUrl(e.target.value)} className="sm:flex-1" aria-label="Document URL" />
          <Button leftIcon={<FileText className="h-4 w-4" />} loading={m.isPending} disabled={!url.trim()} onClick={() => m.mutate()}>Add</Button>
        </div>
      </div>
      {q.isLoading ? <Skeleton className="h-24 rounded-xl" /> : (q.data ?? []).length === 0 ? <EmptyState title="No documents yet" /> : (
        <div className="space-y-2">
          {(q.data ?? []).map((d) => (
            <a key={d.id} href={d.url ?? "#"} target="_blank" rel="noreferrer"
              className="flex items-center justify-between rounded-lg border border-gray-200 p-3 hover:border-brand-300 dark:border-gray-800">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{d.title || d.document_type.replace(/_/g, " ")}</p>
                <p className="text-xs capitalize text-gray-500 dark:text-gray-400">
                  {d.document_type.replace(/_/g, " ")}{d.expires_on ? ` · expires ${d.expires_on}` : ""}{d.is_restricted ? " · restricted" : ""}
                </p>
              </div>
              <FileText className="h-4 w-4 text-gray-400" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Action modals ─────────────────────────────────────────────────────────────

function useActionError() {
  const [error, setError] = useState<string | null>(null);
  const onError = (e: unknown) => {
    const msg = (e as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message
      ?? "Something went wrong. Please try again.";
    setError(msg);
  };
  return { error, setError, onError };
}

function EditModal({ bird, farmId, onClose, onSaved }: {
  bird: import("@/api/aviculture").BirdDetail; farmId: string; onClose: () => void; onSaved: () => void;
}) {
  const [name, setName] = useState(bird.name ?? "");
  const [ring, setRing] = useState(bird.ring_number ?? "");
  const [stage, setStage] = useState(bird.lifecycle_stage);
  const { error, onError } = useActionError();
  const m = useMutation({
    mutationFn: () => updateBird(farmId, bird.id, { name: name.trim() || undefined, ring_number: ring.trim() || undefined, lifecycle_stage: stage }),
    onSuccess: () => { onSaved(); onClose(); },
    onError,
  });
  return (
    <AviModal open onClose={onClose} title="Edit bird">
      <div className="space-y-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField label="Ring number" value={ring} onChange={(e) => setRing(e.target.value)} />
        <Select label="Lifecycle stage"
          options={["unknown", "chick", "juvenile", "adult", "breeding", "retired"].map((s) => ({ value: s, label: s }))}
          value={stage} onChange={(e) => setStage(e.target.value)} />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} onClick={() => m.mutate()}>Save</Button></div>
      </div>
    </AviModal>
  );
}

function TransferModal({ farmId, birdId, onClose, onDone }: { farmId: string; birdId: string; onClose: () => void; onDone: () => void }) {
  const [owner, setOwner] = useState("");
  const [dest, setDest] = useState("");
  const { error, onError } = useActionError();
  const m = useMutation({
    mutationFn: () => transferBird(farmId, birdId, { to_owner_name: owner.trim(), destination: dest.trim() || undefined }),
    onSuccess: () => { onDone(); onClose(); }, onError,
  });
  return (
    <AviModal open onClose={onClose} title="Transfer bird">
      <div className="space-y-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">Records a permanent transfer of custody. The bird stays in its history.</p>
        <TextField label="New owner / recipient" value={owner} onChange={(e) => setOwner(e.target.value)} />
        <TextField label="Destination (optional)" value={dest} onChange={(e) => setDest(e.target.value)} />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!owner.trim()} onClick={() => m.mutate()}>Transfer</Button></div>
      </div>
    </AviModal>
  );
}

function SellModal({ farmId, birdId, onClose, onDone }: { farmId: string; birdId: string; onClose: () => void; onDone: () => void }) {
  const [buyer, setBuyer] = useState("");
  const [price, setPrice] = useState("");
  const { error, onError } = useActionError();
  const m = useMutation({
    mutationFn: () => sellBird(farmId, birdId, { buyer_name: buyer.trim(), price: price.trim() || undefined }),
    onSuccess: () => { onDone(); onClose(); }, onError,
  });
  return (
    <AviModal open onClose={onClose} title="Record sale">
      <div className="space-y-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">Price is recorded as a collection fact. Financial posting is handled by Finance.</p>
        <TextField label="Buyer" value={buyer} onChange={(e) => setBuyer(e.target.value)} />
        <TextField label="Price (optional)" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={m.isPending} disabled={!buyer.trim()} onClick={() => m.mutate()}>Record sale</Button></div>
      </div>
    </AviModal>
  );
}

function DeathModal({ farmId, birdId, onClose, onDone }: { farmId: string; birdId: string; onClose: () => void; onDone: () => void }) {
  const [cause, setCause] = useState("");
  const { error, onError } = useActionError();
  const m = useMutation({
    mutationFn: () => recordDeath(farmId, birdId, { cause: cause.trim() || undefined }),
    onSuccess: () => { onDone(); onClose(); }, onError,
  });
  return (
    <AviModal open onClose={onClose} title="Record death">
      <div className="space-y-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">The bird's full history is preserved permanently.</p>
        <TextField label="Cause (optional)" value={cause} onChange={(e) => setCause(e.target.value)} />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="danger" loading={m.isPending} onClick={() => m.mutate()}>Record death</Button></div>
      </div>
    </AviModal>
  );
}
