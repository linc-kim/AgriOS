# AGRIOS KNOWN TECHNICAL DEBT

**Read `AGRIOS_MASTER_CONTEXT.md` and `CODING_STANDARDS.md` Section 7 (Carryover Policy) first.** This document exists so that a future engineer or AI agent never has to rediscover a known weakness from scratch. Every entry below is either a documented Known Issue (KI) code from the sprint execution process, a specific code-level defect identified during post-launch verification, or a deliberate V1 scope exclusion recorded as an intentional gap rather than an oversight. Entries are organized by category; where a KI code exists, it is given so it can be cross-referenced against `PROJECT_HISTORY.md` and future handover reports.

---

## 1. Specific Code-Level Defects (Verified, Not Yet Fixed)

These were identified during a post-launch verification audit with exact file/line evidence. Each is recorded with enough detail that a future fix does not need to re-derive the diagnosis.

### 1.1 `DiseaseAlert.extended_metadata` — the twin of an already-fixed bug

`backend/app/models/health.py` — `DiseaseAlert` declares its own `extended_metadata` mapped column on top of the `metadata_` column it already inherits from `AGRIOSBase`, following exactly the same redundant pattern that caused `VaccinationRecord`'s confirmed production `DuplicateColumnError` (`PROJECT_HISTORY.md` Section 11; full technical explanation in `DATABASE_ARCHITECTURE.md` Section 1). This was deliberately left untouched when the `VaccinationRecord` instance was fixed, because the specific error being chased at the time was `VaccinationRecord`'s, not `DiseaseAlert`'s — but the identical structural defect is present here and has not yet triggered a visible failure only because nothing has yet exercised the code path that would surface it. **Recommended fix:** remove `DiseaseAlert`'s redundant `extended_metadata` column, exactly as was done for `VaccinationRecord`, after confirming no other code references the attribute by that name.

### 1.2 Migration 028 (`notifications`) — column name mismatch with the project convention

The `notifications` table's `metadata` column was created in its migration as `metadata_` (the Python-facing attribute name) rather than following the project-wide convention of a physical column named `"metadata"` mapped to a Python attribute `metadata_` (`DATABASE_ARCHITECTURE.md` Section 1). This is dormant, not active — `notification_service.py`'s bulk-create functions that would exercise this column are not currently called from any live code path. **Risk if left unaddressed:** the next contributor who wires up bulk notification creation will hit a column-name mismatch that has nothing to do with their own change and may spend real time debugging it as if it were new.

### 1.3 Duplicate wrong-path import in `finance.py`

`backend/app/api/v1/endpoints/finance.py`, inside a function body, imports exception classes from `app.core.exceptions` — the same incorrect path that was fixed at module level in `finance_service.py` (the "V4" fix, `PROJECT_HISTORY.md` Section 11). This one was deliberately left in place at the time because it was not the import actually exercised at startup, but it is the same class of defect and will raise an `ImportError` the moment the specific function containing it is actually invoked. **Recommended fix:** correct the import path to `app.exceptions`, consistent with the rest of the codebase.

### 1.4 Migration 009 (`farm_members`) — `member_status` ENUM duplicate-creation risk

Full root-cause analysis is in `DATABASE_ARCHITECTURE.md` Section 4.4, Pattern B. In short: the migration declares a `member_status_enum` object with `create_type=False` and never calls `.create()` on it, while the column definition further down instantiates a second, separate ENUM object with the same name, also `create_type=False` — meaning neither object is actually responsible for issuing `CREATE TYPE member_status`, and the migration's correctness against a genuinely fresh database depends on some other mechanism doing so. A stray, unused debug `print("Enum create_type =", ...)` statement was also found in `backend/app/models/farm.py` near the corresponding model-side enum declaration, evidence that this exact issue had previously been under active, unfinished investigation. **Recommended fix (proposed, not applied):** call `member_status_enum.create(op.get_bind(), checkfirst=True)` immediately after declaring the object, and reuse that same object in the column definition instead of instantiating a second one; remove the stray `print()` statement in `farm.py` while the file is being touched for this fix.

### 1.5 GitHub Actions workflow location

CI workflow files live at `infrastructure/github/workflows/` rather than the `.github/workflows/` path GitHub actually reads. As a direct result, **CI is not currently running against pull requests** — the "tests + type checks on every PR" step described in the intended production workflow (`DEPLOYMENT_GUIDE.md` Section 8) is not presently enforced by GitHub itself. **Recommended fix:** move the workflow files to the correct path; verify they still reference correct paths internally once moved, since a path-dependent workflow file relocated without review can fail silently in new ways.

