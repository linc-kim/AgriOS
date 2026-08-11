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

### 6. File-upload security — PASS
- **Evidence:** `app/core/uploads.py`; `test_uploads.py` + upload integration tests (Gate 3).
- **Current:** size caps, extension allowlist, **magic-byte** verification, trusted-MIME; bounded reads; in-memory (non-executable) processing.
- **Remaining risk:** the `python-multipart` parser CVEs are **resolved** — upgraded 0.0.20 → 0.0.32 this increment (see §11).
- **Recommendation:** keep validator.
- **Verification:** unit + integration tests (36 passed on the upgraded parser).

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

### 11. Supply-chain / dependency security — PASS (two ACCEPTED RISKS)
- **Status:** the P1 dependency finding from Inc 5 is **remediated** (Gate 6 Inc 6). Backend
  `pip-audit -r requirements.txt` went from **22 vulns in 5 packages → 1 vuln in 1 package**;
  frontend `npm audit --omit=dev` remains **2 moderate** (both consciously accepted, below).
- **Remediation record (previous → new · vulnerability addressed · compatibility · regression):**

| Package | Prev | New | Advisories cleared | Compatibility issues | Regression |
|---|---|---|---|---|---|
| `python-jose[cryptography]` | 3.3.0 | **3.5.0** | PYSEC-2024-232, -233, PYSEC-2025-185 (5) | None — we use HS256 `jwt.encode/decode` + `JWTError`, unchanged. 3.5.0 also cleared the no-fix-listed 2025-185. | auth subset 13 ✓; full 1913 ✓ |
| `fastapi` | 0.115.0 | **0.141.1** | (required to reach the starlette fix line; 0.115 pinned `starlette<0.42`) | 0.141 no longer flattens `include_router` routes into `app.routes` (opaque `_IncludedRouter` node). Fixed two downstream assumptions — see note ▼. | request-surface 59 ✓; full 1913 ✓ |
| `starlette` | 0.38.6 | **1.6.0** | PYSEC-2026-161, -248, -249, -1941, -1943, -2280, -2281 (9) | Only new deprecation: `HTTP_422_UNPROCESSABLE_ENTITY` → `_CONTENT` (old constant still works; left as-is, not a workaround). | full 1913 ✓ |
| `python-multipart` | 0.0.20 | **0.0.32** | PYSEC-2026-1852, -3036, -3037, -3038, -3039, -3040 (6) | None (`pip check` clean). Transitive via FastAPI form/file parsing. | upload subset 36 ✓; full 1913 ✓ |
| `python-dotenv` | 1.0.1 | **1.2.2** | PYSEC-2026-2270 | None. Used by pydantic-settings. | config load ✓; full 1913 ✓ |
| `ecdsa` | 0.19.2 | *(no fix)* | PYSEC-2026-1325 — **ACCEPTED RISK** ▼ | Already latest; hard (non-extra) dep of python-jose — removal would be a workaround (deferred pending approval). | n/a |

  **▼ FastAPI 0.141 routing-representation fallout (both fixed this increment, app-code + test-infra):**
  - `MetricsMiddleware.normalise_path` used `route.path_format`, now the **router-relative**
    template (mount prefix stripped) — every Prometheus `path` label silently lost its `/api/v1`
    prefix. Rebuilt the label from the full request path + resolved `path_params`; verified the
    label is `/api/v1/production/version` again. Dashboards/alerts keyed on the prefix stay valid.
  - The tenant-isolation and write-IDOR sweeps discovered farm-scoped routes by walking
    `app.routes`, which now returns 0 leaf routes — their sanity guard (`assert >150 / >80`)
    tripped, meaning the sweeps had **become no-ops**. Added a recursive `_iter_api_routes` walker;
    discovery restored to **220 GET + 116 POST** farm-scoped routes (matches the historical counts).
    The isolation guard is live again and green.

- **ACCEPTED RISK 1 — `ecdsa` PYSEC-2026-1325 (backend):** Minerva timing side-channel on the
  P-256 curve. Affects ECDSA **signing, key generation, and ECDH** — **signature verification is
  unaffected**, and the python-ecdsa project considers side-channels out of scope (**no planned
  fix**). Greena issues **HS256 (HMAC)** JWTs only (`app/core/security.py`), so no ECDSA signing,
  keygen, or ECDH ever executes; `ecdsa` is present solely as a hard transitive dependency of
  `python-jose`. Exposure on our code path is **nil**. Cannot be upgraded (latest) and would need
  a dependency-graph workaround to remove — deferred, not worked around, per the increment rule.
