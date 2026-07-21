/**
 * ARIA identity reference.
 *
 * The living version of the brand documentation: every variant, size and
 * animation state rendered from the same component the product uses, so this
 * page cannot drift from the real mark the way a static spec sheet does.
 */
import { useState } from "react";

import { AriaMark, AriaAvatar, AriaLockup, type AriaState } from "@/components/brand/AriaMark";
import {
  Container, Section, Reveal, Eyebrow, Heading, Lead, Card,
} from "@/components/marketing/primitives";

const STATES: { key: AriaState; when: string }[] = [
  { key: "idle", when: "Present but not asking for attention. The default." },
  { key: "listening", when: "Microphone open, or the user is typing to ARIA." },
  { key: "thinking", when: "Request in flight, awaiting the model." },
  { key: "responding", when: "Streaming an answer back." },
  { key: "loading", when: "Route or data loading where ARIA is the subject." },
];

const SIZES = [16, 20, 24, 32, 48, 64, 96];

export default function BrandAriaScreen() {
  const [state, setState] = useState<AriaState>("idle");

  return (
    <>
      <section className="border-b border-gray-100 dark:border-white/5">
        <Container className="py-16 sm:py-20">
          <Reveal>
            <Eyebrow>Brand</Eyebrow>
            <div className="flex flex-wrap items-center gap-5">
              <AriaMark size={72} animated state="idle" title="ARIA" />
              <div>
                <Heading as="h1">ARIA</Heading>
                <Lead className="mt-2">The assistant's permanent visual identity.</Lead>
              </div>
            </div>
          </Reveal>
        </Container>
      </section>

      {/* Rationale */}
      <Section>
        <Container>
          <div className="grid gap-10 lg:grid-cols-2">
            <Reveal>
              <Heading as="h2">Why a leaf built from a network</Heading>
              <div className="mt-5 space-y-4 leading-relaxed text-gray-600 dark:text-gray-300">
                <p>
                  Leaf venation is already a branching network. That single fact
                  lets one shape carry both halves of what ARIA is — agricultural
                  and intelligent — without borrowing either idea from somewhere
                  else.
                </p>
                <p>
                  It also rules out the three marks every AI product reaches for.
                  A robot says machine, not expert. A chat bubble says support
                  ticket. A glowing orb says someone else's product. None of them
                  say anything about farming.
                </p>
                <p>
                  The geometry is constructed rather than drawn: a true vertical
                  midrib, veins leaving it at a constant 38°, nodes sitting
                  exactly on the junctions. Organic curves would have made this a
                  nature logo. The discipline is what lets it sit beside
                  enterprise software without looking decorative.
                </p>
                <p>
                  Green at the growing tip, navy at the root — Greena's own two
                  colours doing something meaningful rather than being applied as
                  decoration.
                </p>
              </div>
            </Reveal>

            <Reveal delay={0.1}>
              <Card>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">
                  What it must communicate
                </p>
                <dl className="mt-4 space-y-3 text-sm">
                  {[
                    ["Agriculture", "The silhouette. Unmistakable in one glance."],
                    ["Intelligence", "Nodes on the vein junctions — restrained, three only."],
                    ["Growth", "Upward orientation; the tip is the lightest point."],
                    ["Guidance", "The midrib reads as a path from root to tip."],
                    ["Calm", "Symmetry, and motion that never exceeds a 4% change."],
                    ["Trust", "Geometric construction, no novelty, no gloss."],
                  ].map(([k, v]) => (
                    <div key={k} className="flex gap-3">
                      <dt className="w-28 shrink-0 font-medium text-gray-900 dark:text-white">{k}</dt>
                      <dd className="text-gray-600 dark:text-gray-300">{v}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
            </Reveal>
          </div>
        </Container>
      </Section>

      {/* Variants */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <Reveal>
            <Eyebrow>Variants</Eyebrow>
            <Heading as="h2">Five treatments</Heading>
          </Reveal>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <VariantCard label="Primary" note="Default. Colour gradient, full venation.">
              <AriaMark size={64} title="ARIA primary" />
            </VariantCard>

            <VariantCard label="Simplified" note="≤20px, favicon, dense lists. Midrib only.">
              <AriaMark size={64} detail="simple" title="ARIA simplified" />
            </VariantCard>

            <VariantCard label="Monochrome" note="Inherits currentColor. Print, stamps, single-ink.">
              <span className="text-gray-900 dark:text-white">
                <AriaMark size={64} tone="mono" title="ARIA monochrome" />
              </span>
            </VariantCard>

            <VariantCard label="Light theme" note="On white and near-white surfaces.">
              <span className="rounded-xl bg-white p-4">
                <AriaMark size={56} title="ARIA on light" />
              </span>
            </VariantCard>

            <VariantCard label="Dark theme" note="On #0b0e12 and brand-dark surfaces.">
              <span className="rounded-xl bg-[#0b0e12] p-4">
                <AriaMark size={56} title="ARIA on dark" />
              </span>
            </VariantCard>

            <VariantCard label="Avatar" note="Chat, notifications, anywhere it needs a container.">
              <AriaAvatar size={64} />
            </VariantCard>
          </div>
        </Container>
      </Section>

      {/* Animation */}
      <Section>
        <Container>
          <Reveal>
            <Eyebrow>Motion</Eyebrow>
            <Heading as="h2">Five states</Heading>
            <Lead className="mt-4 max-w-2xl">
              Every state is deliberately slow and low-amplitude. An assistant
              that pulses urgently reads as an alert; ARIA should read as
              attentive. All motion stops under <code className="font-mono text-sm">prefers-reduced-motion</code>.
            </Lead>
          </Reveal>

          <div className="mt-10 grid gap-6 lg:grid-cols-5 sm:grid-cols-3 grid-cols-2">
            {STATES.map((s) => (
              <button
                key={s.key}
                onClick={() => setState(s.key)}
                aria-pressed={state === s.key}
                className={`rounded-2xl border p-5 text-center transition-all ${
                  state === s.key
                    ? "border-brand-500 bg-brand-50/50 dark:border-brand-500/50 dark:bg-brand-500/10"
                    : "border-gray-200 hover:border-gray-300 dark:border-white/10"
                }`}
              >
                <span className="flex justify-center">
                  <AriaMark size={48} state={s.key} animated title={`ARIA ${s.key}`} />
                </span>
                <p className="mt-3 text-sm font-medium capitalize text-gray-900 dark:text-white">
                  {s.key}
                </p>
              </button>
            ))}
          </div>

          <Reveal delay={0.08}>
            <Card className="mt-6">
              <p className="text-sm text-gray-600 dark:text-gray-300">
                <span className="font-medium capitalize text-gray-900 dark:text-white">{state}</span>
                {" — "}
                {STATES.find((s) => s.key === state)?.when}
              </p>
            </Card>
          </Reveal>
        </Container>
      </Section>

      {/* Sizes */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <Reveal>
            <Eyebrow>Scale</Eyebrow>
            <Heading as="h2">16px to 512px</Heading>
            <Lead className="mt-4 max-w-2xl">
              Detail is shed as the mark shrinks, never added. Below 20px use the
              simplified variant — the vein network becomes noise at that size and
              the silhouette carries recognition on its own.
            </Lead>
          </Reveal>

          <Card className="mt-10">
            <p className="mb-5 text-xs font-semibold uppercase tracking-wide text-gray-400">
              Primary
            </p>
            <div className="flex flex-wrap items-end gap-7">
              {SIZES.map((s) => (
                <div key={s} className="text-center">
                  <AriaMark size={s} title={`ARIA ${s}px`} />
                  <p className="mt-2 text-xs text-gray-400">{s}px</p>
                </div>
              ))}
            </div>

            <p className="mb-5 mt-9 text-xs font-semibold uppercase tracking-wide text-gray-400">
              Simplified — correct choice at the smallest sizes
            </p>
            <div className="flex flex-wrap items-end gap-7">
              {[16, 20, 24, 32].map((s) => (
                <div key={s} className="text-center">
                  <AriaMark size={s} detail="simple" title={`ARIA simplified ${s}px`} />
                  <p className="mt-2 text-xs text-gray-400">{s}px</p>
                </div>
              ))}
            </div>
          </Card>
        </Container>
      </Section>

      {/* Usage */}
      <Section>
        <Container>
          <Reveal>
            <Eyebrow>Usage</Eyebrow>
            <Heading as="h2">Rules</Heading>
          </Reveal>

          <div className="mt-10 grid gap-4 md:grid-cols-2">
            <Card>
              <p className="mb-3 text-sm font-semibold text-brand-700 dark:text-brand-300">Do</p>
              <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                <li>Keep clear space of at least 25% of the mark's width on all sides.</li>
                <li>Use the simplified variant at 20px and below.</li>
                <li>Use monochrome wherever colour would compete with surrounding UI.</li>
                <li>Animate only when ARIA is genuinely doing something.</li>
                <li>Pair with the lockup when ARIA needs naming to a new user.</li>
              </ul>
            </Card>
            <Card>
              <p className="mb-3 text-sm font-semibold text-red-600 dark:text-red-400">Don't</p>
              <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                <li>Recolour the gradient outside the Greena palette.</li>
                <li>Rotate, skew, or stretch the mark.</li>
                <li>Add a drop shadow, bevel, or outer glow.</li>
                <li>Place it on a busy photograph without the avatar container.</li>
                <li>Loop an animation state while ARIA is idle.</li>
              </ul>
            </Card>
          </div>

          <Card className="mt-4">
            <p className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Colour</p>
            <div className="flex flex-wrap gap-4">
              {[
                ["#0b7d2c", "Tip"],
                ["#076524", "Forest green — primary"],
                ["#063491", "Navy — root"],
              ].map(([hex, label]) => (
                <div key={hex} className="flex items-center gap-3">
                  <span
                    className="h-10 w-10 rounded-lg border border-black/5"
                    style={{ backgroundColor: hex }}
                  />
                  <div>
                    <p className="font-mono text-xs text-gray-900 dark:text-white">{hex}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Container>
      </Section>

      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <Reveal>
            <div className="flex flex-wrap items-center justify-between gap-6">
              <AriaLockup size={32} />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Source: <code className="font-mono">src/components/brand/AriaMark.tsx</code>
              </p>
            </div>
          </Reveal>
        </Container>
      </Section>
    </>
  );
}

function VariantCard({
  label,
  note,
  children,
}: {
  label: string;
  note: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="text-center">
      <div className="flex h-24 items-center justify-center">{children}</div>
      <p className="mt-3 text-sm font-semibold text-gray-900 dark:text-white">{label}</p>
      <p className="mt-1 text-xs leading-relaxed text-gray-500 dark:text-gray-400">{note}</p>
    </Card>
  );
}
