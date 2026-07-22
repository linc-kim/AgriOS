/**
 * ARIA — identity primitives.
 *
 * `AriaMark` (components/brand) is the mark itself and stays untouched; it is
 * the thing the brand page documents. This file is the product layer on top:
 * the handful of treatments the app actually reaches for, so no screen has to
 * decide for itself how big the mark should be or what colour disc sits behind
 * it.
 */
import { AriaMark, type AriaState, type AriaTone } from "@/components/brand/AriaMark";
import { cn } from "@/lib/cn";

/**
 * Drop-in for a lucide icon — same `className` contract, so it can sit in the
 * module registry beside `LayoutDashboard` and friends without the shell
 * knowing the difference.
 *
 * Defaults to `mono`. The gradient version is the right choice where the mark
 * has room to be itself (headers, avatars, marketing); in a nav rail it would
 * be the only filled, coloured glyph among twelve monochrome outlines, which
 * reads as a misplaced favicon rather than as emphasis.
 */
export function AriaIcon({
  className,
  tone = "mono",
  state,
  animated = false,
  title,
}: {
  className?: string;
  tone?: AriaTone;
  state?: AriaState;
  animated?: boolean;
  title?: string;
}) {
  return (
    <AriaMark
      // Sized by className (h-4 w-4 etc.) exactly like lucide; the `size`
      // attribute is only the fallback when no class is given.
      size={20}
      tone={tone}
      state={state}
      animated={animated}
      title={title}
      className={className}
    />
  );
}

const AVATAR_RING =
  "ring-1 ring-inset ring-brand-600/10 dark:ring-white/10";

/**
 * The assistant's face — used anywhere ARIA speaks: chat, notifications,
 * insight attribution. The disc is what stops the mark being mistaken for a
 * decorative leaf next to a body of text.
 */
export function AriaAvatar({
  size = 36,
  state = "idle",
  animated = false,
  className,
}: {
  size?: number;
  state?: AriaState;
  animated?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full",
        "bg-brand-50 dark:bg-brand-500/12",
        AVATAR_RING,
        className,
      )}
      style={{ width: size, height: size }}
    >
      <AriaMark
        size={Math.round(size * 0.62)}
        detail={size < 28 ? "simple" : "full"}
        state={state}
        animated={animated}
        title="ARIA"
      />
    </span>
  );
}

/**
 * Attribution pill — "ARIA" beside a piece of generated content, so a farmer
 * can always tell what the system inferred from what they themselves recorded.
 * That distinction is the whole trust model, so it gets a component rather than
 * being retyped per screen.
 */
export function AriaBadge({
  label = "ARIA",
  size = "md",
  className,
}: {
  label?: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const sm = size === "sm";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium",
        "bg-brand-50 text-brand-700 dark:bg-brand-500/12 dark:text-brand-300",
        sm ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-[11px]",
        className,
      )}
    >
      <AriaMark size={sm ? 10 : 12} detail="simple" />
      <span className="tracking-[0.08em]">{label}</span>
    </span>
  );
}

type StatusKind = "ready" | "thinking" | "offline" | "limited";

const STATUS: Record<StatusKind, { dot: string; text: string; copy: string }> = {
  ready: {
    dot: "bg-brand-500",
    text: "text-gray-500 dark:text-gray-400",
    copy: "Ready",
  },
  thinking: {
    dot: "bg-navy-500 animate-pulse",
    text: "text-navy-600 dark:text-navy-300",
    copy: "Thinking",
  },
  // Offline is a first-class state, not an error: ARIA falls back to an
  // on-device model, and saying so is more reassuring than a red banner.
  offline: {
    dot: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
    copy: "Offline model",
  },
  limited: {
    dot: "bg-gray-400",
    text: "text-gray-500 dark:text-gray-400",
    copy: "Quota reached",
  },
};

/**
 * A quiet line saying what ARIA can currently do. Deliberately understated —
 * this is ambient information, never an alert.
 */
export function AriaStatus({
  kind = "ready",
  detail,
  className,
}: {
  kind?: StatusKind;
  detail?: string;
  className?: string;
}) {
  const s = STATUS[kind];
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 text-[11px]", s.text, className)}
      role="status"
    >
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", s.dot)} aria-hidden />
      {detail ?? s.copy}
    </span>
  );
}
