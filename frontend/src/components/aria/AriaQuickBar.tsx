/**
 * ARIA workspace — quick actions and suggested prompts.
 *
 * Two rows of shortcuts with different jobs. Quick actions seed a *recording*
 * ("Record deaths" pre-fills the composer so the farmer just adds the number);
 * suggested prompts seed a *question* ("Profit today"). Both exist because a
 * blank chat box is intimidating — a farmer who has never used an assistant
 * does not know it can be asked, and these are the answer to that.
 *
 * Nothing here submits on its own. A tap fills the composer and focuses it, so
 * the farmer always sees and edits what will be sent. That keeps the write path
 * honest: ARIA never records from a button alone.
 */
import {
  Bird,
  Camera,
  Egg,
  FileText,
  MessageCircleQuestion,
  Scale,
  Syringe,
  Wheat,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";

export interface QuickAction {
  label: string;
  /** Text dropped into the composer, ready to complete. */
  seed: string;
  icon: LucideIcon;
  /** Actions that need a screen ARIA can't drive yet route out instead. */
  href?: string;
}

/** The eight record/utility buttons from the spec. */
export const QUICK_ACTIONS: QuickAction[] = [
  { label: "Record feed", seed: "I used ", icon: Wheat },
  { label: "Record eggs", seed: "Collected ", icon: Egg },
  { label: "Record deaths", seed: "We lost ", icon: Bird },
  { label: "Record weight", seed: "We weighed the birds, average ", icon: Scale },
  { label: "Record vaccination", seed: "We vaccinated ", icon: Syringe },
  { label: "Ask ARIA", seed: "", icon: MessageCircleQuestion },
  { label: "Upload image", seed: "", icon: Camera, href: "__upload" },
  { label: "View reports", seed: "", icon: FileText, href: "/reports" },
];

/** Chips above the input — mostly questions, a couple of record starters. */
export const SUGGESTED_PROMPTS: string[] = [
  "Today's flock status",
  "Vaccination schedule",
  "Profit today",
  "Record feed",
  "Record eggs",
  "Why are birds dying?",
  "Review finances",
  "Generate report",
];

export function AriaQuickActions({
  onSeed,
  onUpload,
  onNavigate,
  className,
}: {
  onSeed: (seed: string) => void;
  onUpload: () => void;
  onNavigate: (href: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("grid grid-cols-2 gap-2 sm:grid-cols-4", className)}>
      {QUICK_ACTIONS.map((a) => {
        const Icon = a.icon;
        return (
          <button
            key={a.label}
            type="button"
            onClick={() => {
              if (a.href === "__upload") onUpload();
              else if (a.href) onNavigate(a.href);
              else onSeed(a.seed);
            }}
            className={cn(
              "flex min-h-touch items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-sm font-medium transition-colors",
              "border-gray-200 bg-white text-gray-700 hover:border-brand-300 hover:bg-brand-50/50",
              "dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-200 dark:hover:border-brand-500/40 dark:hover:bg-brand-500/10",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-gray-900",
            )}
          >
            <Icon className="h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" aria-hidden />
            <span className="truncate">{a.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function AriaSuggestedPrompts({
  prompts = SUGGESTED_PROMPTS,
  onPick,
  className,
}: {
  prompts?: string[];
  onPick: (prompt: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex gap-2 overflow-x-auto pb-1", className)}>
      {prompts.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPick(p)}
          className={cn(
            "shrink-0 rounded-full border px-3 py-1.5 text-xs transition-colors",
            "border-gray-200 text-gray-600 hover:border-brand-300 hover:bg-brand-50/60 hover:text-brand-700",
            "dark:border-white/10 dark:text-gray-300 dark:hover:border-brand-500/40 dark:hover:bg-brand-500/10 dark:hover:text-brand-200",
          )}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
