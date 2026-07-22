/**
 * ARIA — suggested next questions.
 *
 * Composed on the client, not by the model. The `/ask` endpoint returns an
 * answer and the sources it drew on; it does not propose follow-ups. Rather
 * than leave the affordance out, we infer from *which records the answer
 * touched* — if ARIA just read the feed logs, "what is my feed cost per bird?"
 * is a genuinely likely next question.
 *
 * Two rules keep this honest. Suggestions are only ever things ARIA can
 * actually answer from farm data, and they are never phrased as though ARIA
 * anticipated you — they are offered as options, not predictions. If a real
 * suggestion endpoint lands later, this file is the only thing that changes.
 */

interface Rule {
  /** Matched against the sources the answer cited, and the answer text. */
  match: RegExp;
  questions: string[];
}

const RULES: Rule[] = [
  {
    match: /feed/i,
    questions: ["What is my feed cost per bird?", "How long will my feed stock last?"],
  },
  {
    match: /mortalit|death|cull/i,
    questions: ["What is driving the mortality?", "Which flock is worst affected?"],
  },
  {
    match: /disease|health|vaccin/i,
    questions: ["What should I do about the disease risk?", "What vaccines are due?"],
  },
  {
    match: /financ|profit|revenue|expense|cost|kes/i,
    questions: ["What were my biggest expenses?", "Am I on track to break even?"],
  },
  {
    match: /production|egg|weight|yield/i,
    questions: ["How does this compare to last month?", "Which flock is most productive?"],
  },
  {
    match: /inventor|stock|supplier/i,
    questions: ["What needs reordering?", "What did I spend on inventory?"],
  },
];

/** Asked at the start, and whenever nothing more specific applies. */
const GENERAL = [
  "How is my farm doing overall?",
  "What should I focus on this week?",
];

/**
 * @param answer  ARIA's reply text.
 * @param sources The records it cited.
 * @param limit   Kept low — a wall of chips is a menu, not a suggestion.
 */
export function suggestFollowUps(
  answer: string,
  sources: string[] = [],
  limit = 3,
): string[] {
  const haystack = `${sources.join(" ")} ${answer}`;

  const matched = RULES.filter((r) => r.match.test(haystack)).flatMap((r) => r.questions);

  // De-duplicate, top up from the general set so there is always something to
  // tap, and cap it.
  return [...new Set([...matched, ...GENERAL])].slice(0, limit);
}

/** The opening prompts on an empty conversation. */
export const OPENING_ACTIONS: { label: string; question: string }[] = [
  { label: "How is my feed stock?", question: "How is my feed stock?" },
  { label: "What is my profit this month?", question: "What is my profit this month?" },
  { label: "What is my disease risk?", question: "What is my disease risk?" },
  { label: "Predict mortality this week", question: "Predict mortality for the next 7 days" },
];
