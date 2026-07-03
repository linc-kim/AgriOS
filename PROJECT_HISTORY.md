# AGRIOS PROJECT HISTORY

**Read `AGRIOS_MASTER_CONTEXT.md` first.** This document is the chronological record of how AGRIOS actually got to its current state — including the mistakes made along the way and the lessons that directly shaped the frozen decisions described throughout this handbook. Understanding this history is not optional context; several of the project's strictest rules (the sprint execution framework, the "product before infrastructure" principle) exist specifically *because* of the events described in Section 1, and will look like unnecessary bureaucracy to anyone who has not seen why they were adopted.

---

## 1. Day 0 — The Infrastructure-Theater Prototype and Its Audit

Before AGRIOS had any real product code, an early build phase produced a codebase that *described* an impressively complex distributed system while containing almost none of it. A Principal Software Architect audit conducted on 2026-06-24, examining the git repository, source files, deployment configs, and the original product discussion document, delivered a blunt diagnosis: **the AGRIOS codebase did not yet exist as a product.**

What actually existed: a FastAPI app with exactly two endpoints (`GET /` returning a static status string, `POST /sync` returning a static "complete" string) — no database, no ORM, no authentication, no real logic of any kind; a 500-line static HTML "Operational Dashboard" showing simulated edge nodes for "Nakuru" and "Kisumu" with an "Inject mock payload" button that added fake rows to a table, entirely disconnected from the FastAPI backend (no fetch calls, no API awareness); and a set of deployment files — a WireGuard mesh config, a Kubernetes cloud-server manifest, a network policy firewall config, a build-verification script, a dependency-compilation script — that were not merely incomplete but **garbled UTF-16LE text that could not be parsed as YAML or executed as shell scripts at all.**

The git commit history, by contrast, read like a mature infrastructure team's changelog: "Implement Milestone 5: Complete chaos test network blackout simulator framework," "Initialize cryptographic WireGuard mesh parameters and network policy firewall shields," "Provision central Kubernetes cloud manifests, otel-gateway, and service identity pools." The actual diffs behind these commits were, respectively: a test file containing five `print()` statements and no assertions; a garbled, unparseable config file; two more garbled, unparseable config files. A Python virtual environment directory (`.venv/`, ~200MB of Windows-compiled binaries for a different Python version than the deployment target) had also been committed directly into the repository.

**The audit's verdict on MVP completion: 0 of 5 defined MVP features built (Poultry Health AI, Feed + Cost + Profit Calculator, Growth & Farm Tracker, Disease Alert System, Market Price Board).** The infrastructure that *was* built — however elaborate its naming — solved problems (multi-region failover, chaos engineering, edge-node offline sync) that no real user had yet experienced, because there were no real users and no real product yet for them to experience problems with.

**The lesson this produced, stated in the audit's own words:** *"Build what a farmer touches first. Build what ops teams manage second. WireGuard tunnels and Kubernetes manifests are meaningless until farmers are using the app."* This single sentence became the seed of the "product before infrastructure" principle now recorded as permanent guidance in `AGRIOS_MASTER_CONTEXT.md` Section 4.1, and the audit's recommended phased roadmap (Phase 0: clean slate; Phase 1: core product; Phase 2: polish and mobile; Phase 3: the offline/infrastructure ambitions, "now build the impressive infrastructure — you've earned it") is the direct ancestor of the phase structure still used in `ROADMAP.md` today.

---

## 2. The Reset — AGRIOS V1 Master Blueprint (Frozen)

In direct response to the Day 0 audit, project leadership issued the **AGRIOS V1 Master Blueprint (Frozen)** — a document explicitly designed to end debate rather than continue it. Its own language is unambiguous about this intent: *"This document does not introduce new decisions. It locks existing ones. Sprint 0 begins the moment this document is finalised."* It resolved several contradictions that had accumulated across earlier, less formal planning documents — for example, whether the Vet role belonged in V1 (resolved: yes, included, because a vet-organization partnership is required at the 100-farmer rollout gate) and whether the system should have 8 roles or a simplified 5 (resolved: 8 roles stand; the 5-role description in an earlier brief was a simplification, not a technical specification).

This blueprint locked 47 individual decisions across six categories (Architecture: 14, Database: 10, Product: 11, Security: 9, Roles: 5, ARIA: 6) — the same decision register (`AD-`/`DB-`/`PD-`/`SD-`/`RD-`/`AR-` codes) referenced throughout every other document in this handbook. It also established the product's single MVP success metric, Daily Active Loggers, explicitly rejecting revenue, AI query volume, and signup count as premature or misleading alternatives (`AGRIOS_MASTER_CONTEXT.md` Section 5.2). The document's closing line — *"The first command is: `mkdir agrios && cd agrios && git init`"* — marks the literal restart point of the codebase that exists today.

