/**
 * Greena — farming enterprises index (`/farming`).
 *
 * The multi-enterprise overview: Greena adapts to what you actually farm.
 * Cards link to each enterprise's own page. Data-driven from lib/enterprises,
 * so it always matches the shipped modules (no Fish).
 */
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { useSeo } from "@/hooks/useSeo";
import { TRIAL_DAYS, PREMIUM_PLAN_LABEL } from "@/lib/policy";
import { ENTERPRISES } from "@/lib/enterprises";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA,
} from "@/components/marketing/primitives";

export default function EnterprisesScreen() {
  useSeo({
    title: "Farming enterprises",
    description:
      "One platform for every enterprise on your farm — poultry, ornamental birds, black soldier fly, rabbits, goats, sheep and pigs. Records, reports and an AI assistant.",
    path: "/farming",
  });

  return (
    <>
      <section className="border-b border-gray-100 dark:border-white/5">
        <Container className="py-16 sm:py-20">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>Enterprises</Eyebrow>
              <Heading as="h1">Greena adapts to what you farm</Heading>
              <Lead className="mx-auto mt-6">
                A farm is rarely one thing. Greena runs the enterprises you
                actually keep — each with its own records and reports, all sharing
                one finance, reporting and AI layer.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ENTERPRISES.map((e) => (
              <Link
                key={e.slug}
                to={`/farming/${e.slug}`}
                className="group flex h-full flex-col rounded-2xl border border-gray-200 bg-white p-6 transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-lg dark:border-white/10 dark:bg-white/[0.02] dark:hover:border-brand-500/40"
              >
                <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-3xl dark:bg-brand-500/10" aria-hidden>
                  {e.emoji}
                </span>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{e.name}</h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{e.tagline}</p>
                <p className="mt-3 flex-1 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{e.summary}</p>
                <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 group-hover:gap-2 dark:text-brand-400">
                  Explore {e.name} <ArrowRight className="h-4 w-4 transition-all" />
                </span>
              </Link>
            ))}
          </Stagger>
        </Container>
      </Section>

      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Heading as="h2">Whatever you farm, start free</Heading>
              <Lead className="mx-auto mt-4">
                Try everything with a {TRIAL_DAYS}-day {PREMIUM_PLAN_LABEL} trial, or
                stay on the free plan for your first flock.
              </Lead>
              <div className="mt-7 flex justify-center">
                <CTA to="/signup">
                  Get started <ArrowRight className="h-4 w-4" />
                </CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>
    </>
  );
}
