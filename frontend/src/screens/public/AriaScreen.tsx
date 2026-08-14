/**
 * Greena — ARIA.
 *
 * The page has to do one job above all: make clear that ARIA answers from the
 * farm's own records, not from the internet. That distinction is the entire
 * value, and it is also what makes it trustworthy enough to act on.
 */
import { useState } from "react";
import {
  ArrowRight, MessageSquare, Camera, Stethoscope, GraduationCap,
  TrendingUp, ClipboardList, Languages, Shield, Check,
} from "lucide-react";

import { AriaMark } from "@/components/brand/AriaMark";

import { LineWaves, GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Stagger, Eyebrow, Heading, Lead, CTA, Card, Pill,
  ScreenFrame,
} from "@/components/marketing/primitives";

const CAPABILITIES = [
  { icon: ClipboardList, name: "Record keeping", copy: "Say what happened and ARIA files it in the right place — feed, eggs, mortality, treatments." },
  { icon: MessageSquare, name: "Natural language", copy: "No forms or menus to learn. Type it the way you would say it to a worker." },
  { icon: TrendingUp, name: "Predictions", copy: "Mortality risk, feed depletion and expected production, projected from your own history." },
  { icon: Stethoscope, name: "Disease guidance", copy: "Describe symptoms and get likely causes with next steps — and when to call a vet." },
  { icon: GraduationCap, name: "Education", copy: "Ask why a number matters. ARIA explains the husbandry, not just the figure." },
  { icon: Camera, name: "Image analysis", copy: "Photograph a bird, droppings or a lesion for a first read.", planned: true },
];

const CONVERSATIONS: Record<string, { user: string; aria: string }[]> = {
  "Logging work": [
    { user: "I collected 320 eggs today", aria: "Logged for Batch B. That's 6% above last week's daily average — lay rate is now 87%." },
    { user: "Log 45kg of feed for Batch A", aria: "Done. Batch A has used 312 kg this week, tracking to a 1.62 feed conversion ratio." },
    { user: "Lost 3 birds in house 2 overnight", aria: "Recorded. That brings Batch C to 11 deaths in 12 days — still inside the normal range for this age, but I'll watch it." },
  ],
  "Asking questions": [
    { user: "What profit did I make last month?", aria: "KES 148,000 across two batches. Feed was 71% of your costs — the largest single line." },
    { user: "Which flock performed best?", aria: "Batch A: 96.4% survival and a 1.58 FCR, finishing four days earlier than Batch C." },
    { user: "How much feed do I have left?", aria: "840 kg of grower in store. At the current rate that's about six days — worth reordering this week." },
  ],
  "Getting help": [
    { user: "A chicken is sick — swollen face and not eating", aria: "Those signs point most often to coryza or a respiratory infection. Isolate the bird today and check whether others are sneezing. If more than a few are affected, call your vet — I've flagged it on Batch B." },
    { user: "Why does feed conversion matter?", aria: "It's how many kilos of feed it takes to add one kilo of bird. Yours is 1.62, so 1.62 kg of feed per kilo gained. Lower is cheaper — and since feed is 71% of your costs, a 0.1 improvement is real money." },
  ],
};

import { useSeo } from "@/hooks/useSeo";

