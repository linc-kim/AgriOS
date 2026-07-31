/**
 * Honesty-framework badge — the canonical, cross-module renderer for the label
 * the deterministic engines assign to every value (recorded · calculated ·
 * forecast · estimate · unknown/unavailable). Keeping recorded facts, derived
 * calculations, projections and assumption-based estimates *visually distinct*
 * is a Greena core principle. Shared so every module renders honesty identically.
 */
import { cn } from "@/lib/cn";

const FACT_STYLES: Record<string, string> = {
  recorded: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  calculated: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  forecast: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  estimate: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  recommendation: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  ai_suggestion: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  unknown: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  unavailable: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
};

const FACT_TITLE: Record<string, string> = {
  recorded: "Recorded fact — entered or measured, unmodified.",
  calculated: "Calculated — deterministic from recorded facts.",
  forecast: "Forecast — a model projection, not a confirmed value.",
  estimate: "Estimate — depends on a supplied assumption.",
  ai_suggestion: "AI suggestion — advisory only.",
  unknown: "Unknown — not enough recorded data.",
  unavailable: "Unavailable — no source for this value yet.",
};

export function FactBadge({ label, className }: { label?: string | null; className?: string }) {
  if (!label) return null;
  return (
    <span
      title={FACT_TITLE[label] ?? label}
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        FACT_STYLES[label] ?? FACT_STYLES.unknown,
        className,
      )}
    >
      {label.replace("_", " ")}
    </span>
  );
}

/** A labelled value `{label, value, detail}` from an engine, rendered with its
 *  honesty badge and an accessible tooltip carrying the engine's `detail`. */
export function LabelledValue({
  figure,
  format,
  className,
}: {
  figure?: { label: string; value: unknown; detail?: string } | null;
  format?: (v: unknown) => string;
  className?: string;
}) {
  if (!figure) return <span className="text-gray-400">—</span>;
  const shown =
    figure.value == null ? "—" : format ? format(figure.value) : String(figure.value);
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)} title={figure.detail}>
      <span>{shown}</span>
      <FactBadge label={figure.label} />
    </span>
  );
}
