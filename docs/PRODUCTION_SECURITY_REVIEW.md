# Production Security Review (Gate 6)

Single consolidated review of Greena's security posture, drawing together the verified
work of Gates 2–5 plus new verification performed this increment (dependency scans, RLS
assessment). Authoritative; indexed from `RUNBOOK_INDEX.md`. Deploy stays gated on Gate 5.

**Classification key:** PASS (meets the bar) · HARDEN (works, strengthen) · DEFER (legit
but not launch-scoped) · ACCEPTED RISK (documented, consciously accepted).

## Domain reviews

### 1. Authentication — PASS (one HARDEN)
- **Evidence:** `app/core/security.py`; auth test subset **83 passed** (Gate 2).
- **Current:** Argon2id account passwords (`hash_password`), bcrypt PIN/OTP, JWT HS256 access (15 min), opaque refresh (bcrypt-hashed, SHA-256-indexed), length-first password policy, refresh-token bounded to ≤72 bytes (Gate 2).
- **Remaining risk:** `bcrypt==4.2.1` pin is load-bearing (upgrade past 4.x breaks OTP/PIN/refresh unless input bounded — now mitigated); no progressive account lockout beyond the `/auth` rate limit.
- **Recommendation:** add per-account lockout/backoff (HARDEN, P2).
- **Verification:** code read + auth regression.

### 2. Authorization — PASS
- **Evidence:** `app/core/permissions.py` (8 roles × ~200 action perms), `require_permission` + `require_farm_access`.
- **Current:** action-based RBAC; farm-membership chokepoint; super_admin bypass.
- **Remaining risk:** platform-role check + service-layer farm scoping — verified consistent by the IDOR sweeps.
- **Recommendation:** keep.
- **Verification:** 220-route read IDOR + 116-route write IDOR + cross-org tests (all pass, Gates 2–3).

### 3. Tenant isolation — PASS
- **Evidence:** `test_tenant_isolation_sweep.py` (220 GET routes), `test_write_idor_and_cross_org.py` (116 POST routes + cross-org).
- **Current:** every farm-scoped route denies non-members (0 leaks); cross-org bidirectional deny.
- **Remaining risk:** enforced at the app layer, not the DB (see §RLS).
- **Recommendation:** keep; RLS as defense-in-depth (P2).
- **Verification:** automated regression, all green.

### 4. Secrets management — PASS
- **Evidence:** Gate 6 secret scan (no tracked `.env`, no live-key patterns, no hardcoded literals in `backend/app`); `config.py` fail-fast; `redact_secrets`.
- **Current:** env-provided secrets; AI keys backend-only; rotation procedure (`DISASTER_RECOVERY.md §2.6`).
- **Remaining risk:** frontend **production bundle** scan runs at deploy (`LAUNCH_RUNBOOK`).
- **Recommendation:** keep; keep the deploy-time bundle scan.
- **Verification:** `git grep` secret scan (Inc 1).

### 5. Session / token security — HARDEN
- **Evidence:** `config.py` cookie settings; `dependencies.py`; `frontend/src/stores/authStore.ts`.
- **Current:** refresh token in **httpOnly** cookie with SameSite + Origin check (CSRF); short-lived access token sent as Bearer (JS-readable).
- **Remaining risk:** an XSS could read the access token from JS storage (bounded by 15-min expiry + strict CSP).
- **Recommendation:** hold the access token in memory (not localStorage) or keep CSP strict (HARDEN, P2).
- **Verification:** code read.

### 6. File-upload security — PASS (dependency caveat)
- **Evidence:** `app/core/uploads.py`; `test_uploads.py` + upload integration tests (Gate 3).
- **Current:** size caps, extension allowlist, **magic-byte** verification, trusted-MIME; bounded reads; in-memory (non-executable) processing.
- **Remaining risk:** the underlying `python-multipart` parser has known CVEs (see §11).
- **Recommendation:** keep validator; **upgrade python-multipart** (P1).
- **Verification:** unit + integration tests.

