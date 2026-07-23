/**
 * ARIA workspace — deterministic answers.
 *
 * When /aria/record comes back `handled: false`, the farmer asked a question
 * rather than recording something. Part 3 forbids Gemini and Claude in this
 * workspace, so ARIA answers from data already loaded into the snapshot panel
 * instead of calling a model.
 *
 * The rule this follows: only answer what the loaded data actually supports,
 * and always name the module the number came from. A question we cannot answer
 * from records gets an honest "here's where that lives" rather than a guess —
 * the same never-invent-data discipline the recording path holds to.
 */
import type {
  FarmProductionDashboard,
  FinanceDashboardResponse,
  UpcomingVaccinationsResponse,
} from "@/types";

/** The modules an answer can cite. Matches the source badges in the UI. */
export type AnswerSource =
  | "Production"
  | "Feed"
  | "Health"
  | "Finance"
  | "Livestock"
  | "Offline Knowledge";

export interface DeterministicAnswer {
  text: string;
  sources: AnswerSource[];
  /** True when we could actually answer from data (vs. a pointer response). */
  grounded: boolean;
}

export interface SnapshotData {
  production?: FarmProductionDashboard;
  finance?: FinanceDashboardResponse;
  vaccinations?: UpcomingVaccinationsResponse;
}

const KES = (v: string | number) => {
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? `KES ${n.toLocaleString("en-KE")}` : String(v);
};

interface Rule {
  match: RegExp;
  answer: (s: SnapshotData) => DeterministicAnswer | null;
}

/**
 * Ordered most-specific first. Each rule reads only the snapshot it needs and
 * returns null when that data has not loaded, so a rule never claims a number
 * it does not have.
 */
const RULES: Rule[] = [
  {
    // "profit today" / "am i making money" / "review finances"
    match: /profit|margin|making money|finances?|revenue|income|expenses?/i,
    answer: (s) => {
      const f = s.finance;
      if (!f) return null;
      const verdict = f.is_profitable ? "in profit" : "running at a loss";
      const margin = f.gross_margin_pct ? ` (${f.gross_margin_pct}% margin)` : "";
      return {
        text:
          `${f.period_label}: ${KES(f.total_revenue_kes)} in, ` +
          `${KES(f.total_expenses_kes)} out — you're ${verdict}, ` +
          `${KES(f.gross_profit_kes)}${margin}. Feed is your largest cost at ${KES(f.feed_cost_kes)}.`,
        sources: ["Finance"],
        grounded: true,
      };
    },
  },
  {
    match: /vaccinat|vaccine|jab|due|overdue|schedule/i,
    answer: (s) => {
      const v = s.vaccinations;
      if (!v) return null;
      const overdue = v.overdue.length;
      const today = v.due_today.length;
      const week = v.due_this_week.length;
      if (overdue + today + week === 0) {
        return {
          text: "Nothing is due or overdue in the next 7 days. Your flocks are on schedule.",
          sources: ["Health"],
          grounded: true,
        };
      }
      const parts: string[] = [];
      if (overdue) parts.push(`${overdue} overdue`);
      if (today) parts.push(`${today} due today`);
      if (week) parts.push(`${week} due this week`);
      const first = v.overdue[0] ?? v.due_today[0] ?? v.due_this_week[0];
      const detail = first
        ? ` The soonest is ${first.next_vaccine_name ?? first.vaccine_name} for ${first.flock_name}.`
        : "";
      return {
        text: `Vaccinations: ${parts.join(", ")}.${detail}`,
        sources: ["Health"],
        grounded: true,
      };
    },
  },
  {
    match: /egg|production|laying|hen.?day|hdp/i,
    answer: (s) => {
      const p = s.production;
      if (!p) return null;
      const hdp = p.avg_hen_day_production != null ? `, ${p.avg_hen_day_production}% hen-day` : "";
      return {
        text: `${p.eggs_today} eggs collected today, ${p.eggs_this_week} this week${hdp}.`,
        sources: ["Production"],
        grounded: true,
      };
    },
  },
  {
    match: /feed|mash|consumption|eating/i,
    answer: (s) => {
      const p = s.production;
      if (!p) return null;
      return {
        text: `Feed used: ${p.feed_today_kg}kg today, ${p.feed_this_week_kg}kg over the last 7 days.`,
        sources: ["Feed"],
        grounded: true,
      };
    },
  },
  {
    // "why are birds dying" / "mortality" / "flock status" / "losses"
    match: /mortalit|dying|death|died|losses|flock status|how are|birds/i,
    answer: (s) => {
      const p = s.production;
      if (!p) return null;
      const rate = p.total_birds > 0 ? ((p.mortality_this_week / p.total_birds) * 100).toFixed(1) : null;
      const context = rate ? ` (${rate}% of ${p.total_birds.toLocaleString("en-KE")} birds)` : "";
      const age = p.avg_bird_age_days != null ? `, average age ${p.avg_bird_age_days} days` : "";
      const framing =
        p.mortality_this_week === 0
          ? "No mortality recorded this week — that's a healthy sign."
          : `${p.mortality_this_week} birds lost this week${context}. ` +
            `To understand the cause, tell me about symptoms and I'll record them for the health module to track.`;
      return {
        text:
          `You have ${p.active_flock_count} active flock(s), ${p.total_birds.toLocaleString("en-KE")} birds${age}. ` +
          framing,
        sources: ["Livestock", "Production"],
        grounded: true,
      };
    },
  },
];

/**
 * Answer a question from loaded snapshot data, or return a pointer response.
 * Never returns null — the workspace always has something honest to say.
 */
export function answerFromSnapshot(question: string, snapshot: SnapshotData): DeterministicAnswer {
  for (const rule of RULES) {
    if (rule.match.test(question)) {
      const answer = rule.answer(snapshot);
      if (answer) return answer;
    }
  }
  return {
    text:
      "I can record farm activity and answer from your own data — feed, eggs, mortality, " +
      "vaccinations and finances. For anything beyond that, open the matching module and I'll " +
      "pick it up from there. What would you like to record or check?",
    sources: ["Offline Knowledge"],
    grounded: false,
  };
}
