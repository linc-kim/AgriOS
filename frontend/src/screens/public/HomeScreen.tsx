/**
 * Greena — Home (conversion-first).
 *
 * This page is a sales experience, not a feature list. It follows the farmer's
 * emotional journey: feel understood → recognise the hidden costs → see the
 * transformation → watch it work in a real moment → understand the outcomes
 * (with features as the evidence) → have doubts answered → take the next step.
 *
 * Honesty rule: every outcome maps to a shipped capability. We sell what the
 * feature *does for the farmer*, never a feature that doesn't exist.
 */
import {
  ArrowRight, Wallet, HeartPulse, ClipboardCheck, Clock, TrendingUp,
  Smartphone, Users, Lock, Check,
} from "lucide-react";

import { AriaMark } from "@/components/brand/AriaMark";
import { LineWaves, GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Pill,
  Card, ScreenFrame, StatTile,
} from "@/components/marketing/primitives";
import { EnterpriseShowcase } from "@/components/marketing/EnterpriseShowcase";
import { useSeo } from "@/hooks/useSeo";
import { TRIAL_DAYS, PREMIUM_PLAN_LABEL } from "@/lib/policy";

// The pressures every farmer knows — said plainly, so they feel understood.
const PRESSURES = [
  "A dozen decisions before breakfast, most of them with money attached.",
  "Disease doesn't wait for a convenient week.",
  "Feed is your biggest cost — and the easiest to lose track of.",
  "The farm grows, and suddenly no one person can hold it all in their head.",
];

// Hidden costs — recognition, not fear. Each is a real, common loss.
const HIDDEN_COSTS = [
  ["A vaccination slips a few days", "One missed window can run through a whole flock before you notice."],
  ["Feed “disappears”", "Without a running count, a few kilos a day becomes a hole in your margin."],
  ["You find out late", "A trend you'd have caught in the numbers only shows up when birds are already down."],
  ["Profit is a guess", "At the end of a cycle, “did this batch make money?” shouldn't be a shrug."],
];

// Transformation — believable shifts, not hype.
const SHIFTS = [
  ["Guesswork", "Evidence"],
  ["Memory", "Records that add up"],
  ["Finding out late", "Seeing it coming"],
  ["“About right”", "A number you trust"],
];

// Outcomes first; the real feature is the proof underneath.
const OUTCOMES = [
  {
    icon: Wallet,
    title: "Know whether you're actually making money",
    body: "Every expense and sale lands against the right flock, so profit per batch is a number — not a feeling at the end of the cycle.",
    proof: "Finance & profit per flock",
  },
  {
    icon: HeartPulse,
    title: "Catch problems before they become losses",
    body: "Vaccinations, treatments and mortality are tracked and flagged, so a small issue gets your attention while it's still small.",
    proof: "Health records & alerts",
  },
  {
    icon: ClipboardCheck,
    title: "Stop running the farm from memory",
    body: "Record it once and it's there for good — counts, weights, feed, treatments — for you, your workers and next season.",
    proof: "Connected records",
  },
  {
    icon: Clock,
    title: "Spend the evening with family, not paperwork",
    body: "One entry updates everything it touches. No re-typing the same figures into three books that still disagree.",
    proof: "Automation & one-time entry",
  },
  {
    icon: TrendingUp,
    title: "Grow without losing the plot",
    body: "More houses, more batches, more people — the farm stays legible because the numbers scale with it.",
    proof: "Multi-farm, roles & reports",
  },
];

// Objections, answered before they're asked.
const REASSURANCE = [
  { icon: Smartphone, title: "Works on the phone in your pocket", body: "No new hardware. If you can use WhatsApp, you can use Greena." },
  { icon: Users, title: "Your workers can use it", body: "Log the day in plain language — “collected 320 eggs” — and Greena does the filing." },
  { icon: Lock, title: "Your data stays yours", body: "Export it whenever you like. We never sell it." },
  { icon: Check, title: "Start free, no card", body: "Begin with one flock at no cost. Upgrade only when it's earning its keep." },
];

