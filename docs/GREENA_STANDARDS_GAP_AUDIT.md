# GREENA STANDARDS — REPOSITORY GAP AUDIT

**Type:** Phase 0/1 audit deliverable (per *Implementation & Gap Matrix* Doc 2 §93, *Execution Plan* Doc 4 §7–10)
**Scope:** Existing AGRIOS/Greena repository vs. the 33-document Greena standards library + 4 implementation-prep documents
**Status:** AUDIT ONLY — no code changed. Awaiting approval before any hardening work (Doc 2 §94, Doc 4 §3).
**Date:** 2026-08-10

> **Naming:** The repository is internally `AGRIOS`; new code (`config.py`, `security.py`, `main.py`) already carries `Greena` branding and `PROJECT_NAME = "Greena"`. Treat **AGRIOS = Greena** — same platform, rebrand in progress. Not a defect.

---

## 0. How to read this

Requirements are classified with the **owner-approved six-label scheme**: **KEEP, HARDEN, BUILD, REFACTOR, DEFER, REMOVE** (a subset of Doc 2 §83–91).

| Class | Meaning |
|---|---|
| **KEEP** | Implementation satisfies the requirement; evidence cited. No change. |
| **HARDEN** | Works, but needs stronger security / validation / reliability — **includes correctness defects to fix** (Doc 2 "FIX" folds in here for this audit). |
| **BUILD** | Genuinely missing and in scope. |
| **REFACTOR** | Works but architecture/maintainability warrants restructuring (evidence required — Master Index §51). |
| **DEFER** | Legitimate but not justified by launch scope / "product before infrastructure" (Master Index §8–9). |
| **REMOVE** | Unnecessary, unsafe, duplicated, or obsolete; removal requires regression (Doc 2 §90). |

Notes: earlier draft labels **FIX** (correctness defect) are folded into **HARDEN**; **DECISION** items are now **resolved** (§6); **VERIFY/TEST** denote an *audit action still owed*, not a classification.

Evidence is cited as `path:line`. Claims of "secure/complete" are only made where I read the implementation (Master Index §47 "No Assumption Rule"). Test **pass** status is marked UNVERIFIED where I could not run the suite (needs local Postgres — see §9).

---

## 1. Executive summary

This is a **mature, well-architected codebase**, not a greenfield. It substantially anticipates the Greena standards: modular monolith, layered controller→service→engine→repository separation, action-based RBAC, Argon2id auth, structured migrations, deterministic-first AI with graceful degradation, Sentry + Prometheus-style metrics, 146 test files, and honest self-documented technical debt.

- **176 services**, **75 endpoint modules**, **26 model modules**, **86 Alembic migrations (001→086)**, **146 test files**.
- **7 of 8 launch modules present** (Poultry, Aviculture, BSF, Rabbit, Goat+Sheep, Swine). **Fish/Aquaculture is absent.**
- The dominant gaps are **not** correctness — they are **payments, credential/AI-rotation hardening, scale infrastructure (deferred by design), file-security controls, and CI enforcement.**

**Headline findings by severity:**