---

## 3. Sprint 0 and Sprint 1 — Foundation and Design System

Sprint 0 built the database foundation (Migrations 001–005: `roles`, `users`, `user_roles`, `otp_requests`, `sessions`), the authentication system, and core infrastructure. Sprint 1 established the design system — at this point using a placeholder Tailwind green (`#16a34a`) rather than the true logo-derived brand color, a gap that was identified and corrected shortly after (Section 4).

---

## 4. The Design System Correction

A dedicated brand and design-system audit, dated 2026-06-24, analyzed the actual AGRIOS logo SVG pixel-by-pixel and determined that the true brand green was `#076524` — a deliberately darker, more desaturated forest green than the generic Tailwind `#16a34a` used in Sprint 0's placeholder configuration. This audit produced the frozen `DESIGN_SYSTEM.md` color system, typography (Inter + JetBrains Mono), spacing (4px base unit), and component language still in use, and explicitly flagged the Sprint 0 Tailwind config as needing correction: *"Sprint 0 used `#16a34a` as `brand-600`. This is a standard Tailwind green — close but NOT the AGRIOS logo green... All future UI must use the corrected value."* Any component still rendering the pre-correction green is carrying forward a Sprint 0 placeholder that was already identified as wrong at the time.

---

## 5. Sprint 2 through Sprint 5 — The Product Core

**Sprint 2** built farm infrastructure (Migrations 006–011: `subscription_plans`, `species_profiles`, `farms`, `farm_members`, `farm_units`, `production_houses`). **Sprint 3** built flock lifecycle and operations (Migrations 012–016 covering `flocks`, `daily_logs`, `production_records`, `weighin_records`, `feed_purchases`) and, in doing so, introduced three carryover items that remained open for several subsequent sprints: `ProductionRecordScreen` shipped as a placeholder ("Coming Soon") despite its API and schemas already existing (KI-02); `CreateFlockScreen` depended on a houses list that required farm structure to already be set up, creating an awkward onboarding sequencing issue (KI-03); and the `/flock` and `/health` bottom-tab routes redirected to a generic `/farms` screen rather than resolving to a farmer's actual default farm (KI-04). **Sprint 4** built the Health module (Migrations 017–018: `vaccination_records`, `disease_alerts`). **Sprint 5** built the Finance module (Migrations 019–022: `expense_categories`, `expenses`, `revenue_records`, `financial_snapshots`) and is where the snapshot pattern (`DATABASE_ARCHITECTURE.md` Section 5) was implemented as the sole read path for financial data.

---

## 6. Sprint 6 — ARIA, and the First File-Corruption Bug

Sprint 6, completed 2026-06-26, built the entire ARIA AI module in one pass: five migrations (023–027), the Farm Context Package compiler, the Gemini/Claude fallback mechanism, all eight proactive insight generators, and four frontend screens (Chat, Insights, Recommendations, Settings) — roughly 4,070 new lines of code across backend and frontend. Every AR-series frozen decision (`ARIA_AI.md` Section 4) was verified compliant at sprint close.

This sprint is also the origin of a recurring operational lesson: a large write to `frontend/src/lib/queryClient.ts` was silently truncated mid-file by the write tooling in use at the time, cutting the file off partway through the `aiQuota:` key definition. This went undetected until the following sprint. The practical lesson that came out of it — recorded explicitly in the Sprint 7 handover report — was to use a `cat > file << 'PYEOF'` heredoc pattern for large new-file writes going forward, specifically to avoid a repeat of silent truncation, rather than trusting a single large tool-mediated write blindly.

---

## 7. Sprint 7 — Platform Layer, Scheduler Wiring, and Two Repairs

Sprint 7 (2026-06-26) delivered the platform layer (Migrations 028–030: `notifications`, `audit_logs`, `market_prices`), wired the APScheduler background jobs into the FastAPI application lifespan (closing the AR-06 carryover from Sprint 6 — daily insight generation had been implemented in Sprint 6 but not yet actually scheduled to run), and delivered all five production cron jobs (`SYSTEM_ARCHITECTURE.md` Section 2.6).

This sprint's handover report also documents a **file repair log** — two pre-existing corruptions discovered and fixed during the sprint: the `queryClient.ts` truncation from Sprint 6 (Section 6, fully restored), and a corrupted `frontend/src/routes/index.tsx` containing both a duplicate `AppRouter` export block and a corrupted byte (a Unicode replacement character, `U+FFFD`) at the ARIA route comment, repaired via a direct Python binary read with explicit Unicode error handling. These two repairs are recorded here deliberately, not as trivia, but because they establish a pattern worth being alert to: **large automated file writes in this project's tooling history have occasionally truncated or corrupted files silently, without raising an error.** Any contributor — human or AI agent — who encounters an unexpectedly short file, a duplicate export block, or a stray replacement-character byte should suspect this exact failure mode before assuming the file was always meant to look that way.