---

## 2. Incomplete Modules and Placeholder Screens

| Code | Description | Status | Notes |
|---|---|---|---|
| KI-02 | `ProductionRecordScreen` renders a `ComingSoonScreen` placeholder despite its backend API and schemas already existing | Deferred to Phase 2 | The backend is ready; only the frontend form is missing. This is a comparatively low-risk gap to close whenever prioritized. |
| KI-03 | `CreateFlockScreen` depends on a houses list, which requires farm structure (units/houses) to already be set up — creating an awkward first-time onboarding sequence if a new farm owner tries to create a flock before setting up any houses | Deferred to Phase 2 | Candidate fix: either force houses setup earlier in onboarding, or allow flock creation without a house and backfill the association later. |
| KI-04 | The `/flock` and `/health` bottom-navigation tabs redirect to a generic `/farms` screen rather than resolving directly to the user's actual default/active farm | Deferred to Phase 2 | Requires a `useActiveFarm()`-style resolver hook; noted again as KI-07 in a later sprint for the notifications tab specifically. |
| KI-07 | `NotificationsScreen` requires `/farms/:farmId/notifications`, but the bottom-nav notifications entry point currently only navigates to the generic `/farms` redirect | Deferred (requires `useActiveFarm()`) | Same underlying root cause as KI-04 — a single default-farm-resolution mechanism would likely close both at once. |
| KI-08 | No admin UI exists for publishing market prices — `super_admin` must call the API directly (e.g. via a raw HTTP client) to add a price in V1 | Deferred, Admin console Phase 2+ scope | The endpoint (`POST /market/prices`) exists and is permission-gated correctly; only the admin-facing form is missing. |

**Escalation rule reminder** (`CODING_STANDARDS.md` Section 7): if any KI above is deferred across three consecutive sprints without resolution, it is meant to be escalated to Architecture Review rather than continually re-deferred — several of the KIs above are already carrying forward from early sprints and are candidates for that escalation the next time sprint planning resumes.

---

## 3. Deliberate V1 Scope Exclusions (Not Bugs — Recorded for Clarity)

These are not defects; they are intentional simplifications whose absence is sometimes mistaken for an oversight. Each is fully explained in `AGRIOS_MASTER_CONTEXT.md`; they are indexed here for completeness.

- **No true offline data entry** — the app shows an offline banner and keeps cached data visible, but cannot save new data without a live connection; data entered during an outage is lost rather than queued. Full offline-first (local write queue + background sync) is Phase 3 scope by design (`AGRIOS_MASTER_CONTEXT.md` Section 4.2).
- **No integrated payment processing** — subscriptions are tracked in the database but money changes hands over M-Pesa outside the system, verified and applied manually by the founder (`AGRIOS_MASTER_CONTEXT.md` Section 5.1).
- **No report export (PDF/Excel)** — a frequently requested feature, explicitly deferred; farmers can view but not export their data in V1.
- **No native app store presence** — AGRIOS is a PWA by design (AD-09, frozen), not a gap awaiting a native rewrite.
- **No AI disease diagnosis, image analysis, or autonomous action-taking** — permanent or phased boundaries, fully specified in `ARIA_AI.md` Sections 2–3. These should never be treated as "todo" items to casually add.
- **No multi-currency, no non-Kenya phone formats, no additional languages beyond English/Swahili** — PD-02/PD-03, frozen for V1; genuinely Phase 2+/expansion work, not a bug.
- **SMS OTP and SMS notifications are inactive at V1 launch** — Africa's Talking credentials are not configured in the launch environment, so Email OTP is the sole functioning verification channel and email is the sole functioning outbound notification channel at launch, even though phone registration and SMS delivery remain fully part of the architecture (`AGRIOS_MASTER_CONTEXT.md` Section 6.1; `SYSTEM_ARCHITECTURE.md` Section 5). This is a deliberate launch configuration, not a missing feature or a defect — see `DEPLOYMENT_GUIDE.md` Section 6.1 for the exact, code-free activation path. It should never be "fixed" by adding a temporary code branch or a workaround; the correct and only expected action is adding the Africa's Talking credentials to Railway when the business is ready to enable SMS.

---

## 4. Architectural Weaknesses Requiring Attention as the Platform Grows

