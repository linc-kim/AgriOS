/**
 * Greena — Contact.
 *
 * The form has no backend endpoint yet, so it does not pretend to submit. It
 * validates, then hands off to the user's mail client with the message
 * pre-filled — the enquiry actually reaches us, and nothing is silently
 * swallowed by a fake success state. Swap in a real endpoint later and the
 * markup stays.
 */
import { useState } from "react";
import { Mail, MessageSquare, Phone, Send, Check, AlertCircle } from "lucide-react";

import { GlowField } from "@/components/marketing/LineWaves";
import {
  Container, Section, Reveal, Eyebrow, Heading, Lead, Card,
} from "@/components/marketing/primitives";

const SUPPORT_EMAIL = "support@greena.app";

const CHANNELS = [
  {
    icon: Mail,
    name: "Email",
    detail: SUPPORT_EMAIL,
    copy: "Support and general questions. We reply within one working day.",
    href: `mailto:${SUPPORT_EMAIL}`,
  },
  {
    icon: MessageSquare,
    name: "In-app",
    detail: "Ask ARIA",
    copy: "Already using Greena? ARIA answers most questions instantly, inside the app.",
    href: "/signup",
  },
  {
    icon: Phone,
    name: "Sales",
    detail: "Cooperatives & large farms",
    copy: "Custom pricing and consolidated reporting for groups and multi-site operations.",
    href: `mailto:${SUPPORT_EMAIL}?subject=Greena%20for%20cooperatives`,
  },
];

type Errors = Partial<Record<"name" | "email" | "message", string>>;

import { useSeo } from "@/hooks/useSeo";

export default function ContactScreen() {
  useSeo({
    title: "Contact",
    description:
      "Questions about the product, pricing for a cooperative, or something not working — reach the Greena team.",
    path: "/contact",
  });
  const [form, setForm] = useState({ name: "", email: "", topic: "Support", message: "" });
  const [errors, setErrors] = useState<Errors>({});
  const [sent, setSent] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    setErrors((prev) => ({ ...prev, [k]: undefined }));
  };

  const validate = (): boolean => {
    const next: Errors = {};
    if (!form.name.trim()) next.name = "Please tell us your name.";
    if (!form.email.trim()) next.email = "We need an address to reply to.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) next.email = "That does not look like an email address.";
    if (form.message.trim().length < 10) next.message = "A little more detail helps us help you.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const subject = encodeURIComponent(`[${form.topic}] ${form.name}`);
    const body = encodeURIComponent(`${form.message}\n\n—\n${form.name}\n${form.email}`);
    window.location.href = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`;
    setSent(true);
  };

  const field =
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition-colors " +
    "placeholder:text-gray-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 " +
    "dark:border-white/10 dark:bg-white/[0.03] dark:text-white";

  return (
    <>
      <section className="relative overflow-hidden border-b border-gray-100 dark:border-white/5">
        <GlowField />
        <Container className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <Eyebrow>Contact</Eyebrow>
              <Heading as="h1">Talk to us</Heading>
              <Lead className="mx-auto mt-6">
                Questions about the product, pricing for a cooperative, or
                something that is not working — it all reaches the same small
                team.
              </Lead>
            </Reveal>
          </div>
        </Container>
      </section>

      <Section>
        <Container>
          <div className="grid gap-10 lg:grid-cols-5">
            {/* Channels */}
            <div className="lg:col-span-2">
              <Reveal>
                <div className="space-y-4">
                  {CHANNELS.map((c) => (
                    <a
                      key={c.name}
                      href={c.href}
                      className="block rounded-2xl border border-gray-200 bg-white p-5 transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-lg dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-brand-500/40"
                    >
                      <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                        <c.icon className="h-5 w-5" />
                      </span>
                      <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                        {c.name}
                      </h3>
                      <p className="mt-0.5 text-sm font-medium text-brand-600 dark:text-brand-400">
                        {c.detail}
                      </p>
                      <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                        {c.copy}
                      </p>
                    </a>
                  ))}
                </div>

                <Card className="mt-4">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">Where we are</p>
                  <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                    Nairobi, Kenya — building for farms across East Africa.
                  </p>
                </Card>
              </Reveal>
            </div>

            {/* Form */}
            <div className="lg:col-span-3">
              <Reveal delay={0.08}>
                <Card>
                  {sent ? (
                    <div className="py-8 text-center">
                      <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                        <Check className="h-6 w-6" />
                      </span>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Your email client should be open
                      </h3>
                      <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                        We pre-filled the message. If nothing opened, write to us
                        directly at{" "}
                        <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-600 dark:text-brand-400">
                          {SUPPORT_EMAIL}
                        </a>
                        .
                      </p>
                      <button
                        onClick={() => setSent(false)}
                        className="mt-6 text-sm font-medium text-brand-600 hover:underline dark:text-brand-400"
                      >
                        Write another message
                      </button>
                    </div>
                  ) : (
                    <form onSubmit={onSubmit} noValidate>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Send us a message
                      </h3>

                      <div className="mt-6 grid gap-4 sm:grid-cols-2">
                        <div>
                          <label htmlFor="name" className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-200">
                            Name
                          </label>
                          <input
                            id="name" value={form.name} onChange={set("name")}
                            className={field} placeholder="Your name"
                            aria-invalid={!!errors.name}
                            aria-describedby={errors.name ? "name-error" : undefined}
                          />
                          {errors.name && <FieldError id="name-error">{errors.name}</FieldError>}
                        </div>

                        <div>
                          <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-200">
                            Email
                          </label>
                          <input
                            id="email" type="email" value={form.email} onChange={set("email")}
                            className={field} placeholder="you@farm.co"
                            aria-invalid={!!errors.email}
                            aria-describedby={errors.email ? "email-error" : undefined}
                          />
                          {errors.email && <FieldError id="email-error">{errors.email}</FieldError>}
                        </div>
                      </div>

                      <div className="mt-4">
                        <label htmlFor="topic" className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-200">
                          Topic
                        </label>
                        <select id="topic" value={form.topic} onChange={set("topic")} className={field}>
                          {["Support", "Sales", "Cooperatives", "Feedback", "Something else"].map((t) => (
                            <option key={t} value={t}>{t}</option>
                          ))}
                        </select>
                      </div>

                      <div className="mt-4">
                        <label htmlFor="message" className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-200">
                          Message
                        </label>
                        <textarea
                          id="message" value={form.message} onChange={set("message")}
                          rows={5} className={`${field} resize-y`}
                          placeholder="Tell us what you farm and what you need."
                          aria-invalid={!!errors.message}
                          aria-describedby={errors.message ? "message-error" : undefined}
                        />
                        {errors.message && <FieldError id="message-error">{errors.message}</FieldError>}
                      </div>

                      <button
                        type="submit"
                        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white transition-all hover:bg-brand-700 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 sm:w-auto dark:focus-visible:ring-offset-[#0b0e12]"
                      >
                        <Send className="h-4 w-4" /> Send message
                      </button>

                      <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
                        This opens your email app with the message ready to send.
                      </p>
                    </form>
                  )}
                </Card>
              </Reveal>
            </div>
          </div>
        </Container>
      </Section>
    </>
  );
}

function FieldError({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <p id={id} className="mt-1.5 flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
      <AlertCircle className="h-3.5 w-3.5" /> {children}
    </p>
  );
}
