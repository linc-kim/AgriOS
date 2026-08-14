/**
 * Greena — Features.
 *
 * Every module gets the same shape: the farmer's problem, what Greena does, and
 * the outcome. Deliberately not a technical description — "tracks feed
 * inventory" tells a farmer nothing they care about; "know what a kilo of gain
 * cost you" does.
 */
import {
  Bird, Wheat, HeartPulse, Wallet, Package, Zap, FileText, Bell,
  BarChart3, ArrowRight, Check,
} from "lucide-react";
import { AriaIcon } from "@/components/aria";
import type { ModuleIcon } from "@/shell/registry";

import { GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Eyebrow, Heading, Lead, CTA, Card, ScreenFrame,
  StatTile,
} from "@/components/marketing/primitives";

interface Feature {
  icon: ModuleIcon;
  name: string;
  problem: string;
  what: string;
  outcomes: string[];
  demo: React.ReactNode;
}

const FEATURES: Feature[] = [
  {
    icon: Bird,
    name: "Farm & Flock Management",
    problem: "Bird counts drift. Nobody is quite sure how many are in house three.",
    what:
      "Every batch is tracked from placement to sale. Mortality and culls come off the live count automatically, and each flock carries its own history.",
    outcomes: [
      "Always know your true live bird count",
      "Compare batches on survival, weight and days to market",
      "See which house consistently performs best",
    ],
    demo: (
      <div className="grid grid-cols-3 gap-3">
        <StatTile value="1,600" label="Batch A" />
        <StatTile value="2,400" label="Batch B" />
        <StatTile value="96.4%" label="Survival" tone="navy" />
      </div>
    ),
  },
  {
    icon: Wheat,
    name: "Feed Management",
    problem: "Feed is the biggest cost on the farm and the hardest to pin down.",
    what:
      "Record purchases and daily consumption. Greena tracks stock, warns before you run out, and works out feed conversion per batch.",
    outcomes: [
      "Know your real cost per kilo of gain",
      "Get warned before stock runs out, not after",
      "Spot the batch that is eating more than it should",
    ],
    demo: (
      <div className="grid grid-cols-3 gap-3">
        <StatTile value="1.62" label="FCR" />
        <StatTile value="840 kg" label="In store" tone="navy" />
        <StatTile value="6 days" label="Until reorder" tone="amber" />
      </div>
    ),
  },
  {
    icon: HeartPulse,
    name: "Health",
    problem: "By the time a problem is obvious, it has usually spread.",
    what:
      "Vaccination schedules, treatment records and mortality patterns in one place, with alerts when deaths rise above the expected range for that age.",
    outcomes: [
      "Never miss a vaccination date",
      "Catch mortality spikes in days, not weeks",
      "Hand a vet a complete history instead of a memory",
    ],
    demo: (
      <div className="space-y-2">
        {[
          ["Newcastle — Batch A", "Due in 3 days", "amber"],
          ["Gumboro — Batch B", "Completed", "brand"],
        ].map(([t, s, tone]) => (
          <div key={t} className="flex items-center justify-between rounded-xl border border-gray-100 p-3 dark:border-white/5">
            <span className="text-sm text-gray-800 dark:text-gray-100">{t}</span>
            <span className={`text-xs font-medium ${tone === "amber" ? "text-amber-600 dark:text-amber-400" : "text-brand-600 dark:text-brand-400"}`}>{s}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    icon: Wallet,
    name: "Finance",
    problem: "Profit is a feeling at the end of the cycle, not a number during it.",
    what:
      "Expenses and revenue attach to the flock that caused them. Feed purchases become expenses automatically, so the books keep themselves.",
    outcomes: [
      "See profit per batch while it is still running",
      "Know which costs are actually eating the margin",
      "Produce a P&L without rebuilding it from receipts",
    ],
    demo: (
      <div className="grid grid-cols-3 gap-3">
        <StatTile value="KES 214k" label="Revenue" />
        <StatTile value="KES 66k" label="Costs" tone="amber" />
        <StatTile value="KES 148k" label="Profit" tone="navy" />
      </div>
    ),
  },
  {
    icon: Package,
    name: "Inventory & Assets",
    problem: "You discover the drinkers are broken on the morning you need them.",
    what:
      "Track supplies, equipment and maintenance schedules, with reorder levels that warn you in advance.",
    outcomes: [
      "Stop emergency trips to the agrovet",
      "Service equipment before it fails",
      "Know what you own and what it is worth",
    ],
    demo: (
      <div className="grid grid-cols-3 gap-3">
        <StatTile value="34" label="Items" />
        <StatTile value="3" label="Low stock" tone="amber" />
        <StatTile value="2" label="Service due" tone="navy" />
      </div>
    ),
  },
  {
    icon: Zap,
    name: "Automation",
    problem: "The routine work is what gets forgotten when the day is busy.",
    what:
      "Rules and reminders that run themselves — vaccination prompts, daily log nudges, low-stock alerts and weekly summaries.",
    outcomes: [
      "The farm chases you, instead of the other way round",
      "Workers get told what to do without being asked",
      "Nothing routine depends on someone remembering",
    ],
    demo: (
      <div className="space-y-2">
        {["Daily log reminder — 20:00", "Vaccination due — 3 days ahead", "Weekly summary — Friday"].map((t) => (
          <div key={t} className="flex items-center gap-2 rounded-xl border border-gray-100 p-3 text-sm text-gray-700 dark:border-white/5 dark:text-gray-200">
            <Zap className="h-4 w-4 text-brand-600 dark:text-brand-400" /> {t}
          </div>
        ))}
      </div>
    ),
  },
  {
    icon: FileText,
    name: "Reports",
    problem: "Getting a straight answer means an evening with a calculator.",
    what:
      "Production, mortality, feed, health and financial reports across any period, exportable to CSV, Excel or PDF.",
    outcomes: [
      "Answer a buyer or lender in minutes",
      "Compare this cycle against the last one",
      "Export the numbers your accountant asks for",
    ],
    demo: (
      <div className="grid grid-cols-2 gap-3">
        <StatTile value="14" label="Report types" />
        <StatTile value="4" label="Export formats" tone="navy" />
      </div>
    ),
  },
  {
    icon: AriaIcon,
    name: "ARIA AI",
    problem: "The data is there, but reading it takes time you do not have.",
    what:
      "An assistant that reads your own records. Log work by typing it naturally, then ask what it means.",
    outcomes: [
      "Record a day's work in one sentence",
      "Ask questions instead of building reports",
      "Get warnings grounded in your own numbers",
    ],
    demo: (
      <div className="space-y-2 text-sm">
        <div className="rounded-2xl bg-brand-600 px-4 py-2.5 text-white">Log 45kg of feed for Batch A</div>
        <div className="rounded-2xl bg-gray-100 px-4 py-2.5 text-gray-800 dark:bg-white/[0.06] dark:text-gray-100">
          Done. Batch A has used 312 kg this week — on track for a 1.6 FCR.
        </div>
      </div>
    ),
  },
  {
    icon: Bell,
    name: "Notifications",
    problem: "Everything feels urgent, so nothing does.",
    what:
      "One feed of what actually needs attention today, delivered in the app and by SMS where it matters.",
    outcomes: [
      "See the day's real priorities at a glance",
      "Get critical alerts even when offline",
      "Stop checking six screens for problems",
    ],
    demo: (
      <div className="space-y-2">
        {[["Mortality above expected — Batch C", "amber"], ["Feed stock low", "amber"], ["Weekly summary ready", "brand"]].map(([t, tone]) => (
          <div key={t} className="flex items-center gap-2 rounded-xl border border-gray-100 p-3 text-sm dark:border-white/5">
            <span className={`h-2 w-2 rounded-full ${tone === "amber" ? "bg-amber-500" : "bg-brand-500"}`} />
            <span className="text-gray-700 dark:text-gray-200">{t}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    icon: BarChart3,
    name: "Analytics",
    problem: "One batch tells you little. The pattern across ten tells you everything.",
    what:
      "Trends across flocks, seasons and houses, so you can see what is actually improving.",
    outcomes: [
      "See whether this year beats last year",
      "Find the house or season that underperforms",
      "Make the next batch better than the last",
    ],
    demo: (
      <div className="grid grid-cols-3 gap-3">
        <StatTile value="+8%" label="Survival YoY" />
        <StatTile value="-0.14" label="FCR change" tone="navy" />
        <StatTile value="12" label="Batches" tone="amber" />
      </div>
    ),
  },
];

import { useSeo } from "@/hooks/useSeo";

export default function FeaturesScreen() {
  useSeo({
    title: "Features",
    description:
      "Records, dashboards, reports and forecasts, automation, and an AI assistant — everything Greena gives your farm in one place.",
    path: "/features",
  });
  return (
    <>
      <section className="relative overflow-hidden border-b border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>Features</Eyebrow>
              <Heading as="h1">Everything your farm needs, connected</Heading>
              <Lead className="mx-auto mt-6">
                Nine modules that share the same records. Enter something once and
                it lands everywhere it belongs — no double entry, no
                reconciliation, no spreadsheet that disagrees with the book.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      {FEATURES.map((f, i) => (
        <Section
          key={f.name}
          className={i % 2 === 1 ? "bg-gray-50/60 dark:bg-white/[0.02]" : ""}
        >
          <Container>
            <div
              className={`grid items-center gap-12 lg:grid-cols-2 ${
                i % 2 === 1 ? "lg:[&>*:first-child]:order-2" : ""
              }`}
            >
              <Reveal>
                <span className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <f.icon className="h-5 w-5" />
                </span>
                <Heading as="h2">{f.name}</Heading>
                <p className="mt-4 text-base italic leading-relaxed text-gray-500 dark:text-gray-400">
                  "{f.problem}"
                </p>
                <Lead className="mt-4">{f.what}</Lead>
                <ul className="mt-6 space-y-2.5">
                  {f.outcomes.map((o) => (
                    <li key={o} className="flex gap-3 text-sm text-gray-700 dark:text-gray-200">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" />
                      {o}
                    </li>
                  ))}
                </ul>
              </Reveal>

              <Reveal delay={0.1} y={24}>
                <ScreenFrame title={`greena.app — ${f.name}`}>{f.demo}</ScreenFrame>
              </Reveal>
            </div>
          </Container>
        </Section>
      ))}

      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <Card className="mx-auto max-w-3xl text-center">
            <Heading as="h2">See it with your own numbers</Heading>
            <Lead className="mx-auto mt-4 max-w-xl">
              Set up a farm and your first flock in about ten minutes. Greena
              guides you through every step.
            </Lead>
            <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <CTA to="/signup">
                Start free <ArrowRight className="h-4 w-4" />
              </CTA>
              <CTA to="/pricing" variant="secondary">
                See pricing
              </CTA>
            </div>
          </Card>
        </Container>
      </Section>
    </>
  );
}
