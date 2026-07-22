/**
 * ARIA — the card family.
 *
 * Everything ARIA produces is one of four things: a prediction, a forecast, a
 * warning, or a suggestion. Each gets a card, and all four share one shell
 * (`AriaCard`) so a farmer learns the layout once. The accent rail on the left
 * edge is the only thing that varies by kind — colour carries the meaning,
 * structure stays put.
 *
 * These render in two places: the AI dashboard, and inline in chat when ARIA's
 * answer is about one of them. Same component both times, which is what makes
 * the assistant and the dashboard feel like one system.
 */
import { motion } from "motion/react";
import { Activity, Lightbulb, ShieldAlert, TrendingUp, type LucideIcon } from "lucide-react";
import {
  MOTION,
  label as toLabel,
  riskSwatch,
  severitySwatch,
} from "./tokens";
import {
  AriaConfidence,
  AriaFactors,
  AriaRiskChip,
  AriaTrendChip,
} from "./AriaSignals";
import { AriaBadge } from "./AriaIdentity";
import { cn } from "@/lib/cn";
import type {
  AIDiseaseRisk,
  AIForecast,
  AIMortalityPrediction,
} from "@/types";

/* ── Shell ─────────────────────────────────────────────────────────────────── */

export function AriaCard({
  title,
  icon: Icon,
  rail,
  attribution = false,
  action,
  children,
  className,
  index = 0,
}: {
  title?: string;
  icon?: LucideIcon;
  /** Tailwind bg-* class for the 3px accent rail. Omit for an unaccented card. */
  rail?: string;
  /** Show the ARIA pill — used where the card sits among non-AI content. */
  attribution?: boolean;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  /** Position in a list, for entry stagger. */
  index?: number;
}) {
  return (
    <motion.section
      initial={{ y: 8 }}
      // Transform only, never opacity — see MOTION in tokens.ts. A card that
      // starts invisible stays invisible whenever motion does not run, and
      // this one demonstrably did.
      animate={{ y: 0 }}
      transition={{ ...MOTION.enter, delay: Math.min(index, 6) * MOTION.stagger }}
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-white p-5",
        "border-gray-200 dark:border-white/10 dark:bg-white/[0.03]",
        className,
      )}
    >
      {rail && <span className={cn("absolute inset-y-0 left-0 w-[3px]", rail)} aria-hidden />}

      {(title || action || attribution) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            {Icon && <Icon className="h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" aria-hidden />}
            {title}
          </h3>
          <span className="flex shrink-0 items-center gap-2">
            {attribution && <AriaBadge size="sm" />}
            {action}
          </span>
        </header>
      )}

      {children}
    </motion.section>
  );
}

/* ── Prediction ────────────────────────────────────────────────────────────── */

/**
 * A number ARIA expects to see, with its working shown. The headline figure is
 * large because it is the answer; everything under it exists to let a farmer
 * decide whether to believe the figure.
 */
export function AriaPredictionCard({
  prediction,
  title = "Mortality prediction",
  horizon = "next 7 days",
  /** Mortality rising is bad — flip for metrics where up is good. */
  higherIsBetter = false,
  className,
  index,
}: {
  prediction: AIMortalityPrediction;
  title?: string;
  horizon?: string;
  higherIsBetter?: boolean;
  className?: string;
  index?: number;
}) {
  const p = prediction;
  return (
    <AriaCard
      title={title}
      icon={Activity}
      rail="bg-navy-500"
      className={className}
      index={index}
      action={<AriaConfidence value={p.confidence} showLabel={false} />}
    >
      <p className="text-[11px] uppercase tracking-wide text-gray-400 dark:text-gray-500">
        {horizon}
      </p>

      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
        <span className="text-3xl font-semibold tabular-nums tracking-[-0.02em] text-gray-900 dark:text-white">
          {p.predicted_next_7d}
        </span>
        <AriaTrendChip trend={p.trend} higherIsBetter={higherIsBetter} />
        {typeof p.recent_7d === "number" && (
          <span className="text-xs text-gray-400 dark:text-gray-500">
            vs {p.recent_7d} recorded
          </span>
        )}
      </div>

      {p.explanation && (
        <p className="mt-2 text-sm leading-relaxed text-gray-500 dark:text-gray-400">
          {p.explanation}
        </p>
      )}

      <AriaFactors factors={p.factors} className="mt-3" />

      <footer className="mt-3 border-t border-gray-100 pt-2.5 dark:border-white/[0.06]">
        <AriaConfidence value={p.confidence} />
      </footer>
    </AriaCard>
  );
}

/* ── Disease warning ───────────────────────────────────────────────────────── */

/**
 * The one card allowed to raise its voice — and only when the level earns it.
 * At `low` it is a calm green card, because a disease panel that looks alarming
 * every day teaches farmers to ignore it on the day it matters.
 */
export function AriaDiseaseCard({
  risk,
  className,
  index,
}: {
  risk: AIDiseaseRisk;
  className?: string;
  index?: number;
}) {
  const s = riskSwatch(risk.level);
  const severe = ["critical", "high"].includes((risk.level ?? "").toLowerCase());

  return (
    <AriaCard
      title="Disease risk"
      icon={ShieldAlert}
      rail={s.rail}
      className={cn(
        severe && "border-amber-200/80 dark:border-amber-500/25",
        className,
      )}
      index={index}
    >
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-3xl font-semibold tabular-nums tracking-[-0.02em] text-gray-900 dark:text-white">
          {risk.score}
          <span className="text-base font-normal text-gray-400 dark:text-gray-500">/100</span>
        </span>
        <AriaRiskChip level={risk.level} />
      </div>

      {risk.recommendation && (
        <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
          {risk.recommendation}
        </p>
      )}

      <AriaFactors factors={risk.factors} className="mt-3" />
    </AriaCard>
  );
}

