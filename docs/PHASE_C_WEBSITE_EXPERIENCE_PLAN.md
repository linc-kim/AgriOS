# Greena Website — Interactive Experience Plan (for approval)

**Date:** 2026-08-14 · **Status:** PLAN — no code written yet, pending owner approval of the open decisions in §11.
**Scope:** rebuild the public marketing site into a scroll-driven, brand-led experience that makes a farmer *experience* Greena, without breaking the app, and with motion that serves comprehension over spectacle.

---

## 1. Principles (non-negotiable)
- **Honest to the code.** Advertise only shipped capabilities. **No Fish/Aquaculture** (excluded per owner). No fabricated features.
- **Motion serves meaning.** Every animation must aid comprehension, brand, storytelling, or demonstrate a real capability — otherwise it's cut.
- **Performance is a feature.** Fast, mobile-first, stable on low-end devices, `prefers-reduced-motion` respected, heavy visuals lazy-loaded with fallbacks. Critical text/nav never depend on animation.
- **Reuse over rebuild.** Use existing brand SVGs, the `motion` library already installed, and the existing `Reveal`/`Stagger`/`AriaMark` primitives. Don't break auth, payments, ARIA, routes, or SEO.

## 2. Ground truth (verified this session)
- **Enterprises that actually ship (7):** Poultry · Ornamental Birds (Aviculture) · Black Soldier Fly (BSF) · Rabbits · Goats · Sheep · Pigs (Swine). **Fish: excluded.**
- **Core modules:** Flocks/Livestock, Feed, Health, Inventory & Assets, Finance, Reports, Automation, ARIA, Production/Analytics.
- **Pricing (source of truth = DB catalog, migration 088):** Free 0 · Starter 999 · Pro **1,499** · Farm Pro 2,499 · Enterprise custom (KES/mo). **21-day Professional trial** + a real **Free tier** (per owner: match website to code).
- **Assets:** `src/assets/brand/` — `greena-emblem(.white).svg`, `greena-lockup(-stacked/-white).svg`, `greena-wordmark.svg`; `public/brand/aria/` — full ARIA mark set (SVG + PNG). Animated `components/brand/AriaMark.tsx`. `components/marketing/{primitives,LineWaves}.tsx` (`Reveal`, `Stagger`, `GlowField`).
- **Motion stack:** `motion@^12` (framer-motion successor: `useScroll`, `useTransform`, `useReducedMotion`, `motion.*`). **No** `three`/`@react-three` installed.

## 3. Motion system (built on real assets)
A small, centralized system so motion is consistent and cuttable:
- **`src/lib/motion.ts`** — tokens: durations (fast 0.2 / base 0.4 / slow 0.7s), easings (standard, entrance, emphasized), scroll ranges. One place to tune or disable.
- **Reduced-motion:** a single `useReducedMotion()` gate (already used in `Reveal`). When set: no parallax, no scroll-scrub, no autoplay — content appears immediately in final state. This is the default fallback, not an afterthought.
- **Scroll infra:** `useScroll`/`useTransform` from `motion`; a `<ScrollScene>` wrapper that maps scroll progress → transform/opacity **only** (GPU-friendly; never animate layout properties). IntersectionObserver to mount/unmount expensive scenes.
- **Reusable pieces (extend existing):** `Reveal`, `Stagger` (keep), add `Parallax`, `ScrollScene`, `CountUp` (for the dashboard numbers), `Typewriter` (ARIA demo), `EnterpriseSwitcher`.
- **Brand motion:** promote the real emblem into an animated hero mark (reuse `AriaMark` patterns); logo used in header, hero, footer, mobile nav, and route/section transitions — real SVG, never distorted/recolored.

## 4. Narrative (scroll-driven, Fish removed)
Primary interaction = **scroll → response → reveal → next**. Each beat is a section:

1. **Hero — "Run your farm on numbers, not memory."** Real Greena emblem; subtle scroll-reactive brand mark; CTA "Start your 21-day free trial." (Poultry may lead as the flagship example, but copy positions Greena as a **multi-enterprise** platform.)
2. **The farm / the problem.** Scattered records (books, phones, spreadsheets) — visualized as drift/scatter that the scroll begins to organize.
3. **Greena enters.** The scatter snaps into one structured system.
4. **The farm becomes visible.** A dashboard *builds* on scroll — live counts, survival, FCR, profit (CountUp tied to scroll).
5. **Enterprise modules.** Interactive **EnterpriseSwitcher** across the 7 real enterprises; each shows its real capabilities. No Fish.
6. **ARIA.** A live-feel demo: type a record → ARIA logs it → ask a question → insight (Typewriter/step reveal). Uses the real ARIA mark. No live Gemini call on the marketing page (deterministic scripted demo).
7. **Records → decisions.** Raw records visibly transform into calculations → insights → recommendations.
8. **Operations.** "What needs you today" surfaces as the farmer scrolls.
9. **Growth.** The system gets more valuable as the farm gets more complex (limits/plans hinted).
10. **Pricing + Conversion.** Real catalog (see §6); end on **"Start your 21-day free trial."**