| Sev | Finding | Class |
|---|---|---|
| CRITICAL (process) | **CI is not running** — workflows live at `infrastructure/github/workflows/`, not `.github/workflows/`, so nothing gates PRs (tests, type-checks, security scans). Every "Testing/Production-Readiness" gate in the standards is currently unenforced. | HARDEN (process defect) |
| HIGH | **No payment integration.** Standards mandate Paystack server-side verification + webhooks + idempotency (Doc 3 §9–15, Doc 4 §56–61). Repo tracks `subscription_plans` in DB but money moves via **manual M-Pesa** outside the system. | DEFER (owner: M-Pesa kept; Paystack a separate post-hardening project) |
| HIGH | **Gemini single-key, no rotation/health-state machine.** Credentials doc requires `GEMINI_API_KEY_1/2`, round-robin, and AVAILABLE/RATE_LIMITED/QUOTA_EXHAUSTED/FAILED/DISABLED states (Doc 3 §16–19, Doc 4 §49–50). Repo has one `GEMINI_API_KEY` with a Gemini→Claude→offline fallback. | HARDEN |
| HIGH | **Fish/Aquaculture missing** though listed in launch scope (Blueprint §5, Prep-Doc §57). | BUILD (owner: future — after hardening, not now) |
| MEDIUM | **File-security controls unexercised.** Media/documents are stored as **URL references** (`avi_bird_media.media_url` etc.); no server-side `UploadFile` path means MIME/magic-byte/size/non-executable/signed-URL controls (Security §16) are neither needed nor present. Becomes a BUILD the moment real uploads are added. | HARDEN (→ BUILD if uploads ship) |
| MEDIUM | **RLS disabled** — authorization is app-layer only. Standards treat DB as a security boundary (Master Index §28); RLS is defense-in-depth, not the current boundary. | HARDEN (defense-in-depth) |
| MEDIUM | **Refresh-token bcrypt truncation trap.** `create_refresh_token()` hashes an ~86-byte token with bcrypt (72-byte cap); safe on the pinned `bcrypt==4.2.1`, **breaks all OTP/PIN/refresh on bcrypt ≥5.0**. | HARDEN |
| MEDIUM | **In-process rate-limit + cache + scheduler.** Correct and honest for single-instance; per-replica and non-durable under horizontal scale. Deferred by design with documented triggers. | DEFER (with load-test gate) |
| LOW | Migration 028 `notifications.metadata_` physical-column name mismatch (latent, feature gated). | HARDEN (correctness defect) |
| LOW | No PostHog; no distributed tracing beyond request/correlation IDs. | DEFER |

---

## 2. Standards hierarchy pass (Master Index §3)

### 2.1 Security & Data Protection — **STRONG, targeted hardening**

| Requirement | State | Evidence | Class |
|---|---|---|---|
| Password hashing (Argon2id) | COMPLETE | `app/core/security.py:128` Argon2 `PasswordHasher`, `hash_password`/`verify_password`, `password_needs_rehash`; length-first NIST policy `validate_password_strength:163`. | KEEP |
| PIN/OTP hashing | COMPLETE | bcrypt via passlib `security.py:23`; `generate_otp_code` uses `secrets.choice`. | KEEP |
| JWT access + opaque refresh | COMPLETE | HS256 short-lived access (`JWT_EXPIRE_MINUTES=15`); refresh = `token_urlsafe(64)`, bcrypt-hashed, `sha256` lookup index `security.py:83,191`. | KEEP |
| Refresh-token bcrypt 72-byte cap | RISK | ~86-byte token hashed by bcrypt; safe only on pinned `bcrypt==4.2.1`. Bound to 72 bytes or pre-hash before any bcrypt 5.x upgrade. | HARDEN |
| Auth token transport | ACCEPTABLE | Access token is Bearer (JS-readable, `frontend/src/api/client.ts`, `stores/authStore.ts`); refresh in httpOnly cookie. Bounded by 15-min expiry. Standards prefer no JS-exposed session token (Security §6) — document as accepted tradeoff or move access token to memory-only. | HARDEN |
| Cookie flags / CSRF | COMPLETE | `REFRESH_COOKIE_SAMESITE` configurable; `none` forces Secure + Origin-check against `ALLOWED_ORIGINS` (`config.py:83–99`). | KEEP |
| Rate limiting | PARTIAL | Sliding-window on `/api/v1/auth/*` only, in-process per-replica (`core/middleware.py:159`). OTP per-phone limits authoritative in `auth_service`. Standards want per-endpoint limits (AI/uploads/exports/payments) — mostly absent. | HARDEN |
| Security headers / HSTS | COMPLETE | `SecurityHeadersMiddleware` (`middleware.py:45`): nosniff, DENY, CSP `default-src 'none'`, HSTS in prod. | KEEP |
| RBAC (action-based) | COMPLETE | `core/permissions.py` — 8 roles × ~200 permissions, roles = permission sets (Security §8). `require_permission` factory. | KEEP |
| Tenant isolation | COMPLETE (verify depth) | `require_farm_access` verifies active `FarmMember` + role, super_admin bypass (`dependencies.py:81`). **Recommend**: automated cross-farm/cross-org IDOR test sweep (Doc 4 §17, §81) — coverage exists but breadth unverified. | KEEP + TEST |
| SQL injection | LIKELY-COMPLETE | SQLAlchemy 2.x async ORM, `select()` throughout; no raw string SQL seen in sampled code. Needs a full parameterization sweep of search/filter/report/export paths (Doc 4 §14). | VERIFY |
| Secret management | COMPLETE | Pydantic `Settings` fail-fast at startup; no hardcoded secrets; two historical `print(DATABASE_URL)` leaks already fixed (tech-debt §2.4). AI-prompt `redact_secrets` (`ai_provider.py:152`). | KEEP |
| Audit logging | PRESENT | `audit_service.py`; immutability/tamper-evidence (Security §31 advanced) not implemented — acceptable for launch. | KEEP / DEFER advanced |
| RLS | MISSING (defense-in-depth) | Disabled in Supabase (tech-debt §6). App-layer is the real boundary. | HARDEN (post-launch) |
| File upload security | PARTIAL (corrected) | **Two real upload paths exist** (earlier "no upload path" was wrong): (1) multimodal ARIA `ai_assistant.py` image/document — 8 MB cap enforced via `_read_capped` ✓, **but MIME trusted from client `content_type`, no magic-byte/signature check, no extension allowlist**; (2) import `production.py:272` — **uncapped `file.read()`** (DoS risk). Module media (`avi_bird_media` etc.) remain URL-refs. No malware scan. Uploaded bytes are processed in-memory (Gemini Vision / parsed records), not written to an executable path — RCE-via-upload risk low but not formally verified. Security §16 partially met. | HARDEN (P1) |
| Prompt-injection / AI-as-boundary | PARTIAL-COMPLETE | Deterministic-first routing, context is bounded farm data, secret redaction. AI authorization inheritance needs an explicit test (Master Index §29, Doc 4 §52–54). | KEEP + TEST |

