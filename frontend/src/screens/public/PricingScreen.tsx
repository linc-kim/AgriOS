/**
 * Greena — Pricing.
 *
 * Plans are fetched live from the public catalogue endpoint (`/billing/plans/
 * public`), which reads the same `subscription_plans` rows the checkout charges
 * from — so what is advertised here is exactly what the application enforces and
 * bills. A static fallback (see lib/pricing) keeps the page correct during a
 * cold start; live data replaces it as soon as it arrives.
 */
import { useEffect, useState } from "react";
import { ArrowRight, Check, HelpCircle } from "lucide-react";

import { GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Card, Pill,
} from "@/components/marketing/primitives";
import { useSeo } from "@/hooks/useSeo";
import {
  fetchPublicPlans, FALLBACK_PLANS, RECOMMENDED_PLAN,
  limit, countLabel, historyLabel, priceDisplay, type PublicPlan,
} from "@/lib/pricing";
import { TRIAL_DAYS, PREMIUM_PLAN_LABEL } from "@/lib/policy";

function planTagline(name: string): string {
  return (
    {
      free: "For a first flock",
      starter: "For a growing farm",
      pro: "For commercial operations",
      farm_pro: "For large, multi-site farms",
      enterprise: "Cooperatives & groups",
    }[name] ?? "For your farm"
  );
}

function planCta(p: PublicPlan): { label: string; to: string } {
  if (p.price_kes < 0) return { label: "Contact sales", to: "/contact" };
  if (p.price_kes === 0) return { label: "Start free", to: "/signup" };
  return { label: `Choose ${p.display_name}`, to: "/signup" };
}

function planFeatures(p: PublicPlan): string[] {
  return [
    countLabel(p.max_farms, "farm"),
    `${limit(p.max_houses_per_farm)} houses per farm`,
    `${limit(p.max_active_flocks)} active flocks`,
    countLabel(p.max_team_members, "team member"),
    `${limit(p.max_aria_queries_per_month)} ARIA questions / month`,
    historyLabel(p.history_days),
  ];
}

const COMPARISON_ROWS: { label: string; get: (p: PublicPlan) => string }[] = [
  { label: "Farms", get: (p) => limit(p.max_farms) },
  { label: "Houses per farm", get: (p) => limit(p.max_houses_per_farm) },
  { label: "Active flocks", get: (p) => limit(p.max_active_flocks) },
  { label: "Team members", get: (p) => limit(p.max_team_members) },
  { label: "ARIA questions / month", get: (p) => limit(p.max_aria_queries_per_month) },
  { label: "History retained", get: (p) => (p.history_days === -1 ? "Full" : `${p.history_days} days`) },
];

function priceNode(p: PublicPlan) {
  const d = priceDisplay(p.price_kes);
  if (d.kind === "free")
    return <span className="text-4xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Free</span>;
  if (d.kind === "custom")
    return <span className="text-4xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">Custom</span>;
  return (
    <>
      <span className="text-sm font-medium text-gray-500 dark:text-gray-400">KES</span>
      <span className="text-4xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">{d.amount}</span>
      <span className="text-sm text-gray-500 dark:text-gray-400">/month</span>
    </>
  );
}

const FAQ = [
  {
    q: "Is there really a free plan?",
    a: `Yes. The Free plan keeps one farm with your core records at no cost, for as long as you need it. New organizations also get a ${TRIAL_DAYS}-day ${PREMIUM_PLAN_LABEL} trial to explore the paid features first.`,
  },
  {
    q: "What happens when the trial ends or I outgrow a plan?",
    a: "Nothing breaks and no records are lost. When a trial ends or a subscription lapses, your account moves to the Free plan and paid features become unavailable until you subscribe.",
  },
  {
    q: "How do I pay?",
    a: "Securely through Paystack, in Kenyan Shillings — card or mobile money. Greena never sees or stores your full card number.",
  },
  {
    q: "Who owns my farm data?",
    a: "You do. Export your records from the reporting tools whenever you like. We never sell your data.",
  },
  {
    q: "Do you offer anything for cooperatives?",
    a: "Yes — talk to us about group pricing and consolidated reporting across many member farms.",
  },
];

