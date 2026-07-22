/**
 * ARIA — the assistant's visual identity.
 *
 * Concept: a leaf whose venation is a node network.
 *
 * Leaf venation is already a branching network in nature, so a single form
 * carries both halves of what ARIA is — agricultural, and intelligent. That
 * avoids the three exhausted options (robot, chat bubble, glowing orb), none of
 * which say anything about farming, and all of which say "chatbot" when ARIA is
 * meant to read as an expert.
 *
 * The geometry is constructed, not drawn: the midrib is a true vertical, the
 * veins leave it at a constant 38°, and the nodes sit exactly on the junctions.
 * Organic curves would have made it a nature logo; the discipline is what makes
 * it sit comfortably next to enterprise software.
 *
 * Reads at every size because the silhouette does the work — a leaf is
 * recognisable in one glance at 16px. Detail is shed as it shrinks (see
 * `detail`), never added.
 */
import { useId } from "react";
import { motion, useReducedMotion } from "motion/react";

export type AriaState = "idle" | "listening" | "thinking" | "responding" | "loading";
export type AriaDetail = "full" | "simple";
export type AriaTone = "colour" | "mono" | "inverse";

interface AriaMarkProps {
  size?: number;
  /** "full" keeps the vein network; "simple" is silhouette + midrib, for ≤20px. */
  detail?: AriaDetail;
  /** "mono" inherits currentColor; "inverse" is for dark or coloured surfaces. */
  tone?: AriaTone;
  /** Animation state. "idle" breathes; omit `animated` to freeze entirely. */
  state?: AriaState;
  animated?: boolean;
  className?: string;
  title?: string;
}

/* ── Geometry ────────────────────────────────────────────────────────────────
 * 24×24 grid, matching the lucide icons ARIA sits beside in the sidebar.
 * Tip (12,2.5) → base (12,21.5). The blade is two mirrored cubics; the control
 * points sit at x=4.2/19.8 so the widest point falls at 45% of the height,
 * which is where a leaf actually reads as a leaf rather than an eye.
 */
/**
 * Control points sit at x≈2.4/21.6 — far outside the blade's actual edge. A
 * cubic only travels about three quarters of the way toward its control point,
 * so pulling them in to the intended edge produced a mark filling 42% of the
 * box, which read thin and undersized beside the lucide icons it shares a
 * sidebar with. These push the curve out to x≈5/19, giving a ~0.75 aspect.
 */
const BLADE = "M12 2.5 C 3.2 8.2, 2.4 15.0, 12 21.5 C 21.6 15.0, 20.8 8.2, 12 2.5 Z";
const MIDRIB = "M12 20.2 L 12 5.0";
/** Vein pairs at a constant 38° off the midrib, longest at the widest point. */
const VEINS = [
  "M12 8.2 L 15.6 5.6", "M12 8.2 L 8.4 5.6",
  "M12 12.4 L 17.2 9.0", "M12 12.4 L 6.8 9.0",
  "M12 16.4 L 16.0 13.2", "M12 16.4 L 8.0 13.2",
];
/** Nodes on the junctions — the "intelligence" signal, and nothing more. */
const NODES: [number, number][] = [[12, 8.2], [12, 12.4], [12, 16.4]];

/* ── Motion ──────────────────────────────────────────────────────────────────
 * Every state is slow and low-amplitude on purpose. An assistant that pulses
 * urgently reads as an alert; ARIA should read as attentive. Nothing here
 * exceeds a 4% scale change or a 1.2s beat.
 */
/**
 * Every state declares an explicit `initial`.
 *
 * On SVG children motion treats opacity as an attribute, and a keyframe array
 * with no starting value resolves to opacity="undefined" — the element renders
 * static and getAnimations() stays empty. Stating the first frame is what makes
 * these run at all.
 */
