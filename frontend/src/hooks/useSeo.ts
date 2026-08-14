/**
 * Greena — per-route document head management (dependency-free).
 *
 * This is a client-rendered SPA, so there is no server-side head. Google renders
 * JavaScript and will pick these tags up; note that non-JS social scrapers
 * (Facebook/LinkedIn) read the STATIC index.html head instead, which carries the
 * site-level Open Graph defaults. Per-route tags here improve search results and
 * the browser title/history.
 */
import { useEffect } from "react";

import { SITE_NAME, absoluteUrl } from "@/lib/site";

interface Seo {
  /** Page title, without the site suffix (e.g. "Pricing"). */
  title: string;
  description?: string;
  /** Site-relative canonical path (e.g. "/pricing"). Defaults to current path. */
  path?: string;
}

function setMeta(selector: string, attr: "name" | "property", key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function setCanonical(href: string) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

export function useSeo({ title, description, path }: Seo) {
  useEffect(() => {
    const fullTitle = title === SITE_NAME ? SITE_NAME : `${title} · ${SITE_NAME}`;
    const url = absoluteUrl(path ?? window.location.pathname);

    document.title = fullTitle;
    setMeta('meta[property="og:title"]', "property", "og:title", fullTitle);
    setMeta('meta[name="twitter:title"]', "name", "twitter:title", fullTitle);
    setMeta('meta[property="og:url"]', "property", "og:url", url);
    setCanonical(url);

    if (description) {
      setMeta('meta[name="description"]', "name", "description", description);
      setMeta('meta[property="og:description"]', "property", "og:description", description);
      setMeta('meta[name="twitter:description"]', "name", "twitter:description", description);
    }
  }, [title, description, path]);
}
