# AGRIOS KNOWN TECHNICAL DEBT

**Read `AGRIOS_MASTER_CONTEXT.md` and `CODING_STANDARDS.md` Section 7 (Carryover Policy) first.** This document exists so that a future engineer or AI agent never has to rediscover a known weakness from scratch. Every entry below is either a documented Known Issue (KI) code from the sprint execution process, a specific code-level defect identified during post-launch verification, or a deliberate V1 scope exclusion recorded as an intentional gap rather than an oversight. Entries are organized by category; where a KI code exists, it is given so it can be cross-referenced against `PROJECT_HISTORY.md` and future handover reports.

**Maintenance note (Phase 1 — Deployment & Stabilization):** this document distinguishes **current** debt (Section 1) from **resolved historical issues** (Section 2). Section 2 exists specifically so that a future contributor does not spend time chasing a bug that no longer exists. When a current defect is fixed, move its entry into Section 2 with the resolution recorded — do not silently delete it, and do not leave it in the "current" list.

---

## 1. Current Code-Level Defects (Verified Present, Not Yet Fixed)

These are present in the source as of this writing, with exact file evidence. Each is recorded with enough detail that a future fix does not need to re-derive the diagnosis.

### 1.1 Migration 028 (`notifications`) — column name mismatch with the project convention

The `notifications` table's JSONB column was created in its migration as a physical column literally named `metadata_` (`backend/alembic/versions/028_create_notifications.py`), rather than following the project-wide convention of a physical column named `"metadata"` mapped to the Python attribute `metadata_` (`DATABASE_ARCHITECTURE.md` Section 1). The `Notification` model inherits `metadata_` from `AGRIOSBase`, which maps to a physical column named `"metadata"` — so the ORM and the physical schema disagree on the column name.

**Status:** tracked, to be inspected **after** deployment succeeds, per the Phase 1 governing rules — the frozen migration chain (001–030) must not be edited, and any fix must be introduced as Migration 031 or later, only if the issue is confirmed reproducible against the deployed schema. **Risk if left unaddressed:** an ORM read/write path that materialises the `metadata_` attribute against the `notifications` table will reference a `metadata` column that does not exist. The notifications feature is currently gated behind an unresolved routing carryover (KI-07), which limits live exposure, but this should be verified — not assumed — once the app is deployed.

### 1.2 GitHub Actions workflow location

CI workflow files live at `infrastructure/github/workflows/` rather than the `.github/workflows/` path GitHub actually reads. As a direct result, **CI is not currently running against pull requests** — the "tests + type checks on every PR" step described in the intended production workflow (`DEPLOYMENT_GUIDE.md` Section 8) is not presently enforced by GitHub itself. **Recommended fix:** move the workflow files to the correct path; verify they still reference correct paths internally once moved, since a path-dependent workflow file relocated without review can fail silently in new ways.

---

## 2. Resolved Historical Issues (Do NOT Re-investigate)

These issues were documented as open in earlier revisions of this handbook but have since been verified fixed in the source. They are retained here — rather than deleted — so a future contributor who encounters a stale reference elsewhere can confirm the issue is closed instead of re-diagnosing it. Where a cross-reference in a frozen document (`DATABASE_ARCHITECTURE.md`, `PROJECT_HISTORY.md`) still describes one of these as latent/open, treat this section as the current, authoritative status.

### 2.1 `DiseaseAlert.extended_metadata` redundant column — RESOLVED