/* ── Forecast ──────────────────────────────────────────────────────────────── */

export function AriaForecastCard({
  forecast,
  className,
  index,
}: {
  forecast: AIForecast;
  className?: string;
  index?: number;
}) {
  const f = forecast;
  return (
    <motion.div
      initial={{ y: 8 }}
      animate={{ y: 0 }}
      transition={{ ...MOTION.enter, delay: Math.min(index ?? 0, 6) * MOTION.stagger }}
      className={cn(
        "rounded-xl border border-gray-200 bg-white p-4",
        "dark:border-white/10 dark:bg-white/[0.03]",
        className,
      )}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
        {toLabel(f.metric)}
      </p>
      <p className="mt-1.5 text-lg font-semibold tabular-nums text-gray-900 dark:text-white">
        {f.projected_value}{" "}
        <span className="text-sm font-normal text-gray-400 dark:text-gray-500">{f.unit}</span>
      </p>

      <div className="mt-1.5 flex items-center gap-2">
        <AriaConfidence value={f.confidence} showLabel={false} />
        <span className="text-[11px] text-gray-400 dark:text-gray-500">
          {f.horizon_days}-day outlook
        </span>
      </div>

      {f.factors?.length > 0 && (
        <ul className="mt-2.5 space-y-1 text-xs leading-snug text-gray-500 dark:text-gray-400">
          {f.factors.slice(0, 3).map((x, i) => (
            <li key={i} className="flex gap-1.5">
              <span className="text-gray-300 dark:text-gray-600" aria-hidden>
                ·
              </span>
              {x}
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );
}

/* ── Recommendation & insight ──────────────────────────────────────────────── */

/** Backend sends `{title, type}` for recommendations, `{title, severity}` for insights. */
export interface AriaRecommendationItem {
  title?: string;
  type?: string;
  [k: string]: unknown;
}
export interface AriaInsightItem {
  title?: string;
  severity?: string;
  [k: string]: unknown;
}

/**
 * Something ARIA suggests doing. Rendered as a row rather than a full card —
 * these arrive five at a time, and five cards would drown the panel they sit in.
 */
export function AriaRecommendation({
  item,
  onAction,
  className,
  index = 0,
}: {
  item: AriaRecommendationItem;
  onAction?: () => void;
  className?: string;
  index?: number;
}) {
  const Row = onAction ? motion.button : motion.div;
  return (
    <Row
      {...(onAction ? { onClick: onAction, type: "button" as const } : {})}
      initial={{ x: -4 }}
      animate={{ x: 0 }}
      transition={{ ...MOTION.enter, delay: Math.min(index, 6) * MOTION.stagger }}
      className={cn(
        "group flex w-full items-start gap-2.5 rounded-lg px-2 py-2 text-left transition-colors",
        onAction && "hover:bg-gray-50 dark:hover:bg-white/[0.04]",
        className,
      )}
    >
      <span
        className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-600 dark:bg-brand-500/12 dark:text-brand-400"
        aria-hidden
      >
        <Lightbulb className="h-3 w-3" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm leading-snug text-gray-800 dark:text-gray-200">
          {item.title || "Recommendation"}
        </span>
        {item.type && (
          <span className="mt-0.5 block text-[11px] text-gray-400 dark:text-gray-500">
            {toLabel(String(item.type))}
          </span>
        )}
      </span>
    </Row>
  );
}

/**
 * Something ARIA noticed. Severity-tinted so the eye finds the urgent one
 * without reading all five.
 */
export function AriaInsightCard({
  item,
  className,
  index = 0,
}: {
  item: AriaInsightItem;
  className?: string;
  index?: number;
}) {
  const sev = String(item.severity ?? "info");
  const s = severitySwatch(sev);

  return (
    <motion.div
      initial={{ x: -4 }}
      animate={{ x: 0 }}
      transition={{ ...MOTION.enter, delay: Math.min(index, 6) * MOTION.stagger }}
      className={cn("flex items-start gap-2.5 rounded-lg px-2 py-2", className)}
    >
      <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", s.rail)} aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="block text-sm leading-snug text-gray-800 dark:text-gray-200">
          {item.title || "Insight"}
        </span>
        {item.severity && (
          <span className={cn("mt-0.5 block text-[11px] font-medium", s.fg)}>
            {toLabel(sev)}
          </span>
        )}
      </span>
    </motion.div>
  );
}

/* ── Headline ──────────────────────────────────────────────────────────────── */

/**
 * ARIA's one-line summary of the farm, at the top of the AI dashboard. The
 * assistant's most prominent moment, so it gets the mark itself rather than a
 * generic icon.
 */
export function AriaHeadline({
  headline,
  meta,
  className,
}: {
  headline: string;
  meta?: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ y: 6 }}
      animate={{ y: 0 }}
      transition={MOTION.enter}
      className={cn(
        "rounded-2xl border px-4 py-3.5",
        "border-brand-200/70 bg-brand-50/70 dark:border-brand-500/25 dark:bg-brand-500/[0.08]",
        className,
      )}
    >
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 shrink-0">
          <AriaBadge size="sm" />
        </span>
        <p className="text-sm leading-relaxed text-brand-900 dark:text-brand-50">{headline}</p>
      </div>
      {meta && (
        <p className="mt-1.5 pl-1 text-[11px] text-brand-700/70 dark:text-brand-200/60">{meta}</p>
      )}
    </motion.div>
  );
}

export { TrendingUp };