### 7. AI security — PASS
- **Evidence:** `app/core/ai_safety.py`, `ai_provider.redact_secrets`; AI-authz-inheritance + injection tests (Gates 3–4).
- **Current:** deterministic-first; prompt-injection sanitize + detect-and-guard; output secret redaction; keys backend-only; provider-manager rotation/failover; AI cannot exceed the caller's permissions.
- **Remaining risk:** injection detection is heuristic (defense-in-depth, not a gate).
- **Recommendation:** keep.
- **Verification:** unit + integration tests.

### 8. Operational security — PASS (one HARDEN)
- **Evidence:** `audit_service`, `/health`, `/production/diagnostics|status`, `DISASTER_RECOVERY.md`, `ALERTING.md`, rollback runbooks.
- **Current:** immutable audit events; startup validation; DR + alerting defined; manual super_admin promotion (deliberate control).
- **Remaining risk:** escalation contacts/domains flagged ⚠️CONFIRM (owner).
- **Recommendation:** confirm on-call + a general incident-response runbook (HARDEN, P2).
- **Verification:** doc audit + backup/restore test.

### 9. Database security — PASS (RLS = ACCEPTED RISK)
- **Evidence:** SQLi sweep **clean** (Gate 2); ORM parameterized `select()`; `AGRIOSBase` ownership/audit/soft-delete; transactions; immutable finance (reversing entries).
- **Current:** repository-only access; no raw string SQL; least-data queries.
- **Remaining risk:** RLS disabled — app layer is the boundary (see §RLS).
- **Recommendation:** enable RLS post-launch (defense-in-depth, P2).
- **Verification:** SQLi sweep + isolation sweeps.

### 10. Infrastructure security — HARDEN (prod-verify at deploy)
- **Evidence:** `SecurityHeadersMiddleware` (nosniff, X-Frame DENY, CSP `default-src 'none'`, HSTS in prod), `DATABASE_SSL` forced for non-local hosts; header tests.
- **Current:** security headers + HSTS + TLS enforcement in code.
- **Remaining risk:** production CORS/TLS/CSP-`connect-src` and the shared-domain cookie blocker are **verifiable only at deploy** (not locally) — covered by `LAUNCH_RUNBOOK.md §3` smoke tests + `DEPLOYMENT_HARDENING.md §1`.
- **Recommendation:** verify at deploy per the runbook (no local action possible — not fabricated here).
- **Verification:** code read + `test_hardening`; prod config = deploy-time.

### 11. Supply-chain / dependency security — HARDEN (P1, new finding)
- **Evidence (verified this increment):** `pip-audit -r requirements.txt` → **22 known vulnerabilities in 5 packages**: `python-jose 3.3.0` (JWT — used for our tokens; fix 3.4.0), `starlette 0.38.6` (web framework), `python-multipart 0.0.20` (upload/form parsing), `python-dotenv 1.0.1`, `ecdsa 0.19.2` (transitive). `npm audit --omit=dev` (frontend) → **2 moderate** in `react-router`/`react-router-dom` (open redirect + constructor injection, fixable).
- **Current:** dependencies pinned; **no automated dependency scanning in CI**.
- **Remaining risk:** known CVEs in the **JWT library and the framework** — the most exploitable of any finding here.
- **Recommendation (P1, locally verifiable):** upgrade to fixed versions (`python-jose→3.4.0`, `python-multipart→latest`, `python-dotenv→1.2.2`, `starlette`/`ecdsa` via FastAPI-compatible bumps, `npm audit fix` for react-router) **then run the full regression**; add `pip-audit` + `npm audit` to CI. Note `bcrypt` must stay ≤4.x unless the refresh-token input is bounded (already done, so a bcrypt bump is now also safe to evaluate).
- **Verification:** pip-audit + npm audit executed (real scans).

### 12. Logging & auditability — PASS (one DEFER)
- **Evidence:** structured logging + request/correlation IDs (`middleware.py`); `redact_secrets`; `audit_service` immutable events; Sentry (prod, scrubbed).
- **Current:** no secrets in logs; auditable auth/admin/payment/permission events.
- **Remaining risk:** audit logs are append-only but not cryptographically tamper-evident (Security Std §31 advanced).
- **Recommendation:** tamper-evident audit chain (DEFER, P3).
- **Verification:** code read + secret-redaction tests.

