/**
 * Greena — Learning (Greena Academy).
 *
 * Content is not written yet, so this page is honest about that: it shows the
 * curriculum and marks what is coming rather than dressing up empty cards as
 * available material. A visitor should leave knowing what will be here and
 * what to do in the meantime.
 */
import { ArrowRight, BookOpen, PlayCircle, FileText, GraduationCap } from "lucide-react";
import { AriaIcon } from "@/components/aria";

import { GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Card, Pill,
} from "@/components/marketing/primitives";

const TRACKS = [
  {
    icon: GraduationCap,
    name: "Getting started",
    copy: "Set up your farm, houses and first flock, and record your first week of work.",
    items: ["Your first 10 minutes in Greena", "Houses, flocks and why the structure matters", "Recording a day properly"],
  },
  {
    icon: BookOpen,
    name: "Poultry fundamentals",
    copy: "The husbandry behind the numbers — what good looks like and why.",
    items: ["Brooding temperature and why it decides week six", "Reading a mortality curve", "Vaccination schedules that actually get followed"],
  },
  {
    icon: FileText,
    name: "Farm economics",
    copy: "Turning records into decisions about money.",
    items: ["Feed conversion, explained properly", "Costing a batch from day one", "When to sell: weight against feed cost"],
  },
  {
    icon: AriaIcon,
    name: "Working with ARIA",
    copy: "Getting more out of the assistant as your records grow.",
    items: ["Logging a day in one sentence", "Questions worth asking every week", "Reading ARIA's warnings"],
  },
];

import { useSeo } from "@/hooks/useSeo";

export default function LearningScreen() {
  useSeo({
    title: "Greena Academy",
    description:
      "Guides and lessons to help you get the most out of Greena and run better farm records.",
    path: "/learning",
  });
  return (
    <>
      <section className="relative overflow-hidden border-b border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Pill>
                <GraduationCap className="h-3.5 w-3.5" />
                Greena Academy
              </Pill>
              <Heading as="h1" className="mt-5">
                Better records make better farmers
              </Heading>
              <Lead className="mx-auto mt-6">
                Software only helps if you know what the numbers mean. Greena
                Academy is short, practical training on poultry husbandry and
                farm economics — written for Kenyan conditions.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>Curriculum</Eyebrow>
              <Heading>Four tracks</Heading>
              <Lead className="mt-4">
                Each is a handful of short lessons — read in five minutes, applied
                the same day.
              </Lead>
            </Reveal>
          </div>

          <Stagger className="mt-12 grid gap-5 md:grid-cols-2">
            {TRACKS.map((t) => (
              <Card key={t.name} interactive className="h-full">
                <div className="mb-4 flex items-center justify-between">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                    <t.icon className="h-5 w-5" />
                  </span>
                  <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-medium text-gray-500 dark:bg-white/10 dark:text-gray-300">
                    In production
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{t.name}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                  {t.copy}
                </p>
                <ul className="mt-4 space-y-2 border-t border-gray-100 pt-4 dark:border-white/5">
                  {t.items.map((i) => (
                    <li key={i} className="flex gap-2.5 text-sm text-gray-600 dark:text-gray-300">
                      <PlayCircle className="mt-0.5 h-4 w-4 shrink-0 text-gray-300 dark:text-gray-600" />
                      {i}
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
              <Heading>Learning is not live yet</Heading>
              <Lead className="mx-auto mt-5">
                We are writing the lessons now, with vets and commercial farmers
                rather than from textbooks. In the meantime ARIA already answers
                husbandry questions inside the app — ask it why a number matters
                and it will explain.
              </Lead>
              <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <CTA to="/signup">
                  Start using Greena <ArrowRight className="h-4 w-4" />
                </CTA>
                <CTA to="/contact" variant="secondary">
                  Tell us what to cover
                </CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>
    </>
  );
}
