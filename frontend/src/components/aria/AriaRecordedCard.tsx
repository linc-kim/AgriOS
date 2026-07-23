/**
 * ARIA — the "recorded" chat card.
 *
 * Confirmation of a write, in the conversation. It reads as done, not chatty:
 * a check, the module it landed in, and the plain-language summary of the row.
 * The module icon and colour are how a farmer learns, over time, where their
 * words end up — a dead bird goes to Livestock, eggs to Production — which is
 * the same trust argument as the source badges on answers.
 */
import { motion } from "motion/react";
import {
  Bird,
  Check,
  Egg,
  Scale,
  Syringe,
  Wheat,
  type LucideIcon,
} from "lucide-react";
import { MOTION } from "./tokens";
import { cn } from "@/lib/cn";

/** Module → how the recorded card presents. */
const MODULE_STYLE: Record<
  string,
  { icon: LucideIcon; label: string; tint: string; ring: string }
> = {
  livestock: {
    icon: Bird,
    label: "Livestock",
    tint: "bg-navy-50 text-navy-600 dark:bg-navy-500/15 dark:text-navy-300",
    ring: "ring-navy-500/20",
  },
  production: {
    icon: Egg,
    label: "Production",
    tint: "bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300",
    ring: "ring-amber-500/20",
  },
  health: {
    icon: Syringe,
    label: "Health",
    tint: "bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300",
    ring: "ring-brand-500/20",
  },
  feed: {
    icon: Wheat,
    label: "Feed",
    tint: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
    ring: "ring-amber-500/20",
  },
};

const FALLBACK = {
  icon: Scale,
  label: "Records",
  tint: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
  ring: "ring-gray-400/20",
};

export function AriaRecordedCard({
  module,
  summary,
  index = 0,
}: {
  module: string;
  summary: string;
  index?: number;
}) {
  const style = MODULE_STYLE[module] ?? FALLBACK;
  const Icon = style.icon;

  return (
    <motion.div
      initial={{ y: 8 }}
      animate={{ y: 0 }}
      transition={{ ...MOTION.enter, delay: Math.min(index, 3) * 0.03 }}
      className={cn(
        "flex items-center gap-3 rounded-xl border bg-white px-3.5 py-3",
        "border-gray-200 ring-1 ring-inset dark:border-white/10 dark:bg-white/[0.03]",
        style.ring,
      )}
      role="status"
    >
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", style.tint)}>
        <Icon className="h-4.5 w-4.5" aria-hidden />
      </span>

      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-brand-600 dark:text-brand-400">
          <Check className="h-3 w-3" aria-hidden />
          Saved to {style.label}
        </p>
        <p className="mt-0.5 truncate text-sm text-gray-800 dark:text-gray-100" title={summary}>
          {summary}
        </p>
      </div>
    </motion.div>
  );
}