export default function HomeScreen() {
  useSeo({
    title: "Farm management that makes you money",
    description:
      "Greena helps farmers know if they're making money, catch problems early, and stop running the farm from memory — for poultry, livestock, rabbits, goats, sheep, pigs and more.",
    path: "/",
  });

  return (
    <>
      {/* ── Hero: recognition + hope ─────────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <LineWaves />
          <GlowField />
        </div>

        <Container className="relative py-24 sm:py-32">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Pill>
                <AriaMark size={15} title="ARIA" />
                Now with ARIA — your farm's AI assistant
              </Pill>
            </Reveal>

            <Reveal delay={0.06}>
              <Heading as="h1" className="mt-6">
                Farm with confidence,
                <br className="hidden sm:block" /> not on a hunch.
              </Heading>
            </Reveal>

            <Reveal delay={0.12}>
              <Lead className="mx-auto mt-6 max-w-2xl">
                You already work hard. Greena makes that work pay — by turning the
                day's records into clear answers: what's healthy, what's costing
                you, and whether this batch is making money. For poultry, birds,
                BSF, rabbits, goats, sheep and pigs.
              </Lead>
            </Reveal>

            <Reveal delay={0.18}>
              <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <CTA to="/signup">
                  Start free <ArrowRight className="h-4 w-4" />
                </CTA>
                <CTA to="/aria-ai" variant="secondary">
                  See how ARIA works
                </CTA>
              </div>
            </Reveal>

            <Reveal delay={0.24}>
              <p className="mt-5 text-sm text-gray-500 dark:text-gray-400">
                No card required · Works on any phone · Your data stays yours
              </p>
            </Reveal>
          </div>

          {/* Evidence, right up front: this is what clarity looks like. */}
          <Reveal delay={0.3} y={28}>
            <div className="mx-auto mt-16 max-w-4xl">
              <ScreenFrame title="greena.app — Dashboard">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatTile value="4,820" label="Live birds" />
                  <StatTile value="96.4%" label="Survival rate" />
                  <StatTile value="1.62" label="Feed conversion" tone="navy" />
                  <StatTile value="KES 148k" label="Profit this cycle" tone="amber" />
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {[
                    ["Batch A — Broilers", "Day 34 · 1,600 birds"],
                    ["Batch B — Layers", "Week 22 · 2,400 birds"],
                    ["Batch C — Broilers", "Day 12 · 820 birds"],
                  ].map(([t, s]) => (
                    <div key={t} className="rounded-xl border border-gray-100 p-3 dark:border-white/5">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">{t}</p>
                      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{s}</p>
                    </div>
                  ))}
                </div>
              </ScreenFrame>
            </div>
          </Reveal>
        </Container>
      </section>

      {/* ── Understood: we know what farming asks of you ─────────────────── */}
      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>We get it</Eyebrow>
              <Heading>Farming is a hundred decisions a day — and they all cost something</Heading>
              <Lead className="mx-auto mt-5">
                You carry the weight of it: the money on the line, the animals
                depending on you, the pride in doing it well. That's a lot to hold
                in your head, season after season.
              </Lead>
            </Reveal>
          </div>
          <Stagger className="mx-auto mt-10 grid max-w-3xl gap-3 sm:grid-cols-2">
            {PRESSURES.map((p) => (
              <div key={p} className="rounded-xl border border-gray-200 bg-white p-4 text-[15px] leading-relaxed text-gray-700 dark:border-white/10 dark:bg-white/[0.02] dark:text-gray-200">
                {p}
              </div>
            ))}
          </Stagger>
        </Container>
      </Section>

      {/* ── Hidden costs: concern, through recognition ───────────────────── */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>The hidden costs</Eyebrow>
              <Heading>The most expensive problems are the ones you can't see</Heading>
              <Lead className="mx-auto mt-5">
                None of these feel like a crisis on the day. They just quietly take
                money off the farm — until you're left wondering where it went.
              </Lead>
            </Reveal>
          </div>
          <Stagger className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-2">
            {HIDDEN_COSTS.map(([t, s]) => (
              <Card key={t}>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{s}</p>
              </Card>
            ))}
          </Stagger>
        </Container>
      </Section>

      {/* ── Transformation: without → with ───────────────────────────────── */}
      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>The shift</Eyebrow>
              <Heading>From running blind to farming with your eyes open</Heading>
            </Reveal>
          </div>
          <Reveal delay={0.08}>
            <div className="mx-auto mt-10 max-w-2xl divide-y divide-gray-200 overflow-hidden rounded-2xl border border-gray-200 bg-white dark:divide-white/10 dark:border-white/10 dark:bg-white/[0.02]">
              {SHIFTS.map(([from, to]) => (
                <div key={from} className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 px-5 py-4">
                  <span className="text-right text-sm text-gray-400 line-through dark:text-gray-500">{from}</span>
                  <ArrowRight className="h-4 w-4 text-brand-500" aria-hidden />
                  <span className="text-[15px] font-semibold text-gray-900 dark:text-white">{to}</span>
                </div>
              ))}
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* ── The story: one entry, everywhere it matters ──────────────────── */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <Eyebrow>A moment on the farm</Eyebrow>
              <Heading>Your worker records the feed. Greena does the rest.</Heading>
              <Lead className="mt-5">
                One person, one entry, thirty seconds. Behind the scenes, the whole
                picture updates — so you never have to sit down and work it all out
                later.
              </Lead>
              <ul className="mt-6 space-y-3">
                {[
                  "Feed stock goes down by what was used",
                  "This flock's cost per bird goes up",
                  "Feed conversion is recalculated",
                  "Your profit forecast adjusts",
                ].map((s) => (
                  <li key={s} className="flex gap-3 text-[15px] text-gray-700 dark:text-gray-200">
                    <Check className="mt-0.5 h-5 w-5 shrink-0 text-brand-600 dark:text-brand-400" />
                    {s}
                  </li>
                ))}
              </ul>
            </Reveal>

            <Reveal delay={0.12} y={24}>
              <ScreenFrame title="greena.app — Feed logged">
                <div className="space-y-3">
                  <div className="rounded-xl border border-gray-100 p-3 dark:border-white/5">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">Added: 2 bags · Batch A</p>
                    <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">by Musa · 6:40 am</p>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <StatTile value="−50kg" label="Feed stock" />
                    <StatTile value="1.62" label="FCR" tone="navy" />
                    <StatTile value="KES 148k" label="Forecast" tone="amber" />
                  </div>
                </div>
              </ScreenFrame>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ── Outcomes (features as evidence) ──────────────────────────────── */}
      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>What changes for you</Eyebrow>
              <Heading>Five ways your farm gets easier to run</Heading>
              <Lead className="mt-4">
                Not a feature list — the outcomes farmers actually feel. The tools
                that make each one happen are named underneath.
              </Lead>
            </Reveal>
          </div>

          <Stagger className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {OUTCOMES.map((o) => (
              <Card key={o.title} interactive className="flex h-full flex-col">
                <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <o.icon className="h-5 w-5" />
                </span>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">{o.title}</h3>
                <p className="mt-1.5 flex-1 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{o.body}</p>
                <p className="mt-4 text-xs font-medium uppercase tracking-[0.08em] text-brand-600/80 dark:text-brand-400/80">
                  {o.proof}
                </p>
              </Card>
            ))}
          </Stagger>

          <Reveal delay={0.1}>
            <div className="mt-10 text-center">
              <CTA to="/features" variant="secondary">
                See exactly how it works <ArrowRight className="h-4 w-4" />
              </CTA>
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* ── ARIA: reduce risk, show how ──────────────────────────────────── */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <Eyebrow>ARIA</Eyebrow>
              <Heading>Ask your farm a question. Get an answer you can act on.</Heading>
              <Lead className="mt-5">
                ARIA reads your actual records — not the internet — and answers in
                plain language. It's like having someone who's memorised every
                figure on the farm, ready whenever you are.
              </Lead>
              <div className="mt-7">
                <CTA to="/aria-ai">
                  How ARIA works <ArrowRight className="h-4 w-4" />
                </CTA>
              </div>
            </Reveal>

            <Reveal delay={0.12} y={24}>
              <ScreenFrame title="ARIA">
                <div className="space-y-3">
                  <Bubble side="user">I collected 320 eggs today</Bubble>
                  <Bubble side="aria">
                    Logged for Batch B. That's 6% above last week's daily average —
                    lay rate is now 87%.
                  </Bubble>
                  <Bubble side="user">Which flock made the most money?</Bubble>
                  <Bubble side="aria">
                    Batch A. KES 214,000 revenue against KES 66,000 in feed and
                    health costs over 42 days.
                  </Bubble>
                </div>
              </ScreenFrame>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ── Enterprises ──────────────────────────────────────────────────── */}
      <EnterpriseShowcase />

      {/* ── Reduce risk: answer the doubts ───────────────────────────────── */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>Will it work for me?</Eyebrow>
              <Heading>Fair question. Here's the honest answer.</Heading>
            </Reveal>
          </div>
          <Stagger className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {REASSURANCE.map((r) => (
              <Card key={r.title} className="h-full">
                <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <r.icon className="h-5 w-5" />
                </span>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{r.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{r.body}</p>
              </Card>
            ))}
          </Stagger>
        </Container>
      </Section>

      {/* ── Close: the natural next step ─────────────────────────────────── */}
      <Section className="relative overflow-hidden border-t border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative">
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Heading>Start with one flock. See the difference in a week.</Heading>
              <Lead className="mx-auto mt-5">
                Set-up takes about ten minutes and Greena walks you through it. Add
                a farm, a house and your first batch — the numbers start working for
                you from day one. Free to begin, with a {TRIAL_DAYS}-day{" "}
                {PREMIUM_PLAN_LABEL} trial when you're ready for more.
              </Lead>
              <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <CTA to="/signup">
                  Start free <ArrowRight className="h-4 w-4" />
                </CTA>
                <CTA to="/pricing" variant="secondary">
                  See pricing
                </CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>
    </>
  );
}

function Bubble({ side, children }: { side: "user" | "aria"; children: React.ReactNode }) {
  const isUser = side === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-brand-600 text-white"
            : "bg-gray-100 text-gray-800 dark:bg-white/[0.06] dark:text-gray-100"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
