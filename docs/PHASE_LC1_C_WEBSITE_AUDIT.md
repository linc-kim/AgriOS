# Greena V1 LC1 — Phase C: Marketing Website Audit (Production)

**Date:** 2026-08-14 · **Environment:** live production `https://agrioskenya.vercel.app` · **Branch/commit:** `phase-2-auth` @ `c1e8d93`
**Method:** each public page loaded in a real browser against production; console checked; rendered content (not just the SPA shell) inspected; pricing cross-checked against the backend catalog source.

## Summary
Functionally the public site is **healthy** — every page renders, **zero console errors**, branding is consistently Greena, no AGRIOS, no Fish, and the new legal / Help / install / social surfaces are live. Two **content-accuracy** issues are launch-significant: the site presents Greena as poultry-only while the app ships six more species modules, and the marketing prices do not match the billing catalog.

## Findings

### HIGH
- **C1 — Website omits shipped functionality; presents Greena as poultry-only.**
  Home ("Built for Kenyan poultry farms"), Features, Solutions and Pricing are framed entirely around poultry (flocks/eggs/broilers/layers). Solutions' "Roadmap" lists **Dairy, Crops, Marketplace, Cooperatives as "Planned."** But the application actually ships and routes live UI for **goat & sheep (incl. goat dairy and wool), rabbit, swine, black soldier fly (BSF), and aviculture** (backend endpoints `sr_*`, `rabbit*`, `swine*`, `bsf*`, `aviculture*`; frontend screens under `src/screens/{smallRuminant,rabbit,swine,bsf,aviculture}`). So the site **omits major existing functionality** and **mislabels shipped capability (dairy) as future** — directly against the LC1 rule "nothing should omit major functionality that already exists."
  *Evidence:* `/solutions` rendered text ("Dairy … Planned"); `frontend/src/routes/index.tsx` (species routes); Phase A audit (76 backend modules).
  *Owner decision:* either expand the marketing site to reflect the multi-species platform, or intentionally keep poultry-first positioning — but in the latter case reconcile the "farm operating system" claim and the fact that signed-in users already see the other modules in-app.

- **C2 — Marketing prices are hardcoded and do not match the billing catalog.**
  `src/screens/public/PricingScreen.tsx` **hardcodes** `Free 0 / Starter 1,500 / Pro 4,500` (lines 19/35/52) and does **not** fetch `/billing/plans`. The seeded backend catalog (migration `088_finalize_plan_catalog`, and prod seed per session notes) is **Free 0 / Starter 999 / Pro 1,499 / Farm Pro 2,499 / Enterprise custom**, and checkout charges the **DB** price (server-derived, verified). Result: **a farmer can be advertised KES 1,500/4,500 but charged a different amount**, and plan names/limits differ too. Trust and potentially consumer-law risk.
  *Caveat:* exact **live** DB values are UNVERIFIED here (`/billing/plans` is auth-gated → 401). The mismatch is established from the seed migration + hardcoded marketing values regardless.
  *Fix direction:* drive the marketing Pricing page from the same catalog source (or, at minimum, make the numbers/limits match the launch catalog), and decide the definitive launch price list.

### PASS / positive
- No console errors on `/`, `/solutions`, `/pricing`, `/contact`, `/help`, `/install`, `/privacy` (production).
- Branding consistently Greena; no AGRIOS or Fish in rendered content.
- New pages live in production: `/privacy`, `/terms`, `/help`, `/install`; footer Legal column; official social links (Instagram, Facebook) in footer + Contact + JSON-LD `sameAs`.
- Per-route titles/canonical/OG working; `/install` device detection + responsiveness verified earlier.

### NOT TESTED / follow-ups
- Full responsive pass across every marketing page and every viewport.
- Live exact plan catalog (needs an authenticated session).
- Features page claim-by-claim accuracy vs shipped modules (spot-checks only so far).

## Recommendation
Both HIGH items are **content/positioning decisions for the owner**, not code bugs — I did not change marketing copy or prices unilaterally. Priority before public launch: **C2** (price mismatch is a hard trust/legal issue), then **C1** (breadth of platform). Both are fixable repo-local once you confirm the intended positioning and the definitive launch price list.
