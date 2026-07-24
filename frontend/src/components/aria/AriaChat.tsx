/**
 * ARIA — conversation surface.
 *
 * The message model carries more than text because ARIA's answers are not just
 * prose: an answer about disease risk should show the disease card, and every
 * answer should show what it was based on. Chat and dashboard render the *same*
 * card components, so an answer in conversation and the panel it came from are
 * visibly the same object.
 *
 * Voice: `AriaComposer` takes an optional `onVoice`. The seam exists and the
 * layout accommodates it, but when the prop is absent nothing renders — no
 * disabled microphone promising a feature the backend does not have. Same for
 * `onAttach`. Wiring either one up is a prop, not a redesign.
 */
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUp, Mic, Paperclip, User as UserIcon } from "lucide-react";
import { AriaAvatar } from "./AriaIdentity";
import { AriaSources } from "./AriaSignals";
import { MOTION } from "./tokens";
import { cn } from "@/lib/cn";

/* ── Model ─────────────────────────────────────────────────────────────────── */

export interface AriaMessage {
  id: string;
  role: "user" | "aria";
  text: string;
  sources?: string[];
  provider?: string;
  /** Rendered under the bubble — a prediction, disease or forecast card. */
  cards?: React.ReactNode;
  /** Suggested next questions, offered after an answer. */
  followUps?: string[];
  error?: boolean;
  /**
   * Reserved for the image-attachment work. Nothing renders it today; it is
   * here so adding attachments does not mean changing the message type
   * everywhere it is consumed.
   */
  attachments?: { id: string; url: string; alt?: string }[];
}

/* ── Bubble ────────────────────────────────────────────────────────────────── */

export function AriaMessageBubble({
  message,
  onFollowUp,
  index = 0,
}: {
  message: AriaMessage;
  onFollowUp?: (q: string) => void;
  index?: number;
}) {
  const mine = message.role === "user";

  return (
    <motion.div
      initial={{ y: 8 }}
      animate={{ y: 0 }}
      transition={{ ...MOTION.enter, delay: Math.min(index, 3) * 0.03 }}
      className="flex w-full flex-col gap-2"
    >
      {/* Avatar and bubble share a row of their own, so the avatar tracks the
          bottom of the *bubble*. Nesting the follow-ups in that row instead
          made `mt-auto` measure the whole group and stranded the avatar down
          beside the chips. */}
      <div className={cn("flex w-full gap-2.5", mine ? "flex-row-reverse" : "flex-row")}>
        {mine ? (
          <span
            className="mt-auto flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400"
            aria-hidden
          >
            <UserIcon className="h-3.5 w-3.5" />
          </span>
        ) : (
          <span className="mt-auto">
            <AriaAvatar size={30} />
          </span>
        )}

        <div
          className={cn(
            "min-w-0 max-w-[85%] rounded-2xl px-4 py-2.5 text-sm sm:max-w-[76%]",
            mine
              ? "rounded-br-md bg-brand-600 text-white"
              : message.error
                ? "rounded-bl-md bg-red-50 text-red-800 dark:bg-red-500/10 dark:text-red-200"
                : "rounded-bl-md bg-gray-50 text-gray-800 dark:bg-white/[0.05] dark:text-gray-100",
          )}
        >
          <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>

          {!mine && (
            <AriaSources
              sources={message.sources}
              provider={message.provider}
              className="mt-2"
            />
          )}
        </div>
      </div>

      {/* Cards and follow-ups hang below, indented to the bubble's left edge
          (avatar 30px + 10px gap) so they read as belonging to the message. */}
      {message.cards && (
        <div className={cn("space-y-3", mine ? "pr-10" : "pl-10")}>{message.cards}</div>
      )}

      {!mine && message.followUps?.length ? (
        <AriaFollowUps questions={message.followUps} onPick={onFollowUp} className="pl-10" />
      ) : null}
    </motion.div>
  );
}

/* ── Follow-ups & quick actions ────────────────────────────────────────────── */

/**
 * Offered after an answer. These are composed on the client from what the
 * answer touched — the backend does not generate them — so they are phrased as
 * things a farmer might ask next, never as ARIA claiming to know what you meant.
 */
export function AriaFollowUps({
  questions,
  onPick,
  className,
}: {
  questions: string[];
  onPick?: (q: string) => void;
  className?: string;
}) {
  if (!questions.length || !onPick) return null;
  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {questions.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => onPick(q)}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs transition-colors",
            "border-gray-200 text-gray-600 hover:border-brand-300 hover:bg-brand-50/60 hover:text-brand-700",
            "dark:border-white/10 dark:text-gray-300 dark:hover:border-brand-500/40 dark:hover:bg-brand-500/10 dark:hover:text-brand-200",
          )}
        >
          {q}
        </button>
      ))}
    </div>
  );
}

/**
 * The opening prompts, shown only on an empty conversation. A farmer who has
 * never used an assistant does not know what it can be asked; these are the
 * answer to that, and they disappear the moment they are no longer needed.
 */