### 2.2 Correctness & Data Integrity — **STRONG**

| Requirement | State | Evidence | Class |
|---|---|---|---|
| Postgres, ACID, transactions | COMPLETE | async SQLAlchemy + asyncpg; `config.py` pool config; multi-step ops in services. | KEEP |
| UUID PKs, ownership + audit fields | COMPLETE | `models/base.py` `AGRIOSBase` (org/farm/created_by/…/deleted_at). | KEEP |
| Soft delete | COMPLETE | `deleted_at` filters throughout (`dependencies.py`, all list queries). | KEEP |
| Immutable finance | PRESENT | Ledger/valuation engines; reversing-entry pattern per finance services. | KEEP (verify in finance audit) |
| Migrations | COMPLETE | 86 sequential migrations, seed reference data (roles/plans/categories/species). | KEEP |
| Migration 028 column mismatch | DEFECT | `notifications` physical `metadata_` vs ORM `metadata` (tech-debt §1.1). Feature-gated, low exposure. | HARDEN (fix as migration ≥087) |

### 2.3 Production Reliability — **GOOD, gated by CI + load test**

| Requirement | State | Evidence | Class |
|---|---|---|---|
| Health check | COMPLETE | `main.py:165` returns 503 when DB down. | KEEP |
| Startup validation / release recording | COMPLETE | `run_startup_validation`, `record_release` in lifespan (`main.py:66–90`). | KEEP |
| Single-leader scheduler | COMPLETE | Postgres advisory-lock leader election (`main.py:92–116`, `services/scheduler.py`). | KEEP |
| **CI enforcement** | **BROKEN** | Workflows at `infrastructure/github/workflows/` — GitHub reads `.github/workflows/`. No gate on PRs (tech-debt §1.2). | **HARDEN (fix first)** |
| Backups / restore test | PARTIAL | `backup_service.py` exists; restore-tested evidence absent (Doc 4 §105–107). | HARDEN |
| Graceful external-service degradation | COMPLETE (AI) | AI degrades Gemini→Claude→offline. Payments/SMS degrade paths depend on those integrations. | KEEP |

### 2.4 Architecture — **COMPLETE**

Modular monolith with strict layering (Architecture §2–5). Controllers thin, services/engines hold logic, repository-style data access, domain engines separate from HTTP/SQL. Module independence honored (per-species services/engines). Adapters: AI via `ai_provider`/`mission_control`. **KEEP.** Minor: no formal API-gateway layer (Doc 8 recommendation) — optional.

### 2.5 Performance & Scalability — **DEFER by design**

