/**
 * Greena — Help Center / FAQ + Support.
 *
 * Answers are grounded in shipped functionality only. The modules listed are the
 * ones that actually exist (poultry/livestock, ornamental birds, BSF, rabbit,
 * goat, sheep, swine, plus feed, inventory, finance, reports, automation, ARIA).
 * Aquaculture/Fish is NOT offered and is deliberately not mentioned. Crops and
 * marketplace are described as planned, matching the module registry.
 */
import { Link } from "react-router-dom";
import { LifeBuoy, Mail, MessageSquare, ArrowRight } from "lucide-react";

import { useSeo } from "@/hooks/useSeo";
import { SUPPORT_EMAIL } from "@/lib/site";
import {
  Container, Section, Reveal, Eyebrow, Heading, Lead, Card, CTA,
} from "@/components/marketing/primitives";

interface QA {
  q: string;
  a: React.ReactNode;
}

const FAQ: { group: string; items: QA[] }[] = [
  {
    group: "Getting started",
    items: [
      {
        q: "What is Greena?",
        a: "Greena is an operating system for your farm: it keeps your records, turns them into reports and forecasts, and gives you an AI assistant, ARIA, that answers questions grounded in your own data.",
      },
      {
        q: "How do I create an account?",
        a: (
          <>
            Choose <Link to="/signup" className="font-medium text-brand-600 dark:text-brand-400">Get started</Link>, sign up with your email and password (or your phone number), and confirm your account with the verification link or one-time code we send you.
          </>
        ),
      },
      {
        q: "I didn’t get my verification email. What now?",
        a: "Check your spam folder first. You can request a fresh verification email from the sign-in screen; verification links expire after a while, so use the most recent one.",
      },
      {
        q: "I forgot my password.",
        a: "Use the “Forgot password” link on the login screen. We’ll email you a reset link that lets you set a new password.",
      },
    ],
  },
  {
    group: "What Greena covers",
    items: [
      {
        q: "Which animals and activities can I manage?",
        a: "Poultry and general livestock, ornamental birds, black soldier fly (BSF) production, rabbits, goats, sheep, and pigs — alongside feed, inventory and assets, finance, reports, and automation. Each area has its own records, dashboards, and reports.",
      },
      {
        q: "Are crops or a marketplace included?",
        a: "Crop planning and a supplier/price marketplace are on the roadmap and not yet generally available. The current focus is livestock, insect, and small-animal management plus the finance and reporting tools around them.",
      },
      {
        q: "What is ARIA?",
        a: "ARIA is Greena’s built-in assistant. It answers questions about your farm, surfaces insights, and helps with day-to-day decisions using your records. It understands English and Swahili.",
      },
      {
        q: "Can I get my data out?",
        a: "Yes. The reporting tools let you view and export your records, so your data stays yours.",
      },
      {
        q: "How do I put Greena on my phone?",
        a: (
          <>
            You can add a Greena icon to your home screen and open it like an app.{" "}
            <Link to="/install" className="font-medium text-brand-600 dark:text-brand-400">
              Follow the simple steps here
            </Link>{" "}
            for Android, iPhone, or iPad.
          </>
        ),
      },
      {
        q: "Do I need the Play Store or App Store?",
        a: "No. Greena is a web app. You add it to your phone’s home screen so it opens like an app — there is nothing to download from an app store.",
      },
    ],
  },
  {
    group: "Plans and billing",
    items: [
      {
        q: "Is there a free plan?",
        a: (
          <>
            Yes — there’s a free tier, plus paid plans with higher limits. Current plans and prices are on the{" "}
            <Link to="/pricing" className="font-medium text-brand-600 dark:text-brand-400">Pricing</Link> page.
          </>
        ),
      },
      {
        q: "How is payment handled?",
        a: "Subscriptions are billed securely through Paystack in Kenyan Shillings (KES). Greena never sees or stores your full card number.",
      },
      {
        q: "How do referrals work?",
        a: "When you refer someone with your code, a discount can be applied to their first payment. You can find and share your code from the referral area once you’re signed in.",
      },
    ],
  },
];

export default function HelpScreen() {
  useSeo({
    title: "Help Center",
    description:
      "Answers to common questions about Greena — getting started, the modules we cover, ARIA, plans and billing — plus how to reach support.",
    path: "/help",
  });

  return (
    <>
      <section className="border-b border-gray-100 dark:border-white/5">
        <Container className="py-16 sm:py-20">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>Help Center</Eyebrow>
              <Heading as="h1">How can we help?</Heading>
              <Lead className="mx-auto mt-6">
                Quick answers to the questions we hear most. Can’t find what you
                need? Our team is one message away.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-3xl space-y-12">
            {FAQ.map((section) => (
              <Reveal key={section.group}>
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-gray-400">
                  {section.group}
                </h2>
                <div className="divide-y divide-gray-200 overflow-hidden rounded-2xl border border-gray-200 bg-white dark:divide-white/10 dark:border-white/10 dark:bg-white/[0.02]">
                  {section.items.map((item) => (
                    <details key={item.q} className="group">
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-[15px] font-medium text-gray-900 marker:content-none hover:bg-gray-50 dark:text-white dark:hover:bg-white/[0.03]">
                        {item.q}
                        <ArrowRight className="h-4 w-4 shrink-0 text-gray-400 transition-transform group-open:rotate-90" />
                      </summary>
                      <div className="px-5 pb-5 text-[15px] leading-relaxed text-gray-600 dark:text-gray-300">
                        {item.a}
                      </div>
                    </details>
                  ))}
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      {/* Support */}
      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <div className="mx-auto max-w-3xl">
            <Reveal>
              <div className="mb-6 flex items-center gap-2 text-brand-600 dark:text-brand-400">
                <LifeBuoy className="h-5 w-5" />
                <span className="text-sm font-semibold uppercase tracking-[0.12em]">Still stuck?</span>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Card>
                  <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                    <Mail className="h-5 w-5" />
                  </span>
                  <h3 className="text-base font-semibold text-gray-900 dark:text-white">Email support</h3>
                  <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                    Write to{" "}
                    <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-600 dark:text-brand-400">
                      {SUPPORT_EMAIL}
                    </a>
                    . We reply within one working day.
                  </p>
                </Card>
                <Card>
                  <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                    <MessageSquare className="h-5 w-5" />
                  </span>
                  <h3 className="text-base font-semibold text-gray-900 dark:text-white">Ask ARIA</h3>
                  <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                    Already using Greena? ARIA answers most questions instantly,
                    right inside the app.
                  </p>
                </Card>
              </div>
              <div className="mt-6">
                <CTA to="/contact">
                  Contact the team <ArrowRight className="h-4 w-4" />
                </CTA>
              </div>
            </Reveal>
          </div>
        </Container>
      </Section>
    </>
  );
}
