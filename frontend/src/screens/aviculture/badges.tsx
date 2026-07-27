/** Shared status / lifecycle badge styling for the Aviculture screens. */
import { cn } from "@/lib/cn";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  archived: "bg-gray-100 text-gray-600 dark:bg-gray-700/40 dark:text-gray-300",
  sold: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  transferred: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  deceased: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
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

const EVENT_LABEL: Record<string, string> = {
  created: "Added to collection",
  updated: "Details updated",
  status_changed: "Status changed",
  archived: "Archived",
  restored: "Restored",
  transferred: "Transferred",
  sold: "Sold",
  purchased: "Purchase recorded",
  died: "Deceased",
  paired: "Paired",
  unpaired: "Unpaired",
  media_added: "Media added",
  document_added: "Document added",
  health_recorded: "Health record",
  note: "Note",
};

export function eventLabel(type: string): string {
  return EVENT_LABEL[type] ?? type;
}

// Honesty labels from the deterministic engines (Doc 04 §16, Doc 15 §15).
const FACT_STYLES: Record<string, string> = {
  recorded: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  calculated: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  forecast: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  recommendation: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  unknown: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  unavailable: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
};

export function FactBadge({ label, className }: { label: string; className?: string }) {
  return (
    <span
      title={label}
      className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        FACT_STYLES[label] ?? FACT_STYLES.unknown, className)}
    >
      {label}
    </span>
  );
}

const RISK_STYLES: Record<string, string> = {
  minimal: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  low: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  moderate: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  high: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  invalid: "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300",
};

export function RiskBadge({ level, className }: { level: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
      RISK_STYLES[level] ?? RISK_STYLES.moderate, className)}>
      {level} risk
    </span>
  );
}

const EVENT_DOT: Record<string, string> = {
  created: "bg-brand-500",
  sold: "bg-sky-500",
  transferred: "bg-violet-500",
  died: "bg-gray-500",
  archived: "bg-gray-400",
  restored: "bg-brand-500",
  purchased: "bg-amber-500",
  media_added: "bg-teal-500",
  document_added: "bg-teal-500",
};

export function eventDot(type: string): string {
  return EVENT_DOT[type] ?? "bg-gray-400";
}
