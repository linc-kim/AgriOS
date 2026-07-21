/**
 * Greena — Marketing UI primitives.
 *
 * The small vocabulary every public page is built from: layout containers,
 * scroll-reveal motion, and the typographic pieces (eyebrow, heading, lead).
 * Keeping them here is what makes eight pages look like one product rather than
 * eight designs.
 *
 * Motion rule: everything animates on entry once, never on loop. Looping motion
 * in a marketing page competes with the content for attention. All of it is
 * disabled under prefers-reduced-motion by `motion`'s own reduced-motion
 * handling plus the explicit checks below.
 */
import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";

// ── Layout ────────────────────────────────────────────────────────────────────

export function Container({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`mx-auto w-full max-w-6xl px-5 sm:px-8 ${className}`}>{children}</div>
  );
}

export function Section({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`relative py-20 sm:py-28 ${className}`}>
      {children}
    </section>
  );
}

// ── Motion ────────────────────────────────────────────────────────────────────

/**
 * Reveals its children as they scroll into view.
 *
 * `once` is deliberate — re-animating on every scroll-by makes long pages feel
 * twitchy and makes it hard to re-read something you just passed.
 */
export function Reveal({
  children,
  delay = 0,
  y = 16,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y }}
      whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** Reveals children in sequence. Use for card grids and feature lists. */
export function Stagger({
  children,
  className = "",
  step = 0.07,
}: {
  children: ReactNode[];
  className?: string;
  step?: number;
}) {
  return (
    <div className={className}>
      {children.map((child, i) => (
        <Reveal key={i} delay={i * step}>
          {child}
        </Reveal>
      ))}
    </div>
  );
}

// ── Typography ────────────────────────────────────────────────────────────────

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-brand-600 dark:text-brand-400">
      {children}
    </p>
  );
}

export function Heading({
  children,
  as: Tag = "h2",
  className = "",
}: {
  children: ReactNode;
  as?: "h1" | "h2" | "h3";
  className?: string;
}) {
  const size =
    Tag === "h1"
      ? "text-4xl sm:text-5xl lg:text-6xl"
      : Tag === "h2"
        ? "text-3xl sm:text-4xl"
        : "text-xl sm:text-2xl";
  return (
    <Tag
      className={`font-semibold tracking-[-0.02em] text-gray-900 dark:text-white ${size} ${className}`}
    >
      {children}
    </Tag>
  );
}

export function Lead({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p className={`text-lg leading-relaxed text-gray-600 dark:text-gray-300 ${className}`}>
      {children}
    </p>
  );
}

// ── Controls ──────────────────────────────────────────────────────────────────

type CTAProps = {
  to: string;
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  className?: string;
};

export function CTA({ to, children, variant = "primary", className = "" }: CTAProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-all " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 " +
    "dark:focus-visible:ring-offset-[#0b0e12]";
  const styles = {
    primary:
      "bg-brand-600 text-white shadow-sm hover:bg-brand-700 hover:shadow-md active:scale-[0.98]",
    secondary:
      "border border-gray-200 bg-white text-gray-900 hover:border-gray-300 hover:bg-gray-50 " +
      "dark:border-white/15 dark:bg-white/[0.04] dark:text-white dark:hover:bg-white/[0.08]",
    ghost:
      "text-gray-700 hover:text-brand-700 dark:text-gray-300 dark:hover:text-brand-300",
  }[variant];

  const external = to.startsWith("http");
  if (external) {
    return (
      <a href={to} className={`${base} ${styles} ${className}`}>
        {children}
      </a>
    );
  }
  return (
    <Link to={to} className={`${base} ${styles} ${className}`}>
      {children}
    </Link>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 dark:border-brand-500/25 dark:bg-brand-500/10 dark:text-brand-300">
      {children}
    </span>
  );
}

// ── Surfaces ──────────────────────────────────────────────────────────────────

export function Card({
  children,
  className = "",
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-gray-200 bg-white p-6 dark:border-white/10 dark:bg-white/[0.03] ${
        interactive
          ? "transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-lg dark:hover:border-brand-500/40"
          : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

/**
 * Stand-in for a product screenshot.
 *
 * Real captures are not available yet, so rather than ship a grey box this
 * renders a labelled browser chrome with the caller's own composition inside —
 * the page reads as finished, and swapping in a real image later is a one-line
 * change per usage.
 */
export function ScreenFrame({
  title,
  children,
  className = "",
}: {
  title: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl dark:border-white/10 dark:bg-[#0f1319] ${className}`}
    >
      <div className="flex items-center gap-2 border-b border-gray-100 bg-gray-50 px-4 py-2.5 dark:border-white/5 dark:bg-white/[0.03]">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
        <span className="ml-3 truncate text-xs text-gray-400">{title}</span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

export function StatTile({
  value,
  label,
  tone = "brand",
}: {
  value: string;
  label: string;
  tone?: "brand" | "navy" | "amber";
}) {
  const toneCls = {
    brand: "text-brand-600 dark:text-brand-400",
    navy: "text-navy-600 dark:text-navy-300",
    amber: "text-amber-600 dark:text-amber-400",
  }[tone];
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-4 dark:border-white/5 dark:bg-white/[0.02]">
      <p className={`text-2xl font-semibold ${toneCls}`}>{value}</p>
      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  );
}