Earlier revisions (this document's former §1.1, plus `DATABASE_ARCHITECTURE.md` Section 1 and `PROJECT_HISTORY.md` Section 11) described `DiseaseAlert` as still declaring a redundant `extended_metadata` column on top of the `metadata_` it inherits from `AGRIOSBase`, i.e. the twin of the `VaccinationRecord` `DuplicateColumnError`. **Verified resolved:** a full-codebase search returns zero occurrences of `extended_metadata` in `backend/`, and `backend/app/models/health.py` `DiseaseAlert` no longer declares it. The application imports cleanly (mapper configuration succeeds), so the historical `DuplicateColumnError` risk is gone.

### 2.2 `finance.py` duplicate wrong-path import — RESOLVED

`backend/app/api/v1/endpoints/finance.py` imported `NotFoundException` from the nonexistent `app.core.exceptions` inside `refresh_flock_snapshot`, which would raise `ImportError` when that endpoint was invoked. **Verified resolved:** corrected to `from app.exceptions import NotFoundException`, consistent with the rest of the codebase. No remaining references to `app.core.exceptions` exist in `backend/`.

### 2.3 Migration 009 (`farm_members`) `member_status` ENUM creation — RESOLVED

Earlier revisions (former §1.4, `DATABASE_ARCHITECTURE.md` Section 4.4 Pattern B, `PROJECT_HISTORY.md` Section 11) described Migration 009 as declaring a `member_status` enum with `create_type=False` that was never actually created, plus a stray debug `print()` in `backend/app/models/farm.py`. **Verified resolved:** Migration 009 now declares the enum once and calls `member_status_enum.create(op.get_bind(), checkfirst=True)` before reusing the same object in the column definition; the migration scan of `backend/alembic/versions/` confirms every enum that uses `create_type=False` (009, 011, 012, 021) makes the corresponding `.create(..., checkfirst=True)` call. No `print()` remains anywhere in `backend/app/models/`.

### 2.4 Startup credential leaks (config + Alembic) — RESOLVED

Two module-level `print()` statements wrote the full `DATABASE_URL` (including the password) to stdout — and therefore into Railway deploy logs — on every application start (`backend/app/config.py`) and every `alembic upgrade head` (`backend/alembic/env.py`). **Verified resolved:** both prints removed. Additionally, a duplicate, unescaped `sqlalchemy.url` assignment in `env.py` (which overrode the `%`-escaped value and would crash `alembic upgrade head` on a DB password containing `%`) was removed; the `%`-escaped assignment is now authoritative.

### 2.5 `/health` returned HTTP 200 while degraded — RESOLVED

`GET /health` previously returned HTTP 200 with a `"degraded"` body even when the database was unreachable, so Railway's status-code-based health check could not detect an unhealthy instance. **Verified resolved:** `/health` now returns HTTP 503 when the `SELECT 1` probe fails and 200 only when the database is reachable; the response body shape is unchanged.

### 2.6 Pre-correction brand green (`#16a34a`) in shipped frontend — RESOLVED

Four hardcoded instances of the Sprint 0 placeholder Tailwind green `#16a34a` (browser `theme-color`, PWA manifest `theme_color`, ErrorBoundary button, finance category-bar fallback) survived into the frontend despite `DESIGN_SYSTEM.md` and `PROJECT_HISTORY.md` Section 4 mandating the true logo green `#076524`. **Verified resolved:** all four replaced with `#076524`; the only remaining `#16a34a` reference is the cautionary comment in `tailwind.config.ts`.

---

## 3. Shipped Modules Not Yet Fully Reflected in the Handbook

### 3.1 Farm Data Export Module (present in V1 source — DOCUMENTED, retained)

A farm data export module exists and is wired into the running application, exposing three endpoints under the farm-scoped path:

- `GET /api/v1/farms/{farm_id}/export/pdf` — a branded PDF report
- `GET /api/v1/farms/{farm_id}/export/excel` — a multi-sheet Excel workbook
- `GET /api/v1/farms/{farm_id}/export/csv` — a flat CSV of daily logs

It is implemented in `backend/app/api/v1/endpoints/exports.py` and `backend/app/services/export_service.py`, registered in `backend/app/api/v1/router.py`, and depends on `reportlab` and `openpyxl` (both present in `requirements.txt`). Access is permission-gated by `Permission.FINANCE_VIEW`. It reads existing data only and introduced **no** migration, so the frozen 30-migration chain (DB-10) is unaffected.

This module post-dates the Sprint 0–10 sequence described in `PROJECT_HISTORY.md`. Earlier revisions of this document listed "No report export (PDF/Excel)" as a deliberate V1 scope exclusion; that statement is **superseded** — the capability shipped. Per the Phase 1 directive, working functionality is retained and documented rather than removed. `ROADMAP.md` still lists PDF export as a Phase 2 item; that roadmap entry should be read as already-delivered-early, and reconciled in `ROADMAP.md` under the same override-and-document discipline used for any scope change (`ROADMAP.md` Section 9) — it is flagged here so the discrepancy is not mistaken for a defect.

---

## 4. Incomplete Modules and Placeholder Screens

| Code | Description | Status | Notes |
|---|---|---|---|
| KI-02 | `ProductionRecordScreen` renders a `ComingSoonScreen` placeholder despite its backend API and schemas already existing | Deferred to Phase 2 | The backend is ready; only the frontend form is missing. This is a comparatively low-risk gap to close whenever prioritized. |
| KI-03 | `CreateFlockScreen` depends on a houses list, which requires farm structure (units/houses) to already be set up — creating an awkward first-time onboarding sequence if a new farm owner tries to create a flock before setting up any houses | Deferred to Phase 2 | Candidate fix: either force houses setup earlier in onboarding, or allow flock creation without a house and backfill the association later. |
| KI-04 | The `/flock` and `/health` bottom-navigation tabs redirect to a generic `/farms` screen rather than resolving directly to the user's actual default/active farm | Deferred to Phase 2 | Requires a `useActiveFarm()`-style resolver hook; noted again as KI-07 in a later sprint for the notifications tab specifically. |
| KI-07 | `NotificationsScreen` requires `/farms/:farmId/notifications`, but the bottom-nav notifications entry point currently only navigates to the generic `/farms` redirect | Deferred (requires `useActiveFarm()`) | Same underlying root cause as KI-04 — a single default-farm-resolution mechanism would likely close both at once. Also limits live exposure of defect §1.1 above. |
| KI-08 | No admin UI exists for publishing market prices — `super_admin` must call the API directly (e.g. via a raw HTTP client) to add a price in V1 | Deferred, Admin console Phase 2+ scope | The endpoint (`POST /market/prices`) exists and is permission-gated correctly; only the admin-facing form is missing. |

**Escalation rule reminder** (`CODING_STANDARDS.md` Section 7): if any KI above is deferred across three consecutive sprints without resolution, it is meant to be escalated to Architecture Review rather than continually re-deferred — several of the KIs above are already carrying forward from early sprints and are candidates for that escalation the next time sprint planning resumes.

---

## 5. Deliberate V1 Scope Exclusions (Not Bugs — Recorded for Clarity)

These are not defects; they are intentional simplifications whose absence is sometimes mistaken for an oversight. Each is fully explained in `AGRIOS_MASTER_CONTEXT.md`; they are indexed here for completeness.

- **No true offline data entry** — the app shows an offline banner and keeps cached data visible, but cannot save new data without a live connection; data entered during an outage is lost rather than queued. Full offline-first (local write queue + background sync) is Phase 3 scope by design (`AGRIOS_MASTER_CONTEXT.md` Section 4.2).
- **No integrated payment processing** — subscriptions are tracked in the database but money changes hands over M-Pesa outside the system, verified and applied manually by the founder (`AGRIOS_MASTER_CONTEXT.md` Section 5.1).
- **No native app store presence** — AGRIOS is a PWA by design (AD-09, frozen), not a gap awaiting a native rewrite.
- **No AI disease diagnosis, image analysis, or autonomous action-taking** — permanent or phased boundaries, fully specified in `ARIA_AI.md` Sections 2–3. These should never be treated as "todo" items to casually add.
- **No multi-currency, no non-Kenya phone formats, no additional languages beyond English/Swahili** — PD-02/PD-03, frozen for V1; genuinely Phase 2+/expansion work, not a bug.
- **SMS OTP and SMS notifications are inactive at V1 launch** — Africa's Talking credentials are not configured in the launch environment, so Email OTP is the intended launch verification channel and email is the intended launch outbound notification channel, even though phone registration and SMS delivery remain fully part of the architecture (`AGRIOS_MASTER_CONTEXT.md` Section 6.1; `SYSTEM_ARCHITECTURE.md` Section 5). This is a deliberate launch configuration, not a missing feature or a defect — see `DEPLOYMENT_GUIDE.md` Section 6.1 for the exact, code-free activation path. It should never be "fixed" by adding a temporary code branch or a workaround; the correct and only expected action is adding the Africa's Talking credentials to Railway when the business is ready to enable SMS. (Note: the *code-level* implementation of Email OTP delivery is tracked separately as Phase 2 authentication work per the deployment sequence — see Section 4 Architectural Weaknesses and `ROADMAP.md`. The scope exclusion here concerns SMS, which is deliberately dormant; it is not a statement that Email OTP is fully wired today.)

> Note: "No report export (PDF/Excel)" was previously listed here as a deliberate exclusion. That exclusion no longer holds — the export module shipped and is documented in Section 3.1.

---

## 6. Architectural Weaknesses Requiring Attention as the Platform Grows

- **Single server, embedded scheduler (AD-13):** the backend runs as one Railway service with 2 Uvicorn workers, and all background jobs run inside that same process. Under heavy simultaneous load (roughly 1,000+ concurrent users, per current capacity estimates), this may degrade, and a server restart currently restarts all scheduled jobs with it. The documented upgrade path is first increasing worker count, then moving to a dedicated worker process (Celery + Redis) once a single job's execution time risks exceeding roughly 60 seconds — not before, per the "product before infrastructure" principle.
- **`bcrypt` version pin is load-bearing:** `requirements.txt` pins `bcrypt==4.2.1`. `create_refresh_token()` (`backend/app/core/security.py`) hashes a `secrets.token_urlsafe(64)` refresh token that is ~86 bytes long, and bcrypt only considers the first 72 bytes. bcrypt 4.x silently truncates to 72 bytes (so hashing succeeds), but bcrypt **5.0+ raises `ValueError: password cannot be longer than 72 bytes`**, which would make every OTP verification, PIN login, and token refresh return HTTP 500. Do not upgrade `bcrypt` past the 4.x line without first bounding the hashed input to 72 bytes (or pre-hashing) in `security.py`. Separately, the `(trapped) error reading bcrypt version` log line emitted by passlib 1.7.4 against modern bcrypt is cosmetic — hashing still works.
- **Email OTP delivery is not yet implemented in code (Phase 2 authentication work):** the authentication service, schemas, and OTP flow are currently phone/identifier-shaped and deliver via SMS only; there is no email-provider integration or `EMAIL_PROVIDER_API_KEY`/`EMAIL_FROM_ADDRESS` handling in `config.py` yet. The channel-agnostic identity architecture is documented and approved (`AGRIOS_MASTER_CONTEXT.md` Section 6.1), but the implementation is deliberately sequenced **after** successful deployment per the Phase 1 directive. This is tracked as the highest-priority Phase 2 item, not a silent gap.
- **No push notifications** — the PWA does not send browser push notifications (this would require a dedicated Service Worker push implementation); only email, SMS (once activated), and in-app notifications exist today.
- **No feature-flag system** — V1 has no mechanism to disable a shipped feature short of a full code deploy (removing a route, or returning a 503 with an explanatory message). A proper feature-flag system (a simple database-backed flag table, or a third-party service) is planned but not yet built.
- **Manual admin promotion** — becoming `super_admin` requires direct SQL access; this is currently a deliberate security control (`AGRIOS_MASTER_CONTEXT.md` Section 6.4), but it also means there is no operational path to add a second `platform_admin` staff member without similarly manual intervention, which will need attention once the founder is no longer the sole operator.
- **RLS (Row Level Security) is disabled in Supabase** — AGRIOS enforces all authorization at the application layer, and RLS is available as a defense-in-depth addition but has not yet been configured. This is recorded as a hardening opportunity, not a current vulnerability, since the actual authorization boundary is the application's permission system, not RLS.

---

## 7. Business and Operational Weaknesses

- **Manual plan upgrades/downgrades** — changing a farm's subscription tier requires an admin editing the database or admin panel directly; there is no self-serve billing flow and no automated proration.
- **Email and SMS cost/abuse exposure** — this applies to whichever OTP channel is currently active, not to SMS specifically: at V1 launch, Email OTP abuse (an attacker triggering unlimited emails to arbitrary addresses) is the intended live exposure once email delivery is wired, bounded by the same rate limit that will later apply to SMS (`AGRIOS_MASTER_CONTEXT.md` Section 6.3); once Africa's Talking is configured, Africa's Talking bills per message, and a bug or abuse of the OTP endpoint beyond the existing rate limit could generate meaningful unexpected cost at scale. Whichever channel is active should be actively monitored via its own provider dashboard rather than assumed safe purely because a rate limit exists in the application layer.
- **AI cost exposure** — bounded but non-zero; monitored via the admin AI usage screen and controlled primarily through the 8,000-token context cap, 150-word response cap, and per-plan monthly quotas (`ARIA_AI.md` Section 8) rather than through any hard spending cap at the provider level.
- **Single-region (Kenya) assumption baked into UX copy and validation** — phone number format validation, currency formatting, and language options are all hardcoded to the Kenya-first assumption; expanding to a second country is a real engineering project, not a configuration change (`ROADMAP.md`).

---

## 8. Scalability Concerns and Their Documented Trigger Points

Rather than speculatively building for scale the product does not yet have, the project records specific, observable triggers for when to revisit each of the following — consistent with the "product before infrastructure" principle:

| Concern | Trigger to act | Not before |
|---|---|---|
| Railway CPU/memory pressure | Sustained high CPU during peak hours, or OOM errors in logs | Do not pre-emptively upgrade the Railway plan on a hunch. |
| Background job execution time | Any single scheduled job's execution time approaches 60 seconds | Do not introduce Celery/Redis before this is actually observed. |
| Database read contention | Admin/report queries visibly compete with write traffic for resources | Consider a Supabase read replica only once this is observed, not preemptively. |
| Session lookup cost | Refresh/logout scans of the `sessions` table become a measurable latency or CPU cost under real login volume | Post-launch optimization only (add a token identifier/index); explicitly not a launch blocker. |
| Moving off Railway entirely | 1,000+ active farmers with real peak-hour bursts, Railway billing exceeding roughly $100/month, or a compliance requirement (ISO 27001, SOC 2, data residency in Kenya) appears | AWS ECS / Google Cloud Run are the documented next steps; this is explicitly *not* a V1 or near-term concern. |
| Kubernetes | 10+ independently-scaling microservices, a dedicated DevOps team, and hundreds of requests per second sustained | The operational guidance is explicit and worth repeating verbatim in spirit: if someone suggests AGRIOS needs Kubernetes now, they are over-engineering. |

---

## 9. How to Use This Document

Before starting any new feature work, check this document for an existing KI or defect that overlaps with the area being touched — several of the entries above are cheap to fix once discovered but easy to reintroduce or rediscover independently if this record is skipped. When a current defect (Section 1) is finally resolved, move it to Section 2 (Resolved Historical Issues) with the resolution recorded, and note the resolution in that sprint's handover report and, where relevant, in `PROJECT_HISTORY.md` — this document is meant to always reflect *current* known debt at the top and a trustworthy record of *closed* issues below it, so that no future contributor re-investigates a bug that no longer exists.
