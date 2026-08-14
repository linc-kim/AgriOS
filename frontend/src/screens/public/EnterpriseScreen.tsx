/**
 * Greena — a single farming enterprise page (`/farming/:slug`).
 *
 * Data-driven from `lib/enterprises` so every page states only shipped
 * capabilities. Poultry may be the flagship, but each enterprise gets its own
 * page for search and clarity. Cross-sells the shared finance/reports/ARIA layer
 * that applies across every enterprise.
 */
import { Navigate, Link, useParams } from "react-router-dom";
import { ArrowRight, Check, Wallet, FileText } from "lucide-react";

import { useSeo } from "@/hooks/useSeo";
import { TRIAL_DAYS, PREMIUM_PLAN_LABEL } from "@/lib/policy";
import { ENTERPRISES, enterpriseBySlug } from "@/lib/enterprises";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Card,
} from "@/components/marketing/primitives";
import { AriaMark } from "@/components/brand/AriaMark";

export default function EnterpriseScreen() {
  const { slug = "" } = useParams();
  const enterprise = enterpriseBySlug(slug);

  // Hooks must run unconditionally — call useSeo before any early return.
  useSeo({
    title: enterprise ? `${enterprise.name} management software` : "Farming enterprises",
    description: enterprise
      ? `Greena for ${enterprise.name.toLowerCase()}: ${enterprise.tagline} ${enterprise.summary}`.slice(0, 230)
      : "Farm management for poultry, livestock, rabbits, goats, sheep, pigs and more.",
    path: enterprise ? `/farming/${enterprise.slug}` : "/farming",
  });

  // Unknown enterprise → send to the index rather than a dead page.
  if (!enterprise) return <Navigate to="/farming" replace />;

  const { name, emoji, summary, capabilities } = enterprise;
  const others = ENTERPRISES.filter((e) => e.slug !== enterprise.slug);

  return (
    <>
      <section className="border-b border-gray-100 dark:border-white/5">
        <Container className="py-16 sm:py-20">
          <div className="mx-auto max-w-3xl">
            <Reveal>
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-4xl dark:bg-brand-500/10" aria-hidden>
                {emoji}
              </div>
              <Eyebrow>Farming enterprise</Eyebrow>
              <Heading as="h1">{name} on Greena</Heading>
              <Lead className="mt-6">{summary}</Lead>
              <div className="mt-8 flex flex-wrap gap-3">
                <CTA to="/signup">
                  Start your {TRIAL_DAYS}-day {PREMIUM_PLAN_LABEL} trial <ArrowRight className="h-4 w-4" />
                </CTA>
                <CTA to="/pricing" variant="secondary">See pricing</CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </section>

      {/* Capabilities */}
      <Section>
        <Container>
          <div className="mx-auto max-w-3xl">
            <Reveal>
              <Eyebrow>What you can track</Eyebrow>
              <Heading>Built for how {name.toLowerCase()} really run</Heading>
            </Reveal>
            <Stagger className="mt-8 grid gap-3 sm:grid-cols-2">
              {capabilities.map((c) => (
                <div key={c} className="flex gap-3 rounded-xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.02]">
                  <Check className="mt-0.5 h-5 w-5 shrink-0 text-brand-600 dark:text-brand-400" />
                  <span className="text-[15px] text-gray-700 dark:text-gray-200">{c}</span>
                </div>
              ))}
            </Stagger>
          </div>
        </Container>
      </Section>

      {/* Shared layer */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="mx-auto max-w-3xl">
            <Reveal>
              <Eyebrow>One system</Eyebrow>
              <Heading>Finance, reports and ARIA — across every enterprise</Heading>
              <Lead className="mt-6">
                Whatever you farm, the same finance, reporting and AI layer sits
                underneath. Record something once and it flows everywhere it
                matters.
              </Lead>
            </Reveal>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <Card>
                <Wallet className="h-6 w-6 text-brand-600 dark:text-brand-400" />
                <h3 className="mt-3 text-base font-semibold text-gray-900 dark:text-white">Finance</h3>
                <p className="mt-1.5 text-sm text-gray-600 dark:text-gray-300">Expenses and revenue per enterprise, so profit is a number, not a guess.</p>
              </Card>
              <Card>
                <FileText className="h-6 w-6 text-brand-600 dark:text-brand-400" />
                <h3 className="mt-3 text-base font-semibold text-gray-900 dark:text-white">Reports</h3>
                <p className="mt-1.5 text-sm text-gray-600 dark:text-gray-300">Production, health and P&amp;L, ready to export.</p>
              </Card>
              <Card>
                <AriaMark size={24} />
                <h3 className="mt-3 text-base font-semibold text-gray-900 dark:text-white">ARIA</h3>
                <p className="mt-1.5 text-sm text-gray-600 dark:text-gray-300">Ask your farm a question and get an answer grounded in your records.</p>
              </Card>
            </div>
          </div>
        </Container>
      </Section>

      {/* Other enterprises */}
      <Section>
        <Container>
          <div className="mx-auto max-w-4xl">
            <Reveal>
              <Eyebrow>Also on Greena</Eyebrow>
              <Heading>More of the farm</Heading>
            </Reveal>
            <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {others.map((e) => (
                <Link
                  key={e.slug}
                  to={`/farming/${e.slug}`}
                  className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md dark:border-white/10 dark:bg-white/[0.02] dark:hover:border-brand-500/40"
                >
                  <span className="text-2xl" aria-hidden>{e.emoji}</span>
                  <span>
                    <span className="block text-sm font-semibold text-gray-900 dark:text-white">{e.name}</span>
                    <span className="block text-xs text-gray-500 dark:text-gray-400">{e.tagline}</span>
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <Card className="mx-auto max-w-3xl text-center">
            <Heading as="h2">Start with {name.toLowerCase()} today</Heading>
            <Lead className="mx-auto mt-4 max-w-xl">
              Set up takes about ten minutes. Greena walks you through your first
              records — the numbers start working for you the same day.
            </Lead>
            <div className="mt-7">
              <CTA to="/signup">
                Start your {TRIAL_DAYS}-day {PREMIUM_PLAN_LABEL} trial <ArrowRight className="h-4 w-4" />
              </CTA>
            </div>
          </Card>
        </Container>
      </Section>
    </>
  );
}
