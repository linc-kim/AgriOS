/**
 * ARIA design system — the component gallery.
 *
 * Every component the AI surfaces are built from, rendered live with fixture
 * data. Same argument as the mark documentation it sits below: a spec sheet
 * that imports the real components cannot drift from what ships.
 *
 * The fixtures deliberately match the shapes the backend actually returns —
 * `{title, type}` for recommendations, `{title, severity}` for insights — so
 * this page also serves as a check that the cards degrade properly on the thin
 * data they really receive, rather than on invented richness.
 */
import { useState } from "react";

import {
  AriaAvatar,
  AriaBadge,
  AriaComposer,
  AriaConfidence,
  AriaDiseaseCard,
  AriaEmptyState,
  AriaForecastCard,
  AriaHeadline,
  AriaInsightCard,
  AriaLoading,
  AriaMessageBubble,
  AriaPredictionCard,
  AriaQuickActions,
  AriaRecommendation,
  AriaRiskChip,
  AriaSources,
  AriaStatus,
  AriaThinking,
  AriaTrendChip,
  OPENING_ACTIONS,
} from "@/components/aria";
import { Container, Section, Reveal, Eyebrow, Heading, Lead, Card } from "@/components/marketing/primitives";
import type { AIDiseaseRisk, AIForecast, AIMortalityPrediction } from "@/types";

/* ── Fixtures ──────────────────────────────────────────────────────────────── */

const MORTALITY: AIMortalityPrediction = {
  scope: "farm",
  predicted_next_7d: 14,
  recent_7d: 9,
  trend: "rising",
  confidence: "medium",
  explanation:
    "Mortality has climbed for three consecutive days in House 2, against a stable pattern elsewhere.",
  factors: [
    { factor: "House 2 daily deaths", impact: "+6", detail: "vs 7-day mean" },
    { factor: "Ambient temperature", impact: "+3", detail: "4 days above 31°C" },
    { factor: "Feed intake", impact: "−2", detail: "down 8% since Tuesday" },
  ],
};

const RISK: AIDiseaseRisk = {
  score: 68,
  level: "high",
  recommendation:
    "Isolate House 2 and call your vet. The combination of falling intake and rising mortality is consistent with an early respiratory infection.",
  factors: [
    { factor: "Mortality trend", impact: "High", detail: "rising 3 days" },
    { factor: "Vaccination status", impact: "Medium", detail: "Gumboro overdue by 5 days" },
  ],
};

const FORECAST: AIForecast = {
  metric: "net_profit",
  horizon_days: 30,
  projected_value: "48,200",
  unit: "KES",
  confidence: "high",
  factors: ["Feed cost steady", "Egg price up 4%", "No capital spend due"],
  series: [],
};

/* ── Gallery ───────────────────────────────────────────────────────────────── */

