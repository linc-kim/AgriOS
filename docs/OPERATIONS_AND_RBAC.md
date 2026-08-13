# Greena — Hardening Audit, Roles & Permissions, Module Reference

Source-grounded reference for operating Greena V1. Every role, permission, and
module below is extracted from the actual codebase (`app/core/permissions.py`,
`app/models/`, `app/api/v1/`), not assumed. Date: 2026-08-13 · commit `1e690bb`.

---

## Part A — Production Hardening Audit

Method: source inspection of the payment, webhook, scheduler, AI, and auth
paths + live database queries. Findings are stated as **verified-robust**,
**fixed this pass**, or **defer (measured/low-value)** — no speculative changes.

| Area | Finding | Status |
|---|---|---|
| External HTTP calls (Paystack, AI) | All bounded: Paystack `timeout=20`; AI `timeout=AI_CALL_TIMEOUT_SECONDS` (15s). No unbounded awaits. | ✅ Robust |
| Payment activation idempotency | `_verify_and_activate` short-circuits on `txn.status == "success"` → `already_processed`; amount, currency, and metadata all re-verified against the **stored** record (never the client). Period end is absolute, so re-activation is not additive. | ✅ Robust |
| Amount / currency / metadata tampering | Rejected with 422 (verified against Paystack's own record). | ✅ Robust |
| Webhook signature | HMAC-SHA512, constant-time; invalid/missing/tampered/whitespace-altered bodies → 401 (verified live). | ✅ Robust |
| Duplicate webhook (sequential) | Idempotent — same signed body twice returns identical result; reward gated by `reward_status` + first-payment count. | ✅ Robust |
| **Referral reward (concurrent duplicate)** | `credit_ledger` had **no DB-level idempotency** — only the app `reward_status` read-then-write guard, racy under concurrent delivery → possible double-credit. **Fixed:** migration 091 adds a partial UNIQUE index on `credit_ledger(payment_reference, source)`; a duplicate insert is now rejected by the DB (verified in prod). | 🔧 Fixed |
| Scheduler failure / restart | Single leader via Postgres advisory lock; on lock loss the next instance takes over (handover, not duplication). Verified: restarts re-elect a leader, 9 jobs re-register. | ✅ Robust |
| Deployment / restart recovery | Migration runs on boot (idempotent); `/health` returns 503 until the DB is reachable, so the platform never routes to a degraded instance. Verified across multiple deploys. | ✅ Robust |
| DB indexing | Hot scoping columns are already indexed; only 4 minor FK columns unindexed (3 AI-table `flock_id`, `payment_transactions.subscription_id`) on near-empty tables — no measured slow query. | ⏸ Defer (no measured need) |
| Logging | Structured (`timestamp | level | logger | message`), request-id middleware, visible in Render logs. | ✅ Present |
| Error alerting | Sentry initialised in production (FastAPI + SQLAlchemy integrations). Event **delivery** needs a Sentry-dashboard check (owner). | ⚠ Verify in dashboard |
| **Backups / DR** | Supabase free tier has **no PITR/automated backups** — the top remaining reliability gap. | ⛔ Owner action |

**Net:** the money-path idempotency gap was the one real correctness bug found and is fixed with a DB guarantee. The remaining reliability gap (backups) is owner-controlled (upgrade Supabase or schedule `pg_dump`).

---

## Part B — Roles & Permissions (from `app/core/permissions.py`)

**8 roles.** Platform roles (`super_admin`, `platform_admin`) have `farm_id = NULL`; the rest are farm-scoped. Access is enforced per-endpoint via `require_permission(Permission.X)` against a **191-permission** matrix.

| Role | Scope | Capability summary |
|---|---|---|
| **super_admin** | Platform | **All 191 permissions.** Platform owner / super administrator. Activates platform-wide modules, admin billing, diagnostics, everything. |
| **platform_admin** | Platform | Platform administration subset (support/ops/billing administration). Not farm-assignable. |
| **enterprise_owner** | Org | Seeded for multi-farm enterprise; V1 mirrors `farm_owner`. |
| **farm_owner** | Farm | Full control of the farm: members, billing entitlement consumption, all production/health/finance/feed/inventory/automation writes, backups, data export. |
| **farm_manager** | Farm | Day-to-day management: production/health/finance/feed/inventory/automation writes; no member/role changes or destructive farm ops. |
| **vet_consultant** | Farm | Health-focused: logs health/vaccination + views most modules read-only. |
| **farm_worker** | Farm | Field data entry: logs ops/feed/production; views assigned modules; no finance/admin. |
| **viewer** | Farm | Read-only across the farm; changes nothing. |

**Permission domains (191 total), by size:**

| Domain | Perms | What it governs |
|---|---|---|
| `sr` | 31 | Small Ruminant (Goat + Sheep, unified) |
| `swine` | 29 | Pig framework |
| `rabbit` | 27 | Rabbit management |
| `bsf` | 23 | Black Soldier Fly / insect farming |
| `avi` | 19 | Aviculture / ornamental birds |
| `opsplan` | 11 | Operations Planner (routine engine) |
| `admin` | 8 | Platform administration (super_admin) |
| `farm` | 7 | Farm + membership management |
| `ops` | 6 | Daily logs, feed, weigh-in, production entry |
| `health` | 5 | Vaccination, disease events, alerts |
| `flock` | 5 | Flock lifecycle (poultry core) |
| `finance` | 5 | Expenses, revenue, records |
| `feed` / `inventory` / `data` / `automation` / `ai` | 2 each | Feed, inventory/assets, export/backup, automation rules, AI (ARIA) |
| `production` / `notification` / `market` / `diagnostics` / `backup` | 1 each | Cross-cutting single-permission areas |

**Grant model:** writers vs readers are assigned by domain loops — e.g. feed/inventory: `enterprise_owner, farm_owner, farm_manager, farm_worker` get `MANAGE`; `vet_consultant, viewer` get `VIEW`. Automation: managers and up write, workers/viewers read. Species modules (`avi`, `bsf`, …) follow the same full/view split. This keeps the matrix consistent and auditable.

### Administrative responsibilities (mapping to the brief's roles)
- **Platform Owner / Super Administrator** → `super_admin`: platform module activation, admin billing grants/revokes, diagnostics, all orgs.
- **Billing Administrator / Customer Support** → `platform_admin` (+ admin billing permissions): subscription grants, support views. *(No separate `billing_admin`/`support` role exists — these are platform-admin responsibilities in V1.)*
- **Farm Owner** → `farm_owner`; **Farm Manager** → `farm_manager`; **Workers** → `farm_worker`; plus `vet_consultant` and `viewer` for specialised/read-only access.

---

## Part C — Module & Capability Catalog (from `app/api/v1/` + models)

Production modules (each a full engine: records → health → finance → reports):
**Poultry** (flock core), **Aviculture / Ornamental Birds**, **Black Soldier Fly (BSF)**, **Rabbit**, **Small Ruminant (Goat + Sheep, shared schema)**, **Swine**, plus **Fish/Aquaculture** (roadmap per project docs).

Platform capabilities: **Organizations & Farms** (multi-tenant, RBAC), **Finance** (expenses/revenue/snapshots), **Health** (vaccination/disease/alerts), **Feed & Inventory**, **Automation** (rules + reminders), **Reports & Exports** (CSV/PDF), **ARIA** (AI assistant — deterministic-first routing with Gemini/Claude providers and an offline fallback), **Mission Control** (strategic layer), **Operations Planner** (routine engine), **Billing/Commercial** (plans, 21-day trial, referrals, credit ledger, Paystack), **Notifications**, **Admin** (platform + billing).

Data model scale: **203 tables, 607 foreign keys**, schema at alembic head **091**.

---

## Scope note (Phases B, E, F)

- **Capacity (Phase B):** the free-tier ceiling is **measured** at ~8–10 rps (knee ~5 concurrent) — see `RELEASE_V1.0.0.md`. Staged 250/500/750/1000-concurrent tests are **not run** because a single 512 MB / 1-worker instance cannot represent that scale; the numbers would be an artefact of saturation, not evidence of support. Re-run after a paid-tier upgrade.
- **Disaster Recovery (Phase C):** restart/deploy/scheduler recovery are **verified** (this doc + release doc); DB-outage handling is verified via the `/health` 503 gate. Backup/restore is the open owner action.
- **Farmer Manual (Phase E) & Encyclopedia (Phase F):** these are exhaustive per-screen/per-button writing efforts. This document is the accurate backbone (real roles, permissions, modules); the full manual + encyclopedia should be authored as a focused follow-on, screen by screen against the live UI, rather than generated speculatively — accuracy over volume.