export default function AriaScreen() {
  useSeo({
    title: "ARIA — your AI farm assistant",
    description:
      "ARIA answers questions about your farm using your own records, surfaces insights, and helps with day-to-day decisions. Understands English and Swahili.",
    path: "/aria-ai",
  });
  const tabs = Object.keys(CONVERSATIONS);
  const [tab, setTab] = useState(tabs[0]);

  return (
    <>
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <LineWaves lines={30} amplitude={20} />
          <GlowField />
        </div>
        <Container className="relative py-24 sm:py-32">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Pill>
                <AriaMark size={15} title="ARIA" />
                Included on every plan
              </Pill>
            </Reveal>
            <Reveal delay={0.06}>
              <Heading as="h1" className="mt-6">
                Meet ARIA
              </Heading>
            </Reveal>
            <Reveal delay={0.12}>
              <Lead className="mx-auto mt-6 max-w-2xl">
                An assistant that has read every record on your farm. Ask it
                anything about your flocks, your costs or your birds' health —
                and it answers from your data, not from the internet.
              </Lead>
            </Reveal>
            <Reveal delay={0.18}>
              <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <CTA to="/signup">
                  Try ARIA free <ArrowRight className="h-4 w-4" />
                </CTA>
                <CTA to="/features" variant="secondary">
                  See all features
                </CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </section>

      {/* Grounded, not generic */}
      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <Eyebrow>What makes it different</Eyebrow>
              <Heading>It answers from your farm</Heading>
              <Lead className="mt-5">
                A general chatbot can tell you what feed conversion means. ARIA
                tells you what <em>yours</em> is, which batch is dragging it down,
                and what that costs you this cycle.
              </Lead>
              <ul className="mt-6 space-y-3">
                {[
                  "Reads your actual flocks, logs, costs and health records",
                  "Cites the numbers behind every answer",
                  "Gets sharper as you record more",
                  "Falls back to a built-in model if the network drops",
                ].map((t) => (
                  <li key={t} className="flex gap-3 text-sm text-gray-700 dark:text-gray-200">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" />
                    {t}
                  </li>
                ))}
              </ul>
            </Reveal>

            <Reveal delay={0.1} y={24}>
              <Card>
                <div className="flex items-start gap-3">
                  <Shield className="mt-0.5 h-5 w-5 shrink-0 text-brand-600 dark:text-brand-400" />
                  <div>
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                      Your data stays yours
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                      ARIA is given only the farm context needed to answer the
                      question in front of it. Your records are never used to
                      train anyone's model, and never shared with other farms.
                    </p>
                  </div>
                </div>
                <div className="mt-5 flex items-start gap-3 border-t border-gray-100 pt-5 dark:border-white/5">
                  <Languages className="mt-0.5 h-5 w-5 shrink-0 text-brand-600 dark:text-brand-400" />
                  <div>
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                      Speaks how you speak
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                      English and Kiswahili, with the shorthand farmers actually
                      use. No command syntax to memorise.
                    </p>
                  </div>
                </div>
              </Card>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* Conversations */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>In practice</Eyebrow>
              <Heading>Real conversations</Heading>
              <Lead className="mt-4">
                Three of the things farmers use ARIA for every day.
              </Lead>
            </Reveal>
          </div>

          <Reveal delay={0.08}>
            <div className="mx-auto mt-10 flex max-w-md justify-center gap-1 rounded-xl border border-gray-200 bg-white p-1 dark:border-white/10 dark:bg-white/[0.03]">
              {tabs.map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  aria-pressed={tab === t}
                  className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    tab === t
                      ? "bg-brand-600 text-white"
                      : "text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </Reveal>

          <Reveal delay={0.12} y={20}>
            <div className="mx-auto mt-8 max-w-2xl">
              <ScreenFrame title="ARIA">
                <div className="space-y-3">
                  {CONVERSATIONS[tab].map((turn, i) => (
                    <div key={i} className="space-y-3">
                      <div className="flex justify-end">
                        <div className="max-w-[85%] rounded-2xl bg-brand-600 px-4 py-2.5 text-sm text-white">
                          {turn.user}
                        </div>
                      </div>
                      <div className="flex justify-start">
                        <div className="max-w-[90%] rounded-2xl bg-gray-100 px-4 py-2.5 text-sm leading-relaxed text-gray-800 dark:bg-white/[0.06] dark:text-gray-100">
                          {turn.aria}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScreenFrame>
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* Capabilities */}
      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>Capabilities</Eyebrow>
              <Heading>What ARIA can do</Heading>
            </Reveal>
          </div>

          <Stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((c) => (
              <Card key={c.name} interactive className="h-full">
                <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                  <c.icon className="h-5 w-5" />
                </span>
                <div className="mb-1.5 flex items-center gap-2">
                  <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                    {c.name}
                  </h3>
                  {c.planned && (
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500 dark:bg-white/10 dark:text-gray-300">
                      Coming soon
                    </span>
                  )}
                </div>
                <p className="text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                  {c.copy}
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
              <Heading>ARIA gets better the more you record</Heading>
              <Lead className="mx-auto mt-5">
                Every log makes the next answer sharper. Start today and by the
                end of your first cycle it knows your farm well enough to warn
                you before problems arrive.
              </Lead>
              <div className="mt-9">
                <CTA to="/signup">
                  Start free <ArrowRight className="h-4 w-4" />
                </CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>
    </>
  );
}
