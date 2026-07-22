/**
 * ARIA — empty states.
 *
 * ARIA is only as good as the records behind it, so its empty state has a job
 * beyond decoration: explain that the silence is about missing data, not a
 * broken assistant, and point at the log that would fix it. A generic "no data"
 * panel here would read as ARIA having nothing to say.
 */
import { motion } from "motion/react";
import { AriaAvatar } from "./AriaIdentity";
import { MOTION } from "./tokens";
import { cn } from "@/lib/cn";

export function AriaEmptyState({
  title = "Not enough data yet",
  description = "ARIA works from your own records. Log a few days of feed, mortality and production, and predictions will appear here.",
  action,
  className,
  compact = false,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <motion.div
      initial={{ y: 6 }}
      animate={{ y: 0 }}
      transition={MOTION.enter}
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed text-center",
        "border-gray-200 bg-white/40 px-6 dark:border-white/10 dark:bg-white/[0.02]",
        compact ? "py-10" : "py-16",
        className,
      )}
    >
      {/* Idle, not animated — an empty state that breathes draws the eye to the
          one part of the screen with nothing to offer. */}
      <AriaAvatar size={compact ? 44 : 56} />
      <h3 className="mt-4 text-base font-semibold text-gray-900 dark:text-white">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-gray-500 dark:text-gray-400">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </motion.div>
  );
}
