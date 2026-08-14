/**
 * Greena — motion system tokens (single source for marketing animation).
 *
 * Centralizes durations, easings and shared variants so scroll-driven sections
 * feel like one system and can be tuned or disabled in one place. Built on the
 * `motion` library already in the app. Every consumer must gate on
 * `useReducedMotion()` — content is always readable without animation.
 */
import type { Variants, Transition } from "motion/react";

/** Seconds. */
export const DURATION = {
  fast: 0.2,
  base: 0.4,
  slow: 0.7,
} as const;

/** Cubic-bezier easings. */
export const EASE = {
  standard: [0.4, 0, 0.2, 1],
  entrance: [0, 0, 0.2, 1],
  emphasized: [0.2, 0, 0, 1],
} as const;

export const springSoft: Transition = { type: "spring", stiffness: 120, damping: 20, mass: 0.6 };

/** Fade + rise, for section reveals. Distance is small on purpose. */
export const revealVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.slow, ease: EASE.entrance },
  },
};

/** Container that reveals children in sequence. */
export const staggerParent = (stagger = 0.08): Variants => ({
  hidden: {},
  visible: { transition: { staggerChildren: stagger } },
});

/** Standard viewport trigger — animate once, a little before fully in view. */
export const inViewOnce = { once: true, amount: 0.3, margin: "0px 0px -10% 0px" } as const;
