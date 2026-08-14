/**
 * Greena — Privacy Policy.
 *
 * Content is grounded in how the platform actually processes data (account
 * identity, farm records, Paystack payments, Gemini/Claude AI, Zoho email,
 * Sentry monitoring, Render/Vercel/Supabase infrastructure). No legal entity
 * numbers, addresses, certifications or retention periods are invented — where a
 * specific figure is not established in the product, the text stays general.
 */
import { Link } from "react-router-dom";

import { useSeo } from "@/hooks/useSeo";
import { SUPPORT_EMAIL } from "@/lib/site";
import { LegalHero, DraftNotice, Prose, Clause, Bullets } from "./legalPrimitives";

export default function PrivacyScreen() {
  useSeo({
    title: "Privacy Policy",
    description:
      "How Greena collects, uses, and protects your account and farm data, and the processors we rely on to run the service.",
    path: "/privacy",
  });

  return (
    <>
      <LegalHero
        eyebrow="Legal"
        title="Privacy Policy"
        lead="Greena is a farm management platform. This policy explains what information we hold, why we hold it, and the choices you have."
        updated="August 2026"
      />

      <Prose>
        <DraftNotice />

        <Clause heading="Who we are">
          <p>
            Greena provides farm record-keeping, reporting, and an AI assistant
            (ARIA) to farmers and agricultural organizations, operating from
            Nairobi, Kenya. In this policy, “Greena”, “we” and “us” refer to the
            Greena service; “you” refers to the person or organization using it.
            For any privacy question, contact us at{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-600 dark:text-brand-400">
              {SUPPORT_EMAIL}
            </a>
            .
          </p>
        </Clause>

        <Clause heading="Information we collect">
          <Bullets
            items={[
              <><strong className="text-gray-900 dark:text-white">Account details</strong> — your name, and an email address and/or phone number used to sign in and to verify your account.</>,
              <><strong className="text-gray-900 dark:text-white">Farm and organization data</strong> — the records you enter: flocks and animals, feed, inventory, health events, finances, and related notes.</>,
              <><strong className="text-gray-900 dark:text-white">Assistant queries</strong> — the questions and instructions you send to ARIA, so it can respond in the context of your farm.</>,
              <><strong className="text-gray-900 dark:text-white">Billing information</strong> — your plan and payment records. Card and mobile-money details are entered directly with our payment processor; Greena does not receive or store your full card number.</>,
              <><strong className="text-gray-900 dark:text-white">Technical data</strong> — authentication tokens, and diagnostic/error information used to keep the service reliable and secure.</>,
            ]}
          />
        </Clause>

        <Clause heading="How we use your information">
          <Bullets
            items={[
              "To provide the platform: storing your records and generating your reports, dashboards, and forecasts.",
              "To run ARIA: answering your questions using your farm’s data.",
              "To authenticate you, keep your account secure, and prevent abuse.",
              "To process subscriptions, trials, and referral discounts.",
              "To send you essential service email such as verification and password-reset messages.",
              "To diagnose problems and improve the reliability and quality of the service.",
            ]}
          />
        </Clause>

        <Clause heading="Service providers we rely on">
          <p>
            To run Greena we use a small number of trusted providers, who process
            data only to deliver their part of the service:
          </p>
          <Bullets
            items={[
              <><strong className="text-gray-900 dark:text-white">Paystack</strong> — payment processing for subscriptions.</>,
              <><strong className="text-gray-900 dark:text-white">Google (Gemini)</strong> and <strong className="text-gray-900 dark:text-white">Anthropic (Claude)</strong> — AI processing that powers ARIA’s responses.</>,
              <><strong className="text-gray-900 dark:text-white">Zoho Mail</strong> — delivery of transactional email.</>,
              <><strong className="text-gray-900 dark:text-white">Supabase</strong> — the managed database that stores your records.</>,
              <><strong className="text-gray-900 dark:text-white">Render</strong> and <strong className="text-gray-900 dark:text-white">Vercel</strong> — hosting for the API and website.</>,
              <><strong className="text-gray-900 dark:text-white">Sentry</strong> — error monitoring that helps us find and fix faults.</>,
            ]}
          />
          <p>
            We do not sell your personal information, and we do not share your
            farm records with other customers.
          </p>
        </Clause>

        <Clause heading="Data retention">
          <p>
            We keep your information for as long as your account is active so that
            your records remain available to you. If you close your account, we
            delete or anonymize your personal data once it is no longer needed to
            provide the service or to meet a legal or accounting obligation. You
            can ask us about deleting your data at any time.
          </p>
        </Clause>

        <Clause heading="Your choices and rights">
          <Bullets
            items={[
              "Access and correct the information in your account at any time from within the app.",
              "Export your records using the built-in reporting and export tools.",
              "Request deletion of your account and associated personal data.",
              "Ask us how your data is processed, or object to a particular use.",
            ]}
          />
          <p>
            To exercise any of these, write to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-600 dark:text-brand-400">
              {SUPPORT_EMAIL}
            </a>
            .
          </p>
        </Clause>

        <Clause heading="Security">
          <p>
            Access to the platform requires authentication, traffic is served
            over encrypted connections, and access to your organization’s data is
            restricted to your organization. No system is perfectly secure, but we
            take reasonable measures to protect your information and to detect and
            respond to problems.
          </p>
        </Clause>

        <Clause heading="Children">
          <p>
            Greena is intended for use by farmers and agricultural businesses and
            is not directed at children.
          </p>
        </Clause>

        <Clause heading="Changes to this policy">
          <p>
            We may update this policy as the product evolves. When we make
            material changes, we will update the date above and, where
            appropriate, notify you in the app.
          </p>
        </Clause>

        <Clause heading="Contact">
          <p>
            Questions about privacy or this policy can be sent to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-600 dark:text-brand-400">
              {SUPPORT_EMAIL}
            </a>
            . See also our{" "}
            <Link to="/terms" className="font-medium text-brand-600 dark:text-brand-400">
              Terms of Service
            </Link>
            .
          </p>
        </Clause>
      </Prose>
    </>
  );
}
