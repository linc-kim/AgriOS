# Gate 6 — Production Readiness Closure

**Date:** 2026-08-11 · **Status:** Gate 6 (production readiness) work **complete**.
**Deploy remains gated on Gate 5 (performance) — see Go/No-Go.**

This is the consolidated closure package for Gate 6. It reconciles the increment work
(Inc 1–6) into a single production-readiness verdict. It introduces no new claims:
every row cites an artifact produced and verified in a prior increment.

Increment map: **1** readiness audit · **2** release-checklist refresh + runbook index ·
**3** backup/restore verification · **4** disaster recovery + alerting · **5** consolidated
security review · **6** dependency security remediation (this increment).

---

## 1. Production Readiness Scorecard

Legend: **READY** = complete + evidenced · **READY\*** = complete in code/docs, one item
verifiable only at deploy or on staging · **GATING** = blocks launch until satisfied.

| # | Area | State | Evidence |
|---|---|---|---|
| 1 | Deployment architecture | READY\* | `SYSTEM_ARCHITECTURE.md`, `DEPLOYMENT_*.md`, `Dockerfile`, `railway.toml`, `vercel.json`; prod CORS/TLS/CSP `connect-src` + shared-domain cookie verified at deploy per `DEPLOYMENT_HARDENING.md §1` |
| 2 | Secrets management | READY\* | Gate 6 scan: no tracked `.env`, no key literals; `config.py` fail-fast; frontend prod-bundle scan runs at deploy (`LAUNCH_RUNBOOK`) |
| 3 | Backup & restore | READY (app-level, **tested**) | `test_backup_restore_cycle.py` — create→verify→loss→dry-run→restore→integrity + failure paths (Inc 3); DB-level PITR = staging |
| 4 | Disaster recovery | READY | `DISASTER_RECOVERY.md` — recovery tiers, 7 scenarios, RTO/RPO (Inc 4) |
| 5 | Monitoring | READY | Sentry (prod), `metrics_service` + `MetricsMiddleware`, `/health`, `/production/diagnostics\|status`; signals in `ALERTING.md` |
| 6 | Alerting | READY | `ALERTING.md` — Critical/High/Medium/Info matrix on exposed signals (Inc 4) |
| 7 | Release checklist | READY | `LAUNCH_RUNBOOK.md` refreshed to current migration head + scope (Inc 2) |
| 8 | Operational runbooks | READY (one HARDEN) | `RUNBOOK_INDEX.md`; provider-outage/scheduler/secret-rotation in `DISASTER_RECOVERY.md §2`; general incident-response runbook still to add (P2) |
| 9 | Production security review | READY (2 accepted risks) | `PRODUCTION_SECURITY_REVIEW.md` — 12 domains, RLS assessment, P0–P3 register (Inc 5) |
| 10 | Environment validation | READY | `diagnostics_service.run_startup_validation` — invalid prod config **fails boot** (`main.py` lifespan) |
| 11 | Dependency security | READY (2 accepted risks) | **Inc 6** — backend `pip-audit` 22→1; frontend `npm audit` 2 moderate accepted; full regression **1913 passed** |
| — | **Performance (Gate 5)** | **GATING** | Staging-only; load/latency criteria not verifiable in the local environment. **Must pass before launch.** |

**Test posture (this increment):** full backend regression **1913 passed, 0 failed** on the
fully-upgraded dependency stack; targeted gates green at every step (auth 13, request-surface 59,
uploads 36, production/metrics 37).

---

## 2. Go / No-Go recommendation

**CONDITIONAL GO — go for launch once Gate 5 (performance) passes on staging and the deploy-time
verifications complete.**

- **Security & operational readiness: GO.** No P0 security blocker remains. The one materially new
  finding from the security review — dependency CVEs — is remediated (§Dependency remediation), and
  the framework upgrade additionally restored an isolation guard that had silently degraded.
- **Performance readiness: PENDING (Gate 5).** Load, latency, and pool-pressure criteria are
  inherently staging-measured and are the standing deploy gate. This package does not and cannot
  clear it locally.