import { SUPPORT_EMAIL } from "@/lib/site";

export default function PricingScreen() {
  useSeo({
    title: "Pricing",
    description: `Plans for farms of every size — a free tier, a ${TRIAL_DAYS}-day ${PREMIUM_PLAN_LABEL} trial, and paid plans billed securely through Paystack in Kenyan Shillings.`,
    path: "/pricing",
  });

  const [plans, setPlans] = useState<PublicPlan[]>(FALLBACK_PLANS);
  const [open, setOpen] = useState<number | null>(0);

  // Seed with the accurate fallback, then reconcile with the live catalogue.
  useEffect(() => {
    let active = true;
    fetchPublicPlans()
      .then((live) => { if (active) setPlans(live); })
      .catch(() => { /* keep the fallback — numbers still correct */ });
    return () => { active = false; };
  }, []);

  const cardPlans = plans;

  return (
    <>
      <section className="relative overflow-hidden border-b border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Pill>Pricing</Pill>
              <Heading as="h1" className="mt-5">
                Priced for a farm, not an enterprise
              </Heading>
              <Lead className="mx-auto mt-6">
                Start on the free plan, or try everything with a {TRIAL_DAYS}-day{" "}
                {PREMIUM_PLAN_LABEL} trial. Prices in Kenyan Shillings, billed
                securely through Paystack.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <Stagger className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {cardPlans.map((p) => {
              const highlight = p.name === RECOMMENDED_PLAN;
              const cta = planCta(p);
              return (
                <Card
                  key={p.name}
                  className={`relative flex h-full flex-col ${
                    highlight
                      ? "border-brand-500 shadow-lg ring-1 ring-brand-500/20 dark:border-brand-500/60"
                      : ""
                  }`}
                >
                  {highlight && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-600 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white">
                      Most popular
                    </span>
                  )}
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {p.display_name}
                  </h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{planTagline(p.name)}</p>
                  <p className="mt-5 flex items-baseline gap-1.5">{priceNode(p)}</p>
                  <ul className="mt-6 space-y-2.5">
                    {planFeatures(p).map((f) => (
                      <li key={f} className="flex gap-2.5 text-sm text-gray-700 dark:text-gray-200">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-8 pt-2">
                    <CTA to={cta.to} variant={highlight ? "primary" : "secondary"} className="w-full">
                      {cta.label}
                    </CTA>
                  </div>
                </Card>
              );
            })}
          </Stagger>
          <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
            New organizations get a {TRIAL_DAYS}-day {PREMIUM_PLAN_LABEL} trial.
            Limits shown are what the application actually enforces.
          </p>
        </Container>
      </Section>

      {/* Comparison — columns are the live plans */}
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
              <table className="w-full min-w-[640px]">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-white/5">
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-400">
                      Feature
                    </th>
                    {cardPlans.map((p) => (
                      <th
                        key={p.name}
                        className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wide text-gray-400"
                      >
                        {p.display_name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON_ROWS.map((row) => (
                    <tr key={row.label} className="border-b border-gray-50 last:border-0 dark:border-white/5">
                      <td className="px-5 py-3 text-sm text-gray-700 dark:text-gray-200">{row.label}</td>
                      {cardPlans.map((p) => (
                        <td key={p.name} className="px-5 py-3 text-center text-sm text-gray-700 dark:text-gray-200">
                          {row.get(p)}
                        </td>
                      ))}
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
                      <span className="text-sm font-medium text-gray-900 dark:text-white">{item.q}</span>
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
              <CTA to={`mailto:${SUPPORT_EMAIL}?subject=Greena%20for%20cooperatives`}>
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
