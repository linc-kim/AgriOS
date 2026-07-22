/**
 * ARIA — waiting states.
 *
 * Two different waits, deliberately different shapes. `AriaThinking` is a
 * *reply* being composed: it sits in the conversation where the answer will
 * appear, so the layout does not jump when it arrives. `AriaLoading` is a
 * *panel* being fetched: it fills the space the panel will occupy.
 *
 * Both respect prefers-reduced-motion via AriaMark, and neither uses a
 * spinner — a spinner says "the software is busy", and ARIA should say "someone
 * is considering your question".
 */
import { motion, useReducedMotion } from "motion/react";
import { AriaAvatar } from "./AriaIdentity";
import { MOTION } from "./tokens";
import { cn } from "@/lib/cn";

/**
 * Typing indicator. Three dots at the same slow cadence as the mark's own
 * thinking state, so the two read as one animation rather than two things
 * blinking out of sync.
 */
export function AriaTypingDots({ className }: { className?: string }) {
  const reduced = useReducedMotion();

  if (reduced) {
    return (
      <span className={cn("text-sm text-gray-400 dark:text-gray-500", className)}>
        Thinking…
      </span>
    );
  }

  return (
    <span className={cn("inline-flex items-center gap-1", className)} aria-hidden>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500"
          initial={{ opacity: 0.25, y: 0 }}
          animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.16, ease: "easeInOut" }}
        />
      ))}
    </span>
  );
}

/**
 * The composing state, shaped like a message so the conversation does not
 * reflow when the real answer replaces it.
 */
export function AriaThinking({
  label = "ARIA is thinking",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <motion.div
      className={cn("flex items-end gap-2.5", className)}
      initial={{ y: 4 }}
      animate={{ y: 0 }}
      transition={MOTION.enter}
      // The label is announced once; the dots themselves are decorative.
      role="status"
      aria-label={label}
    >
      <AriaAvatar size={30} state="thinking" animated />
      <span
        className={cn(
          "inline-flex items-center rounded-2xl rounded-bl-md px-4 py-3",
          "bg-gray-50 dark:bg-white/[0.04]",
        )}
      >
        <AriaTypingDots />
      </span>
    </motion.div>
  );
}

/**
 * Panel-level loading. The mark rotates slowly in its `loading` state — the one
 * place ARIA is allowed to spin, because here it genuinely is the progress
 * indicator rather than an ornament beside one.
 */
export function AriaLoading({
  label = "Gathering your farm data…",
  className,
  compact = false,
}: {
  label?: string;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 text-center",
        compact ? "py-8" : "py-16",
        className,
      )}
      role="status"
    >
      <AriaAvatar size={compact ? 40 : 52} state="loading" animated />
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  );
}
