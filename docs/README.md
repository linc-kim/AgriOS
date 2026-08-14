# Greena Documentation

The definitive documentation set for Greena — the Agricultural Operating System.
Every fact here is grounded in the production system (code, schema, live config)
as of commit `beb8e8f`, schema head `091`.

## Operational excellence
| Doc | Audience | Purpose |
|---|---|---|
| [OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md) | Ops / on-call | Run, deploy, monitor, and recover the platform |
| [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) | Ops / owner | Recovery procedures for every failure mode |
| [SUPPORT_PLAYBOOKS.md](SUPPORT_PLAYBOOKS.md) | Support | Step-by-step responses to common tickets |
| [RELEASE_V1.0.0.md](RELEASE_V1.0.0.md) | Owner / ops | Release notes, rollback, launch & monitoring checklists |
| [OPERATIONS_AND_RBAC.md](OPERATIONS_AND_RBAC.md) | Ops / admin | Hardening audit + role/permission/module reference |

## Role manuals
| Doc | Audience |
|---|---|
| [OWNER_MANUAL.md](OWNER_MANUAL.md) | Platform owner / founder |
| [ADMINISTRATOR_MANUAL.md](ADMINISTRATOR_MANUAL.md) | Super / platform / billing administrators |
| [FARMER_MANUAL.md](FARMER_MANUAL.md) | Farm owners & managers |
| [WORKER_MANUAL.md](WORKER_MANUAL.md) | Farm workers |
| [ARIA_MANUAL.md](ARIA_MANUAL.md) | All users — the AI assistant |

## Product & business
| Doc | Purpose |
|---|---|
| [GREENA_ENCYCLOPEDIA.md](GREENA_ENCYCLOPEDIA.md) | What Greena is, why each part exists, how it all fits |
| [ONBOARDING_AND_TRAINING.md](ONBOARDING_AND_TRAINING.md) | Onboarding flows + training curricula per role |
| [ROADMAP_AND_BUSINESS.md](ROADMAP_AND_BUSINESS.md) | Roadmap, pricing model, business logic |

## Ground-truth quick reference
- **Stack**: Vercel (frontend) → Render (backend, `greena-api-v91z.onrender.com`) → Supabase (Postgres, eu-west-1). Payments: Paystack. AI: Gemini + Claude.
- **Roles (8)**: `super_admin`, `platform_admin`, `enterprise_owner`, `farm_owner`, `farm_manager`, `vet_consultant`, `farm_worker`, `viewer` — 191 permissions.
- **Plans (KES/mo)**: Free 0 · Starter 999 · Professional 1499 · Farm Pro 2499 · Enterprise custom. 21-day Professional trial on org creation. Referral → first Starter payment KES 599; referrer earns KES 100 on activation.
- **Modules**: Poultry, Aviculture, BSF, Rabbit, Small Ruminant (Goat/Sheep), Swine (+ Fish roadmap); Finance, Health, Feed/Inventory, Automation, Reports, ARIA, Mission Control, Operations Planner, Billing, Admin.
- **Schema**: 203 tables, 607 FKs, alembic head 091.

> Scope note: these documents are accurate and comprehensive at the system/role/workflow level. A literal per-pixel "every button" screenshot walkthrough should be captured against the live UI during onboarding-video production; where a screen is referenced, the underlying capability and permission are documented from source.