---

## 8. Sprint 8 — Admin Module, and V1 Feature Completeness

Sprint 8 (2026-06-26) delivered the entire Admin Module (screens A-01 through A-08) with **zero new migrations** — a deliberate demonstration that DB-10 (the 30-migration freeze) held even for a substantial new feature surface, because every admin capability was built as new endpoints and screens querying data models that already existed from Sprints 0–7. This sprint marks the point at which all eight V1 sprints originally scoped in the sprint sequence reference were complete, making Sprint 8 the effective "V1 feature-complete" milestone, followed by two additional hardening sprints before launch.

---

## 9. Sprint 9 — Offline-Aware UI and Settings

Sprint 9 (2026-06-26) completed the offline-aware layer explicitly scoped as V1's *limited* offline behavior (cached-data visibility and service-worker asset caching — not full offline-first write queuing, which remains Phase 3 per the frozen blueprint), added the four Settings screens (Profile, Notifications, Language, About) and the shared Offline/404/Error utility screens, and confirmed that user preferences (e.g. SMS notification opt-out) could be stored entirely inside the existing `user.metadata_` JSONB column with zero new migrations required — a direct, practical demonstration of why the `metadata_` extensibility column (`DATABASE_ARCHITECTURE.md` Section 1) was worth including on every table from the start.

---

## 10. Sprint 10 — Production Hardening and Launch

Sprint 10 (2026-06-26) closed out V1 with no new migrations (the chain remained sealed at 30), a version bump to `1.0.0` across backend and frontend, the `SecurityHeadersMiddleware` (`SYSTEM_ARCHITECTURE.md` Section 2.4), frontend Sentry integration with PII-protected session replay, and the deployment configuration files (`railway.toml`, `frontend/vercel.json`) plus the full `docs/LAUNCH_RUNBOOK.md` operational guide. The sprint's own closing summary: **"AGRIOS V1 is complete and launch-ready,"** with 30 migrations, 40+ backend endpoints, 35+ frontend screens, and over 250 unit tests plus 165 integration tests accumulated across the ten sprints.

---

## 11. Post-Launch Verification — Real Deployment Blockers Found and Fixed

After the V1 build was declared complete, a Lead Release Engineer audit and a subsequent verification pass identified several concrete deployment blockers that static completeness (migrations present, tests passing) had not caught, because they were import-time and runtime defects rather than missing-feature gaps. These were fixed one at a time, each verified narrowly before moving to the next, in the following order:

- **V1 — `backend/app/models/health.py`:** `DiseaseAlert.extended_metadata` carried an invalid `server_default` value that would prevent the FastAPI application from starting at all. Fixed by correcting the `server_default` to a valid JSONB default (`"{}"`).
- **V2 — `backend/app/services/auth_service.py`:** imported a nonexistent `sms_service` object from `sms_service.py`, which exports only bare module-level functions, not a singleton object of that name. Fixed by importing and calling `send_sms()` directly for OTP delivery, matching the pattern already used by every other part of the codebase that sends SMS.
- **V3 — `backend/app/services/farm_service.py`:** imported a nonexistent `SMSService` class for farm-invite SMS. Fixed by using the existing `sms_service.sms_farm_invite(phone, farm_name)` function rather than inventing a new class-based architecture.
- **V4 — `backend/app/services/finance_service.py`:** imported exception classes from a nonexistent path, `app.core.exceptions`, when the project's actual exception module lives at `app.exceptions`. Fixed by correcting the import path. (An identical wrong-path import was also found inside a function body in `app/api/v1/endpoints/finance.py` but was deliberately left untouched at the time, since it was not the error actually raised at import time — it is tracked as a known duplicate of the same defect in `KNOWN_TECHNICAL_DEBT.md`.)
- **Real Railway deployment log — `VaccinationRecord` duplicate `metadata` column:** an actual production Railway deploy log (not a simulation) surfaced `sqlalchemy.exc.DuplicateColumnError: A column with name 'metadata' is already present in table 'vaccination_records'`. Root cause and fix are documented in full in `DATABASE_ARCHITECTURE.md` Section 1 — `VaccinationRecord` had declared its own redundant `extended_metadata` column on top of the one it already inherits from `AGRIOSBase`. A full-codebase search confirmed zero other references to the removed attribute before the fix was considered complete. `DiseaseAlert`'s own, separately-declared `extended_metadata` column was deliberately left untouched at the time, since it was not the error observed in the log — it remains a known latent instance of the identical pattern.