The application is production-ready on every axis that can be established off-staging. Launch is
gated only by the performance validation that must run against real infrastructure.

---

## 3. Launch blockers

| Blocker | Owner | Why it blocks | Where |
|---|---|---|---|
| **Gate 5 performance validation** | Perf/infra | Load + latency criteria unproven; standing deploy gate | Gate 5 staging runbook |
| **Deploy-time prod-config smoke** | Deploy | CORS/TLS/CSP `connect-src` + shared-domain cookie only verifiable against real hosts | `LAUNCH_RUNBOOK.md §3`, `DEPLOYMENT_HARDENING.md §1` |
| **Frontend production-bundle secret scan** | Deploy | Bundle is built at deploy; scan runs then | `LAUNCH_RUNBOOK` release checklist |

None of these is an application-code defect; all are staging/deploy-time verifications by nature.

---

## 4. Accepted risks

| Risk | Class | Rationale | Revisit when |
|---|---|---|---|
| `ecdsa` PYSEC-2026-1325 (Minerva timing side-channel) | ACCEPTED | No fix exists (upstream out-of-scope). Affects ECDSA sign/keygen/ECDH — **not** verification. Greena uses **HS256/HMAC** only, so no ECDSA code runs; `ecdsa` is a hard transitive dep of `python-jose`. Exposure nil. | An asymmetric-JWT (RS/ES) algorithm is introduced, or a fixed `ecdsa`/replacement lands |
| `react-router` v6.30.4 advisories (2 moderate) | ACCEPTED (owner) | Fix only in breaking v7. Advisory #2 (SSR-hydration injection) **N/A** — client-only Vite SPA. Advisory #1 (open redirect) **not reachable** — all nav targets are constants; no `?redirect=`/`returnTo`. | SSR introduced; dynamic redirect params added; major frontend upgrade scheduled |
| RLS disabled (Postgres row-level security) | ACCEPTED | Intentional — app is the only DB path; authz enforced app-layer + guarded by IDOR sweeps (220 read + 116 write, 0 leaks) | Direct/BI DB access with a broad role is ever granted |
| Access token in JS storage | ACCEPTED (bounded) | Bounded by 15-min expiry + strict CSP; refresh token is httpOnly | XSS surface changes; hardening scheduled (P2) |

---

## 5. Deferred work (post-launch, non-blocking)

| Item | Priority | Note |
|---|---|---|
| `pip-audit` + `npm audit` gates in CI | P2 | Surface new advisories automatically |
| react-router v6→v7 migration | P2 | Clears the 2 accepted frontend advisories |
| General incident-response runbook | P2 | Provider/scheduler/rotation already covered in `DISASTER_RECOVERY.md §2` |
| Access-token transport hardening (in-memory) | P2 | Reduce XSS exposure window |
| Broaden rate limiting to exports/imports | P2 | Auth already rate-limited; AI bounded by quota |
| Enable RLS as defense-in-depth | P2 | Needs Supabase; strengthening, not a fix |
| Per-account lockout/backoff | P2 | Beyond the `/auth` rate limit |
| Tamper-evident audit-log chain | P3 | Logs already append-only + immutable |
| **Paystack integration** | Separate project | Owner-deferred to a post-hardening project; **out of scope for Gate 6** (no planning doc produced this gate, by direction) |

---

## 6. Final production recommendation

**Ship-ready pending Gate 5.** Greena's application-layer security and operational posture is
strong, evidenced, and regression-guarded: 12 security domains reviewed, dependency CVEs remediated
(22→1 backend, both residuals consciously accepted and off the live code path), backup/restore
tested end-to-end, DR and alerting documented, environment validation fails-boot on misconfig, and
the full **1913-test** suite is green on the upgraded stack. The isolation sweeps — the automated
guard behind the tenant-isolation and IDOR guarantees — are confirmed live after the framework
upgrade.

**Recommendation:** proceed to Gate 5 performance validation on staging. On a Gate 5 pass plus the
three deploy-time smoke verifications (§3), **launch is approved from a production-readiness
standpoint.** No security or operational blocker stands in the way.