## 5. Where 3D earns its place — recommendation
**Default: no global WebGL.** The farm-coming-alive and dashboard-building beats are achievable with layered **SVG/DOM + `motion`** at a fraction of the weight and with trivial reduced-motion fallbacks.
- **Candidate for `three`/`@react-three/fiber`:** at most **one** optional hero or "enterprises" scene (e.g., a slowly rotating stylized farm/enterprise object) — **lazy-loaded**, behind an IntersectionObserver, with a static SVG poster fallback and full `prefers-reduced-motion`/no-WebGL bail-out. I recommend **building the whole site first without 3D**, then adding this one scene only if it demonstrably raises comprehension/brand — an explicit go/no-go after Phase 3.

## 6. Pricing correction (resolves audit finding C2)
- Centralize plan display in **`src/lib/pricing.ts`** (or fetch `/billing/plans`) so marketing, pricing page, and checkout can't drift.
- Correct the hardcoded numbers to the catalog: **Free 0 / Starter 999 / Pro 1,499 / Farm Pro 2,499 / Enterprise custom**, with the real per-plan limits.
- Messaging: keep the **Free tier** and a **21-day Professional trial** (matches code). Remove "billed monthly, cancel whenever" claims not backed by logic; state what the app actually does.
- **This is a fast, high-value fix and can ship first, independent of the visual rebuild.**

## 7. Branding
Replace the placeholder "G" box in `MarketingLayout` with the real **emblem/lockup** SVG. Logo in header, hero, footer, mobile nav, and tasteful section/loading transitions. Never distort, stretch, recolor, or redesign it. ARIA sections use the real ARIA mark.

## 8. Performance budget
- Animate **transform/opacity only**; no layout thrash. `content-visibility`/IntersectionObserver for off-screen scenes.
- Lazy-load any heavy scene (and all of `three` if used) via dynamic import; poster/fallback first.
- Mobile: lighter motion, no scroll-scrub jank; test on a throttled profile.
- Targets: keep marketing route JS lean (3D, if added, in its own async chunk); LCP text/hero not blocked by animation.

## 9. Accessibility
Semantic headings per section, keyboard-navigable controls (EnterpriseSwitcher as real tablist/buttons), visible focus, no information conveyed by motion/color alone, `prefers-reduced-motion` gives the full content statically. Screen-reader order independent of scroll effects.

## 10. Build phases (incremental, each verified + non-breaking)
- **P0 — Pricing fix (C2):** correct + centralize pricing; ship. *(Small, immediate.)*
- **P1 — Motion system + real logo:** `lib/motion.ts`, `ScrollScene`/`Parallax`/`CountUp`, swap Wordmark → real emblem. No content change yet.
- **P2 — Hero + narrative beats 1–4** (problem → Greena enters → dashboard builds).
- **P3 — Enterprise switcher (7) + ARIA demo (beats 5–6).**
- **P4 — Records→decisions, operations, growth (beats 7–9).**
- **P5 — Pricing/conversion polish (beat 10).**
- **P6 — Optional single 3D scene** (go/no-go).
- **P7 — Verify** (build, browser render, console clean, Lighthouse/perf, reduced-motion, mobile, a11y) → deploy → production re-verify.

Each phase: build → local browser verify → commit → deploy → production check; nothing merged that breaks auth/payments/ARIA/routes/SEO.

## 11. Open decisions for owner (approve to start)
1. **Start with P0 pricing fix now?** (Recommended — it's the launch-risk item and independent of the visual work.)
2. **3D:** approve the "build without 3D first, then one optional hero scene" approach, or explicitly want/don't-want WebGL?
3. **Pricing source:** live-fetch `/billing/plans` (always accurate, needs the endpoint public or a public variant) **or** a static `pricing.ts` mirroring the catalog (simple, but must be kept in sync)?
4. **Enterprise depth:** one unified "enterprises" section with a switcher (recommended for launch) vs a dedicated page per enterprise (more work, better SEO long-term).

---

*Nothing in this plan is built yet. On approval I'll start with P0 (pricing) + P1 (motion system + real logo), deploying and verifying each phase.*
