/**
 * Greena — official social accounts (single source of truth).
 *
 * These are the ONLY confirmed official Greena accounts. Add new platforms here
 * (WhatsApp Business, TikTok, YouTube, LinkedIn, X, …) only once the account
 * exists and its official URL is supplied — never invent handles or placeholders.
 * Every public surface (footer, Contact, Help, onboarding, JSON-LD `sameAs`)
 * should read from this list rather than hardcoding URLs.
 *
 * Social presence is presentational only — nothing in the app depends on it, so
 * an unreachable platform never affects Greena's core functionality.
 *
 * Icons are inlined simple line marks (lucide removed its brand glyphs), so the
 * config carries no external icon dependency.
 */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function InstagramIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  );
}

function FacebookIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
    </svg>
  );
}

export interface SocialLink {
  name: string;
  /** Optional public handle, shown where a label helps. */
  handle?: string;
  url: string;
  Icon: (props: IconProps) => JSX.Element;
}

export const SOCIAL_LINKS: SocialLink[] = [
  {
    name: "Instagram",
    handle: "@greenasoftware",
    url: "https://www.instagram.com/greenasoftware/",
    Icon: InstagramIcon,
  },
  {
    name: "Facebook",
    // Exact page URL — do not swap for an invented /greenasoftware vanity URL
    // unless Facebook later assigns the page a verified username.
    url: "https://www.facebook.com/profile.php?id=61593012823507",
    Icon: FacebookIcon,
  },
];

/** Plain URL list — handy for JSON-LD `sameAs` and the like. */
export const SOCIAL_URLS = SOCIAL_LINKS.map((s) => s.url);
