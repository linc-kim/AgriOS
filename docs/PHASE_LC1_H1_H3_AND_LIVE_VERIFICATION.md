# Greena V1 LC1 — Live Infrastructure Verification + H1 (Legal/Support) + H3 (SEO)

**Date:** 2026-08-14 · **Branch:** `phase-2-auth`
**Evidence standard:** every live check below reports Environment → Test → Result → Evidence. Results are PASS / FAIL / BLOCKED / UNVERIFIED. Configuration in the repo is **not** reported as production reality unless a live check confirmed it.

---

## 1. Live infrastructure status

| # | Test | Environment | Result | Evidence |
|---|------|-------------|--------|----------|
| 1 | Backend service reachable | Render (`greena-api-v91z.onrender.com`) | **PASS** | `GET /health` → 200 `{"status":"ok","version":"1.0.0","environment":"production","db":"connected"}` |
| 2 | DB connectivity | Render → Supabase | **PASS** | `db":"connected"` in the live health payload (production DB reachable from the API) |
| 3 | Cold-start latency | Render (free plan) | **PASS (finding)** | First request timed out at 30s; a 90s retry returned 200 after **67.5s**. Free plan spins down when idle. |
| 4 | API docs exposure | Render | **PASS (secure)** | `GET /openapi.json` → 404; `GET /` → 404. Docs disabled in production. |
| 5 | API routing + auth guard | Render | **PASS** | `GET /api/v1/billing/plans` → 401 `UNAUTHENTICATED` (routes live, guarded). |
| 6 | Live plan prices | Render | **UNVERIFIED** | Plans require auth; not fetched. Prices are DB-seeded and server-derived — cannot confirm the live catalog without an authenticated session. |
| 7 | Frontend deployed | Vercel (project `agri-os-ahn4`) | **PASS (deployed)** | `vercel ls --prod`: latest Production deployment `● Ready`, 14h old — `agri-os-ahn4-hhp8etchy-agri-os.vercel.app`. |
| 8 | Frontend publicly accessible | Vercel | **FAIL (blocker)** | Deployment 302-redirects to `vercel.com/sso-api` (`Set-Cookie: _vercel_sso_nonce`). **Vercel deployment protection (SSO) is ON** → the public site is not reachable and cannot be indexed. |
| 9 | Custom domain / alias | Vercel | **UNVERIFIED / expected absent** | `agri-os-ahn4.vercel.app` → 404. `greena.app` not purchased (owner-deferred). |
| 10 | Deployed commit (both) | Render + Vercel | **UNVERIFIED** | No Render dashboard token in this environment; Vercel deployment carries no git metadata (`vercel inspect` shows no commit/branch). Cannot prove which commit is live. |
| 11 | Paystack runtime | — | **UNVERIFIED** | Not exercised (would require an authenticated checkout against live keys). |

**Access confirmed this session:** Vercel CLI authenticated as `lincolnkeymoney-9884`; `gh` CLI present; sandbox has general internet egress (example.com/github 200 in <1s). **Not available:** `render` CLI / Render API token (Render verification limited to public HTTP).

### Live blockers surfaced
- **LC-B1 (HIGH):** Vercel **deployment protection** makes the production site private — must be disabled for public launch + indexing. *This is an account setting; not changed without owner approval.*
- **LC-B2 (MEDIUM):** Render **free-plan cold start ~67s** — first visitor / crawler after idle waits up to a minute. Upgrade to a paid Render plan (or add a keep-warm ping) before launch.

---

## 2. H1 — Legal & support pages

All pages are client routes under `MarketingLayout`, reachable from the footer, responsive, with per-route titles/descriptions/canonical via `useSeo`. Content is grounded in actual platform behavior; no legal entity numbers, addresses, retention periods, or certifications were invented. Privacy & Terms carry a visible "Draft for review" notice.

| Page | Route | Implementation | Local verification |
|------|-------|----------------|--------------------|
| Privacy Policy | `/privacy` | `src/screens/public/PrivacyScreen.tsx` | **PASS** — renders; title "Privacy Policy · Greena"; lists real subprocessors (Paystack, Gemini, Claude, Zoho, Supabase, Render, Vercel, Sentry) |
| Terms of Service | `/terms` | `src/screens/public/TermsScreen.tsx` | **PASS** — renders; billing/trial/referral/governing-law (Kenya) grounded; prices deferred to `/pricing` |
| Help Center / FAQ | `/help` | `src/screens/public/HelpScreen.tsx` | **PASS** — renders; real module list; **no Fish**; crops/marketplace labelled roadmap; support + Ask-ARIA CTAs |
| Support | (folded into `/help` + existing `/contact`) | Help "Still stuck?" section → `support@greena.app` + `/contact` | **PASS** |

Wiring:
- Footer: added **Legal** column (Privacy, Terms) + **Help Center** under Resources — `src/layouts/MarketingLayout.tsx`.
- Signup consent: "By creating an account you agree to our Terms / Privacy" — `src/screens/auth/SignUpScreen.tsx`.
- Shared building blocks — `src/screens/public/legalPrimitives.tsx`.

---

## 3. H3 — SEO & crawl foundation