A separate diagnostic pass (not yet remediated) investigated why Alembic still attempted `CREATE TYPE member_status` during Migration 009 even though `create_type=False` had been set — the root cause and proposed minimal fix are recorded in `DATABASE_ARCHITECTURE.md` Section 4.4, Pattern B, and in `KNOWN_TECHNICAL_DEBT.md`.

---

## 12. The Authentication Pivot — From Assumed SMS to Channel-Agnostic Identity

AGRIOS was originally designed, from the earliest frozen blueprint onward, around a single hard assumption: phone-number OTP via Africa's Talking as the *only* registration and login mechanism (the original PD-04, "Phone OTP is the only registration method — no email, no Google, no Apple sign-in"). This assumption held all the way through Sprint 0 and every subsequent sprint's authentication-adjacent work.

At the point of preparing for actual V1 launch, it became clear that Africa's Talking credentials would not be configured for the initial go-live — the SMS integration that the entire authentication system had been built around was simply not going to be available on day one. Rather than treat this as a temporary blocker to be worked around with a one-off "email login, just for now" exception bolted onto a phone-first system, the decision was made to treat it as evidence of a deeper design gap: an authentication system that hard-assumes one specific communication technology will always eventually meet a moment where that technology is not available — whether because a credential is not yet configured, a provider has an outage, or a future country/market has no equivalent provider at all. This is the same category of lesson the project had already learned once before, in a different form, in Section 1 of this document: a system built around a single assumed capability is fragile in exactly the way a system built around a real, currently-available capability is not.

The resulting decision, recorded as a formal, permanent amendment to the frozen decision register (see `AGRIOS_MASTER_CONTEXT.md` Section 9, "Formal override record — PD-04 amended"), generalized authentication into a **channel-agnostic identity model**: AGRIOS authenticates through verified communication channels rather than any single assumed technology, with Email OTP as the actually-functioning V1 launch mechanism, phone/SMS OTP remaining fully part of the architecture and intended to activate purely through a Railway environment-variable change once Africa's Talking credentials exist, and authenticator apps, passkeys, and third-party identity providers (Google, Apple, Microsoft) anticipated as future additions to the same single-identity model rather than separate registration systems. A user registering via email and a user registering via phone now produce the exact same kind of account, distinguished only by which channel was used to prove it belongs to a real person — and verifying a second channel on an existing account must never create a second account.

This pivot touched `AGRIOS_MASTER_CONTEXT.md` (the new Section 6.1, superseding the old phone-only Section 6.1 and the "What Must Never Change" phone-only rule in Section 10), `SYSTEM_ARCHITECTURE.md` (Section 5's authentication flow and Section 6's notification channels, both rewritten to be identifier-shaped and channel-agnostic rather than phone/SMS-shaped), `DATABASE_ARCHITECTURE.md` (a new Section 12 documenting optional future identity fields — `email`, `is_email_verified`, `preferred_contact_channel`, and a future identity-linking structure — without redesigning the current schema), `DEPLOYMENT_GUIDE.md` (new email-provider environment variables, and Africa's Talking variables reclassified as optional-at-launch rather than required), `KNOWN_TECHNICAL_DEBT.md` (recording SMS's inactive-at-launch status as a deliberate configuration state, not a defect), and `ROADMAP.md` (sequencing 2FA, authenticator apps, passkeys, and third-party identity providers as explicit future work built on this same model). No application code and no database migration were changed as part of this pivot — it was, deliberately, a documentation-first architectural decision, on the theory that the reasoning needs to be settled and recorded before any implementation work proceeds against it, exactly the same discipline the sprint execution framework has applied to every other frozen decision in this project's history.

---

## 13. Evolution of the Platform — What This History Shows

Read end to end, the project's history shows a consistent pattern worth naming explicitly: **the codebase's most durable rules were almost all produced in direct response to a specific, concrete failure or constraint**, not invented speculatively in advance. The "product before infrastructure" principle came from watching an elaborate but non-functional infrastructure prototype fail an audit. The frozen decision register and sprint execution framework came from a leadership team that had just watched scope drift produce that same failure and decided to make re-litigating settled questions structurally difficult. The heredoc file-write convention came from a real, silent file-truncation incident. The correction pattern, the snapshot pattern, and the append-only table convention all trace to specific reasoning about a specific failure mode (see `DATABASE_ARCHITECTURE.md`). The channel-agnostic authentication model (Section 12) is the newest example of this same pattern: it was produced by a real launch constraint (no Africa's Talking credentials at go-live), and the response was not a one-off patch but a permanent generalization of the underlying principle, precisely so the next constraint of the same shape — a different missing credential, a different country with no equivalent SMS provider — does not require relitigating the same question again. A future contributor who is tempted to relax one of these rules should look for the failure or constraint it was built to address before assuming the rule is merely legacy caution — in nearly every case documented here, it is not.