export function AriaQuickActions({
  actions,
  onPick,
  className,
}: {
  actions: { label: string; question: string }[];
  onPick: (q: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-2 sm:grid-cols-2", className)}>
      {actions.map((a, i) => (
        <motion.button
          key={a.question}
          type="button"
          onClick={() => onPick(a.question)}
          initial={{ y: 6 }}
          animate={{ y: 0 }}
          transition={{ ...MOTION.enter, delay: i * MOTION.stagger }}
          className={cn(
            "rounded-xl border px-3.5 py-3 text-left text-sm transition-colors",
            "border-gray-200 bg-white text-gray-700 hover:border-brand-300 hover:bg-brand-50/50",
            "dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-200",
            "dark:hover:border-brand-500/40 dark:hover:bg-brand-500/10",
          )}
        >
          {a.label}
        </motion.button>
      ))}
    </div>
  );
}

/* ── Composer ──────────────────────────────────────────────────────────────── */

/**
 * 48px on touch, 40px from `sm` up.
 *
 * The design system's 48×48 minimum exists for thumbs; a mouse does not need
 * it, and a row of 48px controls makes the composer look like a toolbar on a
 * desktop. Sizing by breakpoint honours the rule where it is actually about
 * hit accuracy.
 */
const TOUCH_BTN_BASE =
  "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl transition-colors sm:h-10 sm:w-10";

const TOUCH_BTN = `${TOUCH_BTN_BASE} text-gray-400 hover:bg-gray-50 hover:text-gray-600 dark:hover:bg-white/5 dark:hover:text-gray-300`;

/**
 * Auto-growing textarea. Enter sends, Shift+Enter breaks — the convention every
 * messaging app has trained users on. On touch devices the send button is the
 * primary path, so it is a full 48px target.
 */
export function AriaComposer({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder = "Ask ARIA about your farm…",
  /** Supply to reveal the microphone. Absent = no mic rendered. */
  onVoice,
  /** Supply to reveal the attachment control. Absent = nothing rendered. */
  onAttach,
  /**
   * Drops the border and padding, for when the composer sits inside a container
   * that already provides them. An explicit prop rather than overriding classes
   * from outside — `border-0` beating `border` depends on stylesheet order, not
   * on which class the caller passed last.
   */
  bare = false,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
  onVoice?: () => void;
  onAttach?: () => void;
  bare?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const reduced = useReducedMotion();

  // Grow to fit, up to ~5 lines. Reset to auto first or the box can only ever
  // get taller, never shorter, as text is deleted.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
  }, [value]);

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div
      className={cn(
        "flex items-end gap-2 transition-colors",
        !bare && [
          "rounded-2xl border bg-white p-2",
          "border-gray-200 focus-within:border-brand-400",
          "dark:border-white/10 dark:bg-white/[0.03] dark:focus-within:border-brand-500/50",
        ].join(" "),
        className,
      )}
    >
      {onAttach && (
        <button
          type="button"
          onClick={onAttach}
          aria-label="Attach an image"
          className={TOUCH_BTN}
        >
          <Paperclip className="h-4 w-4" />
        </button>
      )}

      <textarea
        ref={ref}
        rows={1}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (canSend) onSubmit();
          }
        }}
        placeholder={placeholder}
        aria-label="Ask ARIA a question"
        className={cn(
          "flex-1 resize-none bg-transparent px-2 py-2.5 text-sm leading-relaxed outline-none",
          "text-gray-900 placeholder:text-gray-400 dark:text-white dark:placeholder:text-gray-500",
        )}
      />

      {onVoice && (
        <button
          type="button"
          onClick={onVoice}
          aria-label="Ask by voice"
          className={TOUCH_BTN}
        >
          <Mic className="h-4 w-4" />
        </button>
      )}

      <motion.button
        type="button"
        onClick={onSubmit}
        disabled={!canSend}
        aria-label="Send"
        whileTap={reduced || !canSend ? undefined : { scale: 0.94 }}
        transition={MOTION.tap}
        className={cn(
          TOUCH_BTN_BASE,
          canSend
            ? "bg-brand-600 text-white hover:bg-brand-700"
            : "bg-gray-100 text-gray-400 dark:bg-white/[0.06] dark:text-gray-600",
        )}
      >
        <ArrowUp className="h-4 w-4" />
      </motion.button>
    </div>
  );
}

/* ── Transcript ────────────────────────────────────────────────────────────── */

/**
 * Scroll container that follows new messages — but only when the farmer is
 * already at the bottom. Yanking the view down while someone is re-reading an
 * earlier answer is the single most irritating thing a chat UI can do.
 */
export function AriaTranscript({
  children,
  dependency,
  className,
}: {
  children: React.ReactNode;
  /** Changes when a message is added. */
  dependency: unknown;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (!el || !pinned) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [dependency, pinned]);

  return (
    <div
      ref={ref}
      onScroll={(e) => {
        const el = e.currentTarget;
        setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
      }}
      className={cn("flex-1 overflow-y-auto", className)}
    >
      {/*
       * Deliberately not wrapped in AnimatePresence.
       *
       * AnimatePresence exists to hold a component in the tree while it plays
       * an `exit` animation. Nothing rendered in this transcript defines one —
       * every entry is a plain initial/animate on the component itself — so it
       * was contributing no behaviour while imposing its strict requirement
       * that every direct child carry a unique key. The transcript's children
       * are a mix of a keyed message list and several conditional siblings
       * (welcome, briefing, confirmation card, thinking indicator), and that
       * combination made React report duplicate keys on every render.
       *
       * Removing it fixes the warning at the cause rather than papering over it
       * with synthetic keys, and changes nothing visible: entry animations
       * still run, exits were never animated.
       */}
      {children}
    </div>
  );
}
