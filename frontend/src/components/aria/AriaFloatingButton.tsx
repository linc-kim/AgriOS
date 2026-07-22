/**
 * ARIA — the floating assistant button.
 *
 * Present on every workspace screen, so ARIA is reachable from wherever a
 * question occurs to a farmer rather than only from its own module.
 *
 * It hides itself on `/ai` — a shortcut to the screen you are already looking
 * at is noise — and clears the iOS home indicator via the safe-area inset. The
 * target is 56px, the design system's primary touch size.
 */
import { useLocation, useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { AriaMark } from "@/components/brand/AriaMark";
import { cn } from "@/lib/cn";

export function AriaFloatingButton({
  to = "/ai",
  label = "Ask ARIA",
  className,
}: {
  to?: string;
  label?: string;
  className?: string;
}) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const reduced = useReducedMotion();

  if (pathname.startsWith(to)) return null;

  return (
    <motion.button
      type="button"
      onClick={() => navigate(to)}
      aria-label={label}
      title={label}
      initial={reduced ? false : { scale: 0.9 }}
      animate={{ scale: 1 }}
      whileHover={reduced ? undefined : { scale: 1.04 }}
      whileTap={reduced ? undefined : { scale: 0.96 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "group fixed right-4 z-40 flex items-center gap-2.5 rounded-full",
        "h-14 min-w-touch-primary pl-4 pr-4 sm:pr-5",
        "bg-brand-600 text-white shadow-lg shadow-brand-900/20",
        "ring-1 ring-inset ring-white/15",
        "hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2",
        "focus-visible:ring-brand-400 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900",
        "bottom-[calc(1.5rem+env(safe-area-inset-bottom))]",
        className,
      )}
    >
      <AriaMark size={26} tone="inverse" state="idle" animated />
      {/* The word only appears where there is room for it; on a phone the mark
          alone has to carry recognition, which is what it was designed for. */}
      <span className="hidden text-sm font-medium sm:inline">{label}</span>
    </motion.button>
  );
}
