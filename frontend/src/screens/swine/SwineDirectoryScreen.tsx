/**
 * Swine — Directory. Browse, filter and register pigs. Registration posts to the
 * backend, which generates the SW- ref and enforces every rule; the client presents.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, Search } from "lucide-react";

import { listPigs, registerPig, type Pig } from "@/api/swine";
import { PRODUCTION_STAGES, PURPOSES, SEXES, STATUSES } from "./config";
import { useWorkspace } from "@/shell/useWorkspace";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { SwineSubnav } from "./SwineSubnav";

export default function SwineDirectoryScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [stage, setStage] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const listQ = useQuery({
    queryKey: ["swine-pigs", farmId, search, status, stage],
    queryFn: () => listPigs(farmId as string, {
      search: search || undefined, status: status || undefined,
      production_stage: stage || undefined, page_size: 100,
    }),
    enabled: !!farmId,
  });

  const createM = useMutation({
    mutationFn: (body: Partial<Pig>) => registerPig(farmId as string, body),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["swine-pigs", farmId] });
      setShowCreate(false);
      navigate(`/swine/${p.id}`);
    },
  });

  if (!farmId) return <p className="py-16 text-center text-sm text-gray-500">Select a farm.</p>;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <SwineSubnav active="/swine" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Pig Directory</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {listQ.data?.meta.total ?? 0} pig(s) in the herd
          </p>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowCreate(true)}>
          Register pig
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ref, name, ear tag…"
            className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm dark:border-gray-700 dark:bg-gray-900"
          />
        </div>
        <select value={stage} onChange={(e) => setStage(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900">
          <option value="">All stages</option>
          {PRODUCTION_STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {listQ.isLoading ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : (listQ.data?.data ?? []).length === 0 ? (
        <p className="py-16 text-center text-sm text-gray-400">No pigs yet. Register your first one.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500 dark:bg-gray-900">
              <tr>
                <th className="px-3 py-2">Ref</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Sex</th>
                <th className="px-3 py-2">Stage</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Breed</th>
              </tr>
            </thead>
            <tbody>
              {listQ.data!.data.map((p) => (
                <tr key={p.id} onClick={() => navigate(`/swine/${p.id}`)}
                  className="cursor-pointer border-t border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50">
                  <td className="px-3 py-2 font-medium text-gray-900 dark:text-gray-100">{p.internal_ref}</td>
                  <td className="px-3 py-2">{p.name ?? "—"}</td>
                  <td className="px-3 py-2 capitalize">{p.sex}</td>
                  <td className="px-3 py-2 capitalize">{p.production_stage.replace(/_/g, " ")}</td>
                  <td className="px-3 py-2 capitalize">{p.status}</td>
                  <td className="px-3 py-2">{p.breed_name ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <RegisterModal
          onClose={() => setShowCreate(false)}
          onSubmit={(body) => createM.mutate(body)}
          submitting={createM.isPending}
          error={createM.isError ? "Could not register (duplicate ear tag, or invalid value?)." : null}
        />
      )}
    </div>
  );
}

function RegisterModal({
  onClose, onSubmit, submitting, error,
}: {
  onClose: () => void;
  onSubmit: (body: Partial<Pig>) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [name, setName] = useState("");
  const [sex, setSex] = useState("unknown");
  const [purpose, setPurpose] = useState("unknown");
  const [stage, setStage] = useState("unknown");
  const [earTag, setEarTag] = useState("");

  return (
    <Modal open onClose={onClose} title="Register pig">
      <div className="space-y-3">
        <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} /></Field>
        <Field label="Ear tag"><input value={earTag} onChange={(e) => setEarTag(e.target.value)} className={inputCls} /></Field>
        <Field label="Sex / class">
          <select value={sex} onChange={(e) => setSex(e.target.value)} className={inputCls}>
            {SEXES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Production stage">
          <select value={stage} onChange={(e) => setStage(e.target.value)} className={inputCls}>
            {PRODUCTION_STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Purpose">
          <select value={purpose} onChange={(e) => setPurpose(e.target.value)} className={inputCls}>
            {PURPOSES.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
          </select>
        </Field>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={submitting}
            onClick={() => onSubmit({ name: name || null, sex, purpose, production_stage: stage, ear_tag: earTag || null })}
          >
            Register
          </Button>
        </div>
      </div>
    </Modal>
  );
}

const inputCls = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">{label}</span>
      {children}
    </label>
  );
}
