/**
 * ARIA — the trust signals.
 *
 * ARIA's value depends on farmers believing it, and belief comes from ARIA
 * being visibly honest about where an answer came from and how sure it is.
 * These are small components carrying a disproportionate amount of the product
 * argument, which is why they are shared rather than reimplemented per screen.
 */
import { Database } from "lucide-react";
import {
  CONFIDENCE_STEPS,
  confidenceSwatch,
  label as toLabel,
  normaliseTrend,
  riskSwatch,
  trendSwatch,
  type AriaConfidenceLevel,
} from "./tokens";
import { cn } from "@/lib/cn";
import type { AIExplainFactor } from "@/types";

/**
 * Confidence as a 3-step meter plus the word. The meter is scannable; the word
 * is what a farmer repeats to a vet. Both, or the component is doing half a job.
 */
export function AriaConfidence({
  value,
  showLabel = true,
  className,
}: {
  value: string;
  showLabel?: boolean;
  className?: string;
}) {
  const key = (value ?? "").toLowerCase().trim() as AriaConfidenceLevel;
  const steps = CONFIDENCE_STEPS[key] ?? 1;
  const s = confidenceSwatch(value);

  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      title={`${toLabel(value)} confidence`}
    >
      <span className="flex items-end gap-[2px]" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn(
              "w-[3px] rounded-[1px] transition-colors",
              // Ascending heights read as a signal-strength meter, which is a
              // metaphor farmers already know from their phones.
              i === 1 ? "h-1.5" : i === 2 ? "h-2.5" : "h-3.5",
              i <= steps ? s.rail : "bg-gray-200 dark:bg-white/10",
            )}
          />
        ))}
      </span>
      {showLabel && (
        <span className={cn("text-[11px] font-medium", s.fg)}>
          {toLabel(value)} confidence
        </span>
      )}
      <span className="sr-only">{toLabel(value)} confidence</span>
    </span>
  );
}

/**
 * Where the answer came from. Named after the farmer's own records — "feed
 * logs", "mortality records" — never after a table or an endpoint.
 */
export function AriaSourceBadge({ source, className }: { source: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium",
        "bg-white/70 text-gray-600 ring-1 ring-inset ring-gray-200/80",
        "dark:bg-white/[0.06] dark:text-gray-300 dark:ring-white/10",
        className,
      )}
    >
      <Database className="h-2.5 w-2.5 shrink-0" aria-hidden />
      {toLabel(source)}
    </span>
  );
}

export function AriaSources({
  sources,
  provider,
  className,
}: {
  sources?: string[];
  provider?: string;
  className?: string;
}) {
  if (!sources?.length && !provider) return null;
  return (
    <div className={cn("flex flex-wrap items-center gap-1", className)}>
      {sources?.length ? (
        <>
          <span className="sr-only">Based on</span>
          {sources.map((s) => (
            <AriaSourceBadge key={s} source={s} />
          ))}
        </>
      ) : null}
      {provider && (
        <span className="px-1 text-[10px] text-gray-400 dark:text-gray-500">via {provider}</span>
      )}
    </div>
  );
}

/** Risk / severity chip. */
export function AriaRiskChip({
  level,
  children,
  className,
}: {
  level: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const s = riskSwatch(level);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
        s.chip,
        className,
      )}
    >
      {children ?? toLabel(level)}
    </span>
  );
}

/**
 * Direction of travel. `higherIsBetter` matters: the same word is good news for
 * eggs and bad news for deaths, and getting it backwards would be worse than
 * showing nothing.
 */
export function AriaTrendChip({
  trend,
  higherIsBetter = false,
  className,
}: {
  trend: string;
  higherIsBetter?: boolean;
  className?: string;
}) {
  const t = normaliseTrend(trend);
  const s = trendSwatch(trend, higherIsBetter);
  const arrow = t === "rising" ? "↑" : t === "falling" ? "↓" : "→";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        s.chip,
        className,
      )}
    >
      <span aria-hidden>{arrow}</span>
      {toLabel(t)}
    </span>
  );
}

/**
 * The explainability list — ARIA showing its working. Each row is one factor
 * and its contribution, which is what makes a prediction arguable rather than
 * oracular.
 */
export function AriaFactors({
  factors,
  className,
}: {
  factors: AIExplainFactor[];
  className?: string;
}) {
  if (!factors?.length) return null;
  return (
    <ul className={cn("space-y-1.5", className)}>
      {factors.map((f, i) => (
        <li
          key={`${f.factor}-${i}`}
          className="flex items-start justify-between gap-3 text-sm leading-snug"
        >
          <span className="text-gray-600 dark:text-gray-300">
            {f.factor}
            {f.detail ? (
              <span className="text-gray-400 dark:text-gray-500"> — {f.detail}</span>
            ) : null}
          </span>
          <span className="shrink-0 font-semibold tabular-nums text-gray-900 dark:text-white">
            {f.impact}
          </span>
        </li>
      ))}
    </ul>
  );
}
