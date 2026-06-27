# AGRIOS Brand Guidelines & Design System v1
**Status: OFFICIAL — Frozen for V1 Development**
**Authority: Supersedes all prior color, typography, or component decisions**
**Date: 2026-06-24**

---

## Table of Contents

1. [Logo Analysis](#1-logo-analysis)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Spacing System](#4-spacing-system)
5. [Component Design Language](#5-component-design-language)
6. [Dashboard Design Language](#6-dashboard-design-language)
7. [Light Mode & Dark Mode](#7-light-mode--dark-mode)
8. [Brand Personality](#8-brand-personality)
9. [Module Expansion Strategy](#9-module-expansion-strategy)

---

## 1. Logo Analysis

### 1.1 Structural Composition

The AGRIOS logo is a **dual-color wordmark** rendered on a near-white field (`#FDFDFD`). It contains two primary visual systems operating in concert:

**System A — The Botanical Symbol (left anchor)**
A large, complex organic form constructed entirely in deep forest green. The shape evokes a leaf unfurling, a seedling emerging from soil, or a plant in active growth. Its path is asymmetric — wider at base, curving and tapering upward — suggesting natural growth momentum rather than static illustration. This is not a literal depiction of a plant. It is an abstraction of agricultural life: the idea that AGRIOS is where living systems are managed.

**System B — The Wordmark (right field)**
The letters of "AGRIOS" are rendered in two colors with deliberate intent:

- Letters in **Forest Green** (`#076524` and variants): Carry the agricultural dimension — earth, crop, growth, life.
- Letters in **Navy Blue** (`#063491` and variants): Carry the technological dimension — intelligence, operating system, data, trust.

The green-to-blue color split within the wordmark is the core brand statement: **AGRIOS is where agriculture meets operating system**. The two cannot be separated.

**Counter Forms (white interiors):** Letter counters are rendered in near-white (`#FCFCFC`, `#F9FBFA`), creating clean apertures in the letterforms. This signals precision and modernity — the type is not decorative but functional.

**Mid-tones (transitional greens):** A secondary register of medium greens (`#276E3E`, `#267643`, `#23723B`) appears at letterform edges and transitions, functioning as ambient depth — the logo has subtle dimensionality without using gradients. This is a mark of quality craft.

**Accent mints (light sage):** `#BFE0C7`, `#C5E0C9` — used as fine detail strokes or termination points. These are not primary colors but confirm a mint/sage adjacency in the brand spectrum.

### 1.2 Color Extraction

All colors sampled directly from the logo SVG:

| Role | HEX | Description |
|------|-----|-------------|
| Primary Forest Green | `#076524` | Main brand green. Agriculture, growth, life |
| Green Variant A | `#086525` | Practically identical to primary — same family |
| Green Variant B | `#095C23` | Slightly darker, cooler green |
| Green Variant C | `#096024` | Mid-forest green |
| Green Variant D | `#076023` | Near-identical to primary |
| Green Variant E | `#095B23` | Letter-form green |
| Primary Navy Blue | `#063491` | Main brand navy. Technology, OS, intelligence |
| Navy Variant A | `#053490` | Near-identical navy |
| Navy Variant B | `#073592` | Slightly warmer navy |
| Navy Variant C | `#05338F` | Slightly deeper navy |
| Navy Variant D | `#0B3792` | Most accessible navy variant |
| Medium Green | `#276E3E` | Transitional — shadows, depth |
| Medium Green B | `#277741` | Leaf mid-tones |
| Medium Green C | `#267643` | Letter edge detail |
| Medium Green D | `#23723B` | Accent depth |
| Medium Green E | `#1C6431` | Deepest mid-tone |
| Medium Navy | `#19449B` | Secondary blue — nav accents |
| Medium Navy B | `#173F96` | Secondary blue depth |
| Accent Sage | `#BFE0C7` | Light sage — UI backgrounds, soft states |
| Accent Sage B | `#C5E0C9` | Light sage variant |
| Near White | `#FDFDFD` | Background field |
| White Counter | `#FCFCFC` | Letter interior apertures |

**Canonical Brand Colors (simplified for production use):**

| Token | HEX | Use |
|-------|-----|-----|
| `--brand-green` | `#076524` | Primary — buttons, icons, active states |
| `--brand-navy` | `#063491` | Secondary — headers, data labels, OS elements |
| `--brand-sage` | `#BFE0C7` | Tint — backgrounds, chips, low-emphasis |
| `--brand-white` | `#FDFDFD` | Canvas — logo background, card surfaces |

### 1.3 Symbolism

| Element | Meaning |
|---------|---------|
| Forest Green | Agriculture, earth, growth, sustainability, life |
| Deep Navy | Technology, intelligence, operating system, trust, enterprise |
| Organic botanical form | The living system at the center of AGRIOS |
| Dual-color wordmark | Two worlds unified: farming + technology |
| Clean white counters | Precision, data clarity, modern design sensibility |
| Mid-tone depth | Craft, not cheapness — a brand built to last |

### 1.4 Brand Personality Signals from Logo

- **Not a startup**: The deep, desaturated green reads as established and serious, not trendy.
- **Not a government app**: The navy is technological, not bureaucratic.
- **Not a consumer app**: The color restraint and precision signals enterprise.
- **Specifically agricultural**: The botanical form is unmistakable — this is for people who grow things.
- **Globally legible**: The color pair (green + navy) has no cultural baggage — it works in Kenya, the EU, and Southeast Asia without reinterpretation.

### 1.5 Enterprise Readiness Assessment

| Criterion | Score | Notes |
|-----------|-------|-------|
| Color sophistication | Strong | Desaturated, professional — not toy-bright |
| Wordmark legibility | Strong | Clear letterforms at small sizes |
| Dual-color discipline | Strong | Two-color maximum — scales to one-color emboss |
| Botanical icon | Strong | Memorable, unique, category-relevant |
| White space use | Strong | Clean apertures signal premium |

### 1.6 Limitations & Mitigations

| Limitation | Mitigation |
|-----------|-----------|
| Two-color logo difficult on dark backgrounds | Provide single-color white version for dark contexts |
| Botanical symbol may lose detail below 32px | Use icon-only mark (symbol without wordmark) at small sizes |
| Navy and green may clash at low contrast | Always maintain minimum 4.5:1 contrast against backgrounds |
| Complex SVG path = slow raster at edge cases | Provide PNG exports at 1x, 2x, 3x for all contexts |

### 1.7 Logo Usage Rules (Derived from Mark)

1. **Clear space**: Minimum clear space = height of the "A" letterform on all four sides.
2. **Minimum size**: 120px wide for wordmark + symbol. 32px for symbol-only mark.
3. **Approved backgrounds**: White (`#FDFDFD`, `#FFFFFF`), Deep Forest Green (`#076524`), Deep Navy (`#063491`), Near-Black (`#0A0A0B`).
4. **Prohibited**: Do not place logo on busy photography. Do not apply drop shadows. Do not distort proportions. Do not recolor individual letters.
5. **Dark background**: Use white (`#FFFFFF`) single-color version.
6. **On Green background**: Use white or navy version.
7. **On Navy background**: Use white or green version.

---

## 2. Color System

### 2.1 Design Principle

AGRIOS uses a **structured two-axis palette** derived directly from the logo:

- **Green Axis**: Agriculture, nature, health, success, active states.
- **Navy Axis**: Technology, intelligence, data, links, informational states.
- **Neutral Axis**: Structure, text, borders, surfaces — no brand hue.
- **Semantic Layer**: Warning, Error, Info mapped to universally understood conventions.

All tints and shades are generated from the two canonical brand colors using consistent luminosity steps, ensuring predictable contrast ratios at each scale level.

### 2.2 Green Scale (Primary)

Derived from `#076524`.

| Token | HEX | Tailwind-equivalent | Use |
|-------|-----|---------------------|-----|
| `green-50` | `#F0FAF4` | — | Page backgrounds, subtle tints |
| `green-100` | `#D1F0DC` | — | Hover states on light surfaces |
| `green-200` | `#A8E0BB` | — | Disabled backgrounds |
| `green-300` | `#72C795` | — | Progress indicators, low emphasis |
| `green-400` | `#3FAB6C` | — | Secondary icons |
| `green-500` | `#1F8A4A` | — | Hover state for primary |
| `green-600` | `#076524` | ← **BRAND PRIMARY** | Buttons, active nav, key icons |
| `green-700` | `#055420` | — | Pressed state for primary |
| `green-800` | `#03401A` | — | Dark text on green tints |
| `green-900` | `#022B11` | — | Deepest shadows on green |

**Primary Button:** Background `green-600`, hover `green-500`, pressed `green-700`, text `#FFFFFF`.

### 2.3 Navy Scale (Secondary)

Derived from `#063491`.

| Token | HEX | Use |
|-------|-----|-----|
| `navy-50` | `#EEF2FF` | Info backgrounds, subtle callouts |
| `navy-100` | `#D1D9F7` | Selected states in data tables |
| `navy-200` | `#A8B7F0` | Disabled navy elements |
| `navy-300` | `#7090E4` | Low-emphasis navy |
| `navy-400` | `#4169D8` | Links, secondary CTAs |
| `navy-500` | `#2248C2` | Hover state for secondary |
| `navy-600` | `#063491` | ← **BRAND SECONDARY** | Headers, data labels, badges |
| `navy-700` | `#052A78` | Pressed state |
| `navy-800` | `#03205C` | Deep text on navy tints |
| `navy-900` | `#02153E` | Darkest navy — footer, overlay |

**Secondary Button:** Background `#FFFFFF`, border `navy-600`, text `navy-600`, hover background `navy-50`.

### 2.4 Neutral Scale

No hue — pure gray for structure.

| Token | HEX | Use |
|-------|-----|-----|
| `gray-50` | `#FAFAFA` | Page background (light mode) |
| `gray-100` | `#F4F4F5` | Card backgrounds, input fills |
| `gray-200` | `#E4E4E7` | Borders, dividers |
| `gray-300` | `#D1D1D6` | Disabled borders |
| `gray-400` | `#A1A1AA` | Placeholder text |
| `gray-500` | `#71717A` | Secondary/tertiary text |
| `gray-600` | `#52525B` | Body text (secondary) |
| `gray-700` | `#3F3F46` | Body text (primary, light mode) |
| `gray-800` | `#27272A` | Headings |
| `gray-900` | `#18181B` | Maximum contrast text |

### 2.5 Semantic Colors

These are platform-wide meaning conventions. They override brand color in context.

| Semantic Role | HEX | CSS Token | Use |
|--------------|-----|-----------|-----|
| Success | `#076524` | `--color-success` | Confirmations, healthy indicators |
| Success Light | `#D1F0DC` | `--color-success-light` | Success backgrounds |
| Warning | `#D97706` | `--color-warning` | Feed alerts, attention needed |
| Warning Light | `#FEF3C7` | `--color-warning-light` | Warning backgrounds |
| Error | `#DC2626` | `--color-error` | Disease alerts, failures, validation |
| Error Light | `#FEE2E2` | `--color-error-light` | Error backgrounds |
| Info | `#063491` | `--color-info` | ARIA responses, informational |
| Info Light | `#EEF2FF` | `--color-info-light` | Info backgrounds |
| Critical | `#7C3AED` | `--color-critical` | Mass mortality events, platform emergencies |
| Critical Light | `#EDE9FE` | `--color-critical-light` | Critical backgrounds |

### 2.6 Sage Accent

Derived from logo's `#BFE0C7`. Used for low-emphasis states, module tints, and soft UI backgrounds.

| Token | HEX | Use |
|-------|-----|-----|
| `sage-100` | `#E8F5ED` | Poultry module chip background |
| `sage-200` | `#C5E0C9` | Tag borders |
| `sage-300` | `#BFE0C7` | ← **LOGO SAGE** | Illustrated elements |
| `sage-400` | `#8FC89D` | Progress bar backgrounds |

### 2.7 Usage Rules

1. **Primary green** is always used for the single most important action on any screen.
2. **Navy blue** is used for secondary actions, data labels, and system/OS elements.
3. **Never use both green and navy as fills on the same button in the same row.**
4. **Semantic colors are non-negotiable** — do not use green for errors or red for success.
5. **Maximum 3 colors visible on any single card** — brand + semantic + neutral.
6. **Gray-50 is the default page background** in light mode. Never use pure white (`#FFFFFF`) as a page background — it reads as unfinished.

### 2.8 Contrast Requirements (WCAG AA)

| Foreground | Background | Ratio | Passes AA? |
|-----------|-----------|-------|-----------|
| `#076524` (green-600) | `#FFFFFF` | 7.2:1 | Yes (AAA) |
| `#063491` (navy-600) | `#FFFFFF` | 9.1:1 | Yes (AAA) |
| `#FFFFFF` | `#076524` | 7.2:1 | Yes (AAA) |
| `#FFFFFF` | `#063491` | 9.1:1 | Yes (AAA) |
| `#18181B` (gray-900) | `#FAFAFA` | 18.1:1 | Yes (AAA) |
| `#076524` | `#D1F0DC` | 5.3:1 | Yes (AA) |

---

## 3. Typography

### 3.1 Font Philosophy

AGRIOS serves users who may be:
- A smallholder farmer checking flock mortality on a cracked Android phone screen under direct sunlight.
- An enterprise operations manager reviewing P&L dashboards on a 27" monitor.

The typography system must work at both extremes. The governing principle: **legibility over style, structure over decoration**.

### 3.2 Type Families

**Primary: Inter**
- Source: Google Fonts (`https://fonts.google.com/specimen/Inter`)
- Weights used: 400 (Regular), 500 (Medium), 600 (SemiBold), 700 (Bold)
- Use: All UI text — headings, body, labels, navigation, buttons
- Rationale: Designed for screen legibility. Excellent number rendering. Variable font support (single file, smaller load). Widely considered the standard for professional SaaS products. Legible at 12px. Exceptional at 48px.

**Monospace: JetBrains Mono**
- Source: Google Fonts (`https://fonts.google.com/specimen/JetBrains+Mono`)
- Weights used: 400 (Regular), 500 (Medium)
- Use: Numeric dashboard metrics, financial figures, data tables, code/IDs
- Rationale: Monospace ensures numeric columns align perfectly. Numbers feel data-grade, not decorative. Distinguished from prose — user instantly knows "this is a number that matters."

**System Fallback Stack:**
```css
font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
```

### 3.3 Type Scale

Base: `16px`. Scale ratio: 1.25 (Major Third).

| Token | Size | Line Height | Weight | Use |
|-------|------|-------------|--------|-----|
| `text-xs` | 12px | 16px (1.33) | 400/500 | Timestamps, metadata, fine print |
| `text-sm` | 14px | 20px (1.43) | 400/500 | Secondary body, labels, captions |
| `text-base` | 16px | 24px (1.5) | 400 | Primary body copy |
| `text-lg` | 18px | 28px (1.56) | 500/600 | Subheadings, card titles |
| `text-xl` | 20px | 28px (1.4) | 600 | Section headers |
| `text-2xl` | 24px | 32px (1.33) | 600/700 | Page titles |
| `text-3xl` | 30px | 36px (1.2) | 700 | Dashboard hero numbers |
| `text-4xl` | 36px | 40px (1.11) | 700 | Major stat callouts |
| `text-5xl` | 48px | 52px (1.08) | 700 | Onboarding headlines |

### 3.4 Heading Hierarchy

| Level | Token | Weight | Use |
|-------|-------|--------|-----|
| H1 | `text-3xl` / 30px | Bold 700 | Page title (one per screen) |
| H2 | `text-2xl` / 24px | SemiBold 600 | Section headers |
| H3 | `text-xl` / 20px | SemiBold 600 | Card titles |
| H4 | `text-lg` / 18px | Medium 500 | Sub-section headers |
| H5 | `text-base` / 16px | Medium 500 | Inline labels |
| H6 | `text-sm` / 14px | Medium 500 | Fine labels |

### 3.5 Dashboard Typography

Dashboard screens carry high information density. Specific rules apply:

| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Stat headline (big number) | JetBrains Mono | 36px | Medium | `gray-900` (light) / `gray-50` (dark) |
| Stat label | Inter | 12px | Medium | `gray-500` |
| Stat change (delta) | JetBrains Mono | 14px | Medium | `green-600` (up) / `error` (down) |
| Table header | Inter | 12px | SemiBold 600 | `gray-500` |
| Table cell — text | Inter | 14px | Regular 400 | `gray-700` |
| Table cell — number | JetBrains Mono | 14px | Regular 400 | `gray-900` |
| Chart axis labels | Inter | 11px | Regular 400 | `gray-400` |
| Chart legend | Inter | 12px | Medium 500 | `gray-600` |
| Card title | Inter | 16px | SemiBold 600 | `gray-800` |
| Badge/chip text | Inter | 12px | SemiBold 600 | contextual |

### 3.6 Mobile Typography Rules

On mobile (< 768px), the following adjustments apply:

1. **Minimum readable size is 14px**. Never render body copy below 14px on mobile.
2. **H1 caps at 24px** on mobile — `text-3xl` becomes `text-2xl`.
3. **Line height increases by 2px** on mobile for body text — outdoor reading in variable light.
4. **Letter-spacing**: `0.01em` on body copy for sun-washed screen legibility.
5. **Stat numbers**: Stay at `text-3xl` (30px) even on mobile — they are the point.
6. **Font weight**: Prefer `600` over `700` on mobile — avoids ink-heavy rendering on budget screens.

### 3.7 Swahili & English Parity

AGRIOS ships in English (en) and Swahili (sw). Typography rules:

- Swahili words are typically 15–20% longer than English equivalents. Design components with text overflow in mind.
- Use `truncate` only where `title` tooltip is also provided.
- Navigation labels must fit at `text-xs` (12px) in both languages — test both.
- Never kern Swahili text differently from English — same font stack, same spacing.

---

## 4. Spacing System

### 4.1 Base Unit

**1 spacing unit = 4px.**

All margins, paddings, gaps, and sizes are multiples of 4. No exceptions.

### 4.2 Spacing Scale

| Token | px | Use |
|-------|----|----|
| `space-0` | 0px | Reset, collapse |
| `space-1` | 4px | Icon padding, tight chips |
| `space-2` | 8px | Icon-label gap, tight list items |
| `space-3` | 12px | Input internal padding (vertical) |
| `space-4` | 16px | Standard component padding, card content |
| `space-5` | 20px | List item padding, relaxed chips |
| `space-6` | 24px | Card padding, section gap |
| `space-8` | 32px | Section spacing on desktop |
| `space-10` | 40px | Hero section internal spacing |
| `space-12` | 48px | Minimum touch target height |
| `space-14` | 56px | Primary touch target / top bar height |
| `space-16` | 64px | Bottom navigation height / large gaps |
| `space-20` | 80px | Section divider on desktop |
| `space-24` | 96px | Hero padding |
| `space-32` | 128px | Max-width margin |

### 4.3 Grid System

**Mobile (< 768px):**
- Columns: 4
- Margin: 16px
- Gutter: 8px
- Max content width: 100%

**Tablet (768px – 1024px):**
- Columns: 8
- Margin: 24px
- Gutter: 16px
- Max content width: 100%

**Desktop (> 1024px):**
- Columns: 12
- Margin: 32px
- Gutter: 24px
- Max content width: 1280px (centered)

**Admin Dashboard (> 1280px):**
- Columns: 12
- Margin: 40px
- Gutter: 24px
- Max content width: 1440px

### 4.4 Layout Anatomy (Mobile App)

```
┌────────────────────────────────┐  ← Screen top
│  Top Bar                56px   │  Fixed. Farm name + bell icon.
├────────────────────────────────┤
│                                │
│  Scrollable Content            │  paddingTop: 56px, paddingBottom: 64px
│                                │
├────────────────────────────────┤
│  Bottom Navigation      64px   │  Fixed. 5 tabs.
└────────────────────────────────┘  ← Screen bottom
```

### 4.5 Component Spacing Standards

| Component | Padding | Gap between children |
|-----------|---------|---------------------|
| Card | 16px (mobile) / 24px (desktop) | 12px |
| Button (medium) | 12px vertical, 20px horizontal | — |
| Button (large) | 14px vertical, 24px horizontal | — |
| Input field | 12px vertical, 16px horizontal | — |
| List item (standard) | 16px vertical, 16px horizontal | — |
| List item (compact) | 10px vertical, 16px horizontal | — |
| Modal | 24px all sides | 16px |
| Toast notification | 12px vertical, 16px horizontal | 8px |
| Bottom sheet | 24px horizontal, 16px top | 12px |
| Stat card | 20px all sides | 8px |

### 4.6 Touch Target Rules (Engineering Constitution — immutable)

| Target type | Minimum size | Preferred size |
|-------------|-------------|----------------|
| Primary action (buttons) | 48×48px | 56×48px |
| Navigation tabs | 48×64px | — |
| List items | 48px height | 56px height |
| Icon buttons | 44×44px | 48×48px |
| Checkbox / Radio | 44×44px | — |
| Toggle switch | 44px height | — |

---

## 5. Component Design Language

### 5.1 Design Philosophy

AGRIOS components follow three governing rules:

1. **Function first.** Every visual decision must aid comprehension or enable action. Decoration exists only when it aids function.
2. **One interaction per moment.** Never present two equal-weight actions simultaneously. Always establish hierarchy.
3. **Offline resilience.** Components must render usefully with stale or missing data. Empty states are not errors — they are transitions.

### 5.2 Buttons

**Hierarchy:**

| Variant | Background | Border | Text | Use |
|---------|-----------|--------|------|-----|
| Primary | `green-600` | none | `#FFFFFF` | Single most important action per screen |
| Secondary | `#FFFFFF` | `navy-600` 1.5px | `navy-600` | Second-tier action |
| Ghost | transparent | `gray-300` 1px | `gray-700` | Tertiary / cancel actions |
| Danger | `error` (`#DC2626`) | none | `#FFFFFF` | Destructive — delete, revoke |
| Disabled | `gray-200` | none | `gray-400` | Inactive state |

**Sizes:**

| Size | Height | Font | Horizontal padding | Use |
|------|--------|------|--------------------|-----|
| Small | 32px | 14px / 500 | 12px | Inline, compact tables |
| Medium | 44px | 14px / 600 | 20px | Standard UI |
| Large | 56px | 16px / 600 | 24px | Primary mobile CTA |

**Rules:**
- Border radius: `8px` on all buttons.
- Icons in buttons: 16px, positioned left of label, 6px gap.
- Loading state: Replace label with spinner. Disable pointer events. Never show spinner and text simultaneously.
- Full-width buttons: Mobile primary actions only. Never on desktop.

### 5.3 Cards

AGRIOS uses **four card variants**:

**Standard Card**
```
Background: white (light) / gray-800 (dark)
Border: 1px gray-200 (light) / gray-700 (dark)
Border-radius: 12px
Padding: 16px (mobile) / 24px (desktop)
Shadow: 0 1px 3px rgba(0,0,0,0.06) — subtle lift, not a floating card
```

**Stat Card (dashboard)**
```
Same as Standard + color-coded left border:
- 4px left border in green-600 for positive metrics
- 4px left border in error for negative/alert metrics
- 4px left border in warning for caution metrics
Contains: Metric label (text-sm, gray-500), Big number (text-3xl, JetBrains Mono), Delta badge
```

**Alert Card**
```
Background: semantic-light (e.g., error-light for disease alerts)
Border: 1px semantic color
Border-radius: 10px
Left icon: 20px semantic icon
Use: Disease alerts, feed shortfall warnings, mortality spikes
```

**Module Card (species)**
```
Header band: 4px top border in module accent color
Title: Module name + species icon
Body: Key metric summary
Use: Switching between Poultry OS, Rabbit OS, etc.
```

### 5.4 Form Inputs

**Text Input:**
```
Height: 48px
Border: 1px gray-300 → green-600 (focus) → error (error state)
Border-radius: 8px
Background: white (light) / gray-800 (dark)
Padding: 12px 16px
Font: text-base, gray-900
Placeholder: gray-400
Label: text-sm (14px), gray-700, above input, 6px gap
Error message: text-sm, error color, below input, 4px gap
```

**Select / Dropdown:**
- Same dimensions as text input.
- Chevron icon (16px, gray-400) right-aligned.
- Options list: white background, `border-radius: 8px`, `shadow: 0 4px 16px rgba(0,0,0,0.12)`.
- Max visible options: 6. Scrollable beyond.

**Toggle Switch:**
```
Track: 48px × 28px, border-radius: 14px
Off state: gray-300 track, white thumb
On state: green-600 track, white thumb
Thumb: 24px diameter, shadow: 0 1px 3px rgba(0,0,0,0.2)
Touch target: 48×48px minimum wrapper
Transition: 150ms ease
```

**Numeric Keypad (PIN entry — already built):**
```
Key size: (screen width - 48px) / 3 per key
Key height: 64px
Font: text-2xl, Inter Bold
Background per key: gray-100 (light), gray-700 (dark)
Active state: scale(0.95), background gray-200
```

### 5.5 Data Tables

Tables are used in the Admin Dashboard. Rules:

**Structure:**
```
Header row: gray-50 background (light), gray-800 (dark)
Header text: text-xs, uppercase, letter-spacing: 0.05em, gray-500
Data rows: alternating white / gray-50 (light) or gray-900 / gray-800 (dark)
Row height: 52px
Border: 1px gray-200 bottom only (no vertical borders — reduces visual noise)
```

**Column types:**
- Text columns: left-aligned, text-sm Inter.
- Number columns: right-aligned, text-sm JetBrains Mono.
- Status columns: centered, semantic badge.
- Action columns: right-aligned, icon buttons only (no text labels in table rows).

**Pagination:**
- Show rows per page selector: [10, 25, 50].
- Page controls: Previous | 1 2 3 … n | Next.
- Never paginate on mobile — use infinite scroll or load-more.

### 5.6 Badges & Chips

**Status Badge:**
```
Height: 22px
Padding: 2px 8px
Border-radius: 99px (pill)
Font: text-xs, SemiBold 600
```

| Status | Background | Text |
|--------|-----------|------|
| Active / Healthy | `green-100` | `green-700` |
| Warning / Attention | `warning-light` | `#92400E` |
| Alert / Sick | `error-light` | `#991B1B` |
| Inactive | `gray-100` | `gray-500` |
| Critical | `critical-light` | `#5B21B6` |

**Module Chip (species tag):**
```
Height: 24px
Padding: 4px 10px
Border-radius: 6px
Background: module-specific sage tint
Border: 1px module accent color
Text: text-xs, SemiBold, module accent color
```

### 5.7 Navigation

**Bottom Navigation (5 tabs — Mobile):**

```
Height: 64px fixed bottom
Background: white (light) / gray-900 (dark)
Top border: 1px gray-200 (light) / gray-800 (dark)
Tabs: 5 equal-width columns

Tab structure:
  Icon: 24px, centered
  Label: text-xs (11px), SemiBold, below icon, 4px gap
  Active: icon and label in green-600
  Inactive: icon and label in gray-400
  Active indicator: 2px top border in green-600 on active tab column
```

**Top Bar (Mobile App):**
```
Height: 56px fixed top
Background: white (light) / gray-900 (dark)
Bottom border: 1px gray-200 (light) / gray-800 (dark)
Left: Farm name (text-base, SemiBold, gray-900) + species module chip
Right: Notification bell (24px) + unread count badge
```

**Side Navigation (Admin Dashboard — Desktop):**
```
Width: 240px fixed left
Background: navy-900 (#02153E)
Logo: top 24px, padded 20px
Navigation groups: labeled sections
Nav item: 40px height, 12px 20px padding, text-sm, white/60% opacity
Nav item (active): white 100%, left 3px green-600 accent bar
Group label: text-xs uppercase, white/40%, 8px top margin
Bottom: user avatar + name + role chip
```

### 5.8 Charts & Data Visualization

AGRIOS uses Recharts (already in package.json). Visual rules:

**Color assignments (consistent across all charts):**
| Series | HEX | Use |
|--------|-----|-----|
| Primary metric | `#076524` | Main data line/bar |
| Comparison / secondary | `#063491` | Second data series |
| Mortality / negative | `#DC2626` | Bad outcome |
| Target / forecast | `#D97706` | Projected/goal line |
| Background fill | `#076524` at 10% opacity | Area chart fill |

**Chart types and their contexts:**

| Chart | When to use | Don't use when |
|-------|-------------|----------------|
| Line chart | Trends over time (mortality rate, egg production) | Comparing categories |
| Bar chart | Comparing flocks, farms, or periods | Showing continuous trends |
| Donut chart | Distribution (feed cost breakdown, species split) | More than 5 categories |
| Area chart | Cumulative growth (flock population over weeks) | Any comparison needed |
| Sparkline | Small in-card trend indicators | Detailed analysis |

**Universal chart rules:**
1. Always show axis labels. Never let a chart be ambiguous about its unit.
2. Tooltip on hover — always. Mobile: tooltip on tap, stays until tap elsewhere.
3. Zero-baseline for bar charts — never truncate the Y axis.
4. Grid lines: horizontal only, dashed, gray-200 color.
5. Legend: below chart on mobile, right of chart on desktop.
6. Empty chart state: Show skeleton with "No data for this period" + reason.

---

## 6. Dashboard Design Language

### 6.1 Farmer Dashboard — Design Principles

The Farmer Dashboard is the screen a smallholder farmer opens every morning. It must answer three questions in under 5 seconds without reading:

1. **Is my flock alive and healthy?** (Red alert = check immediately. Green = continue.)
2. **Did something happen yesterday I need to know?** (Summary of last 24h.)
3. **What do I need to do today?** (Actionable task list.)

**Governing feel:** Simple. Actionable. Immediate. No unnecessary decoration.

**Layout (Mobile-first, 4-column grid):**

```
────────────────────────────────
  TOP BAR (farm name + alert bell)
────────────────────────────────
  [HEALTH BANNER]  ← Full width
  Green: "Flock healthy — 0 alerts"
  Red: "⚠ 3 sick birds detected — Review now"
────────────────────────────────
  STAT ROW (2 cards × 2 rows)
  [Total Birds]    [Feed Level]
  [Avg Daily Eggs] [Mortality Today]
────────────────────────────────
  TODAY'S TASKS
  Checklist of 2–4 logged activities
────────────────────────────────
  RECENT ACTIVITY FEED
  Timeline of last 3 events
────────────────────────────────
  ARIA QUICK ASK
  "Ask ARIA about your farm..."
────────────────────────────────
  BOTTOM NAV
────────────────────────────────
```

**Visual rules for Farmer Dashboard:**
1. The **Health Banner** is the highest-priority element. It is always the first thing below the top bar. Full-width, 64px minimum height, semantic color. Non-negotiable.
2. **Stat cards** use large JetBrains Mono numbers. No chart needed in stat cards on the farmer dashboard — raw numbers are faster to parse than tiny sparklines on a small phone.
3. **Today's Tasks** uses a checkmark list with large touch targets (56px per row). Farmers log data by tapping a task — one tap, one log.
4. **ARIA Quick Ask** is a soft-bordered input, not a prominent CTA. It invites but does not dominate.
5. **Maximum alert banners visible at once: 2.** If more alerts exist, show "2 more alerts →". Do not stack more than 2 banners — this reads as the app screaming.
6. **No charts on the Farmer Dashboard home screen.** Charts are for the Finance tab and reporting screens. The home screen communicates status, not analytics.

### 6.2 Admin Dashboard — Design Principles

The Admin Dashboard is where the AGRIOS founder (and future platform admins) monitor the entire platform. It surfaces the DAL metric (Daily Active Loggers), farm health, user growth, and revenue.

**Governing feel:** Powerful. Data-rich. Enterprise-grade. Comfortable with density.

**Layout (Desktop, 12-column grid):**

```
──────────────────────────────────────────────────────
  SIDE NAV (240px, navy-900)
                              MAIN CONTENT AREA (fluid)
  Platform name               ┌────────────────────────┐
  ─────────                   │ Page title             │
  Overview     ●              │ Date range picker      │
  Farms                       ├────────────────────────┤
  Users                       │ KPI ROW (4 stat cards) │
  Finance                     │ DAL% | Farms | Users | ARR│
  ARIA Logs                   ├───────────┬────────────┤
  Settings                    │ Active    │ Recent     │
  ─────────                   │ Farms     │ Registrations│
  [user info]                 │ table     │ list       │
                              ├───────────┴────────────┤
                              │ DAL Trend (line chart) │
                              └────────────────────────┘
──────────────────────────────────────────────────────
```

**Visual rules for Admin Dashboard:**
1. **DAL% is the hero metric** — displayed at 36px JetBrains Mono in a prominent stat card at the top of every admin screen. Target: 40%+.
2. **Side navigation uses navy-900** (`#02153E`) — the deepest navy from the logo. This signals "system", not "product". It feels like infrastructure.
3. **Tables are the primary content format** on admin screens. Farmers see cards. Admins see rows.
4. **Date range pickers are always visible** in the top-right of every data screen. Default: Last 7 days.
5. **Color coding is consistent** — a green number is always up, a red number is always down. No reversals.
6. **Empty states on admin screens include context** — not just "No data" but "No farms registered in the last 7 days. Check acquisition channels."
7. **No pagination on tables with fewer than 50 rows** — show all rows. Pagination adds cognitive overhead for no benefit.
8. **Export button** (CSV) is always present on data tables — admin users will export. Make it one click.

---

## 7. Light Mode & Dark Mode

### 7.1 Mode Philosophy

AGRIOS ships with **light mode as the default**. Dark mode is supported and must be a complete, first-class experience — not an afterthought.

**Why light mode is default:** The primary users (smallholder farmers in Kenya) use AGRIOS outdoors in bright sunlight. Light mode has better contrast in direct sunlight. Dark mode is a preference feature, not a survival feature.

**Dark mode trigger:** Follow `prefers-color-scheme` media query. Allow manual override via Settings toggle.

### 7.2 Light Theme — Complete Token Set

**Backgrounds:**
| Token | HEX | Use |
|-------|-----|-----|
| `bg-base` | `#FAFAFA` | Page / app background |
| `bg-surface` | `#FFFFFF` | Card surfaces, modals |
| `bg-surface-raised` | `#FFFFFF` | Dropdowns, tooltips |
| `bg-subtle` | `#F4F4F5` | Input fills, tab backgrounds |
| `bg-muted` | `#E4E4E7` | Disabled areas, skeleton loaders |

**Text:**
| Token | HEX | Use |
|-------|-----|-----|
| `text-primary` | `#18181B` | Headings, primary body |
| `text-secondary` | `#3F3F46` | Standard body |
| `text-tertiary` | `#71717A` | Captions, metadata |
| `text-disabled` | `#A1A1AA` | Disabled inputs, placeholders |
| `text-on-dark` | `#FFFFFF` | Text on green or navy fills |
| `text-link` | `#063491` | Hyperlinks |
| `text-link-hover` | `#2248C2` | Hover state for links |

**Borders:**
| Token | HEX | Use |
|-------|-----|-----|
| `border-default` | `#E4E4E7` | Standard card borders, dividers |
| `border-strong` | `#D1D1D6` | Input borders (resting) |
| `border-focus` | `#076524` | Input borders (focused) |
| `border-error` | `#DC2626` | Input borders (error state) |

**Brand on Light:**
| Token | HEX | Use |
|-------|-----|-----|
| `brand-primary` | `#076524` | Primary buttons, active states, icons |
| `brand-primary-hover` | `#1F8A4A` | Primary button hover |
| `brand-primary-light` | `#D1F0DC` | Primary background tint |
| `brand-secondary` | `#063491` | Secondary elements, links, badges |
| `brand-secondary-light` | `#EEF2FF` | Secondary background tint |

**Top Bar (Light):**
- Background: `#FFFFFF`
- Border bottom: `1px #E4E4E7`
- Text: `#18181B`

**Bottom Navigation (Light):**
- Background: `#FFFFFF`
- Border top: `1px #E4E4E7`
- Active tab: `#076524`
- Inactive tab: `#A1A1AA`

**Side Navigation — Admin (Light):**
- Background: `#02153E` (navy-900 — same as dark, navigation stays dark)
- Active item text: `#FFFFFF`
- Inactive item text: `rgba(255,255,255,0.55)`

### 7.3 Dark Theme — Complete Token Set

**Backgrounds:**
| Token | HEX | Use |
|-------|-----|-----|
| `bg-base` | `#0A0A0B` | Page / app background |
| `bg-surface` | `#18181B` | Card surfaces, modals |
| `bg-surface-raised` | `#27272A` | Dropdowns, tooltips (above surface) |
| `bg-subtle` | `#27272A` | Input fills, tab backgrounds |
| `bg-muted` | `#3F3F46` | Disabled areas, skeleton loaders |

**Text:**
| Token | HEX | Use |
|-------|-----|-----|
| `text-primary` | `#FAFAFA` | Headings, primary body |
| `text-secondary` | `#D1D1D6` | Standard body |
| `text-tertiary` | `#71717A` | Captions, metadata |
| `text-disabled` | `#52525B` | Disabled inputs, placeholders |
| `text-on-dark` | `#FFFFFF` | Text on brand fills |
| `text-link` | `#7090E4` | Hyperlinks (lightened for dark bg) |
| `text-link-hover` | `#A8B7F0` | Hover state for links |

**Borders:**
| Token | HEX | Use |
|-------|-----|-----|
| `border-default` | `#3F3F46` | Standard card borders, dividers |
| `border-strong` | `#52525B` | Input borders (resting) |
| `border-focus` | `#3FAB6C` | Input borders (focused — lightened green) |
| `border-error` | `#F87171` | Input borders (error — lightened red) |

**Brand on Dark:**
| Token | HEX | Use |
|-------|-----|-----|
| `brand-primary` | `#3FAB6C` | Primary buttons (lightened for dark bg) |
| `brand-primary-hover` | `#72C795` | Primary button hover |
| `brand-primary-light` | `#022B11` | Primary background tint |
| `brand-secondary` | `#7090E4` | Secondary elements (lightened navy) |
| `brand-secondary-light` | `#02153E` | Secondary background tint |

**Top Bar (Dark):**
- Background: `#18181B`
- Border bottom: `1px #3F3F46`
- Text: `#FAFAFA`

**Bottom Navigation (Dark):**
- Background: `#18181B`
- Border top: `1px #3F3F46`
- Active tab: `#3FAB6C` (lightened green)
- Inactive tab: `#52525B`

**Semantic colors in dark mode:**
| Role | Dark HEX | (Light HEX for reference) |
|------|----------|--------------------------|
| Success text | `#4ADE80` | `#076524` |
| Success background | `#022B11` | `#D1F0DC` |
| Warning text | `#FCD34D` | `#D97706` |
| Warning background | `#2D1F06` | `#FEF3C7` |
| Error text | `#F87171` | `#DC2626` |
| Error background | `#2D0808` | `#FEE2E2` |
| Info text | `#7090E4` | `#063491` |
| Info background | `#02153E` | `#EEF2FF` |
| Critical text | `#C084FC` | `#7C3AED` |
| Critical background | `#1E0A3C` | `#EDE9FE` |

### 7.4 Logo Usage in Each Mode

| Mode | Logo Version |
|------|-------------|
| Light mode | Full color (green + navy on white) |
| Dark mode | Single color white — both symbol and wordmark in `#FFFFFF` |
| On green button/banner | White version |
| On navy header | White version |
| Favicon | Symbol only, green on white |
| App icon (PWA) | Symbol on green-600 background, white symbol |

---

## 8. Brand Personality

### 8.1 The AGRIOS Promise

> **AGRIOS is the trusted agronomist in your pocket.**

Not a flashy app. Not a government portal. Not a generic business tool. AGRIOS is the expert system that knows your farm, remembers everything, and tells you what matters — before you have to ask.

### 8.2 Brand Voice

**Four adjectives that define every piece of AGRIOS copy:**

1. **Clear** — Never clever when clear would do. If a farmer has to read a sentence twice, rewrite it.
2. **Confident** — AGRIOS states facts. It does not hedge. "3 birds showed abnormal behavior yesterday" not "It appears some birds may possibly have had some issues."
3. **Respectful** — Never condescending. The farmer knows their farm. AGRIOS knows data. Together they decide.
4. **Practical** — Every message ends with something the farmer can do. Information without action is noise.

**Voice comparison:**

| Wrong | Right |
|-------|-------|
| "It seems like there may be some potential concerns with your flock's health status." | "2 birds showed reduced movement today. Check for illness." |
| "Your farm's financial performance has been suboptimal." | "You spent KSh 3,200 more on feed than you earned this week." |
| "ARIA is an AI assistant that can help you with queries about your agricultural data." | "Ask ARIA anything about your farm." |
| "Please ensure that all daily logs are completed on time for optimal system performance." | "Log today before 8pm — it only takes 2 minutes." |

### 8.3 Writing Principles

1. **Lead with the fact, end with the action.** "Mortality is 2% this week. Review the sick birds report."
2. **Numbers in digits, always.** "3 birds" not "three birds". Numbers scan faster.
3. **Use the farmer's language.** "Flock" not "poultry population". "Feed" not "nutritional input". "Sick bird" not "morbidity event".
4. **Short sentences in alerts.** Alerts are read in 2 seconds. Max 12 words.
5. **ARIA speaks like a colleague, not a chatbot.** No "Sure! I'd be happy to help you with that!" — just the answer.

### 8.4 Design Principles

**P1 — Clarity over cleverness**
A farmer looking at their mortality rate at 6am should not need to interpret a visualization. Numbers, clear labels, clear context. Always.

**P2 — Data tells the story**
AGRIOS does not celebrate the farmer. It surfaces what their farm is doing. Let results create pride. The UI's job is to get out of the way.

**P3 — Mobile is the promise**
The platform is built for a phone that may be cracked, running on 3G, with a dirty screen, held by someone who has been working since 4am. Every interaction must account for this.

**P4 — African by design, global by scale**
The platform is designed for Kenya first. That means Swahili support, M-Pesa integration (Phase 2), SMS as primary notification channel, offline-first architecture. The product does not adopt a Western SaaS aesthetic and apply it to African agriculture. It builds for the context.

**P5 — Alerts earn attention**
Alert fatigue kills engagement. AGRIOS alerts are sparse, accurate, and actionable. Every alert is either: (a) something the farmer must know today, or (b) something that will cost them money if ignored. Nothing else qualifies.

**P6 — ARIA is honest about what it knows**
ARIA Lite does not diagnose disease. It does not pretend to know things it doesn't. When asked something outside its data ("Is Newcastle disease spreading in my county?"), it says "I don't have real-time disease surveillance data. For disease outbreak alerts, contact your local veterinary office." Honesty is a feature.

### 8.5 Tone by Context

| Context | Tone | Example |
|---------|------|---------|
| Health alert | Urgent, brief | "⚠ Disease alert: 4 birds quarantined. Act now." |
| Daily summary | Factual, encouraging | "Good day: 0 losses, 94% production rate." |
| ARIA response | Informative, direct | "Your feed cost per egg is KSh 4.2, up 12% from last week." |
| Onboarding | Welcoming, instructional | "Let's set up your first flock. It takes 3 minutes." |
| Error states | Honest, solution-focused | "Can't connect right now. Your data is saved locally." |
| Empty states | Contextual, forward-looking | "No health events this week. Log daily to track trends." |

### 8.6 Product Personality at a Glance

| Dimension | AGRIOS Is | AGRIOS Is Not |
|-----------|----------|---------------|
| Tone | Trusted advisor | Cheerful chatbot |
| Design | Data-forward professional | Decorative or playful |
| Communication | Direct and specific | Vague and hedging |
| Relationship | Expert partner | Superior or paternalistic |
| Technology | Quietly powerful | Flashy or tech-for-tech's-sake |
| Culture | African-first, globally rigorous | Western-imported, culturally neutral |

---

## 9. Module Expansion Strategy

### 9.1 The Species Extensibility System

AGRIOS is designed so that adding a new agricultural module (Rabbit OS, Dairy OS, etc.) requires:

- **Zero changes** to the color system
- **Zero changes** to typography
- **Zero changes** to component library
- **One new module accent color** (from a pre-defined module palette)
- **One new set of species-specific screen layouts** (reusing all existing components)
- **One database activation** (`UPDATE species_profiles SET is_active = TRUE WHERE slug = 'rabbit'`)

The design system is the **chassis**. Each module is an **engine variant**. The chassis never changes.

### 9.2 Module Accent Color System

Each agricultural module is assigned a unique accent color. This accent color appears in:
- Module chip/badge
- Module card top border
- Module-specific illustrations
- Module navigation indicator (when module is active)

The accent color **never** replaces the primary green or navy blue — it supplements them.

| Module | Status | Accent Color | HEX | Rationale |
|--------|--------|-------------|-----|-----------|
| Poultry OS | Active (Phase 1) | Brand Green | `#076524` | Core product color — poultry IS the default |
| Rabbit OS | Future | Warm Amber | `#D97706` | Warmth, fur, small livestock |
| Dairy OS | Future | Sky Blue | `#0284C7` | Water, milk, freshness, cattle |
| Fish OS | Future | Teal | `#0D9488` | Water, aquatic life, freshness |
| Crop OS | Future | Earth Brown | `#92400E` | Soil, harvest, root crops |
| Enterprise Suite | Future | Royal Purple | `#7C3AED` | Premium, multi-farm, executive |

All six accent colors:
- Pass 4.5:1 contrast against white backgrounds.
- Are visually distinct from each other at a glance.
- Do not clash with the primary green or navy.
- Are drawn from Tailwind's standard palette for implementation simplicity.

### 9.3 Module Activation — UI Patterns

When a new module is activated (admin toggle → `is_active = TRUE`):

**Navigation change:**
- Bottom nav Tab 2 ("Flock") becomes a multi-species selector if more than one species is active.
- A species switcher chip appears in the Top Bar left, replacing the static farm name chip.

**Dashboard change:**
- Stat cards auto-adapt labels to species context: "Total Birds" becomes "Total Rabbits" or "Total Cattle".
- Health events render species-appropriate icons.
- Feed tracking units shift automatically from `kg feed/bird/day` to `kg feed/head/day` for dairy.

**Color change:**
- Module chip and module card accent change to module accent color.
- Active module indicator in navigation uses module accent.
- All other platform colors — buttons, links, text, backgrounds — remain unchanged.

**What does NOT change when a module activates:**
- Primary green button color
- Navy secondary elements
- Typography
- Spacing
- Card structure
- Navigation anatomy
- ARIA interface
- Admin dashboard layout

### 9.4 Module Design Isolation

Each module may introduce **module-only components** if the species requires it. These are quarantined in the design system as extensions, never replacements.

| Module | Possible New Components |
|--------|------------------------|
| Rabbit OS | Breeding cycle tracker (calendar), litter weight chart |
| Dairy OS | Milking session logger, lactation curve chart |
| Fish OS | Pond/tank health gauge, dissolved oxygen monitor |
| Crop OS | Field map overlay, growth stage timeline |
| Enterprise | Multi-farm comparison table, consolidated P&L |

All new components must:
1. Use the same spacing tokens.
2. Use the same typography scale.
3. Use the same card structure.
4. Use module accent color only for the 4px border and module chip — not for primary actions.
5. Be documented in this design system as an addendum before being built.

### 9.5 Scaling to Enterprise

When AGRIOS reaches the Enterprise tier (multi-farm accounts), the design system scales without redesign:

**Visual hierarchy additions:**
- Enterprise badge (purple accent, royal purple) on farm cards
- Enterprise navigation level: Enterprise → Farm → Module
- Consolidated dashboard view: all farms in one screen
- Comparison views: farm A vs farm B for the same metric

**No changes to:**
- Component architecture
- Color tokens
- Typography
- Mobile layout

The enterprise shell is a new navigation layer — the existing product sits inside it unchanged.

---

## Appendix A — CSS Custom Properties (Production Token Reference)

```css
:root {
  /* Brand */
  --brand-green: #076524;
  --brand-navy: #063491;
  --brand-sage: #BFE0C7;

  /* Green Scale */
  --green-50:  #F0FAF4;
  --green-100: #D1F0DC;
  --green-200: #A8E0BB;
  --green-300: #72C795;
  --green-400: #3FAB6C;
  --green-500: #1F8A4A;
  --green-600: #076524;
  --green-700: #055420;
  --green-800: #03401A;
  --green-900: #022B11;

  /* Navy Scale */
  --navy-50:  #EEF2FF;
  --navy-100: #D1D9F7;
  --navy-200: #A8B7F0;
  --navy-300: #7090E4;
  --navy-400: #4169D8;
  --navy-500: #2248C2;
  --navy-600: #063491;
  --navy-700: #052A78;
  --navy-800: #03205C;
  --navy-900: #02153E;

  /* Neutral Scale */
  --gray-50:  #FAFAFA;
  --gray-100: #F4F4F5;
  --gray-200: #E4E4E7;
  --gray-300: #D1D1D6;
  --gray-400: #A1A1AA;
  --gray-500: #71717A;
  --gray-600: #52525B;
  --gray-700: #3F3F46;
  --gray-800: #27272A;
  --gray-900: #18181B;

  /* Semantic */
  --color-success:        #076524;
  --color-success-light:  #D1F0DC;
  --color-warning:        #D97706;
  --color-warning-light:  #FEF3C7;
  --color-error:          #DC2626;
  --color-error-light:    #FEE2E2;
  --color-info:           #063491;
  --color-info-light:     #EEF2FF;
  --color-critical:       #7C3AED;
  --color-critical-light: #EDE9FE;

  /* Module Accents */
  --module-poultry: #076524;
  --module-rabbit:  #D97706;
  --module-dairy:   #0284C7;
  --module-fish:    #0D9488;
  --module-crop:    #92400E;
  --module-enterprise: #7C3AED;

  /* Light Mode Surfaces (default) */
  --bg-base:           #FAFAFA;
  --bg-surface:        #FFFFFF;
  --bg-surface-raised: #FFFFFF;
  --bg-subtle:         #F4F4F5;
  --bg-muted:          #E4E4E7;

  /* Light Mode Text */
  --text-primary:   #18181B;
  --text-secondary: #3F3F46;
  --text-tertiary:  #71717A;
  --text-disabled:  #A1A1AA;
  --text-on-dark:   #FFFFFF;
  --text-link:      #063491;

  /* Light Mode Borders */
  --border-default: #E4E4E7;
  --border-strong:  #D1D1D6;
  --border-focus:   #076524;
  --border-error:   #DC2626;

  /* Layout */
  --top-bar-height:    56px;
  --bottom-nav-height: 64px;
  --side-nav-width:    240px;

  /* Spacing */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-14: 56px;
  --space-16: 64px;

  /* Border Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 1px 3px rgba(0,0,0,0.10), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.12);
  --shadow-xl: 0 10px 40px rgba(0,0,0,0.16);
}

/* Dark Mode Overrides */
[data-theme="dark"] {
  --bg-base:           #0A0A0B;
  --bg-surface:        #18181B;
  --bg-surface-raised: #27272A;
  --bg-subtle:         #27272A;
  --bg-muted:          #3F3F46;

  --text-primary:   #FAFAFA;
  --text-secondary: #D1D1D6;
  --text-tertiary:  #71717A;
  --text-disabled:  #52525B;
  --text-link:      #7090E4;

  --border-default: #3F3F46;
  --border-strong:  #52525B;
  --border-focus:   #3FAB6C;
  --border-error:   #F87171;

  --brand-green: #3FAB6C;

  --color-success:        #4ADE80;
  --color-success-light:  #022B11;
  --color-warning:        #FCD34D;
  --color-warning-light:  #2D1F06;
  --color-error:          #F87171;
  --color-error-light:    #2D0808;
  --color-info:           #7090E4;
  --color-info-light:     #02153E;
  --color-critical:       #C084FC;
  --color-critical-light: #1E0A3C;
}
```

---

## Appendix B — Tailwind Config (Production Override)

The existing `tailwind.config.ts` established `brand-600: #16a34a`. This must be updated to reflect the AGRIOS logo color.

**Required change to `tailwind.config.ts`:**

```typescript
// Replace existing brand palette with:
brand: {
  50:  '#F0FAF4',
  100: '#D1F0DC',
  200: '#A8E0BB',
  300: '#72C795',
  400: '#3FAB6C',
  500: '#1F8A4A',
  600: '#076524',  // ← Updated to match logo exact
  700: '#055420',
  800: '#03401A',
  900: '#022B11',
},
navy: {
  50:  '#EEF2FF',
  100: '#D1D9F7',
  200: '#A8B7F0',
  300: '#7090E4',
  400: '#4169D8',
  500: '#2248C2',
  600: '#063491',  // ← Logo navy
  700: '#052A78',
  800: '#03205C',
  900: '#02153E',
},
```

**Note on prior Sprint 0 Tailwind config:** Sprint 0 used `#16a34a` as `brand-600`. This is a standard Tailwind green — close but NOT the AGRIOS logo green. The logo green is `#076524` — noticeably darker and more forest-like. All future UI must use the corrected value.

---

## Appendix C — Font Loading

Add to `index.html` `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

**Performance note:** `display=swap` ensures text is visible during font load. The `preconnect` directives reduce font load time by ~200ms on first visit.

---

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | FROZEN for V1 |
| Authority | Chief Brand Architect |
| Source of truth for | All UI color, typography, spacing, component decisions |
| Supersedes | Any prior color or style decisions in Sprint 0 config files |
| Override process | Requires explicit CTO approval — document new version, do not edit in place |
| Next review | Sprint 3 (post-MVP launch) |

---

*This document is the official design authority for AGRIOS V1. No UI decision that contradicts this document is valid without a documented override. When in doubt, refer here first.*