| Asset | Implementation | Verification |
|-------|----------------|--------------|
| robots.txt | `frontend/public/robots.txt` | **PASS** — served at `/robots.txt`; allows public marketing paths, disallows app/auth areas, references sitemap |
| sitemap.xml | `frontend/public/sitemap.xml` | **PASS** — served at `/sitemap.xml`; 11 public URLs; app routes excluded |
| Canonical URLs | `index.html` (site) + `useSeo` (per route) | **PASS** — `<link rel=canonical>` set per route |
| Open Graph | `index.html` upgraded: `og:site_name`, `og:url`, absolute `og:image`, `og:locale` + per-route `og:title/description` | **PASS** (static head verified in source; per-route via `useSeo`) |
| Twitter/X card | `index.html` `summary_large_image` + per-route | **PASS** |
| JSON-LD | `index.html` — `Organization` + `SoftwareApplication` (KES offer, no unavailable modules) | **PASS** — valid JSON, accurate, **no Fish** |
| Titles / descriptions | `useSeo` applied to all 10 public pages | **PASS** — verified in browser (e.g. "Help Center · Greena") |

**SEO caveats (honest):** This is a client-rendered SPA (no SSR). Google renders JS and will read per-route tags; **non-JS social scrapers read only the static `index.html` head**, so per-route social cards need SSR/prerender to be perfect — the site-level OG/Twitter defaults cover the common case. All canonical/OG/sitemap URLs use the intended domain `https://greena.app` (configurable via `VITE_SITE_URL`); indexing is additionally gated by **LC-B1** (SSO) and the unpurchased domain.

---

## 4. Tests run

| Command | Result |
|---------|--------|
| `npx tsc --noEmit` (frontend) | **2 errors — both pre-existing**, in `src/screens/rabbit/RabbitBreedingScreen.tsx` + `RabbitHealthScreen.tsx` (untouched by this work; `git diff` on `src/screens/rabbit/` is empty). **0 errors in changed files.** |
| `npx vite build` | **PASS** — built in 41.5s; PWA precache 269 entries; only the pre-existing >500kB chunk-size advisory. |
| `npm run lint` | **BROKEN AT BASELINE (pre-existing)** — ESLint v9.39.4 installed but no `eslint.config.js`; the script still uses the removed v8 `--ext` flag. Fails before evaluating any file. Flagged, not fixed (out of scope). |
| Browser render check (dev server) | **PASS** — `/privacy`, `/help` render; `useSeo` updates titles; **no console errors**; `/robots.txt` + `/sitemap.xml` served. |

---

## 5. Production tests
Not yet run against production for H1/H3 — **changes are not deployed** (see §7). Endpoints/pages will be re-verified from production after deployment.

---

## 6. Remaining launch blockers (genuine)
- **LC-B1 (HIGH):** Vercel deployment protection — site is private. Owner decision needed.
- **H1-legal (HIGH → mitigated):** Privacy/Terms now exist but are **templates pending legal review**.
- **LC-B2 (MEDIUM):** Render cold start ~67s.
- **Pre-existing (MEDIUM):** frontend lint tooling broken (ESLint 9 flat-config migration); 2 pre-existing rabbit type errors.

## 7. Files changed
**New:** `frontend/src/lib/site.ts`, `frontend/src/hooks/useSeo.ts`, `frontend/src/screens/public/legalPrimitives.tsx`, `PrivacyScreen.tsx`, `TermsScreen.tsx`, `HelpScreen.tsx`, `frontend/public/robots.txt`, `frontend/public/sitemap.xml`, this report.
**Modified:** `frontend/index.html`, `frontend/src/routes/index.tsx`, `frontend/src/layouts/MarketingLayout.tsx`, `frontend/src/screens/auth/SignUpScreen.tsx`, and `useSeo` added to `Home/Features/Solutions/Aria/Pricing/Learning/About/Contact` screens.

## 8. Commits / deployments
- Commits on `phase-2-auth`: `7a2aaea` (legal/SEO/install), `be7b1ca` (PWA report doc).
- **Deployed to Vercel production** via `vercel --prod`: deployment `dpl_5vYjP9LjzJ99nneivSuFSAWedeaa`, `readyState: READY`, aliased to **`https://agrioskenya.vercel.app`**.
- Production verification (public / logged-out via curl, no Vercel cookies): `/`, `/install`, `/privacy`, `/terms`, `/help`, `/robots.txt`, `/sitemap.xml`, `/manifest.webmanifest` → **all 200**. Production manifest shows the broadened description + `maskable-512`; head carries JSON-LD `SoftwareApplication`, canonical, `og:site_name`, `twitter:card`; title "Greena — the farm operating system". Greena API still returns **401** on a guarded route (auth intact); raw deployment URL still **302** (preview protection intact).

### Correction to LC-B1 (SSO)
The earlier "site is not public" finding was **incomplete**: I had only tested the generated deployment URLs (`*-hash-*.vercel.app`), which are SSO-protected. The **production alias `agrioskenya.vercel.app` is and was publicly reachable (200)**. Vercel's protection here covers deployment/preview URLs only, not the assigned production alias — so the public-access goal is already met and **no protection setting was changed** (changing it was unnecessary and would have weakened preview isolation). Remaining note: the production alias is the old AGRIOS-era subdomain `agrioskenya.vercel.app`; canonical/OG/sitemap point at the intended `greena.app` (not yet purchased). Set `VITE_SITE_URL` to the real public origin, or finish the domain, before submitting to Search Console.

## 9. Next recommended phase
Domain acquisition + `VITE_SITE_URL`/canonical alignment (so SEO points at the real public origin), Render paid plan to kill the ~67s cold start, then Phase C marketing-page depth or Phase D auth runtime verification.
