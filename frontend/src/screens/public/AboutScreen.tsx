/**
 * Greena — About.
 *
 * Why the product exists, in terms a farmer would recognise. Avoids the usual
 * founding-story inflation: no claimed customer counts or awards we do not
 * have. Trust here comes from being specific about the problem, not from
 * borrowed credibility.
 */
import { ArrowRight, Target, Eye, Heart, ShieldCheck, Smartphone, Users } from "lucide-react";

import { GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Card,
} from "@/components/marketing/primitives";

const PRINCIPLES = [
  {
    icon: Smartphone,
    name: "Works on the phone in your pocket",
    copy: "Not everyone has a laptop or reliable data. Greena is built to be usable on a modest phone, on a patchy connection, standing in a poultry house.",
  },
  {
    icon: Heart,
    name: "Plain language, always",
    copy: "No jargon a farmer has to decode. If a number needs explaining, we explain it — that is a design requirement, not a help article.",
  },
  {
    icon: ShieldCheck,
    name: "Your data is yours",
    copy: "Export it any time in four formats. We do not sell it, and we do not train models on it. Leaving should be as easy as joining.",
  },
  {
    icon: Users,
    name: "Built with farmers, not at them",
    copy: "Every module started as a problem someone described to us. When something does not survive contact with a real farm, it changes.",
  },
];

import { useSeo } from "@/hooks/useSeo";

export default function AboutScreen() {
  useSeo({
    title: "About",
    description:
      "Greena is building the operating system for African farms — practical record-keeping, insight, and an assistant that understands your farm.",
    path: "/about",
  });
  return (
    <>
      <section className="relative overflow-hidden border-b border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>About</Eyebrow>
              <Heading as="h1">
                Farming runs on decisions.
                <br className="hidden sm:block" /> Decisions run on records.
              </Heading>
              <Lead className="mx-auto mt-6">
                Greena exists because most farms already do the hard part — the
                daily work — and then lose the value of it, because nobody can
                get a straight answer out of a notebook.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-3xl">
            <Reveal>
              <Eyebrow>Why Greena exists</Eyebrow>
              <Heading>The problem is not effort</Heading>
              <div className="mt-6 space-y-5 text-lg leading-relaxed text-gray-600 dark:text-gray-300">
                <p>
                  Visit a poultry farm in Kiambu or Nakuru and you will find
                  someone who knows their birds intimately. They will tell you
                  which house runs cold, which batch was trouble, and roughly
                  what feed costs.
                </p>
                <p>
                  Ask what the last batch actually earned, after feed, drugs,
                  labour and losses — and the answer is usually a shrug, or a
                  number arrived at by feel. Not because the farmer is careless,
                  but because the information is spread across a notebook, a
                  phone, a feed store and three people's memories.
                </p>
                <p>
                  That gap is expensive. It is the difference between repeating a
                  good cycle deliberately and repeating a bad one by accident.
                  Greena closes it: record the work once, and the farm tells you
                  what it means.
                </p>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>

      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="grid gap-5 md:grid-cols-2">
            <Reveal>
              <Card className="h-full">
                <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <Target className="h-5 w-5" />
                </span>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white">Mission</h3>
                <p className="mt-3 leading-relaxed text-gray-600 dark:text-gray-300">
                  Give every farmer — at any scale — the same quality of
                  information a large commercial operation takes for granted,
                  on the device they already own.
                </p>
              </Card>
            </Reveal>

            <Reveal delay={0.08}>
              <Card className="h-full">
                <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-navy-50 text-navy-600 dark:bg-navy-500/10 dark:text-navy-300">
                  <Eye className="h-5 w-5" />
                </span>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white">Vision</h3>
                <p className="mt-3 leading-relaxed text-gray-600 dark:text-gray-300">
                  An operating system for African agriculture — already running
                  poultry, birds, rabbits, goats, sheep, pigs and BSF, and growing
                  toward crops and the cooperatives that connect farms together.
                </p>
              </Card>
            </Reveal>
          </div>
        </Container>
      </Section>

      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>How we build</Eyebrow>
              <Heading>Four things we will not compromise on</Heading>
            </Reveal>
          </div>

          <Stagger className="mt-12 grid gap-5 md:grid-cols-2">
            {PRINCIPLES.map((p) => (
              <Card key={p.name} className="h-full">
                <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <p.icon className="h-5 w-5" />
                </span>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">{p.name}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                  {p.copy}
                </p>
              </Card>
            ))}
          </Stagger>
        </Container>
      </Section>

      <Section className="relative overflow-hidden border-t border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative">
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Heading>Built in Nairobi, for farms like yours</Heading>
              <Lead className="mx-auto mt-5">
                Greena is early, and we would rather hear from you than guess.
                If something is missing or wrong, tell us — it tends to get
                fixed.
              </Lead>
              <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <CTA to="/signup">
                  Start free <ArrowRight className="h-4 w-4" />
                </CTA>
                <CTA to="/contact" variant="secondary">
                  Get in touch
                </CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>
    </>
  );
}
