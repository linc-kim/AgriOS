/**
 * NotFoundScreen — 404 for unmatched routes.
 *
 * Rendered standalone (outside the marketing layout), so it carries its own
 * Greena mark, a friendly line, and a few useful ways back. Theme-aware to match
 * the rest of the site.
 */
import { Link } from "react-router-dom";
import { ArrowRight, Home } from "lucide-react";

import greenaEmblem from "@/assets/brand/greena-emblem.svg";
import { useSeo } from "@/hooks/useSeo";

const LINKS = [
  { to: "/farming", label: "What you can farm" },
  { to: "/pricing", label: "Pricing" },
  { to: "/help", label: "Help center" },
  { to: "/contact", label: "Contact us" },
];

export default function NotFoundScreen() {
  useSeo({ title: "Page not found", description: "The page you were looking for isn't here.", path: "/404" });

  return (
    <div className="flex min-h-[100dvh] flex-col bg-white text-gray-900 dark:bg-[#0b0e12] dark:text-white">
      <header className="px-5 py-5 sm:px-8">
        <Link to="/" className="inline-flex items-center gap-2" aria-label="Greena home">
          <img src={greenaEmblem} alt="" aria-hidden className="h-8 w-auto" />
          <span className="text-lg font-semibold tracking-[-0.02em]">Greena</span>
        </Link>
      </header>

      <main className="flex flex-1 items-center justify-center px-5 py-16">
        <div className="mx-auto w-full max-w-md text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-brand-600 dark:text-brand-400">
            Error 404
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-[-0.02em] sm:text-5xl">
            This page wandered off.
          </h1>
          <p className="mt-5 text-base leading-relaxed text-gray-600 dark:text-gray-300">
            The page you were looking for isn't here — it may have moved, or the
            link was mistyped. Let's get you back on track.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              to="/"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-brand-700 hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#0b0e12]"
            >
              <Home className="h-4 w-4" /> Back to home
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-5 py-3 text-sm font-semibold text-gray-900 transition-all hover:border-gray-300 hover:bg-gray-50 dark:border-white/15 dark:bg-white/[0.04] dark:text-white dark:hover:bg-white/[0.08]"
            >
              Go to my farm <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <nav className="mt-10 border-t border-gray-200 pt-6 dark:border-white/10" aria-label="Helpful links">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-gray-400">
              Or try one of these
            </p>
            <ul className="flex flex-wrap justify-center gap-x-5 gap-y-2">
              {LINKS.map((l) => (
                <li key={l.to}>
                  <Link
                    to={l.to}
                    className="text-sm font-medium text-brand-600 hover:underline dark:text-brand-400"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </main>
    </div>
  );
}
