/**
 * Greena Logo — renders ONLY the approved master-derived assets.
 * Never recreate/regenerate artwork; swap the SVGs in src/assets/brand only via
 * the brand pipeline (brand/build_assets.py from the master .ai).
 */
import { cn } from "@/lib/cn";

import emblem from "@/assets/brand/greena-emblem.svg";
import emblemWhite from "@/assets/brand/greena-emblem-white.svg";
import lockup from "@/assets/brand/greena-lockup.svg";
import lockupWhite from "@/assets/brand/greena-lockup-white.svg";
import stacked from "@/assets/brand/greena-lockup-stacked.svg";
import wordmark from "@/assets/brand/greena-wordmark.svg";

type Variant = "lockup" | "emblem" | "wordmark" | "stacked";
type Tone = "color" | "white";

const SOURCES: Record<Variant, Record<Tone, string>> = {
  lockup: { color: lockup, white: lockupWhite },
  emblem: { color: emblem, white: emblemWhite },
  stacked: { color: stacked, white: stacked },
  wordmark: { color: wordmark, white: wordmark },
};

interface LogoProps {
  variant?: Variant;
  tone?: Tone;
  className?: string;
  /** Decorative logos (next to a text label) can be hidden from a11y tree. */
  decorative?: boolean;
}

export function Logo({
  variant = "lockup",
  tone = "color",
  className,
  decorative = false,
}: LogoProps) {
  return (
    <img
      src={SOURCES[variant][tone]}
      alt={decorative ? "" : "Greena"}
      aria-hidden={decorative || undefined}
      draggable={false}
      className={cn("select-none", className)}
    />
  );
}
