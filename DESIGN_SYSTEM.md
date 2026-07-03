# AGRIOS DESIGN SYSTEM

**Read `AGRIOS_MASTER_CONTEXT.md` first.** Every visual and interaction decision below traces back to one governing constraint: the primary user opens this product outdoors, on a mid-range Android phone, often in direct sunlight, at the start or end of a physical workday. If a design choice cannot survive that context, it does not belong in AGRIOS regardless of how it looks on a designer's monitor.

**Status:** Frozen for V1. Any change to color, typography, spacing, or component decisions requires an explicit override, documented as a new version of this file — never edited in place.

---

## 1. The Logo and What It Encodes

The AGRIOS wordmark is a dual-color composition on a near-white field: a botanical, leaf-like abstract symbol in deep forest green anchors the left side, and the word "AGRIOS" itself is rendered in two colors — forest green letters and deep navy letters, split deliberately within the same word.

**Why this split matters and must never be simplified away:** the green-to-navy split inside a single wordmark is the core brand statement — agriculture and operating system are not two separate ideas layered on top of each other, they are one word that cannot be separated into its parts. Every time a future designer is tempted to render the logo in a single color "for simplicity," this is the reasoning to weigh against that instinct: single-color versions exist and are correct *only* for dark backgrounds or low-contrast contexts (Section 7.4), never as a default simplification.

**Canonical brand colors, extracted directly from the logo SVG:**

| Token | HEX | Role |
|---|---|---|
| `--brand-green` | `#076524` | Primary — buttons, icons, active states |
| `--brand-navy` | `#063491` | Secondary — headers, data labels, OS-flavored elements |
| `--brand-sage` | `#BFE0C7` | Tint — backgrounds, chips, low-emphasis states |
| `--brand-white` | `#FDFDFD` | Canvas — logo background, card surfaces |

**Why this exact green, and not a standard Tailwind green:** an early build used Tailwind's stock `#16a34a` as the brand green before the logo's actual color was properly extracted and reconciled. `#16a34a` is a brighter, more generic green; the true logo green, `#076524`, is deliberately darker and more desaturated — described in the design system's own words as reading "established and serious, not trendy," which matters because the brand's whole positioning depends on *not* looking like a flashy consumer app or a toy-bright startup product (Section 8). Any tailwind config, CSS variable file, or component library found still referencing `#16a34a` as `brand-600` is carrying forward a pre-correction value and should be updated to `#076524`.