const NODE_MOTION: Record<AriaState, (i: number) => object> = {
  // Barely alive — proves the assistant is present without asking for attention.
  idle: (i) => ({
    initial: { opacity: 0.55 },
    animate: { opacity: [0.55, 1, 0.55] },
    transition: { duration: 3.6, repeat: Infinity, delay: i * 0.5, ease: "easeInOut" },
  }),
  // Receiving: nodes light base→tip, the direction information travels inward.
  listening: (i) => ({
    initial: { opacity: 0.3, scale: 0.85 },
    animate: { opacity: [0.3, 1, 0.3], scale: [0.85, 1.35, 0.85] },
    transition: { duration: 1.2, repeat: Infinity, delay: (2 - i) * 0.18, ease: "easeInOut" },
  }),
  // Working: a signal travelling the midrib, tip→base.
  thinking: (i) => ({
    initial: { opacity: 0.25 },
    animate: { opacity: [0.25, 1, 0.25] },
    transition: { duration: 0.9, repeat: Infinity, delay: i * 0.22, ease: "easeInOut" },
  }),
  // Answering: all three settle bright together.
  responding: () => ({
    initial: { opacity: 0.6 },
    animate: { opacity: [0.6, 1, 0.85] },
    transition: { duration: 1.6, repeat: Infinity, ease: "easeInOut" },
  }),
  loading: (i) => ({
    initial: { opacity: 0.2 },
    animate: { opacity: [0.2, 1, 0.2] },
    transition: { duration: 1.1, repeat: Infinity, delay: i * 0.3, ease: "easeInOut" },
  }),
};

const BLADE_MOTION: Record<AriaState, object> = {
  idle: { initial: { scale: 1 }, animate: { scale: [1, 1.02, 1] }, transition: { duration: 4.2, repeat: Infinity, ease: "easeInOut" } },
  listening: { initial: { scale: 1 }, animate: { scale: [1, 1.035, 1] }, transition: { duration: 1.2, repeat: Infinity, ease: "easeInOut" } },
  thinking: { initial: { rotate: 0 }, animate: { rotate: [0, 1.4, 0, -1.4, 0] }, transition: { duration: 2.6, repeat: Infinity, ease: "easeInOut" } },
  responding: { initial: { scale: 1 }, animate: { scale: [1, 1.02, 1] }, transition: { duration: 1.6, repeat: Infinity, ease: "easeInOut" } },
  loading: { initial: { rotate: 0 }, animate: { rotate: [0, 360] }, transition: { duration: 2.8, repeat: Infinity, ease: "linear" } },
};

