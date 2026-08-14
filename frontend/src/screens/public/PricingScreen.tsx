/**
 * Greena — Pricing.
 *
 * Plan limits mirror the subscription_plans rows seeded by migration 006, so
 * what is advertised here is what the application actually enforces. If those
 * limits change, this page changes with them.
 */
import { useState } from "react";
import { ArrowRight, Check, Minus, HelpCircle } from "lucide-react";

import { GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Card, Pill,
} from "@/components/marketing/primitives";

const PLANS = [
  {
    name: "Free",
    price: "0",
    tagline: "For a first flock",
    features: [
      "1 farm",
      "3 houses",
      "3 active flocks",
      "2 team members",
      "5 ARIA questions a month",
      "90 days of history",
      "All core modules",
    ],
    cta: "Start free",
    highlight: false,
  },
  {
    name: "Starter",
    price: "1,500",
    tagline: "For a growing farm",
    features: [
      "3 farms",
      "10 houses per farm",
      "10 active flocks",
      "5 team members",
      "30 ARIA questions a month",
      "Full history",
      "Automation & reminders",
      "CSV, Excel & PDF export",
    ],
    cta: "Choose Starter",
    highlight: true,
  },
  {
    name: "Pro",
    price: "4,500",
    tagline: "For commercial operations",
    features: [
      "Unlimited farms",
      "Unlimited houses",
      "Unlimited flocks",
      "Unlimited team members",
      "Unlimited ARIA",
      "Full history",
      "Advanced analytics",
      "Priority support",
    ],
    cta: "Choose Pro",
    highlight: false,
  },
];

const COMPARISON: [string, string, string, string][] = [
  ["Farms", "1", "3", "Unlimited"],
  ["Houses per farm", "3", "10", "Unlimited"],
  ["Active flocks", "3", "10", "Unlimited"],
  ["Team members", "2", "5", "Unlimited"],
  ["ARIA questions / month", "5", "30", "Unlimited"],
  ["History retained", "90 days", "Full", "Full"],
  ["Daily logs & records", "yes", "yes", "yes"],
  ["Health & vaccinations", "yes", "yes", "yes"],
  ["Feed & inventory", "yes", "yes", "yes"],
  ["Finance & reports", "yes", "yes", "yes"],
  ["Automation & reminders", "no", "yes", "yes"],
  ["Data export", "no", "yes", "yes"],
  ["Backups & restore", "no", "yes", "yes"],
  ["Advanced analytics", "no", "no", "yes"],
  ["Priority support", "no", "no", "yes"],
];

const FAQ = [
  {
    q: "Is the free plan really free?",
    a: "Yes. No card, no trial clock. One farm with up to three flocks, and all the core modules. It stays free for as long as you need it.",
  },
  {
    q: "What happens if I outgrow a plan?",
    a: "Nothing breaks. You keep your records and are prompted to upgrade when you hit a limit — for example, when placing a fourth concurrent flock on Free.",
  },
  {
    q: "Can I use Greena without internet?",
    a: "Yes, for reading and recording. Entries sync when you reconnect, and ARIA falls back to an on-device model when the network is unavailable.",
  },
  {
    q: "How do I pay?",
    a: "M-Pesa or card, billed monthly. Cancel any time — your data stays accessible on the free plan.",
  },
  {
    q: "Who owns my farm data?",
    a: "You do. Export it whenever you like in CSV, Excel, JSON or PDF. We never sell it and never use it to train anyone's model.",
  },
  {
    q: "Do you offer anything for cooperatives?",
    a: "Yes — group pricing across many member farms, with consolidated reporting. Get in touch and we'll put something together.",
  },
];

function Cell({ value }: { value: string }) {
  if (value === "yes")
    return <Check className="mx-auto h-4 w-4 text-brand-600 dark:text-brand-400" />;
  if (value === "no")
    return <Minus className="mx-auto h-4 w-4 text-gray-300 dark:text-gray-600" />;
  return <span className="text-sm text-gray-700 dark:text-gray-200">{value}</span>;
}

import { useSeo } from "@/hooks/useSeo";

