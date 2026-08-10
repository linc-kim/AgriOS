# GATE 2 — Security & Core Platform Hardening — Completion Report

**Status:** Implementation complete, fully verified. **Awaiting owner approval. NOT committed, NOT pushed.**
**Date:** 2026-08-11 · **Branch:** `phase-2-auth` (local; 76 commits ahead of origin)

## Objectives completed
1. **CI activated** — `ci.yml` moved to the path GitHub actually reads (`.github/workflows/`); deploy workflows deliberately left parked (owner decision open).
2. **Refresh-token bcrypt-72-byte safety** — new tokens bounded to `token_urlsafe(48)` (64 chars, 384-bit entropy); a future bcrypt-major upgrade no longer breaks all OTP/PIN/refresh. No forced logout (old tokens drain in ≤30 days).
3. **Tenant-isolation / cross-farm IDOR read sweep** — new test proves a non-member is denied on **all 220** runtime-discovered farm-scoped GET routes (0 leaks, 0 5xx), plus curated cross-module, AI/ARIA-context, and unauthenticated cases.
4. **SQLi** — swept, confirmed clean (ORM-only; `text()` static or bound). No change.
5. **Migration 028 "defect"** — verified already resolved by migration 031 against the live DB. No migration created.

## Files changed (delta)
- `backend/app/core/security.py` — `create_refresh_token()` length bound + rationale (+12/−1).
- `.github/workflows/ci.yml` — `git mv` from `infrastructure/github/workflows/ci.yml` (content unchanged).
- `backend/tests/integration/test_tenant_isolation_sweep.py` — **new** (4 tests, 220-route sweep).
- `docs/GREENA_STANDARDS_GAP_AUDIT.md`, `docs/GATE_2_REPORT.md` — audit/report docs.

## Database migrations
**None created.** Migration 028 issue was already fixed by `031_fix_notifications_metadata_column.py`.

## Tests executed
- **Environment:** local embedded Postgres 16.14 on `127.0.0.1:5433`; Python 3.12 venv; `DATABASE_URL`/`TEST_DATABASE_URL` → local; `GEMINI/CLAUDE/AT` keys empty (offline AI path); `ENVIRONMENT=development`.
- **Isolation sweep:** `pytest tests/integration/test_tenant_isolation_sweep.py -v` → **4 passed** in 33.5s.
- **Auth/security subset (post refresh-token change):** `pytest -k "auth or security or token or refresh or otp or pin or login"` → **83 passed** in 53.8s.
- **Full regression:** `pytest -q` → **1850 passed, 0 failed** in 439.8s (7m19s). Baseline before Gate 2 was 1846; delta = +4 new isolation tests.
- **Skipped tests:** none newly skipped by Gate 2.

## Tests passed / failed
**1850 passed, 0 failed, 0 errors.** Warnings (2006) are pre-existing `datetime.utcnow()` deprecations — non-blocking (tracked P2).

## Coverage impact
Security/authorization read-path coverage **increased** — the 220-route isolation guarantee is now regression-guarded where it previously had none. Exact line-coverage % not measured this run (ran `-q`, not `--cov`); CI (`ci.yml`) runs `--cov` and will report the number on first PR.

## Performance impact
None at runtime. Refresh tokens are shorter (negligible). No middleware/query changes. Full-suite wall-clock varied (271s→440s) due to concurrent machine load, not code.

## Security impact
**Positive, no regressions.** (1) Latent auth time-bomb removed. (2) Cross-tenant read isolation now proven platform-wide and locked by tests. (3) SQLi confirmed absent. (4) No new attack surface introduced (one test file + a shorter token).

## Breaking changes
**None.** Token change is backward-compatible (old tokens still verify on pinned bcrypt 4.2.1). CI move only affects GitHub once merged to `main`.

## Rollback strategy
Pure `git revert` of the Gate 2 commit restores prior state — no migrations, no data changes, no external state. The refresh-token change needs no data rollback (only new tokens differ). CI: move `ci.yml` back if undesired.

## Independent audits requested by owner
- **Login/auth rate limiting is independent of AI quota — CONFIRMED.** `RateLimitMiddleware` limits `_PROTECTED_PREFIXES=("/api/v1/auth/",)` by client IP (20 req/60s sliding window, `core/middleware.py:174`), plus per-phone OTP limits in `auth_service`. AI cost control is a **separate** mechanism: per-farm `monthly_budget_usd` + `ai_usage_log` + `QuotaExceededException` (402) at the service layer. Different trigger, scope, and code path — neither depends on the other.
- **File-upload security — PARTIAL (audit corrected).** Two real upload endpoints exist (earlier "no upload path" was wrong): multimodal ARIA (`ai_assistant.py`) enforces an 8 MB cap (`_read_capped`) ✓ but trusts client `content_type` (no magic-byte signature check, no extension allowlist); data import (`production.py:272`) does an **uncapped** `file.read()` (DoS risk). Module media (`avi_bird_media` …) are URL-references. No malware scan. Uploaded bytes are processed in-memory (Gemini Vision / parsed records), not written to an executable path — RCE risk low but not formally verified. → **HARDEN, P1** (add magic-byte + extension allowlist on multimodal; cap the import read; assert non-executable storage).

## Remaining authorization work (planned)
- **P1 — Write/mutation IDOR sweep (POST/PUT/PATCH/DELETE).** The read sweep proves the shared `require_farm_access` chokepoint denies non-members; writes flow through the same guard, but the standards require writes tested directly (Doc 4 §17). Plan: for a representative create/update/delete per module family, assert a non-member receives 403/404 and **no row is written/modified** (verify via a follow-up read). Brittleness managed by minimal valid payloads + asserting the security property (never 2xx / no state change) rather than exact codes.
- **P1 — Cross-organization isolation** for org-scoped admin/reporting surfaces (most data is farm-scoped and now covered).

## Remaining risks / limitations
- Read-path isolation proven; **write-path IDOR not yet tested** (P1 above).
- File-upload hardening outstanding (P1 above).
- Coverage % not numerically captured this run.
- Deploy-workflow activation still an open owner decision.
- Gemini single-key (no rotation) unchanged — separate later AI gate (P1).

## Recommendation
**Proceed.** Gate 2 delivers verified security hardening with zero regressions and no breaking changes. Recommend: (a) approve Gate 2 and authorize the commit; (b) decide deploy-workflow activation; (c) schedule the P1 write-IDOR sweep and file-upload hardening as Gate 3 (or the next security increment) before the load-test/AI-rotation gates.