Caching, Redis, queue workers, read replicas, CQRS, partitioning are **absent** and **deliberately deferred** with explicit trigger points (tech-debt §8; Master Index §8–9 "no premature complexity"). In-process rate-limit/cache/scheduler are honest for the 2-worker single-service deployment. **The 1,000-user load test (Doc 4 §95–103) has not been run** — this is the gate that converts these DEFERs into BUILDs if it fails. **DEFER + measure.**

### 2.6 AI Safety & Correctness — **STRONG core, credential hardening**

Deterministic-first honored (Blueprint §4, AI Std §3); offline grounding keeps ARIA honest; secret redaction present; medical never-diagnose enforced by caller (`ai_provider.py:99`). **Gaps:** single Gemini key vs. two-key rotation + health states (Doc 3 §16–19); AI cost controls are context/word caps + per-plan quotas (no provider hard cap — acceptable, monitored). **HARDEN (rotation).**

### 2.7 Observability — **GOOD**

Sentry (prod-gated), Prometheus-style `MetricsMiddleware` + registry, request/correlation IDs, structured logging, `/health`. **Missing:** PostHog (product analytics), distributed tracing. Both **DEFER** (Observability §21 "analytics failure must never be critical"). **KEEP + DEFER analytics.**

### 2.8 UX / Accessibility — **NOT AUDITED THIS PASS**

Frontend exists (Vite/React/Tailwind, brand green `#076524` corrected). Loading/empty/error-state, a11y, and reduced-motion coverage need a dedicated frontend sweep (Doc 10). Known placeholder screens: KI-02 ProductionRecord, KI-08 market-price admin UI (tech-debt §4). **Deferred to a frontend-specific audit.**

---

## 3. Launch-module inventory (Prep-Doc §57, §63)

| Module | Backend | Migrations | ARIA | Frontend | Status |
|---|---|---|---|---|---|
| Poultry (flock) | ✅ | 001–030 core | ✅ | ✅ | COMPLETE (some KI placeholders) |
| Aviculture | ✅ | 053–054 | ✅ | ✅ | COMPLETE |
| BSF | ✅ | 061 | ✅ | ✅ | COMPLETE |
| Rabbit | ✅ | 066–070 | ✅ | ✅ | COMPLETE |
| Goat + Sheep (SR) | ✅ | 072–078 | ✅ | ✅ | COMPLETE |
| Swine | ✅ | 079–086 | ✅ | ✅ (workspace) | COMPLETE (M12 readiness audit done) |
| Operations Planner | ✅ | 071 | ✅ | partial | Backend complete; FE/integration pending |
| **Fish / Aquaculture** | ❌ | — | ❌ | ❌ | **MISSING** |

---

## 4. Credentials & external services (Doc 3, Doc 4 §126–129)

| Service | Standard says | Repo state | Class |
|---|---|---|---|
| Paystack | Required; server-side verify + webhook + idempotency | **Absent**; manual M-Pesa, DB-tracked plans only | DECISION |
| Gemini | 2 keys, rotation, health states | 1 key `GEMINI_API_KEY`; Claude fallback; offline | HARDEN |
| Claude (Anthropic) | Not in standards | Present as AI fallback (`CLAUDE_API_KEY`) | KEEP (document) |
| Africa's Talking (SMS/OTP) | Backend-only, rate-limited | Configured, sandbox default, dormant at launch (deliberate) | KEEP |
| Email provider | Backend-only | `console` default; SMTP wired; **Email-OTP delivery code incomplete** (tech-debt §6) | BUILD (Phase 2 auth) |
| PostHog | Selective analytics | Absent | DEFER |
| Object storage | Signed uploads, non-executable | Absent (URL refs only) | HARDEN/BUILD if uploads ship |
| Sentry | Error monitoring | Present, prod-gated | KEEP |
| Redis | Cache/sessions/locks/queue | Absent (in-process) | DEFER |

All secrets are env-provided and fail-fast validated; no frontend secret exposure observed in sampled config. A production frontend **bundle secret scan** (Doc 4 §109) still needs to be run.

---

## 5. Recommended implementation order (Doc 4 §6, §147)

Ordered by the standards' own priority (security → correctness → reliability → payments → performance), and by dependency. **Nothing here starts without your approval.**

