/**
 * ARIA — the pending confirmation card.
 *
 * When ARIA is mid-record — missing a flock, probing for symptoms, or waiting
 * for a yes — that is not a chat bubble. A bubble scrolls away and reads as
 * conversation; this is an open task with a decision attached, so it gets a
 * card that holds its place and states plainly what will be saved.
 *
 * Three shapes, one component, because they are the same object at different
 * stages: a question with options ("Which flock?"), a probe that can be skipped
 * ("Any symptoms?"), and the final confirm ("Ready to record… save?"). The
 * accent and the primary action change; the structure does not.
 */
import { motion } from "motion/react";
import { Check, HelpCircle, X } from "lucide-react";
import { AriaAvatar } from "./AriaIdentity";
import { MOTION } from "./tokens";
import { cn } from "@/lib/cn";
import type { AriaRecordStage } from "@/api/ariaRecord";

export interface AriaConfirmationCardProps {
  stage: AriaRecordStage;
  /** The question or confirmation prompt. */
  prompt: string;
  /** Tappable answers. For confirming, the first is the affirmative. */
  options: string[];
  /** What ARIA understood so far, shown as a read-back on the confirm step. */
  understood?: string | null;
  /** Assumptions ARIA is surfacing (bag size, date defaulted to today). */
  note?: string | null;
  onPick: (option: string) => void;
  /** Free-typed answer path — the card never forces a tap. */
  disabled?: boolean;
}

export function AriaConfirmationCard({
  stage,
  prompt,
  options,
  understood,
  note,
  onPick,
  disabled = false,
}: AriaConfirmationCardProps) {
  const confirming = stage === "confirming";
  const probing = stage === "probing";

  return (
    <motion.div
      initial={{ y: 8 }}
      animate={{ y: 0 }}
      transition={MOTION.enter}
      className="flex w-full gap-2.5"
    >
      <span className="mt-auto">
        <AriaAvatar size={30} state={confirming ? "responding" : "thinking"} animated />
      </span>

      <div
        className={cn(
          "min-w-0 flex-1 overflow-hidden rounded-2xl rounded-bl-md border",
          confirming
            ? "border-brand-200 bg-brand-50/60 dark:border-brand-500/30 dark:bg-brand-500/[0.08]"
            : "border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.03]",
        )}
        role="group"
        aria-label={confirming ? "Confirm before saving" : "ARIA needs more information"}
      >
        {/* Read-back — the farmer sees exactly what will be written. */}
        {understood && (
          <div className="border-b border-gray-100 px-4 py-2.5 dark:border-white/[0.06]">
            <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
              {confirming ? "I'll record" : "So far"}
            </p>
            <p className="mt-0.5 text-sm font-medium text-gray-900 dark:text-white">{understood}</p>
          </div>
        )}

        <div className="px-4 py-3">
          <p className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-100">
            {!confirming && (
              <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden />
            )}
            <span>{prompt}</span>
          </p>

          {note && (
            <p className="mt-2 text-xs leading-relaxed text-gray-500 dark:text-gray-400">{note}</p>
          )}

          {options.length > 0 && (
            <div className={cn("mt-3 flex flex-wrap gap-2", confirming && "flex-row-reverse justify-end")}>
              {options.map((opt, i) => {
                const isPrimary = confirming && i === 0;
                const isCancel = /^(no|cancel|skip)/i.test(opt);
                return (
                  <button
                    key={opt}
                    type="button"
                    disabled={disabled}
                    onClick={() => onPick(opt)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                      "min-h-touch disabled:opacity-50 sm:min-h-0",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-gray-900",
                      isPrimary
                        ? "bg-brand-600 text-white hover:bg-brand-700"
                        : isCancel
                          ? "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/[0.06]"
                          : "border border-gray-200 bg-white text-gray-700 hover:border-brand-300 hover:bg-brand-50/60 dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-200 dark:hover:border-brand-500/40 dark:hover:bg-brand-500/10",
                    )}
                  >
                    {isPrimary && <Check className="h-3.5 w-3.5" aria-hidden />}
                    {isCancel && /^no|cancel/i.test(opt) && <X className="h-3.5 w-3.5" aria-hidden />}
                    {opt}
                  </button>
                );
              })}
            </div>
          )}

          {probing && (
            <p className="mt-2 text-[11px] text-gray-400 dark:text-gray-500">
              Optional — this helps ARIA track health patterns, but you can skip it.
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
}
