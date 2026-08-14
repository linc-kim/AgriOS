/**
 * Greena — interactive multi-enterprise showcase for the homepage.
 *
 * A tab switcher across the shipped enterprises; selecting one reveals its real
 * capabilities and links to its full page. Motion is a subtle cross-fade that is
 * dropped entirely under prefers-reduced-motion. Keyboard-accessible (real
 * tablist semantics); nothing here is required to read the content.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, Check } from "lucide-react";

import { ENTERPRISES } from "@/lib/enterprises";
import { Container, Section, Reveal, Eyebrow, Heading, Lead } from "@/components/marketing/primitives";

export function EnterpriseShowcase() {
  const [active, setActive] = useState(0);
  const reduced = useReducedMotion();
  const e = ENTERPRISES[active];

  return (
    <Section>
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <Reveal>
            <Eyebrow>Every enterprise</Eyebrow>
            <Heading>One platform, whatever you farm</Heading>
            <Lead className="mx-auto mt-5">
              A farm is rarely one thing. Pick an enterprise to see what Greena
              tracks — each shares the same finance, reporting and AI layer.
            </Lead>
          </Reveal>
        </div>

        <div className="mx-auto mt-10 max-w-4xl">
          {/* Switcher */}
          <div role="tablist" aria-label="Farming enterprises" className="flex flex-wrap justify-center gap-2">
            {ENTERPRISES.map((item, i) => {
              const selected = i === active;
              return (
                <button
                  key={item.slug}
                  role="tab"
                  type="button"
                  aria-selected={selected}
                  onClick={() => setActive(i)}
                  className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#0b0e12] ${
                    selected
                      ? "border-brand-600 bg-brand-600 text-white"
                      : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-white/15 dark:bg-white/[0.04] dark:text-gray-200"
                  }`}
                >
                  <span aria-hidden>{item.emoji}</span>
                  {item.name}
                </button>
              );
            })}
          </div>

          {/* Panel */}
          <motion.div
            key={e.slug}
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0, 0, 0.2, 1] }}
            className="mt-8 rounded-2xl border border-gray-200 bg-white p-6 sm:p-8 dark:border-white/10 dark:bg-white/[0.02]"
          >
            <div className="flex items-start gap-4">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-brand-50 text-3xl dark:bg-brand-500/10" aria-hidden>
                {e.emoji}
              </span>
              <div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white">{e.name}</h3>
                <p className="mt-1 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{e.summary}</p>
              </div>
            </div>

            <ul className="mt-6 grid gap-2.5 sm:grid-cols-2">
              {e.capabilities.map((c) => (
                <li key={c} className="flex gap-2.5 text-sm text-gray-700 dark:text-gray-200">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" />
                  {c}
                </li>
              ))}
            </ul>

            <Link
              to={`/farming/${e.slug}`}
              className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600 hover:gap-2.5 dark:text-brand-400"
            >
              Explore {e.name} on Greena <ArrowRight className="h-4 w-4 transition-all" />
            </Link>
          </motion.div>
        </div>
      </Container>
    </Section>
  );
}
