/**
 * Greena — Solutions.
 *
 * Who Greena is for, described by the shape of the operation rather than by
 * bird count alone — a 500-bird layer unit and a 500-bird broiler unit have
 * very different problems.
 */
import { ArrowRight, Check, Sprout, Building2, Egg, Drumstick, Dna, Compass } from "lucide-react";

import { GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Card, Pill,
} from "@/components/marketing/primitives";

const SEGMENTS = [
  {
    icon: Sprout,
    name: "Smallholder farms",
    scale: "50 – 1,000 birds",
    pain: "Records live in a book, and profit is worked out at the end — if at all.",
    fits: [
      "Free plan covers a single farm and flock",
      "Works on a basic phone, offline-tolerant",
      "ARIA logs the day in one sentence",
    ],
  },
  {
    icon: Building2,
    name: "Commercial farms",
    scale: "1,000 – 50,000 birds",
    pain: "Several houses, several batches, and workers who each track things differently.",
    fits: [
      "Multiple houses and concurrent batches",
      "Role-based access for workers, managers and vets",
      "Automation chases the routine work",
    ],
  },
  {
    icon: Egg,
    name: "Layer operations",
    scale: "Egg production",
    pain: "Lay rate drifts slowly, and it is hard to tell a bad week from a bad trend.",
    fits: [
      "Daily egg collection and lay-rate tracking",
      "Feed cost per tray, not per bag",
      "Production curves against breed standard",
    ],
  },
  {
    icon: Drumstick,
    name: "Broiler operations",
    scale: "Meat production",
    pain: "Margins turn on feed conversion and days to market — both easy to lose track of.",
    fits: [
      "FCR calculated per batch, continuously",
      "Weight tracking against target curves",
      "Profit per batch before the birds leave",
    ],
  },
  {
    icon: Dna,
    name: "Breeders & hatcheries",
    scale: "Genetics & supply",
    pain: "Parent stock, fertility and hatch results need a longer memory than a notebook has.",
    fits: [
      "Batch lineage and long-cycle history",
      "Health records that follow the line",
      "Reports across many cycles",
    ],
  },
];

const ROADMAP = [
  ["Crops", "Plantings, growth stages and harvest records alongside livestock."],
  ["Dairy", "Herds, milk yield per animal, and feed economics."],
  ["Marketplace", "Verified suppliers and live market prices."],
  ["Cooperatives", "Group reporting across many member farms."],
];

import { useSeo } from "@/hooks/useSeo";

export default function SolutionsScreen() {
  useSeo({
    title: "Solutions",
    description:
      "Greena for poultry, livestock, ornamental birds, black soldier fly, rabbits, goats, sheep and pigs — with the finance and reporting tools around them.",
    path: "/solutions",
  });
  return (
    <>
      <section className="relative overflow-hidden border-b border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>Solutions</Eyebrow>
              <Heading as="h1">Built for how your farm actually runs</Heading>
              <Lead className="mx-auto mt-6">
                A hundred birds behind the house and forty thousand under
                contract are different businesses. Greena scales between them
                without becoming software you need training to open.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <Stagger className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {SEGMENTS.map((s) => (
              <Card key={s.name} interactive className="flex h-full flex-col">
                <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <s.icon className="h-5 w-5" />
                </span>
                <div className="mb-2 flex items-center gap-2">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {s.name}
                  </h3>
                </div>
                <p className="mb-3 text-xs font-medium uppercase tracking-wide text-gray-400">
                  {s.scale}
                </p>
                <p className="mb-4 text-sm italic leading-relaxed text-gray-500 dark:text-gray-400">
                  "{s.pain}"
                </p>
                <ul className="mt-auto space-y-2">
                  {s.fits.map((f) => (
                    <li key={f} className="flex gap-2.5 text-sm text-gray-700 dark:text-gray-200">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" />
                      {f}
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </Stagger>
        </Container>
      </Section>

      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Pill>
                <Compass className="h-3.5 w-3.5" />
                Roadmap
              </Pill>
              <Heading className="mt-5">Where Greena is going</Heading>
              <Lead className="mt-4">
                Poultry is where we started because it is where the record-keeping
                pain is sharpest. The same foundation extends to the rest of the
                farm.
              </Lead>
            </Reveal>
          </div>

          <Stagger className="mx-auto mt-12 grid max-w-3xl gap-4 sm:grid-cols-2">
            {ROADMAP.map(([name, copy]) => (
              <Card key={name}>
                <div className="mb-2 flex items-center gap-2">
                  <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                    {name}
                  </h3>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500 dark:bg-white/10 dark:text-gray-300">
                    Planned
                  </span>
                </div>
                <p className="text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                  {copy}
                </p>
              </Card>
            ))}
          </Stagger>
        </Container>
      </Section>

      <Section>
        <Container>
          <Card className="mx-auto max-w-3xl text-center">
            <Heading as="h2">Not sure where you fit?</Heading>
            <Lead className="mx-auto mt-4 max-w-xl">
              Start on the free plan with one flock. Nothing to pay, and nothing
              to migrate later — the same account grows with you.
            </Lead>
            <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <CTA to="/signup">
                Start free <ArrowRight className="h-4 w-4" />
              </CTA>
              <CTA to="/contact" variant="secondary">
                Talk to us
              </CTA>
            </div>
          </Card>
        </Container>
      </Section>
    </>
  );
}
