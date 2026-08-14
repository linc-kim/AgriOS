# Greena V1 LC1 — Phase A: Platform Gap Report

**Date:** 2026-08-14
**Branch:** `phase-2-auth`
**Method:** Static code/repository inspection only. **No live environment was contacted** — per owner decision, all live‑infrastructure verification (deploy health, running webhooks, production DB, browser runtime) is treated as **BLOCKED** for this pass and marked as such below. Nothing was modified during this audit.

Each finding cites evidence as `path:line` where applicable. Severity legend:
**CRITICAL** = blocks launch / legal/financial exposure · **HIGH** = must fix before public launch · **MEDIUM** = fix soon, not launch‑blocking · **LOW** = hygiene.

---

## 0. Executive summary

The platform is **substantially further along than the LC1 spec assumes**. Backend exposes **845 route handlers across 76 endpoint modules** (`backend/app/api/v1/endpoints/`), **91 Alembic migrations** (latest `091_credit_ledger_reward_idempotency`), and the frontend has **199 screen/component files** with **full module parity** — every backend module has corresponding UI routes (`frontend/src/routes/index.tsx`).

Key corrections to the spec's stated baseline:

| Spec claim | Reality (evidence) | Impact |
|---|---|---|
| Backend on **Render** | Confirmed: `backend/render.yaml` (`greena-api`, docker, `/health`, `alembic upgrade head` pre‑deploy). Deploys from **`phase-2-auth`**, not `main`. | Host resolved. Branch hygiene = MEDIUM. |
| **Fish ✓ completed** | **No Fish/aquaculture module exists** — no router, model, migration, or UI. Fish appears only as passing text in ARIA knowledge files. | Must **not** advertise Fish anywhere. HIGH. |
| Old **AGRIOS branding** everywhere | **Frontend `src/` has zero AGRIOS references.** Residue is internal (`AGRIOSBase` ORM base class, table comments), docs, and `.env.example`. | Public branding already clean. Cosmetic/internal only. MEDIUM. |

**No CRITICAL launch‑blockers were found in static inspection.** The most material gaps are: **missing legal/support pages** (Privacy, Terms, etc.), **missing SEO crawl assets** (robots.txt, sitemap.xml), and the **Fish spec/reality drift**. Live‑runtime verification (deploy, billing webhooks, referral lifecycle, performance, full farmer journey) remains **BLOCKED** and unproven.

---

## 1. Findings by severity

### CRITICAL
*None identified from static inspection.* (Live‑runtime CRITICALs cannot be ruled out — see §3 BLOCKED items.)

### HIGH