**Gate 0 — Enforcement (cheap, unblocks everything):**
1. **Fix CI** — move `infrastructure/github/workflows/` → `.github/workflows/`, verify paths, confirm tests+type-checks+security-scan run on PRs. *Until this lands, no other gate is trustworthy.*
2. Run the full test suite against local Postgres; publish real pass/fail (§9). Establish the true baseline.

**Gate 1 — Security hardening (highest priority, low blast radius):**
3. Bound refresh-token input to ≤72 bytes (or SHA-256 pre-hash) so bcrypt ≥5.0 is safe.
4. Add an automated **tenant-isolation / IDOR test sweep** across farm-scoped endpoints (Doc 4 §17, §81) and an **AI-authorization-inheritance** test (§52–54).
5. Full **SQL-injection / parameterization sweep** of search/filter/sort/report/export/import paths (Doc 4 §14).
6. Extend rate limiting beyond `/auth` to AI, exports, imports (per-endpoint, still in-process pre-Redis).

**Gate 2 — Correctness fixes:**
7. Migration ≥087 to resolve `notifications.metadata_` mismatch (Doc 4 §117 migration discipline).

**Gate 3 — Payments (DECISION-gated, see §6):**
8. If building Paystack: adapter + server-side verify + signed idempotent webhooks + entitlement reconciliation (Doc 4 §56–61) — full test matrix.

**Gate 4 — AI credential hardening:**
9. Two-key Gemini rotation with health-state machine + usage tracking (Doc 3 §16–21). Backend-only, additive.

**Gate 5 — Load & scale (evidence-driven):**
10. Run staged 100→1,000-user load test (Doc 4 §99). **Only if it fails** do the deferred Redis/cache/queue/read-replica items become BUILDs, targeted at the measured bottleneck.

**Gate 6 — Recovery & production config:**
11. Backup **restore** test (§106); production config + frontend bundle secret scan (§108–110).

**Gate 7 — Final:**
12. Re-run gap matrix, regression, security tests; produce `docs/GREENA_PRODUCTION_READINESS_REPORT.md` (Doc 4 §143).

**Deferred (scope decisions, not order): Fish/Aquaculture, PostHog, distributed tracing, RLS, CQRS/partitioning/read-replicas, offline-first write queue.**

---

## 5b. Priority register (P0–P3) — every item

Priority = urgency to launch (not effort). **P0** launch-blocking (critical security/correctness/process). **P1** high, required before launch. **P2** medium, hardening/quality. **P3** low / future / deferred.

| Pri | Item | Class | Status |
|---|---|---|---|
| **P0** | CI enforcement (workflows in wrong path) | HARDEN | ✅ Gate 0 — `ci.yml` activated |
| **P0** | Tenant isolation enforced on all farm-scoped reads | KEEP+TEST | ✅ Gate 2 — 220-route sweep, non-member denied, 0 leaks |
| **P0** | AI/ARIA context inherits caller permissions | KEEP+TEST | ✅ Gate 2 — explicit deny test |
| **P0** | SQL-injection / parameterization | KEEP | ✅ Verified clean |
| **P0** | Refresh-token bcrypt-72-byte safety | HARDEN | ✅ Gate 2 — bounded, 0 forced logout |
| **P0** | Auth core (Argon2id, JWT, sessions), RBAC, secret mgmt | KEEP | Verified; no change |
| **P1** | Gemini two-key rotation + health-state machine | HARDEN | Open — later AI gate |
| **P1** | Backup **restore** test (not just backup exists) | HARDEN | Open |
| **P1** | Staged 100→1,000-user load test | DEFER→measure | Open — gates the scale DEFERs |
| **P1** | Cross-farm **write/mutation** IDOR sweep | KEEP+TEST | Open — read sweep proves the shared chokepoint; writes use same guard |
| **P1** | Rate-limiting beyond `/auth` (exports/imports) | HARDEN | **Revised** — deferred from Gate 2 (see §6b); needs limits policy |
| **P1** | File-security posture (if/when real uploads ship) | HARDEN→BUILD | Open — currently URL-refs only |
| **P2** | RLS defense-in-depth | HARDEN | Post-launch |
| **P2** | Access-token transport (localStorage→memory) | HARDEN | Open — bounded by 15-min expiry |
| **P2** | Frontend UX/a11y audit (Doc 10) | — | Not yet audited |
| **P2** | `datetime.utcnow()` deprecation cleanup (1.7k warnings) | HARDEN | Open — cosmetic |
| **P2** | PostHog analytics; distributed tracing | DEFER | Optional |
| **P3** | Fish/Aquaculture module | BUILD | Future — after hardening (owner) |
| **P3** | Redis / cache / queue / read-replicas / CQRS / partitioning | DEFER | Load-test-gated |
| **P3** | Advanced security (tamper-evident logs, adaptive risk) | DEFER | Beyond launch |
| **P3** | Paystack payments | DEFER | Separate post-hardening project (owner) |

