/**
 * Greena — Public site shell.
 *
 * Sticky translucent nav, mobile drawer, and the footer, wrapped around every
 * marketing route. Authenticated visitors get "Go to dashboard" instead of
 * Login / Get started, so an existing customer landing on the homepage is one
 * click from their farm rather than being asked to sign in again.
 */
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Menu, X, ArrowRight } from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { Container, CTA } from "@/components/marketing/primitives";
import { SOCIAL_LINKS } from "@/lib/social";
import greenaEmblem from "@/assets/brand/greena-emblem.svg";

const NAV = [
  { to: "/features", label: "Features" },
  { to: "/solutions", label: "Solutions" },
  { to: "/aria-ai", label: "ARIA AI" },
  { to: "/pricing", label: "Pricing" },
  { to: "/learning", label: "Learning" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

function Wordmark() {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="Greena home">
      <img src={greenaEmblem} alt="" aria-hidden className="h-8 w-auto" />
      <span className="text-lg font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
        Greena
      </span>
    </Link>
  );
}

export default function MarketingLayout() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { pathname } = useLocation();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Close the drawer on navigation — leaving it open over the new page is a
  // classic mobile-nav bug.
  useEffect(() => setOpen(false), [pathname]);

  // Lock scroll behind the drawer.
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
      isActive
        ? "text-brand-700 dark:text-brand-300"
        : "text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
    }`;

  return (
    <div className="min-h-[100dvh] bg-white text-gray-900 dark:bg-[#0b0e12] dark:text-white">
      {/* Keyboard users land here first and can jump the nav entirely. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-brand-600 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        Skip to content
      </a>

      <header
        className={`sticky top-0 z-50 border-b transition-colors ${
          scrolled
            ? "border-gray-200/80 bg-white/85 backdrop-blur-md dark:border-white/10 dark:bg-[#0b0e12]/85"
            : "border-transparent bg-transparent"
        }`}
      >
        <Container>
          <nav className="flex h-16 items-center justify-between gap-4" aria-label="Main">
            <Wordmark />

            <div className="hidden items-center gap-0.5 lg:flex">
              {NAV.map((item) => (
                <NavLink key={item.to} to={item.to} className={linkCls}>
                  {item.label}
                </NavLink>
              ))}
            </div>

            <div className="hidden items-center gap-2 lg:flex">
              {isAuthenticated ? (
                <CTA to="/dashboard">
                  Go to dashboard <ArrowRight className="h-4 w-4" />
                </CTA>
              ) : (
                <>
                  <CTA to="/login" variant="ghost">
                    Log in
                  </CTA>
                  <CTA to="/signup">Get started</CTA>
                </>
              )}
            </div>

            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-label={open ? "Close menu" : "Open menu"}
              aria-expanded={open}
              className="rounded-lg p-2 text-gray-700 hover:bg-gray-100 lg:hidden dark:text-gray-200 dark:hover:bg-white/10"
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </nav>
        </Container>
      </header>

      {open && (
        <div className="fixed inset-x-0 top-16 z-40 h-[calc(100dvh-4rem)] overflow-y-auto border-t border-gray-200 bg-white px-5 pb-10 pt-4 lg:hidden dark:border-white/10 dark:bg-[#0b0e12]">
          <div className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-xl px-4 py-3 text-base font-medium ${
                    isActive
                      ? "bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300"
                      : "text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-white/5"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          <div className="mt-6 flex flex-col gap-2">
            {isAuthenticated ? (
              <CTA to="/dashboard" className="w-full">
                Go to dashboard <ArrowRight className="h-4 w-4" />
              </CTA>
            ) : (
              <>
                <CTA to="/signup" className="w-full">
                  Get started
                </CTA>
                <CTA to="/login" variant="secondary" className="w-full">
                  Log in
                </CTA>
              </>
            )}
          </div>
        </div>
      )}

      <main id="main">
        <Outlet />
      </main>

      <footer className="border-t border-gray-200 bg-gray-50/60 py-14 dark:border-white/10 dark:bg-white/[0.02]">
        <Container>
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-5">
            <div>
              <Wordmark />
              <p className="mt-3 max-w-xs text-sm leading-relaxed text-gray-500 dark:text-gray-400">
                The operating system for your farm — records, insight and an
                assistant that understands your flock.
              </p>
            </div>

            <FooterCol
              title="Product"
              links={[
                { to: "/features", label: "Features" },
                { to: "/solutions", label: "Solutions" },
                { to: "/aria-ai", label: "ARIA AI" },
                { to: "/pricing", label: "Pricing" },
              ]}
            />
            <FooterCol
              title="Resources"
              links={[
                { to: "/learning", label: "Greena Academy" },
                { to: "/help", label: "Help Center" },
                { to: "/about", label: "About" },
                { to: "/contact", label: "Contact" },
              ]}
            />
            <FooterCol
              title="Legal"
              links={[
                { to: "/privacy", label: "Privacy Policy" },
                { to: "/terms", label: "Terms of Service" },
              ]}
            />
            <FooterCol
              title="Get started"
              links={[
                { to: "/signup", label: "Create an account" },
                { to: "/login", label: "Log in" },
                { to: "/install", label: "Put Greena on your phone" },
              ]}
            />
          </div>

          <div className="mt-12 flex flex-col gap-4 border-t border-gray-200 pt-6 text-sm text-gray-500 sm:flex-row sm:items-center sm:justify-between dark:border-white/10 dark:text-gray-400">
            <p>© {new Date().getFullYear()} Greena. Built for farmers.</p>

            <ul className="flex items-center gap-2">
              {SOCIAL_LINKS.map(({ name, url, Icon }) => (
                <li key={name}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Greena on ${name}`}
                    className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 transition-colors hover:bg-gray-100 hover:text-brand-700 dark:text-gray-400 dark:hover:bg-white/10 dark:hover:text-brand-300"
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </a>
                </li>
              ))}
            </ul>

            <p>Nairobi, Kenya</p>
          </div>
        </Container>
      </footer>
    </div>
  );
}

function FooterCol({
  title,
  links,
}: {
  title: string;
  links: { to: string; label: string }[];
}) {
  return (
    <div>
      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-gray-400">
        {title}
      </p>
      <ul className="space-y-2">
        {links.map((l) => (
          <li key={l.to}>
            <Link
              to={l.to}
              className="text-sm text-gray-600 transition-colors hover:text-brand-700 dark:text-gray-300 dark:hover:text-brand-300"
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