**Logo usage rules, derived directly from the mark's own construction:**
- Minimum clear space on all four sides equals the height of the "A" letterform.
- Minimum size: 120px wide for the full wordmark + symbol; 32px for the symbol-only mark (below 32px, the wordmark's fine detail is lost, so the symbol alone must carry the brand).
- Approved backgrounds: near-white, deep forest green, deep navy, or near-black. Never place the logo on top of busy photography, never apply a drop shadow, never distort its proportions, never recolor individual letters independently of the system above.

---

## 2. Color System

### 2.1 Design principle: a structured two-axis palette

AGRIOS deliberately uses exactly two brand hues plus a hue-free neutral scale plus a semantic layer — never more. The **green axis** carries agriculture, health, and active/success states. The **navy axis** carries technology, data, and informational states. The **neutral axis** carries structure (text, borders, surfaces) with no brand coloring at all. The **semantic layer** (success, warning, error, info, critical) maps to universally understood conventions and always overrides brand color when the two would conflict — green is never used for an error state, red is never used for a success state, no matter how tempting a particular screen's palette might make that swap look.

Both the green and navy scales are generated from their single canonical hex value using consistent luminosity steps (50 through 900), which guarantees predictable, testable contrast ratios at every step rather than ad hoc per-screen color picking.

### 2.2 Core scales (reference — full CSS custom property block lives in the codebase's global stylesheet)

**Green** (from `#076524`): `50` `#F0FAF4` → `600` `#076524` (brand primary, buttons/active nav/key icons) → `900` `#022B11`.
**Navy** (from `#063491`): `50` `#EEF2FF` → `600` `#063491` (brand secondary, headers/data labels/badges) → `900` `#02153E`.
**Neutral (gray)**: `50` `#FAFAFA` (default light-mode page background) → `900` `#18181B` (maximum-contrast text). **Pure white (`#FFFFFF`) is never the page background** — it is reserved for card/surface elements, because a pure-white canvas reads as visually unfinished against the intentional warmth of the gray-50 base.

**Semantic colors** (override brand color in context, always): Success `#076524`, Warning `#D97706`, Error `#DC2626`, Info `#063491`, Critical `#7C3AED` (reserved specifically for mass-mortality events and platform-wide emergencies — a distinct fifth tier above ordinary "error," because a single sick bird and a mass die-off are not the same severity of event and should never share a visual treatment).

### 2.3 Usage rules

Primary green is reserved for the single most important action on any given screen — never more than one green-filled button per screen. Navy is for secondary actions, data labels, and anything that should read as "system" rather than "action." **Green and navy are never used as fills on the same button in the same row** — this rule exists to prevent exactly the kind of two-competing-CTAs-of-equal-visual-weight problem that undermines the "one interaction per moment" component philosophy (Section 5.1). A maximum of three colors should be visible on any single card: brand, semantic, neutral — never more, or the card stops communicating hierarchy and starts communicating noise.

All brand/semantic pairings are verified against WCAG AA at minimum (most pairings in the system clear AAA, 7:1 or higher) — this is not a nice-to-have, given the outdoor, high-glare usage context described at the top of this document; a contrast ratio that merely passes on a lab monitor may still fail in direct Kenyan sunlight, so the system deliberately targets ratios well above the legal minimum wherever practical.

---

## 3. Typography

### 3.1 Governing principle: legibility over style, structure over decoration

The type system has to work at both ends of the actual user spectrum: a smallholder farmer checking mortality counts on a cracked screen at 6am, and an enterprise operations manager reviewing a P&L dashboard on a 27" monitor. Every typographic decision below is checked against both.

### 3.2 The two type families and why each was chosen

- **Inter** (400/500/600/700) — all UI text: headings, body, labels, navigation, buttons. Chosen specifically for screen legibility, excellent numeral rendering, and because it remains highly legible from 12px up through 48px without needing a second "display" typeface.
- **JetBrains Mono** (400/500) — reserved exclusively for numeric dashboard metrics, financial figures, data table numbers, and IDs. The reasoning is not aesthetic preference: monospace digits align perfectly in columns, and using a visually distinct typeface for numbers signals to the user, at a glance and without reading, "this is a number that matters" versus ordinary prose. A stat headline, a table's numeric column, and a delta badge should always be JetBrains Mono; a table's text column should always be Inter. Mixing this up — rendering a financial figure in Inter, or a paragraph in JetBrains Mono — breaks the signal this pairing exists to send.

### 3.3 Mobile-specific typography rules (non-negotiable)

Body copy is never rendered below 14px on mobile. H1 caps at 24px on mobile (not the desktop 30px). Line height increases slightly on mobile body text specifically to aid outdoor, variable-light reading. Stat numbers stay at their full desktop size (30px, `text-3xl`) even on mobile — they are the entire point of the screen they appear on, and shrinking them to "fit" would defeat their purpose. Font weight prefers 600 over 700 on mobile to avoid ink-heavy rendering on budget-device screens.

### 3.4 Swahili/English parity

AGRIOS ships in English and Swahili with runtime switching (no reload). Swahili words typically run 15–20% longer than their English equivalents, so every component must be designed with text overflow in mind from the start rather than retrofitted after Swahili strings are added — `truncate` is only acceptable where a `title` tooltip is also provided, and navigation labels must be tested at 12px in **both** languages before a screen is considered complete, not just in English.

---

## 4. Spacing System

**Base unit: 4px. Every margin, padding, gap, and dimension in the system is a multiple of 4 — no exceptions.** This single rule is what makes the entire visual system feel coherent across dozens of independently-built screens; a one-off 15px or 22px value anywhere in the codebase is a deviation from the system, not a stylistic choice, and should be treated as a defect.

Touch targets are governed as an "Engineering Constitution" concern, not a mere style preference, because they directly affect whether a farmer can reliably operate the app one-handed in the field: primary action buttons minimum 48×48px (preferred 56×48px), navigation tabs 48×64px, list items minimum 48px height, icon buttons minimum 44×44px. These minimums should never be reduced to fit more content on a screen — if content does not fit at the minimum touch target size, the correct fix is to restructure the layout, not to shrink the tappable area.

---

## 5. Component Design Language

### 5.1 The three governing rules

1. **Function first.** A visual decision earns its place only if it aids comprehension or enables action; decoration exists only in service of function, never for its own sake.
2. **One interaction per moment.** Never present two equal-weight actions simultaneously — there must always be a clear primary action and everything else subordinate to it (see the green/navy same-row rule, Section 2.3).
3. **Offline resilience.** Every component must render usefully with stale or missing data. An empty state is a transition, not an error — it should tell the user what will appear there once data exists, not simply say "nothing here."

### 5.2 Buttons

Border radius is 8px on every button, system-wide, no exceptions. Primary buttons are filled `green-600`; secondary buttons are white with a `navy-600` border and text; ghost buttons are for tertiary/cancel actions only; danger buttons (`#DC2626` fill) are reserved for destructive actions like delete or revoke. Loading state replaces the label with a spinner and disables pointer events — a button must never show a spinner and its label text simultaneously, since that communicates two contradictory states at once. Full-width buttons are a mobile-only pattern for primary CTAs; a full-width button on desktop is a signal the layout has not been properly adapted for the larger viewport.

### 5.3 Cards — four variants, each with a distinct job

- **Standard Card** — white/gray-800 surface, 12px radius, a genuinely subtle shadow (`0 1px 3px rgba(0,0,0,0.06)`) that reads as a slight lift, not a floating panel.
- **Stat Card** — a Standard Card plus a 4px color-coded left border (green for positive metrics, error-red for negative/alert metrics, warning-amber for caution) — the border color is a farmer's fastest possible read of "is this good or bad" before they've processed a single number.
- **Alert Card** — semantic-light background with a matching border and left icon; reserved for disease alerts, feed shortfall warnings, mortality spikes — genuinely urgent, actionable content only.
- **Module Card (species)** — a 4px top border in a module's accent color (Section 9), used when switching between Poultry OS and any future species module.

### 5.4 Data tables (Admin Dashboard only)

Farmers see cards; admins see rows — this distinction is deliberate and appears throughout the system (Section 6.2). Header rows use a light gray background with uppercase, letter-spaced, small text; number columns are right-aligned and set in JetBrains Mono; text columns are left-aligned Inter; no vertical borders (horizontal only) to reduce visual noise; pagination is skipped entirely for tables under 50 rows, since pagination controls add cognitive overhead with no benefit at that scale, and an export (CSV) button is always present because admin users are expected to export data as a matter of course.

### 5.5 Charts

Recharts is the exclusive charting library. Color assignments are fixed and consistent across every chart in the product: primary metric always `#076524`, comparison/secondary series always `#063491`, mortality/negative always `#DC2626`, target/forecast always `#D97706`. A chart must always show axis labels — a chart whose unit is ambiguous is treated as a defect, not a minor omission. Bar charts always use a zero baseline; truncating the Y-axis on a bar chart is prohibited because it visually exaggerates differences in a way that misleads a farmer making a real decision about their flock or finances.

---

## 6. Dashboard Design Language

### 6.1 The Farmer Dashboard's three-question test

Every element on the farmer home dashboard exists to answer one of exactly three questions, in under five seconds, without requiring the farmer to read a paragraph: *Is my flock alive and healthy? Did something happen yesterday I need to know? What do I need to do today?* The Health Banner is the highest-priority element on the screen for exactly this reason — it is always the first thing below the top bar, full-width, minimum 64px, and rendered in the semantic color matching the flock's current status. A maximum of two alert banners may be visible at once; if more exist, the UI shows "2 more alerts →" rather than stacking additional banners, because a screen that visually screams at the user trains them to stop paying attention to any of it (alert fatigue is treated as a design failure, not a content problem). **There are deliberately no charts on the farmer home screen** — stat cards use large JetBrains Mono numbers instead, because raw numbers are faster to parse than a tiny sparkline on a small phone screen; charts belong on the Finance tab and dedicated reporting screens, where the user has already signaled analytical intent by navigating there.

### 6.2 The Admin Dashboard's opposite governing feel

Where the Farmer Dashboard is simple, actionable, and sparse, the Admin Dashboard is deliberately powerful, data-rich, and comfortable with density — because its single user (`super_admin`, and eventually `platform_admin` staff) is not a time-pressured field worker but someone actively doing platform operations work at a desk. The Daily Active Loggers percentage (`AGRIOS_MASTER_CONTEXT.md` Section 5.2) is the hero metric on every admin screen, rendered at 36px JetBrains Mono, because it is the one number that predicts everything else about the business's health. The side navigation is rendered in the deepest navy in the entire palette (`#02153E`) specifically because that shade should feel like *infrastructure*, not *product* — reinforcing, purely through color, that the admin surface is a different kind of tool than the farmer-facing app, even though both are built from the same underlying component system.

---

## 7. Light Mode and Dark Mode

### 7.1 Why light mode is the default, and why dark mode is not an afterthought

Light mode is the default specifically because the primary users work outdoors in bright Kenyan sunlight, where light-mode contrast is dramatically easier to read than dark-mode contrast. This is a survival-context decision, not a taste preference. Dark mode is still built as a complete, first-class experience — following the `prefers-color-scheme` media query with a manual override available in Settings — because enterprise/desk users (admins, future enterprise-tier customers) legitimately prefer it, but it is treated as a preference feature for that audience, never as the primary experience the product is designed around.

### 7.2 What changes between modes, and what deliberately does not

Backgrounds, text, and border tokens fully re-map between light and dark (see the CSS custom property reference in the codebase's global stylesheet for the complete token table). Brand colors are *lightened* rather than reused unchanged in dark mode — for example `brand-primary` becomes `#3FAB6C` rather than the light-mode `#076524` — because the deep forest green that reads as rich and professional against a white background would have insufficient contrast against a near-black one. Semantic colors follow the same lightening logic. **The one thing that deliberately does not change**: the Admin sidebar stays navy-900 in both light and dark mode, because that navigation surface is meant to always read as "system," independent of the user's local light/dark preference for their own content area.

---

## 8. Brand Personality

### 8.1 The one-line promise

> **AGRIOS is the trusted agronomist in your pocket.**

Not a flashy consumer app, not a government portal, not a generic SaaS business tool. This framing exists to give every future copywriter and designer a single test: would a trusted, competent agronomist say this, in this tone, at this moment? If not, revise it.

### 8.2 Four adjectives that define every piece of copy

**Clear** — never clever when clear would do; if a sentence needs a second read, rewrite it. **Confident** — AGRIOS states facts rather than hedging ("3 birds showed abnormal behavior yesterday," never "it appears some birds may possibly have had some issues"). **Respectful** — the farmer knows their farm, AGRIOS knows data, and the product never talks down to them. **Practical** — every message ends with something actionable; information without a next step is treated as noise, not content.

### 8.3 Writing principles worth internalizing

Lead with the fact, end with the action. Numbers are always digits, never spelled out — digits scan faster. Use the farmer's own vocabulary ("flock," not "poultry population"; "feed," not "nutritional input"; "sick bird," not "morbidity event"). Alerts are read in about two seconds and are capped around twelve words for that reason. ARIA in particular speaks like a knowledgeable colleague, never a chatbot — no "Sure! I'd be happy to help you with that!" preambles, just the answer (see `ARIA_AI.md` for the full voice specification).

### 8.4 Five design principles

**Clarity over cleverness** — a farmer reading their mortality rate at 6am should never need to interpret a visualization; numbers and clear labels, always. **Data tells the story** — the UI does not celebrate the farmer; it surfaces what the farm is actually doing and lets real results create pride, getting out of the way rather than performing enthusiasm. **Mobile is the promise** — every interaction is designed assuming a cracked screen, 3G, a dirty display, and a user who has been working since 4am. **African by design, global by scale** — Swahili support, SMS as the primary notification channel, and offline-aware architecture are not localizations bolted onto a Western SaaS product; they are foundational, because the product is built for this context first, not adapted to it after the fact. **Alerts earn attention** — every alert must be either something the farmer must know today or something that will cost them money if ignored; nothing else qualifies, because alert fatigue is the fastest way to make a farmer stop trusting (and therefore stop opening) the app.

---

## 9. Module Expansion Strategy

The design system is deliberately built as a **chassis**, with each future agricultural module (Rabbit OS, Dairy OS, Fish OS, Crop OS, Enterprise Suite) as an **engine variant** riding on top of it. Activating a new module should require, on the design side: zero changes to the color system, zero changes to typography, zero changes to the core component library, one new module accent color drawn from the pre-defined module palette (Rabbit = warm amber `#D97706`, Dairy = sky blue `#0284C7`, Fish = teal `#0D9488`, Crop = earth brown `#92400E`, Enterprise = royal purple `#7C3AED`), and one new set of species-specific screens built from existing components. The module accent color supplements the two brand hues — it never replaces primary green or secondary navy anywhere in the system, and it is used only for a module's chip, its card's top border, and its navigation indicator when active — never for a primary action's fill color. This constraint exists so that a future module can be visually distinguished from Poultry OS without the product ever feeling like it has multiple, competing brand identities stitched together.

If a future module genuinely requires a component the existing system does not have (a breeding-cycle calendar for Rabbit OS, a lactation-curve chart for Dairy OS), that new component must still use the existing spacing tokens, existing typography scale, and existing card structure, and must be documented in this file as a formal addendum before being built — it is an extension of this system, never a parallel one.