## 6. Decisions — RESOLVED (owner, 2026-08-10)

1. **Fish/Aquaculture → BUILD (future launch module).** Classified BUILD, **not** built during hardening. This pass only identifies shared infrastructure that must support it later (see §6a). Fish is developed **after** the platform-hardening phase unless explicitly instructed otherwise. Focus stays on the seven completed modules + shared platform.
2. **Payments → keep manual M-Pesa for launch.** Recorded as an **accepted, documented divergence** from the Paystack mandate (Doc 3 §9–15). No payment-provider code this cycle; Paystack remains a HIGH backlog item, revisited post-launch. `subscription_plans` + manual founder-applied M-Pesa remain the launch billing path (tech-debt §5).
3. **Execution boundary → Gate 0 + Gate 1 only, then STOP and report** before payments / AI-rotation / load-test / scale work.

### 6a. Shared infrastructure Fish/Aquaculture will consume (no build now — for future planning)

When Fish is built it must **reuse**, not re-create (Master Index §53–55, Module Std §25): the platform auth/RBAC (`core/permissions.py` — add an `aqua:*` permission block mirroring `swine:*`), farm-scoped tenant isolation (`require_farm_access`), the shared `AGRIOSBase` ownership/audit/soft-delete mixin, the finance/valuation engines, ARIA + Mission Control routing (`aria_router`, `ai_provider`), the reporting/export services, automation/reminder engine, and the Alembic migration chain (next free number at build time). Use an existing single-species housed-livestock module (**Swine, Module 20**) as the structural template; pond/tank housing maps to the swine group/pen hierarchy, water-quality readings map to the BSF environment-reading pattern (`bsf_environment_*`).

---

## 6b. Gate execution log (live)

> **Gate numbering** follows the governing documents (owner-confirmed): **Gate 1** = this Audit & Gap Matrix; **Gate 2** = Security & Core Platform Hardening. (Earlier turns used a looser "Gate 0/1" label; unified here.)

**Gate 1 — Repository Audit & Gap Matrix: DONE, APPROVED.** This document, six-label classification, P0–P3 register, resolved decisions, real baseline **`1846 passed, 0 failed`** (271s, local Postgres 16, seeded via the 86-migration chain).

**Gate 2 — Security & Core Platform Hardening: COMPLETE (this turn)**
- ✅ **CI activated** — `ci.yml` → `.github/workflows/ci.yml` (`git mv`, history preserved). `deploy-*.yml` **left parked** (prod auto-deploy on push to `main` — owner decision, **OPEN**).
- ✅ **Refresh-token bcrypt-72-byte bound** — `create_refresh_token()` now `token_urlsafe(48)` (64 chars, 384-bit entropy); new tokens survive a future bcrypt-major upgrade, existing longer tokens keep verifying on pinned bcrypt 4.x and drain within `REFRESH_TOKEN_EXPIRE_DAYS`. No forced logout.
- ✅ **Tenant-isolation / cross-farm IDOR sweep** — new `tests/integration/test_tenant_isolation_sweep.py`: a non-member is denied on **all 220** farm-scoped GET routes (runtime-discovered) — 0 leaks, 0 5xx — plus a curated cross-module subset, an AI/ARIA-context deny test, and an unauth (401) test. Converts the audit's biggest "VERIFY" item into regression-guarded evidence.
- ✅ **SQLi sweep — CLEAN** (no code change; ORM-only, `text()` static/bound).
- ✅ **Migration 028 "defect" — already resolved** by `031_fix_notifications_metadata_column.py`; live schema has `metadata` (+`priority`/`is_archived`). **No migration created.** (Correction to tech-debt §1.1 — see §8.)

