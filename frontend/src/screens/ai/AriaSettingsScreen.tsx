/**
 * ARIA AI Settings (Module 13 Part 8, capability 13).
 *
 * The farm's AI configuration and its cost dashboard: turn AI on or off, choose
 * the model (Gemini Flash, Gemini Pro, or offline-deterministic-only), set the
 * temperature and token ceiling, toggle image and document analysis, and watch
 * spend. "Offline deterministic only" is a first-class choice — with it, ARIA
 * still answers from your records, it just never calls a model.
 */
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Cpu, DollarSign, WifiOff } from "lucide-react";

import { getSettings, getUsage, updateSettings, type AISettings } from "@/api/ariaAssistant";
import { useWorkspace } from "@/shell/useWorkspace";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";

const MODELS: { value: AISettings["model"]; label: string; hint: string; icon: typeof Cpu }[] = [
  { value: "gemini-flash", label: "Gemini Flash", hint: "Fast, low cost", icon: Cpu },
  { value: "gemini-pro", label: "Gemini Pro", hint: "Deeper reasoning", icon: Cpu },
  { value: "offline", label: "Offline only", hint: "Deterministic, no model calls", icon: WifiOff },
];

export default function AriaSettingsScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const qc = useQueryClient();
  const [draft, setDraft] = useState<AISettings | null>(null);
  const [saved, setSaved] = useState(false);

  const settingsQ = useQuery({
    queryKey: ["ai-settings", farmId],
    queryFn: () => getSettings(farmId as string),
    enabled: !!farmId,
  });
  const usageQ = useQuery({
    queryKey: ["ai-usage", farmId],
    queryFn: () => getUsage(farmId as string),
    enabled: !!farmId,
  });

  useEffect(() => {
    if (settingsQ.data) setDraft(settingsQ.data);
  }, [settingsQ.data]);

  const save = useMutation({
    mutationFn: (changes: Partial<AISettings>) => updateSettings(farmId as string, changes),
    onSuccess: (s) => {
      setDraft(s);
      qc.invalidateQueries({ queryKey: ["ai-settings", farmId] });
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
    },
  });

  if (!farmId) {
    return <p className="py-16 text-center text-sm text-gray-500">Select a farm to configure ARIA.</p>;
  }
  if (settingsQ.isLoading || !draft) {
    return <div className="space-y-4"><Skeleton className="h-40 rounded-2xl" /><Skeleton className="h-40 rounded-2xl" /></div>;
  }

  const set = (patch: Partial<AISettings>) => {
    setDraft((d) => (d ? { ...d, ...patch } : d));
    save.mutate(patch);
  };

  const u = usageQ.data;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">AI Settings</h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400">
            How ARIA uses AI on {currentFarm?.name}. Deterministic engines always run first.
          </p>
        </div>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-brand-600 dark:text-brand-400">
            <CheckCircle2 className="h-4 w-4" /> Saved
          </span>
        )}
      </header>

      {/* Enable */}
      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
        <label className="flex items-center justify-between gap-4">
          <span>
            <span className="block text-sm font-semibold text-gray-900 dark:text-white">AI assistant</span>
            <span className="block text-[13px] text-gray-500 dark:text-gray-400">
              When off, ARIA answers only from your records — no model is ever called.
            </span>
          </span>
          <Toggle checked={draft.ai_enabled} onChange={(v) => set({ ai_enabled: v })} label="Enable AI" />
        </label>
      </section>

      {/* Model */}
      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
        <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Model</h2>
        <div className="grid gap-2 sm:grid-cols-3">
          {MODELS.map((m) => {
            const active = draft.model === m.value;
            const Icon = m.icon;
            return (
              <button
                key={m.value}
                type="button"
                onClick={() => set({ model: m.value })}
                aria-pressed={active}
                className={cn(
                  "rounded-xl border p-3 text-left transition-colors",
                  active
                    ? "border-brand-400 bg-brand-50 dark:border-brand-500/40 dark:bg-brand-500/10"
                    : "border-gray-200 hover:bg-gray-50 dark:border-white/10 dark:hover:bg-white/[0.04]",
                )}
              >
                <Icon className={cn("h-4 w-4", active ? "text-brand-600 dark:text-brand-300" : "text-gray-400")} />
                <span className="mt-1.5 block text-sm font-medium text-gray-900 dark:text-white">{m.label}</span>
                <span className="block text-[11px] text-gray-500 dark:text-gray-400">{m.hint}</span>
              </button>
            );
          })}
        </div>
        {draft.providers && !draft.providers.gemini && draft.model !== "offline" && (
          <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-400">
            No Gemini key is configured on the server, so ARIA runs in grounded offline mode until one is added.
          </p>
        )}
      </section>

      {/* Tuning */}
      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
        <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Tuning</h2>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-[13px]">
              <label htmlFor="temp" className="text-gray-600 dark:text-gray-300">Temperature</label>
              <span className="tabular-nums text-gray-500">{draft.temperature.toFixed(2)}</span>
            </div>
            <input
              id="temp" type="range" min={0} max={1} step={0.05} value={draft.temperature}
              onChange={(e) => setDraft((d) => (d ? { ...d, temperature: Number(e.target.value) } : d))}
              onMouseUp={(e) => set({ temperature: Number((e.target as HTMLInputElement).value) })}
              onTouchEnd={(e) => set({ temperature: Number((e.target as HTMLInputElement).value) })}
              className="mt-1 w-full accent-brand-600"
            />
            <p className="text-[11px] text-gray-400">Lower is more precise; higher is more varied.</p>
          </div>
          <div>
            <label htmlFor="tokens" className="text-[13px] text-gray-600 dark:text-gray-300">Max response tokens</label>
            <input
              id="tokens" type="number" min={16} max={4096} value={draft.max_output_tokens}
              onChange={(e) => setDraft((d) => (d ? { ...d, max_output_tokens: Number(e.target.value) } : d))}
              onBlur={(e) => set({ max_output_tokens: Number(e.target.value) })}
              className="mt-1 w-32 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
            />
          </div>
          <label className="flex items-center justify-between">
            <span className="text-[13px] text-gray-600 dark:text-gray-300">Allow image analysis (Gemini Vision)</span>
            <Toggle checked={draft.allow_vision} onChange={(v) => set({ allow_vision: v })} label="Allow vision" />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-[13px] text-gray-600 dark:text-gray-300">Allow document uploads</span>
            <Toggle checked={draft.allow_documents} onChange={(v) => set({ allow_documents: v })} label="Allow documents" />
          </label>
        </div>
      </section>

      {/* Usage / cost dashboard */}
      <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <DollarSign className="h-4 w-4 text-gray-400" /> Usage &amp; cost
        </h2>
        {usageQ.isLoading || !u ? (
          <Skeleton className="h-20 rounded-xl" />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3">
              <Stat label="This month" value={`$${u.this_month.cost_usd.toFixed(4)}`} sub={`${u.this_month.calls} calls`} />
              <Stat label="Total spend" value={`$${u.total.cost_usd.toFixed(4)}`} sub={`${u.total.calls} calls`} />
              <Stat label="Tokens (total)" value={u.total.tokens.toLocaleString()} sub="prompt + output" />
            </div>
            {u.by_provider.length > 0 && (
              <div className="mt-3 border-t border-gray-100 pt-2 dark:border-white/[0.06]">
                {u.by_provider.map((p) => (
                  <div key={p.provider} className="flex justify-between text-[12px] text-gray-500 dark:text-gray-400">
                    <span className="capitalize">{p.provider}</span>
                    <span className="tabular-nums">{p.calls} calls · ${p.cost_usd.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            )}
            <p className="mt-2 text-[11px] text-gray-400">
              Deterministic and offline answers are free — you only pay when a model is actually called.
            </p>
          </>
        )}
      </section>
    </div>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors",
        checked ? "bg-brand-600" : "bg-gray-300 dark:bg-white/20",
      )}
    >
      <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform",
        checked ? "translate-x-[22px]" : "translate-x-0.5")} />
    </button>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl bg-gray-50 p-3 dark:bg-white/[0.04]">
      <p className="text-[11px] uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-gray-900 dark:text-white">{value}</p>
      <p className="text-[11px] text-gray-400">{sub}</p>
    </div>
  );
}
