/**
 * Greena — canonical site configuration.
 *
 * SITE_URL is the public origin used to build canonical + Open Graph URLs and
 * the sitemap. It is configurable so the same build can be pointed at a preview
 * origin or the final custom domain without code changes.
 *
 * Default: the intended production domain `https://greena.app`. Until that
 * domain is purchased and DNS is pointed at Vercel, canonical/OG URLs will
 * reference a domain that is not yet live — set VITE_SITE_URL to the actual
 * public origin at build time to override. (Search indexing is additionally
 * gated by Vercel deployment protection; see the Phase report.)
 */
export const SITE_URL = (
  import.meta.env.VITE_SITE_URL ?? "https://greena.app"
).replace(/\/+$/, "");

export const SITE_NAME = "Greena";
export const SUPPORT_EMAIL = "support@greena.app";

/** Absolute URL for a site-relative path, e.g. absoluteUrl("/pricing"). */
export function absoluteUrl(path: string): string {
  if (!path.startsWith("/")) path = `/${path}`;
  return `${SITE_URL}${path === "/" ? "" : path}`;
}