**Plan revisions (per owner clause — revise when implementation reveals facts):**
- **Dropped** the planned migration-028 fix — the defect is already fixed; creating a migration would violate "don't fix what isn't broken" (Master Index §10, §51).
- **Deferred** rate-limiting broadening out of Gate 2 → P1 follow-up. Reason: AI is already governed by `ai_usage_log` + per-farm `monthly_budget_usd` (adding AI rate-limits would duplicate existing controls — Master Index §53), there are no uploads (URL-refs) and no payments (M-Pesa), so the only remaining surface is exports/imports — a smaller, limits-policy-dependent change best reviewed on its own rather than bundled with the isolation-evidence work.
- **Added** an explicit **write/mutation IDOR** sweep as a P1 follow-up (the read sweep proves the shared `require_farm_access` chokepoint; writes use the same guard, but the standards want writes tested directly — Doc 4 §17).

**Gate 3 — File-upload, write-path & data-layer hardening: COMPLETE (see `docs/GATE_3_REPORT.md`).** P0 all implemented + verified: shared upload validator (`app/core/uploads.py` — size caps, extension allowlist, magic-byte verification, trusted MIME) wired into the 3 upload sites (multimodal image/doc + the previously **uncapped** import); write-path IDOR proven across all **116** farm-scoped POST routes + a no-state-change assertion; cross-org isolation proven bidirectionally. P1 reviewed with live-DB evidence: pooling **KEEP** (31-conn ceiling < Supabase 60); index review — **208 FKs lack indexes but are overwhelmingly audit/actor columns**, bulk-indexing rejected per Doc 3 §14, targeted additions deferred to load-test evidence; cache/query tuning **DEFER** to the load test. No migrations.

## 7. What is explicitly NOT a gap (do not "fix")

- In-process scheduler/cache/rate-limit — deliberate, trigger-gated (tech-debt §8).
- Manual admin promotion — deliberate security control (tech-debt §6).
- No offline write queue, no native app, Kenya-only formats — frozen V1 decisions.
- No AI disease diagnosis / autonomous actions — permanent ARIA boundary (`ARIA_AI.md` §2–3, memory [[greena-frozen-decisions]]).
- Feature flags — **present** (Module 10 `admin_platform`), contrary to tech-debt §6 which is stale on this point.

---

## 8. Corrections to the team's own records (found during audit)

- `KNOWN_TECHNICAL_DEBT.md §6` says "No feature-flag system" — **outdated**; feature flags shipped in Module 10 (`app/models/admin_platform.py`, `admin_platform_service.py`, `endpoints/admin_platform.py`).
- `KNOWN_TECHNICAL_DEBT.md §1.1` (Migration 028 `notifications.metadata_` mismatch) — **already resolved** by `031_fix_notifications_metadata_column.py`; the live migrated schema exposes `metadata` (+ later `priority`/`is_archived`/`archived_at`), matching the ORM. Verified against the live DB during Gate 2. This "current defect" should move to the resolved section of the debt doc.
- Standards mandate **Paystack**; the live product deliberately uses **manual M-Pesa** — a standards-vs-repo divergence, reconciled explicitly by owner decision (§6.2): M-Pesa kept for launch, Paystack a separate post-hardening project.

## 9. Verification limits of this pass (Doc 4 §123 — no fabricated completion)

- **Test pass/fail: UNVERIFIED.** 146 test files exist; `tests/conftest.py` builds `agrios_test` via Alembic migrations and needs a reachable Postgres. Supabase is unreachable from here (memory [[local-postgres-for-tests]]); I did not stand up local Postgres this pass. No test was run — so none is claimed to pass.
- **Load test: NOT RUN.** No 1,000-user evidence exists in-repo.
- **Frontend a11y/UX, finance-engine correctness, full SQLi sweep: NOT YET performed** — flagged for their own passes.
- Claims above are limited to code I actually read; breadth-dependent items (IDOR across *all* endpoints, parameterization across *all* queries) are marked VERIFY/TEST, not COMPLETE.