- **Single server, embedded scheduler (AD-13):** the backend runs as one Railway service with 2 Uvicorn workers, and all background jobs run inside that same process. Under heavy simultaneous load (roughly 1,000+ concurrent users, per current capacity estimates), this may degrade, and a server restart currently restarts all scheduled jobs with it. The documented upgrade path is first increasing worker count, then moving to a dedicated worker process (Celery + Redis) once a single job's execution time risks exceeding roughly 60 seconds — not before, per the "product before infrastructure" principle.
- **No push notifications** — the PWA does not send browser push notifications (this would require a dedicated Service Worker push implementation); only email, SMS (once activated, Section 3), and in-app notifications exist today.
- **No feature-flag system** — V1 has no mechanism to disable a shipped feature short of a full code deploy (removing a route, or returning a 503 with an explanatory message). A proper feature-flag system (a simple database-backed flag table, or a third-party service) is planned but not yet built.
- **Manual admin promotion** — becoming `super_admin` requires direct SQL access; this is currently a deliberate security control (`AGRIOS_MASTER_CONTEXT.md` Section 6.4), but it also means there is no operational path to add a second `platform_admin` staff member without similarly manual intervention, which will need attention once the founder is no longer the sole operator.
- **RLS (Row Level Security) is disabled in Supabase** — AGRIOS enforces all authorization at the application layer, and RLS is available as a defense-in-depth addition but has not yet been configured. This is recorded as a hardening opportunity, not a current vulnerability, since the actual authorization boundary is the application's permission system, not RLS.

---

## 5. Business and Operational Weaknesses

- **Manual plan upgrades/downgrades** — changing a farm's subscription tier requires an admin editing the database or admin panel directly; there is no self-serve billing flow and no automated proration.
- **Email and SMS cost/abuse exposure** — this applies to whichever OTP channel is currently active, not to SMS specifically: at V1 launch, Email OTP abuse (an attacker triggering unlimited emails to arbitrary addresses) is the live exposure, bounded by the same rate limit that will later apply to SMS (`AGRIOS_MASTER_CONTEXT.md` Section 6.3); once Africa's Talking is configured, Africa's Talking bills per message, and a bug or abuse of the OTP endpoint beyond the existing rate limit could generate meaningful unexpected cost at scale. Whichever channel is active should be actively monitored via its own provider dashboard rather than assumed safe purely because a rate limit exists in the application layer.
- **AI cost exposure** — bounded but non-zero; monitored via the admin AI usage screen and controlled primarily through the 8,000-token context cap, 150-word response cap, and per-plan monthly quotas (`ARIA_AI.md` Section 8) rather than through any hard spending cap at the provider level.
- **Single-region (Kenya) assumption baked into UX copy and validation** — phone number format validation, currency formatting, and language options are all hardcoded to the Kenya-first assumption; expanding to a second country is a real engineering project, not a configuration change (`ROADMAP.md`).

---

## 6. Scalability Concerns and Their Documented Trigger Points

Rather than speculatively building for scale the product does not yet have, the project records specific, observable triggers for when to revisit each of the following — consistent with the "product before infrastructure" principle:

| Concern | Trigger to act | Not before |
|---|---|---|
| Railway CPU/memory pressure | Sustained high CPU during peak hours, or OOM errors in logs | Do not pre-emptively upgrade the Railway plan on a hunch. |
| Background job execution time | Any single scheduled job's execution time approaches 60 seconds | Do not introduce Celery/Redis before this is actually observed. |
| Database read contention | Admin/report queries visibly compete with write traffic for resources | Consider a Supabase read replica only once this is observed, not preemptively. |
| Moving off Railway entirely | 1,000+ active farmers with real peak-hour bursts, Railway billing exceeding roughly $100/month, or a compliance requirement (ISO 27001, SOC 2, data residency in Kenya) appears | AWS ECS / Google Cloud Run are the documented next steps; this is explicitly *not* a V1 or near-term concern. |
| Kubernetes | 10+ independently-scaling microservices, a dedicated DevOps team, and hundreds of requests per second sustained | The operational guidance is explicit and worth repeating verbatim in spirit: if someone suggests AGRIOS needs Kubernetes now, they are over-engineering. |

---

## 7. How to Use This Document

Before starting any new feature work, check this document for an existing KI or defect that overlaps with the area being touched — several of the entries above (particularly Section 1) are cheap to fix once discovered but easy to reintroduce or rediscover independently if this record is skipped. When a KI listed here is finally resolved, it should be removed from this document and the resolution should be recorded in that sprint's handover report and, where relevant, in `PROJECT_HISTORY.md` — this document is meant to always reflect *current* known debt, not a permanent historical ledger (that role belongs to `PROJECT_HISTORY.md`).