- **H1 — Missing legal & support pages.** Public routes exist for `/`, `/features`, `/solutions`, `/aria-ai`, `/pricing`, `/learning`, `/about`, `/contact` only (`frontend/src/routes/index.tsx:177‑188`). There is **no Privacy Policy, Terms of Service, Help Center, FAQ, Documentation, Roadmap, Release Notes, or Support page.** A public SaaS handling payments and personal data needs Privacy + Terms at minimum before launch (legal exposure). Required by spec Phase C.
- **H2 — Fish advertised risk / spec drift.** Spec Phase C lists a Fish industry page and marks Fish complete, but no Fish capability exists in code. Any website/pricing/docs copy must **exclude Fish** to avoid advertising non‑existent functionality (spec's own rule). Currently the frontend does **not** advertise Fish (good) — this is a guard, not a present defect.
- **H3 — Missing SEO crawl assets.** `frontend/public/` has favicon, manifest, og‑image, safari‑pinned‑tab, icons — but **no `robots.txt` and no `sitemap.xml`** (search returned none). `index.html` head has good OG basics but **lacks** `og:url`, Twitter Card tags, canonical URL, and JSON‑LD structured data (`frontend/index.html:1‑30`). `og:image` is a **relative** path (`/og-image.png`) — social/crawlers need an absolute URL (deferred until domain exists). Required by spec Phase J.

### MEDIUM

- **M1 — Deployment doc drift (Railway vs Render).** `.env.example` still describes the backend as a "Railway service"; host is Render (`backend/render.yaml`). Reconcile so env docs match reality.
- **M2 — Internal AGRIOS residue.** ORM declarative base is `AGRIOSBase` (`backend/app/models/base.py`, used across all model files) and various table comments/docstrings say AGRIOS. Not user‑facing, but the spec asks for brand consistency. Rename is a mechanical, higher‑risk refactor (touches every model) — schedule deliberately, not casually.
- **M3 — Release branch hygiene.** `render.yaml` auto‑deploys from `phase-2-auth`, which is far ahead of `main` and (per project notes) unmerged/unpushed. Decide the branching/release model before go‑live.
- **M4 — Pricing values unverifiable statically.** Plan prices are **DB‑seeded**, read server‑side from `subscription_plans` (`backend/app/services/billing_service.py:76‑84`); the checkout UI fetches active plans. Design is sound (client can never set price), but **displayed price correctness requires the live DB** — see BLOCKED B4.
- **M5 — Root‑level legacy docs.** Multiple `AGRIOS_*.md` / `*.docx` at repo root (audit, blueprint, founder doc, ops manual) predate the Greena rename. Inventory and either rename/retire or clearly mark historical.

### LOW

- **L1 — `vendor-skills-review/` in repo.** ~15 unrelated design/skill folders committed at root — repo bloat, unrelated to the product. Consider removing or moving out of the product repo.
- **L2 — Build/cache artifacts.** `backend/.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `frontend/dist` present locally; confirm all are gitignored (path noise inflated an earlier grep).

---

## 2. Area‑by‑area status (static pass)

| Area | Status | Evidence / notes |
|---|---|---|
| Backend API | **PASS** | 845 handlers, 76 modules, 91 migrations. |
| Modules (poultry, aviculture, BSF, rabbit, goat, sheep, swine) | **PASS** | Models + endpoints + UI routes all present. **Fish: N/A (absent).** |
| Frontend ↔ backend parity | **PASS** | Every backend module has screens (`routes/index.tsx`). |
| Authentication (code) | **PASS** | signup, login, verify‑email, resend‑verification, forgot/reset‑password, refresh rotation, logout‑all, phone OTP/PIN (`endpoints/auth.py`). |
| Billing (code/design) | **PASS** | Server‑derived price, discount can only lower, webhook amount re‑verified vs stored txn, HMAC‑SHA512 constant‑time webhook (`paystack_service.py:101‑102`). |
| Referral (code) | **PASS (static)** | Referral + credit‑ledger models/migrations (`090`, `091` idempotency guard). Runtime = BLOCKED. |
| Secrets hygiene | **PASS** | No `.env` committed; `.gitignore` covers all `.env*` except `*.example`. |
| Security headers / CORS | **PASS (present)** | `backend/app/core/middleware.py`, `app/main.py`. Depth review pending. |
| SEO assets | **PARTIAL** | Favicon/manifest/OG present; robots/sitemap/canonical/Twitter/JSON‑LD missing (H3). |
| Website pages | **PARTIAL** | Core marketing pages present; legal/support pages missing (H1). |
| Branding (public) | **PASS** | Frontend `src/` clean Greena; internal residue only (M2). |
| Accessibility | **NOT TESTED** | Needs component + browser pass. |
| Responsiveness / cross‑browser | **NOT TESTED** | Needs browser pass. |
| Notifications / uploads (flows) | **NOT TESTED** | Endpoints exist; behavior unverified. |
| Deployment (live) | **BLOCKED** | See §3. |

---

## 3. BLOCKED — live‑infrastructure items (owner‑deferred this pass)

These cannot be verified without reaching the live stack (owner chose "treat as blocked"). They are **unproven**, not passing:

- **B1** Render deploy health, startup, scheduler, background jobs, restart recovery (Phase F).
- **B2** Vercel live frontend ↔ backend, CORS, sessions, console cleanliness (Phase G).
- **B3** Paystack runtime: initialize → redirect → callback → webhook delivery, duplicate/failed/cancelled/timeout handling (Phase H).
- **B4** Live plan prices in `subscription_plans`; end‑to‑end subscription activation (M4).
- **B5** Referral full lifecycle + abuse cases against live webhooks (Phase I).
- **B6** Production Playwright, performance/latency, full farmer journey, final production audit (Phases L, N, O, P).

Supabase is unreachable from this environment (project note), so even read‑only DB verification is blocked here.

---

## 4. Recommended remediation order

1. **H1** Legal/support pages (Privacy, Terms first) — launch‑blocking legal.
2. **H3** SEO crawl assets (robots.txt, sitemap.xml, canonical, Twitter, JSON‑LD) — Phase J, repo‑local.
3. **H2** Confirm no Fish advertising as website copy evolves (guardrail).
4. **M1/M3/M5** Doc & branch hygiene reconciliation.
5. **M2** `AGRIOSBase` rename — deliberate, tested refactor.
6. When live access is available: work the BLOCKED set B1–B6 in order.

---

*This is Phase A, pass 1: architecture, parity, branding, auth, billing design, security hygiene, SEO/website inventory. Accessibility, responsiveness, notifications/uploads behavior, and all live‑runtime verification remain open and are tracked above. No claim in this report depends on unverified runtime.*