export default function PricingScreen() {
  useSeo({
    title: "Pricing",
    description:
      "Simple plans for farms of every size — start free, upgrade when you're ready. Billed securely through Paystack in Kenyan Shillings.",
    path: "/pricing",
  });
  const [open, setOpen] = useState<number | null>(0);

  return (
    <>
      <section className="relative overflow-hidden border-b border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Pill>Launch pricing</Pill>
              <Heading as="h1" className="mt-5">
                Priced for a farm, not an enterprise
              </Heading>
              <Lead className="mx-auto mt-6">
                Start free and stay free until the farm outgrows it. Prices in
                Kenyan shillings, billed monthly, cancel whenever.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <Stagger className="grid gap-5 lg:grid-cols-3">
            {PLANS.map((p) => (
              <Card
                key={p.name}
                className={`relative flex h-full flex-col ${
                  p.highlight
                    ? "border-brand-500 shadow-lg ring-1 ring-brand-500/20 dark:border-brand-500/60"
                    : ""
                }`}
              >
                {p.highlight && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-600 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white">
                    Most popular
                  </span>
                )}
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {p.name}
                </h3>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{p.tagline}</p>
                <p className="mt-5 flex items-baseline gap-1.5">
                  <span className="text-sm font-medium text-gray-500 dark:text-gray-400">KES</span>
                  <span className="text-4xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
                    {p.price}
                  </span>
                  <span className="text-sm text-gray-500 dark:text-gray-400">/month</span>
                </p>
                <ul className="mt-6 space-y-2.5">
                  {p.features.map((f) => (
                    <li key={f} className="flex gap-2.5 text-sm text-gray-700 dark:text-gray-200">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" />
                      {f}
                    </li>
                  ))}
                </ul>
                <div className="mt-8 pt-2">
                  <CTA
                    to="/signup"
                    variant={p.highlight ? "primary" : "secondary"}
                    className="w-full"
                  >
                    {p.cta}
                  </CTA>
                </div>
              </Card>
            ))}
          </Stagger>
        </Container>
      </Section>

      {/* Comparison */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>Compare</Eyebrow>
              <Heading>Every plan, side by side</Heading>
            </Reveal>
          </div>

          <Reveal delay={0.08}>
            {/* Own scroll container so the page body never scrolls sideways. */}
            <div className="mt-10 overflow-x-auto rounded-2xl border border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.03]">
              <table className="w-full min-w-[540px]">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-white/5">
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-400">
                      Feature
                    </th>
                    {["Free", "Starter", "Pro"].map((h) => (
                      <th
                        key={h}
                        className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wide text-gray-400"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON.map(([label, free, starter, pro]) => (
                    <tr
                      key={label}
                      className="border-b border-gray-50 last:border-0 dark:border-white/5"
                    >
                      <td className="px-5 py-3 text-sm text-gray-700 dark:text-gray-200">
                        {label}
                      </td>
                      <td className="px-5 py-3 text-center"><Cell value={free} /></td>
                      <td className="px-5 py-3 text-center"><Cell value={starter} /></td>
                      <td className="px-5 py-3 text-center"><Cell value={pro} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* FAQ */}
      <Section>
        <Container>
          <div className="mx-auto max-w-2xl">
            <Reveal>
              <div className="text-center">
                <Eyebrow>Questions</Eyebrow>
                <Heading>Before you decide</Heading>
              </div>
            </Reveal>

            <div className="mt-10 space-y-3">
              {FAQ.map((item, i) => (
                <Reveal key={item.q} delay={i * 0.04}>
                  <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.03]">
                    <button
                      onClick={() => setOpen(open === i ? null : i)}
                      aria-expanded={open === i}
                      className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                    >
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {item.q}
                      </span>
                      <HelpCircle
                        className={`h-4 w-4 shrink-0 transition-transform ${
                          open === i ? "rotate-180 text-brand-600 dark:text-brand-400" : "text-gray-400"
                        }`}
                      />
                    </button>
                    {open === i && (
                      <p className="px-5 pb-5 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                        {item.a}
                      </p>
                    )}
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <Card className="mx-auto max-w-3xl text-center">
            <Heading as="h2">Running something larger?</Heading>
            <Lead className="mx-auto mt-4 max-w-xl">
              Cooperatives, contract farming groups and multi-site operations get
              custom pricing and consolidated reporting. Tell us what you run.
            </Lead>
            <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <CTA to="/contact">
                Contact sales <ArrowRight className="h-4 w-4" />
              </CTA>
              <CTA to="/signup" variant="secondary">
                Start free instead
              </CTA>
            </div>
          </Card>
        </Container>
      </Section>
    </>
  );
}
