/**
 * Greena — shared building blocks for long-form legal / policy pages.
 *
 * Kept deliberately plain: a centered hero, a readable prose column, and small
 * typographic helpers so Privacy and Terms stay visually consistent without
 * pulling in a markdown pipeline.
 */
import type { ReactNode } from "react";

import { Container, Section, Reveal, Eyebrow, Heading, Lead } from "@/components/marketing/primitives";

export function LegalHero({
  eyebrow,
  title,
  lead,
  updated,
}: {
  eyebrow: string;
  title: string;
  lead: string;
  updated: string;
}) {
  return (
    <section className="border-b border-gray-100 dark:border-white/5">
      <Container className="py-16 sm:py-20">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <Eyebrow>{eyebrow}</Eyebrow>
            <Heading as="h1">{title}</Heading>
            <Lead className="mt-6">{lead}</Lead>
            <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
              Last updated {updated}
            </p>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}

/** Amber note flagging that the template needs professional legal review. */
export function DraftNotice() {
  return (
    <div className="mx-auto mb-10 max-w-3xl rounded-xl border border-amber-300/70 bg-amber-50 p-4 text-sm leading-relaxed text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200">
      <strong className="font-semibold">Draft for review.</strong> This document
      describes how Greena actually handles your information today. It is a
      working template and should be reviewed by a qualified legal professional
      before Greena relies on it commercially.
    </div>
  );
}

export function Prose({ children }: { children: ReactNode }) {
  return (
    <Section>
      <Container>
        <div className="mx-auto max-w-3xl space-y-8 text-[15px] leading-relaxed text-gray-600 dark:text-gray-300">
          {children}
        </div>
      </Container>
    </Section>
  );
}

export function Clause({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{heading}</h2>
      {children}
    </section>
  );
}

export function Bullets({ items }: { items: ReactNode[] }) {
  return (
    <ul className="ml-1 space-y-2">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2.5">
          <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}