export function AriaMark({
  size = 24,
  detail = "full",
  tone = "colour",
  state = "idle",
  animated = false,
  className = "",
  title,
}: AriaMarkProps) {
  const reduced = useReducedMotion();
  const live = animated && !reduced;

  // Unique per instance and stable across renders. A module-scoped counter was
  // incrementing on every render instead of every mount, so a page with 24
  // marks accumulated 61 gradient defs and the id changed underneath the fill
  // on each re-render.
  const gid = `aria-g-${useId().replace(/:/g, "")}`;

  const bladeFill = tone === "colour" ? `url(#${gid})` : "currentColor";

  /**
   * On `colour` the blade is a green→navy gradient, so white venation drawn on
   * top is correct and legible.
   *
   * On `mono`/`inverse` the blade is a single flat `currentColor`, and white
   * veins were being drawn on top of it regardless of theme — the ternary that
   * chose the colour returned "#ffffff" for all three branches, so it never
   * varied. On a light surface that happened to look right (white veins on a
   * grey leaf against a white page read as cut-through). In dark mode it
   * inverted: near-black sidebar, grey leaf, pure-white veins glowing brighter
   * than the mark itself.
   *
   * The intent was always negative space, so express it as negative space: mask
   * the venation out of the blade and let whatever is behind show through. That
   * is theme-independent by construction — there is no colour to get wrong.
   */
  const masked = tone !== "colour";
  const mid = `aria-m-${gid}`;
  const veinStroke = "#ffffff";
  const veinOpacity = 0.9;

  const Blade = live ? motion.path : "path";
  const Node = live ? motion.circle : "circle";
  const bladeAnim = live ? BLADE_MOTION[state] : {};

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      style={{ overflow: "visible" }}
    >
      {title && <title>{title}</title>}

      <defs>
        {tone === "colour" && (
          /* Green at the growing tip, navy at the root: the palette's own
             story, not decoration. Kept to two stops so it survives flattening
             to a favicon. */
          <linearGradient id={gid} x1="12" y1="2.5" x2="12" y2="21.5" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#0b7d2c" />
            <stop offset="55%" stopColor="#076524" />
            <stop offset="100%" stopColor="#063491" />
          </linearGradient>
        )}

        {masked && (
          /* White keeps the blade, black knocks the venation out of it. The
             mask's own opacities are the animation surface: a node fading to
             black is a hole opening, which reads the same as the coloured
             version's node brightening. */
          <mask id={mid} maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">
            <path d={BLADE} fill="#ffffff" />
            <path d={MIDRIB} stroke="#000000" strokeWidth={1.4} strokeLinecap="round" />
            {detail === "full" && (
              <>
                <g stroke="#000000" strokeWidth={1.1} strokeLinecap="round">
                  {VEINS.map((d) => (
                    <path key={d} d={d} />
                  ))}
                </g>
                {NODES.map(([cx, cy], i) => {
                  const anim = live ? NODE_MOTION[state](i) : {};
                  return (
                    <Node
                      key={`${cx}-${cy}`}
                      cx={cx}
                      cy={cy}
                      r={1.5}
                      fill="#000000"
                      style={{ transformOrigin: `${cx}px ${cy}px` }}
                      {...(anim as object)}
                    />
                  );
                })}
              </>
            )}
          </mask>
        )}
      </defs>

      <g style={{ transformOrigin: "12px 12px" }}>
        <Blade
          d={BLADE}
          fill={bladeFill}
          {...(masked ? { mask: `url(#${mid})` } : {})}
          {...(bladeAnim as object)}
        />

        {/* On colour the venation is drawn over the gradient. On mono it is
            already carved out by the mask above, so drawing it again here would
            re-introduce the white-on-dark problem. */}
        {!masked && (
          <>
            <path
              d={MIDRIB}
              stroke={veinStroke}
              strokeOpacity={veinOpacity}
              strokeWidth={1.4}
              strokeLinecap="round"
            />

            {detail === "full" && (
              <>
                <g stroke={veinStroke} strokeOpacity={veinOpacity * 0.75} strokeWidth={1.1} strokeLinecap="round">
                  {VEINS.map((d) => (
                    <path key={d} d={d} />
                  ))}
                </g>

                {NODES.map(([cx, cy], i) => {
                  const anim = live ? NODE_MOTION[state](i) : {};
                  return (
                    <Node
                      key={`${cx}-${cy}`}
                      cx={cx}
                      cy={cy}
                      r={1.5}
                      fill={veinStroke}
                      style={{ transformOrigin: `${cx}px ${cy}px` }}
                      {...(anim as object)}
                    />
                  );
                })}
              </>
            )}
          </>
        )}
      </g>
    </svg>
  );
}

/**
 * ARIA lockup — mark plus wordmark, for headers and the marketing site.
 */
export function AriaLockup({
  size = 28,
  className = "",
  tone = "colour",
}: {
  size?: number;
  className?: string;
  tone?: AriaTone;
}) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <AriaMark size={size} tone={tone} title="ARIA" />
      <span
        className="font-semibold tracking-[0.14em] text-gray-900 dark:text-white"
        style={{ fontSize: size * 0.52 }}
      >
        ARIA
      </span>
    </span>
  );
}

/**
 * Avatar treatment — the mark on a tinted disc, for chat and notifications
 * where it must hold its own against surrounding content.
 */
export function AriaAvatar({
  size = 36,
  state = "idle",
  animated = false,
  className = "",
}: {
  size?: number;
  state?: AriaState;
  animated?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-brand-50 dark:bg-brand-500/12 ${className}`}
      style={{ width: size, height: size }}
    >
      <AriaMark size={size * 0.62} state={state} animated={animated} title="ARIA" />
    </span>
  );
}