## RLS assessment (explicit)
**Classification: ACCEPTED RISK — an intentional architectural choice, not a deficiency.**
- **Decision:** authorization is enforced at the **application layer** (`require_farm_access` + RBAC + tenant-scoped queries); PostgreSQL **Row-Level Security is not enabled** in Supabase.
- **Rationale:** the app is the *only* path to the database — the frontend never holds DB credentials and never connects directly (`SYSTEM_ARCHITECTURE`, `config.py`). The authorization boundary is therefore the app's permission system, which is **verified by automated IDOR sweeps** (220 read + 116 write routes, 0 cross-tenant leaks) that run in the regression suite as guards.
- **Assumptions:** (a) no direct client/BI access to the production DB using a broad role; (b) the backend DB credential is backend-only and least-privilege; (c) every farm-scoped route passes through the access chokepoint (enforced + tested).
- **Operational safeguards:** the isolation regression sweeps, the audit log, and the secret hygiene above. If assumption (a) ever changes (e.g., analysts get direct DB access), RLS becomes **required**.
- **Recommendation:** enable RLS as **defense-in-depth** post-launch (P2) — a strengthening, not a fix for a current hole.

## Gates 2–4 issue carry-forward (every prior item resolved or justified)
| Issue | Origin | Status |
|---|---|---|
| Refresh-token bcrypt-72 truncation | Gate 2 | ✅ CLOSED (bounded to `token_urlsafe(48)`) |
| Migration 028 `metadata_` mismatch | Gate 2 | ✅ CLOSED (already fixed by migration 031) |
| SQL injection | Gate 2 | ✅ PASS (full sweep clean) |
| Tenant read isolation | Gate 2 | ✅ CLOSED (220-route sweep) |
| Write IDOR + cross-org | Gate 3 | ✅ CLOSED (116-route sweep + state-change) |
| File-upload validation | Gate 3 | ✅ CLOSED (validator + tests) |
| Prompt injection | Gates 3–4 | ✅ CLOSED (sanitize + detect-and-guard) |
| AI single-key / no rotation | Gate 4 | ✅ CLOSED (AI Provider Manager) |
| Access-token in JS storage | Gate 2 (noted) | ➡️ CARRIED FORWARD (HARDEN, P2) |
| RLS disabled | Gate 1 (noted) | ➡️ CARRIED FORWARD (ACCEPTED RISK, P2) |
| Rate limiting only on `/auth` | Gate 2 (deferred) | ➡️ CARRIED FORWARD (HARDEN, P2 — AI bounded by quota; exports/imports still unbounded) |

## Prioritized remediation register (P0–P3)
| Pri | Item | Class | Locally verifiable? |
|---|---|---|---|
| **P0** | *(none security-blocking beyond the Gate 5 performance gate)* | — | — |
| **P1** | **Dependency upgrades** (python-jose/starlette/python-multipart/dotenv/ecdsa + react-router) then full regression; add pip-audit + npm audit to CI | HARDEN | ✅ yes (upgrade + run tests) |
| **P2** | Access-token transport hardening | HARDEN | ✅ |
| **P2** | Broaden rate limiting to exports/imports | HARDEN | ✅ |
| **P2** | Enable RLS (defense-in-depth) | HARDEN | partly (needs Supabase) |
| **P2** | Per-account lockout/backoff | HARDEN | ✅ |
| **P2** | Confirm escalation contacts + incident-response runbook | HARDEN | doc only |
| **P3** | Tamper-evident audit log | DEFER | ✅ |
| **P3** | Expand app-level backup to newer modules | DEFER | ✅ |

**Scope note:** no recommendation here requires infrastructure I cannot verify locally, except the two explicitly marked (prod TLS/CORS verification = deploy-time per the runbook; RLS enablement = needs Supabase) — those are flagged, not fabricated.

## Verdict
The application-layer security posture is **strong and regression-guarded**. The one materially
new, high-priority finding is **dependency CVEs (P1)** — verifiable and fixable locally. No P0
security blocker remains; production readiness continues to depend on the Gate 5 performance
gate and the P1 dependency remediation.
