/**
 * ARIA — the shared visual vocabulary.
 *
 * Every AI surface in Greena expresses the same four ideas: how sure ARIA is,
 * how bad something is, which way a number is moving, and where an answer came
 * from. Before this file each screen invented its own mapping, so "high
 * confidence" was green in one place and amber in another.
 *
 * The rule these follow: severity borrows the alert palette (amber/red), and
 * confidence borrows the brand palette (green). They are different questions —
 * a high-confidence prediction of a bad outcome is green-certain about a red
 * fact — and colouring them from one scale is what made the old screens read as
 * contradictory.
 */

/** Backend sends free-form strings; anything unrecognised falls back to neutral. */
export type AriaConfidenceLevel = "high" | "medium" | "low";
export type AriaRiskLevel = "critical" | "high" | "moderate" | "low";
export type AriaTrend = "rising" | "falling" | "stable";
export type AriaSeverity = "critical" | "alert" | "warning" | "info";

interface Swatch {
  /** Chip/badge treatment — background, text, and a border for the dark side. */
  chip: string;
  /** Bare foreground, for icons and inline text. */
  fg: string;
  /** A 1px accent rail, used on the left edge of cards. */
  rail: string;
}

const NEUTRAL: Swatch = {
  chip: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
  fg: "text-gray-500 dark:text-gray-400",
  rail: "bg-gray-300 dark:bg-white/20",
};

/**
 * Confidence — brand green at its most certain, fading to neutral. Deliberately
 * not a red/amber/green traffic light: low confidence is not a *problem*, it is
 * ARIA being honest, and colouring it red would train farmers to distrust the
 * assistant rather than read the number carefully.
 */
export const CONFIDENCE: Record<AriaConfidenceLevel, Swatch> = {
  high: {
    chip: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
    fg: "text-brand-600 dark:text-brand-400",
    rail: "bg-brand-500",
  },
  medium: {
    chip: "bg-navy-50 text-navy-700 dark:bg-navy-500/15 dark:text-navy-200",
    fg: "text-navy-600 dark:text-navy-300",
    rail: "bg-navy-400",
  },
  low: NEUTRAL,
};

/** Risk — the alert scale. This one *is* a traffic light, because it should be. */
export const RISK: Record<AriaRiskLevel, Swatch> = {
  critical: {
    chip: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
    fg: "text-red-600 dark:text-red-400",
    rail: "bg-red-500",
  },
  high: {
    chip: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
    fg: "text-amber-600 dark:text-amber-400",
    rail: "bg-amber-500",
  },
  moderate: {
    chip: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
    fg: "text-sky-600 dark:text-sky-400",
    rail: "bg-sky-500",
  },
  low: {
    chip: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
    fg: "text-brand-600 dark:text-brand-400",
    rail: "bg-brand-500",
  },
};

export const SEVERITY: Record<AriaSeverity, Swatch> = {
  critical: RISK.critical,
  alert: RISK.critical,
  warning: RISK.high,
  info: RISK.moderate,
};

/**
 * Trend colour depends on whether the metric is one you want to go up. Mortality
 * rising is bad; egg production rising is good. Callers say which.
 */
export function trendSwatch(trend: string, higherIsBetter = false): Swatch {
  const t = normaliseTrend(trend);
  if (t === "stable") return NEUTRAL;
  const good = higherIsBetter ? t === "rising" : t === "falling";
  return good ? RISK.low : RISK.high;
}

export const confidenceSwatch = (v: string): Swatch =>
  CONFIDENCE[normalise(v, ["high", "medium", "low"]) as AriaConfidenceLevel] ?? NEUTRAL;

export const riskSwatch = (v: string): Swatch =>
  RISK[normalise(v, ["critical", "high", "moderate", "low"]) as AriaRiskLevel] ?? NEUTRAL;

export const severitySwatch = (v: string): Swatch =>
  SEVERITY[normalise(v, ["critical", "alert", "warning", "info"]) as AriaSeverity] ?? NEUTRAL;

export function normaliseTrend(v: string): AriaTrend {
  const t = (v ?? "").toLowerCase();
  if (t.includes("ris") || t.includes("up") || t.includes("increas")) return "rising";
  if (t.includes("fall") || t.includes("down") || t.includes("decreas")) return "falling";
  return "stable";
}

/** Matches a backend string against known keys, tolerating case and spacing. */
function normalise(v: string, keys: string[]): string | undefined {
  const s = (v ?? "").toLowerCase().trim().replace(/[\s_-]+/g, "");
  return keys.find((k) => k === s);
}

/** "disease_risk" → "Disease risk". Shared so labels are capitalised identically. */
export const label = (s: string): string =>
  (s ?? "").replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());

/**
 * Confidence as a 3-step meter. Reading a filled bar is faster than parsing the
 * word, and it keeps the chip narrow enough for a phone.
 */
export const CONFIDENCE_STEPS: Record<AriaConfidenceLevel, number> = {
  high: 3,
  medium: 2,
  low: 1,
};

/**
 * Motion. One place, so nothing in the AI surface animates on a timing that
 * disagrees with the mark itself. These are slow on purpose — see AriaMark.
 *
 * Entry animations move transform only, never opacity. `Reveal` in the
 * marketing primitives carries the full story: an entry that starts at
 * `opacity: 0` renders the content invisible whenever motion does not run, and
 * it still reports complete textContent, so every DOM-level check passes while
 * a farmer sees a blank panel. Animating transform alone makes the worst case
 * "sits 8px low" instead of "is not there".
 *
 * This is not hypothetical here: the ARIA cards were built with an opacity
 * entry and eleven of them sat at opacity 0 on the brand page, with
 * `getAnimations()` empty — the animation never started at all.
 */
export const MOTION = {
  /** Entry for cards and messages. Short, no bounce; premium reads as settled. */
  enter: { duration: 0.28, ease: [0.22, 1, 0.36, 1] as const },
  /** Hover/press feedback. */
  tap: { duration: 0.12, ease: "easeOut" as const },
  /** Stagger between siblings in a list. */
  stagger: 0.045,
} as const;
