/**
 * Greena — Terms of Service.
 *
 * Grounded in the platform's real commercial behavior: free tier, paid
 * subscriptions billed through Paystack in KES, a Professional trial, and a
 * referral first-payment discount. Specific prices are intentionally not
 * restated here — they are shown on the Pricing page and derived server-side —
 * so this document cannot drift from the live catalog.
 */
import { Link } from "react-router-dom";

import { useSeo } from "@/hooks/useSeo";
import { SUPPORT_EMAIL } from "@/lib/site";
import { LegalHero, DraftNotice, Prose, Clause, Bullets } from "./legalPrimitives";

export default function TermsScreen() {
  useSeo({
    title: "Terms of Service",
    description:
      "The terms governing your use of Greena — accounts, subscriptions and billing, acceptable use, and the limits of the service.",
    path: "/terms",
  });

  return (
    <>
      <LegalHero
        eyebrow="Legal"
        title="Terms of Service"
        lead="These terms govern your use of Greena. By creating an account or using the service, you agree to them."
        updated="August 2026"
      />

      <Prose>
        <DraftNotice />

        <Clause heading="The service">
          <p>
            Greena is a farm management platform that lets you keep records,
            generate reports and forecasts, and use an AI assistant (ARIA) across
            supported farming activities. We provide the service on an ongoing
            basis and may add, change, or remove features as it develops.
          </p>
        </Clause>

        <Clause heading="Your account">
          <Bullets
            items={[
              "You must provide accurate sign-up details and verify your email or phone number.",
              "You are responsible for keeping your login credentials secure and for activity under your account.",
              "You must be authorized to act for any organization you register or manage in Greena.",
              "Tell us promptly at the support address below if you believe your account has been compromised.",
            ]}
          />
        </Clause>

        <Clause heading="Plans, trials, and billing">
          <Bullets
            items={[
              <>Greena offers a free tier and paid subscription plans. Current plans and prices are shown on the <Link to="/pricing" className="font-medium text-brand-600 dark:text-brand-400">Pricing</Link> page; the amount charged is always the plan’s published price.</>,
              "Paid subscriptions are billed through our payment processor, Paystack, in Kenyan Shillings (KES).",
              "A paid plan may include a free trial period. Unless you subscribe, access to paid features ends when the trial ends.",
              "Where a valid referral applies, a discount may be applied to the referred account’s first payment, as described on the Pricing and referral screens.",
              "Subscriptions grant access to features and usage limits for your plan. When a subscription ends, your account moves to the free tier and paid features become unavailable, but your existing records remain accessible within free-tier limits.",
            ]}
          />
        </Clause>

        <Clause heading="Acceptable use">
          <p>You agree not to:</p>
          <Bullets
            items={[
              "Use Greena for any unlawful purpose or in breach of another party’s rights.",
              "Attempt to access data belonging to other organizations, or to probe, scan, or breach security controls.",
              "Interfere with or disrupt the service, or place an unreasonable load on it through automated means.",
              "Misrepresent the AI assistant’s output as professional veterinary, financial, or legal advice — it is guidance, not a substitute for a qualified professional.",
            ]}
          />
        </Clause>

        <Clause heading="Your data">
          <p>
            You keep ownership of the records you enter. You grant us the
            permission needed to store and process that data to operate the
            service for you, including generating reports and ARIA responses. How
            we handle personal data is described in our{" "}
            <Link to="/privacy" className="font-medium text-brand-600 dark:text-brand-400">
              Privacy Policy
            </Link>
            .
          </p>
        </Clause>

        <Clause heading="Availability and changes">
          <p>
            We work to keep Greena available and reliable, but we do not guarantee
            uninterrupted service. We may perform maintenance, and we may modify or
            discontinue features. Where a change is significant, we will aim to
            give reasonable notice.
          </p>
        </Clause>

        <Clause heading="Disclaimers and limitation of liability">
          <p>
            The service is provided “as is”. ARIA and other insights are generated
            from the data available and can be incomplete or incorrect; you remain
            responsible for decisions about your farm. To the extent permitted by
            law, Greena is not liable for indirect or consequential losses, or for
            loss arising from your reliance on outputs of the service.
          </p>
        </Clause>

        <Clause heading="Suspension and termination">
          <p>
            You may stop using Greena and close your account at any time. We may
            suspend or terminate access if these terms are breached or if required
            to protect the service or other users. On termination, the sections
            that by their nature should survive — such as data ownership,
            disclaimers, and limitation of liability — continue to apply.
          </p>
        </Clause>

        <Clause heading="Governing law">
          <p>
            These terms are governed by the laws of Kenya. Nothing here removes
            any consumer rights you have that cannot be waived by agreement.
          </p>
        </Clause>

        <Clause heading="Contact">
          <p>
            Questions about these terms can be sent to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-600 dark:text-brand-400">
              {SUPPORT_EMAIL}
            </a>
            .
          </p>
        </Clause>
      </Prose>
    </>
  );
}
