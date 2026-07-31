/** Shared status / lifecycle-stage badges for the BSF screens. */
import { cn } from "@/lib/cn";
import { STAGE_LABELS } from "@/api/bsf";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  harvested: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  completed: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  split: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  merged: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  terminated: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  archived: "bg-gray-100 text-gray-600 dark:bg-gray-700/40 dark:text-gray-300",
};

export function BatchStatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
        STATUS_STYLES[status] ?? STATUS_STYLES.archived,
        className,
      )}
    >
      {status}
    </span>
  );
}

// Ordered lifecycle: colour deepens as the batch matures toward harvest.
const STAGE_STYLES: Record<string, string> = {
  egg: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300",
  hatchling: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  feeding_larvae: "bg-lime-50 text-lime-700 dark:bg-lime-500/15 dark:text-lime-300",
  mature_larvae: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  prepupae: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  pupae: "bg-teal-50 text-teal-700 dark:bg-teal-500/15 dark:text-teal-300",
  adult: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  unknown: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
};

export function StageBadge({ stage, className }: { stage: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        STAGE_STYLES[stage] ?? STAGE_STYLES.unknown,
        className,
      )}
    >
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}
