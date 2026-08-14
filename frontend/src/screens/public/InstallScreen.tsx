/**
 * Greena — "Put Greena on your phone".
 *
 * A deliberately plain guide for people with little technical experience. It
 * auto-selects the visitor's platform but always lets them switch, offers the
 * one-tap native install when the browser supports it, and otherwise shows the
 * exact hand-steps for Android, iPhone/iPad, or a computer.
 *
 * Wording matches what each platform actually shows and is honest about
 * variation ("if you see X, tap it; otherwise tap Y") — we never claim a button
 * exists on every device.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Smartphone, Monitor, Share, MoreVertical, Plus, Check, Download, Home, Apple,
} from "lucide-react";

import { useSeo } from "@/hooks/useSeo";
import { usePwaInstall, type Platform } from "@/hooks/usePwaInstall";
import { Container, Section, Reveal, Eyebrow, Heading, Lead } from "@/components/marketing/primitives";

type Tab = "android" | "apple" | "computer";

interface Step {
  title: string;
  body: ReactNode;
  icon: ReactNode;
}

const ANDROID_STEPS: Step[] = [
  { icon: <Smartphone />, title: "Open Greena in Chrome", body: "Open Greena on your phone using the Chrome app." },
  { icon: <MoreVertical />, title: "Tap the menu", body: "Tap the three-dots button in the top-right corner." },
  {
    icon: <Download />,
    title: "Tap “Install app”",
    body: "If you see Install app, tap it. If you see Add to Home screen instead, tap that.",
  },
  { icon: <Check />, title: "Tap “Install” or “Add”", body: "Follow the button your phone shows to confirm." },
  { icon: <Home />, title: "Find Greena", body: "The Greena icon appears on your home screen." },
];

const APPLE_STEPS: Step[] = [
  { icon: <Apple />, title: "Open Greena in Safari", body: "Open Greena using the Safari browser — not another browser." },
  {
    icon: <Share />,
    title: "Tap the Share button",
    body: "It is the square with an arrow pointing up (at the bottom on iPhone, at the top on iPad).",
  },
  {
    icon: <Plus />,
    title: "Find “Add to Home Screen”",
    body: "Scroll down the list until you see Add to Home Screen, then tap it.",
  },
  { icon: <Check />, title: "Tap “Add”", body: "Tap Add in the top-right corner." },
  { icon: <Home />, title: "Find Greena", body: "The Greena icon is now on your home screen." },
];

const COMPUTER_STEPS: Step[] = [
  {
    icon: <Monitor />,
    title: "Open Greena in Chrome or Edge",
    body: "Open Greena in your web browser on your computer.",
  },
  {
    icon: <Download />,
    title: "Look for the install icon",
    body: "Near the right end of the address bar, look for a small install icon and click it.",
  },
  {
    icon: <Check />,
    title: "Click “Install”",
    body: "Confirm, and Greena opens in its own window like a normal program.",
  },
  {
    icon: <Home />,
    title: "That’s it",
    body: "If you don’t see an install icon, you can keep using Greena in your browser — everything works the same.",
  },
];

const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: "android", label: "Android", icon: <Smartphone className="h-4 w-4" /> },
  { id: "apple", label: "iPhone / iPad", icon: <Apple className="h-4 w-4" /> },
  { id: "computer", label: "Computer", icon: <Monitor className="h-4 w-4" /> },
];

function tabForPlatform(p: Platform): Tab {
  if (p === "android") return "android";
  if (p === "ios" || p === "ipados") return "apple";
  return "computer";
}

const STEPS: Record<Tab, Step[]> = {
  android: ANDROID_STEPS,
  apple: APPLE_STEPS,
  computer: COMPUTER_STEPS,
};

export default function InstallScreen() {
  useSeo({
    title: "Put Greena on your phone",
    description:
      "Add a Greena icon to your phone's home screen and open it like an app. Simple step-by-step instructions for Android, iPhone, iPad and computers.",
    path: "/install",
  });

  const { platform, isStandalone, canPromptInstall, installed, promptInstall } = usePwaInstall();
  const [tab, setTab] = useState<Tab>(() => tabForPlatform(platform));
  const [choice, setChoice] = useState<"accepted" | "dismissed" | null>(null);

  // Keep the tab aligned with the detected platform until the user overrides it.
  useEffect(() => setTab(tabForPlatform(platform)), [platform]);

  const alreadyInstalled = isStandalone || installed || choice === "accepted";

  return (
    <>
      <section className="border-b border-gray-100 dark:border-white/5">
        <Container className="py-16 sm:py-20">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>Get the app</Eyebrow>
              <Heading as="h1">Put Greena on your phone</Heading>
              <Lead className="mx-auto mt-6">
                You can add a Greena icon to your home screen. Then you open
                Greena by tapping the icon, just like an app.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="mx-auto max-w-3xl">
            {/* Already installed → reassure, don't nag. */}
            {alreadyInstalled ? (
              <Reveal>
                <div className="flex items-start gap-4 rounded-2xl border border-brand-200 bg-brand-50 p-6 dark:border-brand-500/30 dark:bg-brand-500/10">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white">
                    <Check className="h-6 w-6" />
                  </span>
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Greena is on your device
                    </h2>
                    <p className="mt-1 text-[15px] leading-relaxed text-gray-600 dark:text-gray-300">
                      You can open Greena any time by tapping its icon on your
                      home screen — no need to install it again.
                    </p>
                  </div>
                </div>
              </Reveal>
            ) : (
              <>
                {/* One-tap native install when the browser offers it. */}
                {canPromptInstall && (
                  <Reveal>
                    <div className="mb-10 rounded-2xl border border-gray-200 bg-white p-6 text-center dark:border-white/10 dark:bg-white/[0.03]">
                      <p className="text-[15px] text-gray-600 dark:text-gray-300">
                        Your device can add Greena for you in one tap.
                      </p>
                      <button
                        type="button"
                        onClick={async () => setChoice(await promptInstall())}
                        className="mt-4 inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-6 py-3.5 text-base font-semibold text-white transition-all hover:bg-brand-700 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#0b0e12]"
                      >
                        <Download className="h-5 w-5" /> Install Greena
                      </button>
                      <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                        Or follow the steps below.
                      </p>
                    </div>
                  </Reveal>
                )}

                {/* Device switch — auto-selected, always overridable. */}
                <div
                  role="tablist"
                  aria-label="Choose your device"
                  className="mb-8 flex flex-wrap gap-2"
                >
                  {TABS.map((t) => {
                    const selected = tab === t.id;
                    return (
                      <button
                        key={t.id}
                        role="tab"
                        type="button"
                        aria-selected={selected}
                        onClick={() => setTab(t.id)}
                        className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#0b0e12] ${
                          selected
                            ? "border-brand-600 bg-brand-600 text-white"
                            : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-white/15 dark:bg-white/[0.04] dark:text-gray-200"
                        }`}
                      >
                        {t.icon}
                        {t.label}
                      </button>
                    );
                  })}
                </div>

                {/* Steps */}
                <ol className="space-y-4">
                  {STEPS[tab].map((step, i) => (
                    <li
                      key={step.title}
                      className="flex gap-4 rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.02]"
                    >
                      <span
                        aria-hidden
                        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-lg font-bold text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                      >
                        {i + 1}
                      </span>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span aria-hidden className="text-brand-600 dark:text-brand-400 [&>svg]:h-5 [&>svg]:w-5">
                            {step.icon}
                          </span>
                          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                            <span className="sr-only">Step {i + 1}: </span>
                            {step.title}
                          </h3>
                        </div>
                        <p className="mt-1.5 text-[15px] leading-relaxed text-gray-600 dark:text-gray-300">
                          {step.body}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>

                <p className="mt-6 rounded-xl bg-gray-50 px-4 py-3 text-center text-[15px] font-medium text-gray-700 dark:bg-white/[0.03] dark:text-gray-200">
                  Next time: just tap the Greena icon to open Greena.
                </p>

                {tab === "apple" && (
                  <p className="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
                    On iPhone and iPad, adding to the Home Screen works in Safari.
                  </p>
                )}

                <p className="mt-8 text-center text-sm text-gray-500 dark:text-gray-400">
                  Greena is a web app you add to your home screen — it is not in
                  the Play Store or App Store. There is nothing else to download.
                </p>
              </>
            )}
          </div>
        </Container>
      </Section>
    </>
  );
}
