/**
 * Greena — Home.
 *
 * The first impression. Structure: hero → proof → what it replaces → module
 * grid → ARIA → outcomes → close.
 *
 * Copy is written for a farmer, not a buyer of software: it names the job
 * (knowing what the flock cost and earned) rather than the feature list.
 */
import {
  ArrowRight, Bird, Wheat, HeartPulse, Wallet, Package, Zap, FileText,
  Bell, BarChart3, Check,
} from "lucide-react";

import { AriaMark } from "@/components/brand/AriaMark";

import { LineWaves, GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Pill,
  Card, ScreenFrame, StatTile,
} from "@/components/marketing/primitives";

const MODULES = [
  { icon: Bird, name: "Flocks", copy: "Every batch from placement to sale, with live bird counts." },
  { icon: Wheat, name: "Feed", copy: "Stock, purchases and consumption — and what a kilo actually cost you." },
  { icon: HeartPulse, name: "Health", copy: "Vaccinations, treatments and disease alerts before they spread." },
  { icon: Wallet, name: "Finance", copy: "Expenses and revenue per flock, so profit is a number not a guess." },
  { icon: Package, name: "Inventory", copy: "Supplies, assets and maintenance, with reorder warnings." },
  { icon: Zap, name: "Automation", copy: "Reminders and rules that chase the work for you." },
  { icon: FileText, name: "Reports", copy: "Production, mortality and P&L, ready to export." },
  { icon: Bell, name: "Notifications", copy: "The things that need you today — nothing that doesn't." },
  { icon: BarChart3, name: "Analytics", copy: "Trends across flocks, seasons and houses." },
];

const REPLACES = [
  "Exercise books that get lost or rained on",
  "Six different spreadsheets that disagree",
  "Guessing feed cost per bird at the end of a cycle",
  "Finding out about a disease outbreak a week late",
  "Not knowing which flock actually made money",
];

import { useSeo } from "@/hooks/useSeo";

export default function HomeScreen() {
  useSeo({
    title: "The farm operating system",
    description:
      "Greena keeps your farm's records, turns them into reports and forecasts, and gives you ARIA — an AI assistant grounded in your own data. Built for farms across East Africa.",
    path: "/",
  });
  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
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
                Run your farm on numbers,
                <br className="hidden sm:block" /> not memory.
              </Heading>
            </Reveal>

            <Reveal delay={0.12}>
              <Lead className="mx-auto mt-6 max-w-2xl">
                Greena keeps every flock, feed bag, vaccination and shilling in one
                place — then tells you what it means. Built for Kenyan poultry
                farms, from a hundred birds to a hundred thousand.
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

          {/* Product glimpse */}
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
                    <div
                      key={t}
                      className="rounded-xl border border-gray-100 p-3 dark:border-white/5"
                    >
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

      {/* ── What it replaces ─────────────────────────────────────────────── */}
      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <Reveal>
                <Eyebrow>The problem</Eyebrow>
                <Heading>You already have the data. It's just scattered.</Heading>
                <Lead className="mt-5">
                  Most farms record plenty — in books, on phones, in someone's head.
                  The trouble starts when you need to answer a simple question:
                  did this batch make money, and why?
                </Lead>
              </Reveal>
            </div>

            <Reveal delay={0.1}>
              <Card>
                <p className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">
                  Greena replaces
                </p>
                <ul className="space-y-3">
                  {REPLACES.map((item) => (
                    <li key={item} className="flex gap-3 text-sm text-gray-600 dark:text-gray-300">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" />
                      {item}
                    </li>
                  ))}
                </ul>
              </Card>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* ── Modules ──────────────────────────────────────────────────────── */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>One system</Eyebrow>
              <Heading>Everything the farm runs on</Heading>
              <Lead className="mt-4">
                Nine connected modules. Record something once and it shows up
                everywhere it matters — a feed purchase becomes an expense, a
                mortality updates your live count.
              </Lead>
            </Reveal>
          </div>

          <Stagger className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {MODULES.map((m) => (
              <Card key={m.name} interactive className="h-full">
                <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <m.icon className="h-5 w-5" />
                </span>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                  {m.name}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                  {m.copy}
                </p>
              </Card>
            ))}
          </Stagger>

          <Reveal delay={0.1}>
            <div className="mt-10 text-center">
              <CTA to="/features" variant="secondary">
                Explore every feature <ArrowRight className="h-4 w-4" />
              </CTA>
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* ── ARIA ─────────────────────────────────────────────────────────── */}
      <Section>
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <Eyebrow>ARIA</Eyebrow>
              <Heading>Ask your farm a question</Heading>
              <Lead className="mt-5">
                ARIA reads your actual records — not the internet — and answers in
                plain language. Log the day's work by typing it the way you'd say
                it, and ask what it means afterwards.
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

      {/* ── Close ────────────────────────────────────────────────────────── */}
      <Section className="relative overflow-hidden border-t border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative">
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Heading>Start with one flock.</Heading>
              <Lead className="mx-auto mt-5">
                Set up takes about ten minutes, and Greena walks you through it.
                Add a farm, a house and your first batch — the numbers start
                working from day one.
              </Lead>
              <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <CTA to="/signup">
                  Create your account <ArrowRight className="h-4 w-4" />
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
