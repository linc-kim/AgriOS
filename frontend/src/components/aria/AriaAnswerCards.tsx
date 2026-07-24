/**
 * ARIA — knowledge and decision answer cards.
 *
 * When a question is answered deterministically (from the knowledge base or the
 * decision engine, never a model), the answer arrives as a structured card
 * rather than a plain bubble — because these answers *have* structure worth
 * showing: best practices, warnings, and for decisions the full case of pros,
 * cons, assumptions, risks and what's missing.
 *
 * The see-a-vet line on disease topics is not decoration: it is the §4.4
 * boundary made visible. ARIA explains a disease; it never tells the farmer
 * their birds have it.
 */
import { motion } from "motion/react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  HelpCircle,
  Scale,
  Stethoscope,
  XCircle,
} from "lucide-react";
import type { AriaDecisionAnswer, AriaKnowledgeAnswer } from "@/api/ariaIntelligence";
import { AriaSourceBadge } from "./AriaSignals";
import { MOTION } from "./tokens";
import { cn } from "@/lib/cn";

export function AriaKnowledgeCard({ answer }: { answer: AriaKnowledgeAnswer }) {
  return (
    <motion.div
      initial={{ y: 8 }}
      animate={{ y: 0 }}
      transition={MOTION.enter}
      className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.03]"
    >
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-2.5 dark:border-white/[0.06]">
        <BookOpen className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
        <span className="text-sm font-semibold text-gray-900 dark:text-white">{answer.title}</span>
        <span className="ml-auto rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium capitalize text-gray-500 dark:bg-white/10 dark:text-gray-400">
          {answer.category}
        </span>
      </div>

      <div className="space-y-3 px-4 py-3">
        <p className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">{answer.explanation}</p>

        {answer.best_practices.length > 0 && (
          <div>
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Best practice</p>
            <ul className="space-y-1">
              {answer.best_practices.map((b, i) => (
                <li key={i} className="flex gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" aria-hidden />
                  {b}
                </li>
              ))}
            </ul>
          </div>
        )}

        {answer.warnings.length > 0 && (
          <div className="rounded-lg bg-amber-50/70 px-3 py-2 dark:bg-amber-500/[0.08]">
            {answer.warnings.map((w, i) => (
              <p key={i} className="flex gap-2 text-sm text-amber-800 dark:text-amber-200">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                {w}
              </p>
            ))}
          </div>
        )}

        {answer.vet_now && (
          <p className="flex items-center gap-1.5 rounded-lg bg-red-50/70 px-3 py-2 text-[13px] font-medium text-red-700 dark:bg-red-500/[0.08] dark:text-red-300">
            <Stethoscope className="h-4 w-4 shrink-0" aria-hidden />
            This is general guidance, not a diagnosis. For a sick flock, consult a vet.
          </p>
        )}

        <div className="flex items-center gap-1.5 pt-0.5">
          <AriaSourceBadge source="Offline Knowledge" />
          <span className="text-[10px] text-gray-400">{answer.source}</span>
        </div>
      </div>
    </motion.div>
  );
}

const LEAN: Record<string, { label: string; tint: string }> = {
  consider: { label: "Worth considering", tint: "bg-brand-50 text-brand-700 dark:bg-brand-500/12 dark:text-brand-300" },
  caution: { label: "Proceed with caution", tint: "bg-amber-50 text-amber-700 dark:bg-amber-500/12 dark:text-amber-300" },
  hold: { label: "Hold off", tint: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300" },
  need_info: { label: "Need more info", tint: "bg-navy-50 text-navy-700 dark:bg-navy-500/12 dark:text-navy-200" },
};

export function AriaDecisionCard({ answer }: { answer: AriaDecisionAnswer }) {
  const lean = LEAN[answer.lean] ?? LEAN.need_info;
  return (
    <motion.div
      initial={{ y: 8 }}
      animate={{ y: 0 }}
      transition={MOTION.enter}
      className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.03]"
    >
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-2.5 dark:border-white/[0.06]">
        <Scale className="h-4 w-4 text-brand-600 dark:text-brand-400" aria-hidden />
        <span className="text-sm font-semibold text-gray-900 dark:text-white">{answer.question}</span>
        <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold", lean.tint)}>
          {lean.label}
        </span>
      </div>

      <div className="space-y-3 px-4 py-3">
        <p className="text-sm leading-relaxed text-gray-800 dark:text-gray-200">{answer.headline}</p>

        <div className="grid gap-3 sm:grid-cols-2">
          <Column icon={CheckCircle2} tint="text-brand-500" title="For" items={answer.pros} />
          <Column icon={XCircle} tint="text-gray-400" title="Against" items={answer.cons} />
        </div>

        {answer.risks.length > 0 && (
          <Column icon={AlertTriangle} tint="text-amber-500" title="Risks" items={answer.risks} />
        )}
        {answer.assumptions.length > 0 && (
          <Muted title="Assuming" items={answer.assumptions} />
        )}
        {answer.missing.length > 0 && (
          <div className="rounded-lg bg-navy-50/60 px-3 py-2 dark:bg-navy-500/[0.08]">
            <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-navy-600 dark:text-navy-300">
              <HelpCircle className="h-3 w-3" aria-hidden />
              ARIA needs to know
            </p>
            <ul className="space-y-1">
              {answer.missing.map((m, i) => (
                <li key={i} className="text-sm text-navy-800 dark:text-navy-100">{m}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          {answer.sources.map((s) => (
            <AriaSourceBadge key={s} source={s} />
          ))}
        </div>
      </div>
    </motion.div>
  );
}

function Column({
  icon: Icon,
  tint,
  title,
  items,
}: {
  icon: typeof CheckCircle2;
  tint: string;
  title: string;
  items: string[];
}) {
  if (!items.length) return null;
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">{title}</p>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i} className="flex gap-1.5 text-sm text-gray-700 dark:text-gray-300">
            <Icon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", tint)} aria-hidden />
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Muted({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-gray-400">{title}</p>
      <ul className="space-y-0.5">
        {items.map((it, i) => (
          <li key={i} className="text-[13px] leading-snug text-gray-500 dark:text-gray-400">· {it}</li>
        ))}
      </ul>
    </div>
  );
}