- **ACCEPTED RISK 2 — `react-router` GHSA-wrjc-x8rr-h8h6 + GHSA-337j-9hxr-rhxg (frontend, 2
  moderate):** fixed only in **react-router v7.18+**, a breaking major migration (our 6.30.4 is
  already the newest v6 and still flagged). **Owner-accepted** (see decision below). Exposure
  analysis: advisory #2 (arbitrary constructor injection via `deserializeErrors()` in **SSR
  hydration**) is **not applicable** — Greena's frontend is a client-only Vite SPA (`createRoot`,
  no SSR); advisory #1 (open redirect via backslash in `<Link>`/`useNavigate`) is **not reachable**
  — every navigation target is an application-defined constant, with no `?redirect=`/`returnTo`
  handling anywhere in `src/`.
  > **Owner decision (2026-08-11):** Accepted Risk — React Router v6.30.4 advisories. The
  > application is a client-side Vite SPA and does not implement SSR. All navigation targets are
  > application-defined constants; no user-controlled redirect parameters are accepted.
  > **Revisit when:** SSR/server rendering is introduced; dynamic redirect parameters are added;
  > or a major frontend framework upgrade is scheduled.
  >
  > **Migration timing (owner):** react-router 6.30.4 is already the newest v6 — the fix exists
  > only in the breaking v7 series. Bundle the v7 migration into a **future frontend
  > framework upgrade**; do **not** introduce a major routing change during the production-
  > readiness gate.
- **Recommendation:** add `pip-audit` + `npm audit` gates to CI so new advisories surface
  automatically (P2); schedule the react-router v7 migration as part of a future frontend
  framework upgrade (not a standalone mid-gate change).
- **Verification:** `pip-audit -r requirements.txt` (1/1, ecdsa only) + `npm audit --omit=dev`
  (2 moderate, react-router) + full backend regression **1913 passed, 0 failed** — all real scans/runs.

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
| ~~**P1**~~ | ~~**Dependency upgrades** (python-jose/starlette/python-multipart/dotenv)~~ → **RESOLVED (Inc 6)**: 22→1 backend advisories; full regression 1913 passed. Residuals `ecdsa` + `react-router` = ACCEPTED RISK. | ✅ DONE | ✅ verified |
| **P2** | Add `pip-audit` + `npm audit` gates to CI (surface new advisories automatically) | HARDEN | ✅ |
| **P2** | react-router v6→v7 migration (clears the 2 accepted frontend advisories) | HARDEN | ✅ (frontend build/test) |
| **P2** | Access-token transport hardening | HARDEN | ✅ |
| **P2** | Broaden rate limiting to exports/imports | HARDEN | ✅ |
| **P2** | Enable RLS (defense-in-depth) | HARDEN | partly (needs Supabase) |
| **P2** | Per-account lockout/backoff | HARDEN | ✅ |
| **P2** | Confirm escalation contacts + incident-response runbook | HARDEN | doc only |
| **P3** | Tamper-evident audit log | DEFER | ✅ |
| **P3** | Expand app-level backup to newer modules | DEFER | ✅ |

**Scope note:** no recommendation here requires infrastructure I cannot verify locally, except the two explicitly marked (prod TLS/CORS verification = deploy-time per the runbook; RLS enablement = needs Supabase) — those are flagged, not fabricated.

## Verdict
The application-layer security posture is **strong and regression-guarded**. The P1 dependency
finding is now **remediated (Inc 6)**: 21 of 22 backend advisories cleared (jose, fastapi/starlette,
multipart, dotenv), the full regression is green on the upgraded stack (**1913 passed, 0 failed**),
and the framework upgrade even revealed and fixed a would-be silent gap — the isolation sweeps had
degraded to no-ops under FastAPI's new routing and are now live again. The **two residual advisories
are consciously accepted**: `ecdsa` (no fix exists; off our HS256 path) and `react-router` (owner-
accepted; not applicable / not reachable in a client-only SPA). **No P0 security blocker remains.**
Production readiness now depends only on the **Gate 5 performance gate** — there is no outstanding
security blocker. See `GATE_6_CLOSURE.md` for the consolidated go/no-go package.