export function BrandAriaSystemSection() {
  const [draft, setDraft] = useState("");

  return (
    <>
      <Section className="border-t border-gray-100 dark:border-white/5">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Reveal>
              <Eyebrow>Design system</Eyebrow>
              <Heading>The components</Heading>
              <Lead className="mt-4">
                Every AI surface in Greena is built from these. Rendered live from{" "}
                <code className="font-mono text-[0.9em]">src/components/aria</code> with the
                same data shapes the API returns.
              </Lead>
            </Reveal>
          </div>

          {/* Identity */}
          <Row title="Identity" note="Mark treatments the product reaches for.">
            <Spec label="AriaAvatar">
              <div className="flex items-center gap-3">
                <AriaAvatar size={28} />
                <AriaAvatar size={36} />
                <AriaAvatar size={48} />
              </div>
            </Spec>
            <Spec label="AriaBadge" note="Attribution — marks what ARIA inferred.">
              <div className="flex items-center gap-2">
                <AriaBadge size="sm" />
                <AriaBadge />
              </div>
            </Spec>
            <Spec label="AriaStatus">
              <div className="flex flex-col items-start gap-1.5">
                <AriaStatus kind="ready" />
                <AriaStatus kind="thinking" />
                <AriaStatus kind="offline" />
              </div>
            </Spec>
          </Row>

          {/* Trust signals */}
          <Row
            title="Trust signals"
            note="Confidence uses the brand scale, risk uses the alert scale. Different questions, different palettes."
          >
            <Spec label="AriaConfidence">
              <div className="flex flex-col items-start gap-2">
                <AriaConfidence value="high" />
                <AriaConfidence value="medium" />
                <AriaConfidence value="low" />
              </div>
            </Spec>
            <Spec label="AriaRiskChip">
              <div className="flex flex-wrap gap-1.5">
                <AriaRiskChip level="critical" />
                <AriaRiskChip level="high" />
                <AriaRiskChip level="moderate" />
                <AriaRiskChip level="low" />
              </div>
            </Spec>
            <Spec label="AriaTrendChip" note="Direction is coloured by whether up is good.">
              <div className="flex flex-wrap gap-1.5">
                <AriaTrendChip trend="rising" />
                <AriaTrendChip trend="rising" higherIsBetter />
                <AriaTrendChip trend="stable" />
              </div>
            </Spec>
            <Spec label="AriaSources">
              <AriaSources sources={["feed_logs", "mortality_records"]} provider="gemini" />
            </Spec>
          </Row>

          {/* Waiting */}
          <Row title="Waiting" note="A reply being composed, and a panel being fetched.">
            <Spec label="AriaThinking">
              <AriaThinking />
            </Spec>
            <Spec label="AriaLoading">
              <AriaLoading compact label="Gathering your farm data…" />
            </Spec>
          </Row>
        </Container>
      </Section>

      {/* Cards */}
      <Section className="bg-gray-50/60 dark:bg-white/[0.02]">
        <Container>
          <Reveal>
            <Eyebrow>Cards</Eyebrow>
            <Heading as="h3">What ARIA produces</Heading>
            <Lead className="mt-3 max-w-2xl">
              Four kinds of output, one shell. The accent rail carries the meaning; the
              structure never moves.
            </Lead>
          </Reveal>

          <div className="mt-10 grid gap-5 lg:grid-cols-2">
            <AriaPredictionCard prediction={MORTALITY} />
            <AriaDiseaseCard risk={RISK} />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <Card className="!p-5">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                AriaForecastCard
              </p>
              <AriaForecastCard forecast={FORECAST} />
            </Card>

            <Card className="!p-5">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                AriaRecommendation · AriaInsightCard
              </p>
              <div className="-mx-2">
                <AriaRecommendation item={{ title: "Reorder layer mash — 4 days of stock left", type: "inventory" }} />
                <AriaRecommendation item={{ title: "Gumboro vaccination is overdue in House 2", type: "health" }} />
                <AriaInsightCard item={{ title: "Feed cost per bird is up 11% this batch", severity: "warning" }} />
                <AriaInsightCard item={{ title: "House 1 is your most efficient flock", severity: "info" }} />
              </div>
            </Card>
          </div>

          <div className="mt-5">
            <AriaHeadline
              headline="Disease risk high (68/100); ~14 deaths projected next week; net profit forecast KES 48,200."
              meta="Gemini · explainable and grounded in your records"
            />
          </div>
        </Container>
      </Section>

      {/* Conversation */}
      <Section>
        <Container>
          <Reveal>
            <Eyebrow>Conversation</Eyebrow>
            <Heading as="h3">Chat</Heading>
          </Reveal>

          <div className="mt-10 grid gap-5 lg:grid-cols-2">
            <Card className="!p-5">
              <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-gray-400">
                AriaMessageBubble
              </p>
              <div className="space-y-4">
                <AriaMessageBubble
                  message={{ id: "u", role: "user", text: "What is my disease risk?" }}
                />
                <AriaMessageBubble
                  message={{
                    id: "a",
                    role: "aria",
                    text: "Disease risk is high at 68/100, driven mainly by three days of rising mortality in House 2 and an overdue Gumboro vaccination.",
                    sources: ["mortality_records", "vaccination_schedule"],
                    provider: "gemini",
                    followUps: ["What should I do about the disease risk?", "What vaccines are due?"],
                  }}
                  onFollowUp={() => {}}
                />
              </div>
            </Card>

            <Card className="!p-5">
              <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-gray-400">
                AriaQuickActions · AriaComposer
              </p>
              <AriaQuickActions actions={OPENING_ACTIONS.slice(0, 4)} onPick={() => {}} />
              <AriaComposer
                className="mt-4"
                value={draft}
                onChange={setDraft}
                onSubmit={() => setDraft("")}
              />
              <p className="mt-3 text-xs leading-relaxed text-gray-500 dark:text-gray-400">
                The microphone and attachment controls appear only when{" "}
                <code className="font-mono">onVoice</code> /{" "}
                <code className="font-mono">onAttach</code> are supplied. The backend has
                neither yet, so neither renders — the seam exists without promising a
                feature that does not.
              </p>
            </Card>
          </div>

          <div className="mt-5">
            <AriaEmptyState compact />
          </div>
        </Container>
      </Section>
    </>
  );
}

/* ── Layout helpers ────────────────────────────────────────────────────────── */

function Row({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-12">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>
      {note && (
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-gray-500 dark:text-gray-400">
          {note}
        </p>
      )}
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</div>
    </div>
  );
}

function Spec({
  label,
  note,
  children,
}: {
  label: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="!p-4">
      <div className="flex min-h-[76px] items-center">{children}</div>
      <p className="mt-3 border-t border-gray-100 pt-2.5 font-mono text-[11px] text-gray-900 dark:border-white/5 dark:text-white">
        {label}
      </p>
      {note && (
        <p className="mt-1 text-[11px] leading-relaxed text-gray-500 dark:text-gray-400">{note}</p>
      )}
    </Card>
  );
}
