# AGRIOS V1 MASTER BLUEPRINT (FROZEN)

**Document Authority:** Chief Technology Officer  
**Document Status:** FROZEN — No changes permitted after this document is signed off  
**Effective From:** Sprint 0, Day 1  
**Supersedes:** All prior design notes, audit findings, and draft blueprints  
**Override Process:** Any change to a locked decision requires explicit written CTO override with documented justification  

---

> This document is the single source of truth for AGRIOS V1.  
> It does not introduce new decisions. It locks existing ones.  
> Sprint 0 begins the moment this document is finalised.

---

---

# SECTION 1 — FINAL AGRIOS V1 DEFINITION

---

## What AGRIOS V1 Is

AGRIOS is an **Agricultural Operating System** delivered as a mobile-first Progressive Web App, designed for smallholder and semi-commercial poultry farmers in Kenya. It is the operational backbone of a farm — the system that tracks daily activity, monitors financial performance, manages bird health records, and provides AI-powered operational intelligence through a conversational assistant named ARIA.

**AGRIOS V1 is Poultry-first.** The architecture is designed to support future species modules (Rabbit, Dairy, Fish, Crop) without schema modification, but V1 ships with Poultry as the only active operational module.

**AGRIOS V1 is Kenya-first.** Phone-based authentication, KES currency, Africa's Talking SMS, Swahili language support, and Kenya county targeting are non-negotiable V1 features, not future additions.

**AGRIOS V1 is not an infrastructure platform.** It is not an IoT system, not a drone platform, not a marketplace, not a social network. It is a farm operations tool that a farmer uses every day.

## The Product in One Sentence

> AGRIOS is the daily operating system for Kenyan poultry farmers — it tracks their birds, monitors their money, manages their health records, and answers their questions with AI.

## The Strategic Thesis (Locked)

> **Health gets the install. Profit keeps the user.**

- Disease alerts and vaccination management are the acquisition feature — a farmer facing a sick bird needs help immediately
- Daily P&L tracking and financial intelligence are the retention feature — a farmer thinks about money every day
- ARIA (the AI assistant) is the engagement flywheel — it turns operational data into insight and makes AGRIOS indispensable

---

---

# SECTION 2 — FINAL SCOPE LOCK

---

## INCLUDED IN V1

### Core Platform
- Phone OTP registration and login (Africa's Talking SMS)
- PIN-based subsequent authentication
- JWT access and refresh token management
- 8-role RBAC system (seeded and enforced)
- Farm creation, structure management (units + production houses)
- Farm member invite and role assignment
- SMS notification delivery (vaccinations, log reminders, disease alerts)
- In-app notification centre
- Background job scheduler (daily reminders, insight generation)
- Swahili / English language toggle

### Poultry Module
- Flock creation and lifecycle management (active → sold / closed / culled)
- Daily operations logging: mortality, feed consumption, egg production
- Weigh-in records and biomass tracking
- Feed purchase logging
- Daily log completeness tracking and nudges
- Vaccination records and upcoming vaccination schedule
- Disease alert consumption (read from admin-published alerts)
- Financial engine: expense logging, revenue recording, P&L snapshot computation
- Calculators: feed needs, profit projection, break-even, FCR
- Market prices board (curated by admin)
- Flock performance metrics: FCR, survival rate, daily mortality average

### Admin Module
- Platform overview dashboard (users, farms, AI usage, costs)
- User management (view, search, suspend, adjust quota)
- Farm oversight (view all farms and their data)
- Subscription plan management (override per farm)
- Disease alert publisher (create, publish, update, deactivate, SMS dispatch)
- Market price manager (add, update)
- AI usage and cost reporting

### ARIA — AI Assistant Lite
- Conversational Q&A on the farmer's own farm data
- Daily proactive insights (8 insight types, generated at 06:00 Nairobi)
- Structured action recommendations (triggered by thresholds)
- AI quota enforcement per subscription plan
- Gemini 2.0 Flash as primary provider, Claude Haiku as fallback
- Responses in English or Swahili (matching user's question language)

### Infrastructure
- PWA: installable on Android Chrome without app store
- Offline-aware: cached data visible when connection lost
- Service worker for static asset caching
- Automated daily database backups (Supabase)
- Error monitoring (Sentry)
- CI/CD pipeline (GitHub Actions → Railway + Vercel)
- Audit log for all data mutations

---

## EXCLUDED FROM V1

The following are explicitly deferred. They may not be added to V1 sprints without a formal override.

### Features Deferred to Phase 2
- AI disease diagnosis (text-based symptom assessment)
- AI sell-timing advisor
- AI proactive SMS morning briefings
- Image upload for health records and receipts
- Voice input to ARIA (Swahili STT)
- PDF report export (batch performance, P&L)
- M-Pesa payment integration for subscription upgrades

### Features Deferred to Phase 3
- Full offline-first operation (local SQLite queue + background sync)
- Outbreak pattern detection (cross-farm anonymised health event aggregation)
- ARIA image-based disease diagnosis (photo + symptom assessment)

### Features Deferred to Phase 4 and Beyond
- ARIA autonomous action-taking (agent mode)
- Multi-farm enterprise analytics
- Predictive disease risk scoring
- Marketplace (feed, vaccine, chick suppliers)
- Farmer community and verified discussions
- Vet consultation booking and payment
- Weather integration
- IoT sensor integration
- Drone or satellite systems
- Insurance or lending products
- Rabbit OS module
- Dairy OS module
- Fish OS module
- Crop OS module
- Enterprise multi-farm account tier

### Architecture Components Not Activated in V1
- `enterprise_owner` role (seeded but no user-facing flows)
- `platform_admin` role (seeded but founder uses `super_admin`)
- File storage pipeline (Supabase Storage configured, not user-facing)
- All species in `species_profiles` except Poultry (`is_active = FALSE`)

---

---

# SECTION 3 — FINAL SYSTEM ARCHITECTURE

---

## Architecture Statement

AGRIOS V1 is a four-pillar system. The pillars are independently buildable but have strict dependency chains. No pillar's functionality is accessible without its prerequisite pillars being operational.

```
┌──────────────────────────────────────────────────────────┐
│                    AGRIOS V1 SYSTEM                      │
├──────────────────┬───────────────────────────────────────┤
│  PILLAR 1        │  CORE PLATFORM                        │
│  (Foundation)    │  Auth · Roles · Farms · SMS · Jobs    │
├──────────────────┼───────────────────────────────────────┤
│  PILLAR 2        │  POULTRY MODULE                       │
│  (Product)       │  Flocks · Ops · Health · Finance      │
├──────────────────┼───────────────────────────────────────┤
│  PILLAR 3        │  ADMIN MODULE                         │
│  (Operations)    │  Users · Alerts · Market · Analytics  │
├──────────────────┼───────────────────────────────────────┤
│  PILLAR 4        │  ARIA — AI ASSISTANT LITE             │
│  (Intelligence)  │  Context · Chat · Insights · Recs     │
└──────────────────┴───────────────────────────────────────┘
```

## Dependency Chain (Final)

```
[1] Auth & Identity
        │
        ├──[2] Role & Permission Engine
        │           │
        │           └──[3] Farm Infrastructure (farms, units, houses)
        │                       │
        │                       ├──[4] Flock Management
        │                       │           │
        │                       │           ├──[5] Daily Operations
        │                       │           │           │
        │                       │           │           ├──[6] Financial Engine
        │                       │           │           │           │
        │                       │           │           │           └──[7] Calculators
        │                       │           │           │
        │                       │           │           └──[8] ARIA Context Compiler
        │                       │           │                       │
        │                       │           │                       ├──[9] Conversation Engine
        │                       │           │                       ├──[10] Insight Generator
        │                       │           │                       └──[11] Recommendation Engine
        │                       │           │
        │                       │           └──[12] Health Management
        │                       │
        │                       └──[13] Admin Farm Oversight
        │
        ├──[14] Notification Engine
        │           │
        │           └──[15] Admin Alert Publisher
        │
        └──[16] Market Price Manager (Admin, standalone)
```

**Critical path to MVP (shortest build sequence):**  
`[1] → [2] → [3] → [4] → [5] → [6] → [8] → [9] → Dashboard integration → Admin`

## Technology Stack (Final, Locked)

| Layer | Technology | Version | Rationale |
|---|---|---|---|
| Backend framework | FastAPI | Python 3.12 | Async-first, AI ecosystem, existing choice |
| ORM | SQLAlchemy | 2.x async | Type-safe, async-compatible |
| Migrations | Alembic | Latest | Paired with SQLAlchemy |
| Database | PostgreSQL | 16 via Supabase | Relational integrity, managed service |
| Auth | Custom OTP + JWT | — | Kenya phone-first, AT integration |
| SMS | Africa's Talking | — | Kenyan coverage, price, local infrastructure |
| Frontend | React + Vite + TypeScript | React 18 | AI-assisted dev quality, PWA support |
| Styling | Tailwind CSS | Latest | Mobile-first utilities |
| State | Zustand + TanStack Query | — | Lightweight, offline-aware |
| Forms | React Hook Form + Zod | — | Validation at schema level |
| Charts | Recharts | — | SVG, mobile-compatible |
| i18n | i18next | — | English + Swahili |
| PWA | Vite PWA plugin | — | Auto service worker + manifest |
| Backend hosting | Railway | — | Zero-ops, GitHub deploy |
| Frontend hosting | Vercel | — | CDN, preview deployments |
| Primary AI | Gemini 2.0 Flash | — | Speed, cost, Swahili, multimodal (Phase 2) |
| Fallback AI | Claude Haiku | — | Reliability, structured output |
| Background jobs | FastAPI + APScheduler | — | Embedded scheduler, sufficient for V1 |
| Error monitoring | Sentry | — | Real-time alerts to founder |

---

## Extensibility Principle (Locked, Constitutional)

**AGRIOS Core never changes to activate a new species.** The `species_profiles` table is the extensibility engine. Activating Rabbit OS in V2 requires:
1. `UPDATE species_profiles SET is_active = TRUE WHERE species_key = 'rabbit'`
2. Add rabbit-specific tables (does not modify any existing table)

No existing table is altered. No existing API is modified. No migration touches a live operational table.

---

---

# SECTION 4 — FINAL DATABASE MODEL SUMMARY

---

## Architectural Constants (Database Layer)

- **UUID v4 primary keys** — all tables
- **Soft deletes** — `deleted_at TIMESTAMPTZ NULL` on all operational tables
- **Timestamps** — `created_at` and `updated_at` on all tables
- **Farm tenancy** — `farm_id` on every operational table; row-level access enforced in application
- **Species extensibility** — `species_key VARCHAR(50)` FK to `species_profiles` on all species-specific tables
- **JSONB extensibility** — `metadata JSONB DEFAULT '{}'` on all tables that may require future fields
- **Audit trail** — `created_by UUID` FK to `users` on all user-generated records

## Migration Sequence (30 Migrations, Final)

### Tier 0 — Authentication Foundation (Migrations 001–005)
| # | Table | Purpose |
|---|---|---|
| 001 | `roles` | 8 role definitions (seeded) |
| 002 | `users` | User accounts |
| 003 | `user_roles` | Role-to-farm assignment |
| 004 | `otp_requests` | OTP delivery and verification |
| 005 | `sessions` | JWT session tracking |

### Tier 1 — Platform Configuration (Migrations 006–007)
| # | Table | Purpose |
|---|---|---|
| 006 | `subscription_plans` | Free / Starter / Pro definitions (seeded) |
| 007 | `species_profiles` | Species registry; Poultry active, all others `is_active = FALSE` (seeded) |

### Tier 2 — Farm Structure (Migrations 008–011)
| # | Table | Purpose |
|---|---|---|
| 008 | `farms` | Farm registry with plan and owner |
| 009 | `farm_members` | Farm membership and roles |
| 010 | `farm_units` | Physical farm sections |
| 011 | `production_houses` | Individual structures within units |

### Tier 3 — Poultry Operations (Migrations 012–016)
| # | Table | Purpose |
|---|---|---|
| 012 | `flocks` | Bird batches with lifecycle state |
| 013 | `daily_logs` | Daily mortality, feed, water per flock. UNIQUE(flock_id, log_date) |
| 014 | `production_records` | Egg and production output per flock |
| 015 | `weighin_records` | Weight samples and biomass estimates |
| 016 | `feed_purchases` | Feed stock purchases (farm or flock level) |

### Tier 4 — Health (Migrations 017–018)
| # | Table | Purpose |
|---|---|---|
| 017 | `vaccination_records` | Vaccination events with `next_due_date` computation |
| 018 | `disease_alerts` | Platform-wide alerts (no farm FK; county + species targeted) |

### Tier 5 — Finance (Migrations 019–022)
| # | Table | Purpose |
|---|---|---|
| 019 | `expense_categories` | 17 categories seeded; `is_system` categories cannot be deleted |
| 020 | `expenses` | Individual expense records |
| 021 | `revenue_records` | Sales and revenue events |
| 022 | `financial_snapshots` | Pre-computed P&L per flock/farm/period. Never real-time aggregated. |

### Tier 6 — AI (Migrations 023–027)
| # | Table | Purpose |
|---|---|---|
| 023 | `ai_conversations` | Conversation threads |
| 024 | `ai_messages` | Individual messages (user + assistant) |
| 025 | `ai_insights` | Proactively generated farm insights. Expires via `expires_at`. |
| 026 | `ai_recommendations` | Structured action recommendations. Status: pending → acted / dismissed / expired |
| 027 | `ai_usage_log` | Immutable cost and usage record per AI call |

### Tier 7 — Platform Layer (Migrations 028–030)
| # | Table | Purpose |
|---|---|---|
| 028 | `notifications` | In-app notification storage per user |
| 029 | `audit_logs` | Immutable append-only mutation log for all data changes |
| 030 | `market_prices` | Admin-curated price data. Historical (new rows only, no updates) |

## Critical Constraints (Final)

| Rule | Enforcement Layer |
|---|---|
| One active flock per production house at a time | Application (checked on POST /flocks) |
| `UNIQUE(flock_id, log_date)` | Database constraint — enables safe daily log upsert |
| `UNIQUE(farm_id, user_id)` in farm_members | Database constraint — one role per user per farm |
| Financial records use soft delete only | Application convention — `deleted_at` never NULL for finance |
| `audit_logs` is append-only | No UPDATE endpoint exists; no application layer update path |
| `species_profiles.is_active` can only be set by `super_admin` | Application permission check |
| OTP: max 3 wrong attempts before lock | Application layer — checked against `otp_requests.attempts` |
| Financial snapshots are computed, never manually entered | No POST from user; only triggered by expense/revenue mutations |

---

---

# SECTION 5 — FINAL USER ROLES & RBAC

---

## Role Definitions (8 Roles, Final)

| Role Key | Display Name | Scope | V1 Active |
|---|---|---|---|
| `super_admin` | Super Admin | Platform-wide | ✅ — Founder only |
| `platform_admin` | Platform Admin | Platform-wide | Seeded, no V1 UI flows |
| `enterprise_owner` | Enterprise Owner | Multi-farm | Seeded, deferred to V2 |
| `farm_owner` | Farm Owner | Single farm | ✅ |
| `farm_manager` | Farm Manager | Single farm | ✅ |
| `vet_consultant` | Vet / Consultant | Single farm (read health only) | ✅ |
| `farm_worker` | Farm Worker | Single farm (daily ops) | ✅ |
| `viewer` | Viewer | Single farm (read only) | ✅ |

**V1 user-facing roles:** `farm_owner`, `farm_manager`, `vet_consultant`, `farm_worker`, `viewer`  
**Founder uses:** `super_admin`  
**Not user-facing in V1:** `platform_admin`, `enterprise_owner`

---

## Permission Matrix (Final)

**Legend:** ✅ Full access · 👁 Read only · ✏️ Own records only · ❌ Denied · 🔒 Super admin only

| Permission | super_admin | farm_owner | farm_manager | vet_consultant | farm_worker | viewer |
|---|---|---|---|---|---|---|
| **FARM MANAGEMENT** | | | | | | |
| Create farm | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Edit farm profile | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Delete farm | 🔒 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Add farm unit / house | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Invite farm members | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Remove farm members | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Change member roles | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **FLOCK MANAGEMENT** | | | | | | |
| Create flock | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Close / sell flock | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View flock list | ✅ | ✅ | ✅ | 👁 | 👁 | 👁 |
| View flock detail | ✅ | ✅ | ✅ | 👁 | 👁 | 👁 |
| **DAILY OPERATIONS** | | | | | | |
| Submit daily log | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Correct daily log | ✅ | ✅ | ✅ | ❌ | ✏️ | ❌ |
| Log feed purchase | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Log weigh-in | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Log production (eggs) | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| View daily logs | ✅ | ✅ | ✅ | 👁 | 👁 | 👁 |
| **HEALTH MANAGEMENT** | | | | | | |
| Log vaccination | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| View vaccination schedule | ✅ | ✅ | ✅ | ✅ | 👁 | 👁 |
| View disease alerts | ✅ | ✅ | ✅ | ✅ | 👁 | 👁 |
| **FINANCE** | | | | | | |
| Log expense | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Edit / delete expense | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Log revenue / sale | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View P&L and financial reports | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **AI / ARIA** | | | | | | |
| Send ARIA message | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View ARIA insights | ✅ | ✅ | ✅ | 👁 | 👁 | ❌ |
| **ADMIN FUNCTIONS** | | | | | | |
| Access admin dashboard | 🔒 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Publish disease alerts | 🔒 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Manage market prices | 🔒 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Manage users and farms | 🔒 | ❌ | ❌ | ❌ | ❌ | ❌ |
| View AI cost and usage | 🔒 | ❌ | ❌ | ❌ | ❌ | ❌ |

## Contradictions Resolved in This Section

**Contradiction:** Prior blueprint listed 8 roles; task brief listed 5 simplified roles.  
**Resolution:** The 8 roles stand. `enterprise_owner` and `platform_admin` are seeded but have no V1 user-facing flows. The Vet role (`vet_consultant`) is **included** in V1 with read-only access to health data — Gate 3 (100 farmers) requires at least one vet organisation partner using this role.

---

---

# SECTION 6 — FINAL DASHBOARD STRUCTURE

---

## Dashboard 1 — Farmer Dashboard (PWA, Mobile-First)

**Access:** `farm_owner`, `farm_manager`, `vet_consultant` (health zones only), `farm_worker` (operations zones only), `viewer`  
**URL:** `app.agrios.app`

### Layout: 5-Tab Bottom Navigation

| Tab | Icon | Name | Primary Content |
|---|---|---|---|
| Tab 1 | 🏠 | Home | Farm Dashboard (all zones) |
| Tab 2 | 🐓 | Flock | Flock list and detail |
| Tab 3 | 💊 | Health | Vaccination schedule, disease alerts |
| Tab 4 | 💰 | Finance | P&L, expenses, revenue, calculators |
| Tab 5 | 🤖 | ARIA | AI assistant, insights, recommendations |

### Home Dashboard — 6 Zones (Final)

| Zone | Name | Data Source | Priority |
|---|---|---|---|
| Zone 1 | Active Disease Alert Banner | `disease_alerts` (county + species match) | Conditionally visible — appears only when active alert exists |
| Zone 2 | Today's Farm Pulse | `daily_logs`, `flocks` | Always visible — core engagement |
| Zone 3 | Active Flocks Summary | `flocks`, `weighin_records` | Always visible |
| Zone 4 | ARIA Insights Strip | `ai_insights` (3 most recent, undismissed) | Visible when insights exist |
| Zone 5 | Financial Pulse | `financial_snapshots` (current month) | Visible when financial data exists |
| Zone 6 | Upcoming Tasks | `vaccination_records`, `daily_logs` (completeness) | Always visible |

**Dashboard performance target:** All 6 zones loaded in under 2 seconds on a 3G connection. Powered by a single `GET /farms/:id/summary` endpoint using PostgreSQL CTEs. No N+1 queries.

### Screen Count (Farmer PWA): 61 Screens Across 9 Groups

| Group | Screen Range | Count |
|---|---|---|
| Onboarding | O-01 to O-05 | 5 |
| Farmer Dashboard | F-01 to F-03 | 3 |
| Farm Management | FM-01 to FM-07 | 7 |
| Flock Management | FL-01 to FL-08 | 8 |
| Health | H-01 to H-05 | 5 |
| Finance | FI-01 to FI-08 | 8 |
| Feed & Market | FR-01 to FR-03 | 3 |
| ARIA | AI-01 to AI-04 | 4 |
| Settings | S-01 to S-04 | 4 |
| Shared / Utility | Auth, Error, Offline | ~14 |
| **Total** | | **~61** |

---

## Dashboard 2 — Admin Dashboard (Web, Desktop-First)

**Access:** `super_admin` only  
**URL:** `admin.agrios.app`  
**Layout:** Left sidebar navigation + main content area

### Admin Navigation (8 Screens, Final)

| Screen | Code | Purpose |
|---|---|---|
| Overview | A-01 | Platform KPIs (users, farms, AI cost, alerts) |
| User Management | A-02 | List, search, suspend, adjust quota |
| Farm Management | A-03 | List all farms, override plan |
| Subscription Manager | A-04 | Plan assignments |
| Disease Alerts | A-05 | Create, publish, deactivate alerts |
| Market Prices | A-06 | Add and manage market price data |
| AI Usage & Cost | A-07 | Daily/weekly AI volume and cost |
| Settings | A-08 | Admin account settings |

**No additional dashboards exist in V1.** There is no enterprise dashboard, no vet portal, no cooperative dashboard. Any such request is deferred.

---

---

# SECTION 7 — FINAL AI DEFINITION (ARIA V1)

---

## ARIA Identity

**Name:** ARIA  
**Full name:** Agricultural Real-time Intelligence Assistant  
**V1 Name:** ARIA Lite  
**Character:** Knowledgeable, concise, data-honest, Kenya-aware. Never overconfident. Never makes up numbers.

---

## What ARIA CAN Do in V1 (Locked)

| Capability | Detail |
|---|---|
| Answer factual farm questions | Retrieves and explains data from the farmer's own records |
| Compare flocks | "Which of my flocks has the better FCR?" |
| Surface financial position | "What was my feed cost per bird this batch?" |
| Identify upcoming tasks | "What vaccines are due in the next 7 days?" |
| Cite its data sources | Every response names the data it used and the date range |
| Respond in English or Swahili | Matches the language of the farmer's question |
| Generate proactive daily insights | 8 threshold-triggered insight types, generated at 06:00 Nairobi time |
| Ask clarifying follow-up questions | One relevant follow-up per response |
| Respect quota limits | Tracks and enforces per-plan monthly query limits |
| Fail gracefully | Returns a clear, friendly error if AI providers are unavailable |

### 8 Proactive Insight Types (Final)

| Trigger | Condition | Severity |
|---|---|---|
| Mortality spike | Today's rate > 2× last 7-day average | WARNING |
| Feed drop | Today's feed < 80% of 7-day average | WARNING |
| Vaccination overdue | `next_due_date` has passed | ALERT |
| Vaccination due soon | `next_due_date` within 3 days | INFO |
| FCR above standard | FCR > breed standard + 20% | WARNING |
| Harvest approaching | Flock at 80% of expected cycle length | INFO |
| Daily log missing | Today not logged by 20:00 | REMINDER |
| Market price change | Price movement > 10% from prior week | INFO |

---

## What ARIA CANNOT Do in V1 (Locked)

| Prohibited Capability | When Available |
|---|---|
| Disease diagnosis | Phase 2 (text-based symptom assessment) |
| Veterinary medical advice | Never — always refers to vet |
| Image analysis | Phase 3 (photo-based disease assessment) |
| Invent or estimate data | Never — cites real records or states data is missing |
| Answer questions outside farm context | Never — bounded to AGRIOS data |
| Access other farms' data | Never — Farm Context Package is always farm-scoped |
| Execute actions on behalf of user | Phase 4 (autonomous agent mode) |
| Send SMS independently | Never — only admin-triggered SMS notifications |

---

## ARIA Technical Boundaries (V1)

| Parameter | Value |
|---|---|
| AI provider (primary) | Gemini 2.0 Flash |
| AI provider (fallback) | Claude Haiku |
| Context window limit | 8,000 tokens (Farm Context Package + history + prompt) |
| Context trimming order | Oldest conversation messages → old production records → daily logs > 14 days old |
| AI call timeout | 15 seconds |
| Response length | Max 150 words unless table or list is required |
| Monthly quota (free plan) | 5 queries |
| Monthly quota (starter plan) | 30 queries |
| Monthly quota (pro plan) | Unlimited |
| Insight generation schedule | Daily at 06:00 Africa/Nairobi |
| Daily log reminder | Daily at 20:00 Africa/Nairobi (per farm with missing log) |

## ARIA System Prompt (Final, V1)

```
You are ARIA, the AI Farm Operations Assistant for AGRIOS.

Your purpose: Help poultry farmers in Kenya understand their farm data and 
make better decisions. You have access to real-time data from their farm, 
provided below in the FARM CONTEXT section.

RULES YOU MUST FOLLOW:
1. Only use data from the FARM CONTEXT. Never invent numbers.
2. If data is not available, say: "I don't have that data yet — try logging 
   it in the app."
3. Do not diagnose diseases or give veterinary medical advice.
4. Maximum 150 words per response unless a table or list is necessary.
5. Always name the specific flock when referencing flock data.
6. Cite your data: "Based on your logs from June 1–14..."
7. End each response with one relevant follow-up question.
8. Respond in the same language as the user's question (English or Swahili).

FARM CONTEXT:
{farm_context_json}

CONVERSATION HISTORY:
{conversation_history}

USER QUESTION:
{user_question}
```

---

---

# SECTION 8 — FINAL MVP SUCCESS METRIC

---

## The One Metric

> **Daily Active Loggers (DAL)**  
> *The percentage of active farms that log at least one daily operational record on any given day.*

### Why This Metric and Not Another

- **Not MAU or DAU** — a farmer can open the app every day without adding any data. Opening the app is not value.
- **Not revenue** — revenue requires M-Pesa integration which is Phase 2.
- **Not AI queries** — ARIA has no data to reason over if daily logging doesn't happen.
- **Not farm signups** — creating an account is not using the product.

Daily logging is the single behaviour that powers everything else. A farm that logs consistently has FCR data, financial snapshots, mortality trends, and ARIA context. A farm that does not log is a dead account with good intentions.

When logging happens, ARIA becomes useful. When ARIA is useful, farmers pay. When farmers pay, AGRIOS survives.

**DAL is the only metric that matters before any other metric can matter.**

### Targets

| Gate | Target | Observation Period |
|---|---|---|
| Gate 1 (5 farmers) | ≥ 60% DAL | 3 consecutive days |
| Gate 2 (20 farmers) | ≥ 70% DAL | 7 consecutive days |
| Gate 3 (100 farmers) | ≥ 80% DAL | 14 consecutive days |

### Early Warning Trigger

If DAL falls below 50% for **3 consecutive days** at any gate:
1. Stop feature development immediately
2. Contact every non-logging farmer personally
3. Understand the reason before continuing any sprint work

---

---

# SECTION 9 — FINAL DECISION REGISTER

---

These decisions are **frozen**. They may not be revisited during Sprint 0 through Sprint 10 without a formal written override documenting: the decision being changed, the reason, and the impact on the build sequence.

---

## Architecture Decisions

| ID | Decision | Status |
|---|---|---|
| AD-01 | FastAPI (Python 3.12) is the backend framework | FROZEN |
| AD-02 | PostgreSQL 16 via Supabase is the database | FROZEN |
| AD-03 | SQLAlchemy 2.x async + Alembic is the ORM and migration stack | FROZEN |
| AD-04 | React 18 + Vite + TypeScript is the frontend stack | FROZEN |
| AD-05 | Tailwind CSS is the only styling system | FROZEN |
| AD-06 | Zustand + TanStack Query is the state management architecture | FROZEN |
| AD-07 | Railway is the backend hosting platform | FROZEN |
| AD-08 | Vercel is the frontend hosting platform | FROZEN |
| AD-09 | The product is delivered as a PWA — no native app store submission in V1 | FROZEN |
| AD-10 | Africa's Talking is the SMS provider — not Twilio, not any other | FROZEN |
| AD-11 | Gemini 2.0 Flash is the primary AI provider | FROZEN |
| AD-12 | Claude Haiku is the fallback AI provider — no OpenAI in V1 | FROZEN |
| AD-13 | APScheduler embedded in FastAPI handles background jobs in V1 | FROZEN |
| AD-14 | Sentry is the error monitoring platform | FROZEN |

## Database Decisions

| ID | Decision | Status |
|---|---|---|
| DB-01 | UUID v4 primary keys on all tables | FROZEN |
| DB-02 | Soft deletes via `deleted_at TIMESTAMPTZ NULL` on all tables — no hard deletes in production | FROZEN |
| DB-03 | `species_profiles` is the extensibility engine — adding a new species NEVER modifies existing tables | FROZEN |
| DB-04 | `farm_id` is present on every operational table — all queries are farm-scoped | FROZEN |
| DB-05 | `metadata JSONB DEFAULT '{}'` on all species-extensible tables | FROZEN |
| DB-06 | `UNIQUE(flock_id, log_date)` constraint on `daily_logs` — daily log upsert pattern is the implementation | FROZEN |
| DB-07 | Financial snapshots are computed server-side and cached — dashboard never aggregates raw transactions in real time | FROZEN |
| DB-08 | `audit_logs` is append-only — no UPDATE or DELETE endpoint exists or will be created | FROZEN |
| DB-09 | `market_prices` is historical — new rows only, existing rows are never updated | FROZEN |
| DB-10 | 30 migrations in exact sequence (Tier 0 through Tier 7 as specified) | FROZEN |

## Product Decisions

| ID | Decision | Status |
|---|---|---|
| PD-01 | AGRIOS V1 is Poultry-only — no other species module is activated in V1 | FROZEN |
| PD-02 | AGRIOS V1 is Kenya-only — no other country configuration, currency, or phone format is supported in V1 | FROZEN |
| PD-03 | KES (Kenyan Shilling) is the only supported currency in V1 | FROZEN |
| PD-04 | Phone OTP is the only registration method — no email, no Google, no Apple sign-in | FROZEN |
| PD-05 | PIN login is the session re-entry method after initial OTP verification | FROZEN |
| PD-06 | Bottom 5-tab navigation (Home / Flock / Health / Finance / ARIA) is the farmer app navigation — no changes | FROZEN |
| PD-07 | ARIA in V1 is read-only data Q&A — no disease diagnosis, no image processing, no autonomous actions | FROZEN |
| PD-08 | Disease diagnosis is Phase 2 — it is not a V1 feature under any circumstances | FROZEN |
| PD-09 | M-Pesa payment integration is Phase 2 — subscription is managed manually in V1 | FROZEN |
| PD-10 | Daily Active Loggers (DAL) is the sole MVP success metric | FROZEN |
| PD-11 | The strategic thesis is locked: Health gets the install. Profit keeps the user. | FROZEN |

## Security Decisions

| ID | Decision | Status |
|---|---|---|
| SD-01 | JWT access tokens expire in 15 minutes | FROZEN |
| SD-02 | JWT refresh tokens expire in 30 days and rotate on every use | FROZEN |
| SD-03 | Access tokens stored in memory (Zustand). Refresh tokens stored in httpOnly cookies. | FROZEN |
| SD-04 | OTP max 3 wrong attempts before account lock | FROZEN |
| SD-05 | OTP expires after 10 minutes | FROZEN |
| SD-06 | OTP request rate limit: max 3 requests per phone number per 10 minutes | FROZEN |
| SD-07 | CORS configured to `app.agrios.app` and `admin.agrios.app` only | FROZEN |
| SD-08 | HTTPS enforced — no HTTP in any production environment | FROZEN |
| SD-09 | All farmer financial data is siloed by `farm_id` — cross-farm data is never returned to a farmer | FROZEN |

## Roles Decisions

| ID | Decision | Status |
|---|---|---|
| RD-01 | 8 roles exist in the system (seeded at Migration 001) — no new roles in V1 | FROZEN |
| RD-02 | `enterprise_owner` and `platform_admin` are seeded but have no V1 user-facing flows | FROZEN |
| RD-03 | `vet_consultant` role is active in V1 — read access to health data for a single farm | FROZEN |
| RD-04 | `super_admin` is the founder-only role — no UI-based promotion to this role | FROZEN |
| RD-05 | Farm financial data (P&L, expenses, revenue) is not visible to `vet_consultant`, `farm_worker`, or `viewer` | FROZEN |

## ARIA Decisions

| ID | Decision | Status |
|---|---|---|
| AR-01 | Farm Context Package is compiled server-side before every AI call — the AI never has direct database access | FROZEN |
| AR-02 | Context window is capped at 8,000 tokens — trim order is fixed | FROZEN |
| AR-03 | AI call timeout is 15 seconds — after which a fallback error message is returned | FROZEN |
| AR-04 | ARIA responses are capped at 150 words unless a table or list is required | FROZEN |
| AR-05 | ARIA system prompt (as defined in Section 7) is fixed for V1 — no A/B testing, no prompt changes mid-sprint | FROZEN |
| AR-06 | Proactive insights are generated at 06:00 Africa/Nairobi — this schedule does not change in V1 | FROZEN |

---

---

# APPENDIX A — CONTRADICTIONS RESOLVED

The following contradictions were identified across prior documents and are now definitively resolved.

| Contradiction | Prior State | Resolution |
|---|---|---|
| Vet role in/out of V1 | Task brief listed it as "future optional if excluded"; Build Manifest Gate 3 required vet organisation partner | **INCLUDED in V1.** Vet role is active with read-only health data access. Gate 3 requires it. |
| 8 roles vs. 5 simplified roles | Build Manifest defined 8; task brief listed 5 | **8 roles stand.** The 5 in the brief are simplified descriptions. Technical implementation is 8 roles as designed. |
| Background jobs: APScheduler vs. Celery | Build Manifest mentioned both | **APScheduler for V1.** Celery upgrade is triggered only if daily job execution exceeds 60 seconds. Not in Sprint 0–10. |
| Disease diagnosis position | Original product discussion listed it as MVP feature; Blueprint and Manifest moved it to Phase 2 | **Phase 2, unambiguously.** Disease diagnosis does not appear in V1 under any framing. |
| File storage (Supabase Storage) | Mentioned as "configured but not user-facing" | **Configured in Sprint 0, not user-facing.** Infrastructure ready, no user upload flows in V1. |
| `platform_admin` role UI | Never explicitly stated as in or out of V1 | **No V1 UI.** Role is seeded. Founder uses `super_admin`. `platform_admin` is for future staff. |

---

---

# APPENDIX B — SUBSCRIPTION PLANS (FINAL)

| Feature | Free | Starter | Pro |
|---|---|---|---|
| Price | KES 0/month | KES 500/month | KES 1,500/month |
| Farms | 1 | 1 | 3 |
| Production houses per farm | 3 | 10 | Unlimited |
| Active flocks | 3 | 10 | Unlimited |
| ARIA queries per month | 5 | 30 | Unlimited |
| SMS reminders | Vaccination only | All types | All types + custom |
| Historical data | 90 days | 1 year | Unlimited |
| Team members | 2 | 5 | 20 |

**Subscription upgrade path in V1:** Manual (admin overrides plan in admin dashboard). M-Pesa self-serve upgrade is Phase 2.

---

---

# APPENDIX C — SMS NOTIFICATION TYPES (FINAL)

| Type | Trigger | Recipient | Template |
|---|---|---|---|
| OTP | Registration / login | Registering user | "Your AGRIOS code is {code}. Valid for 10 minutes." |
| Farm invite | Member invited | Invitee | "You have been invited to {farm_name} on AGRIOS. Reply ACCEPT or visit: {link}" |
| Vaccination reminder | 3 days before `next_due_date` | Farm owner + manager | "Reminder: {vaccine_name} due for {flock_name} on {date}. Log it at: {link}" |
| Vaccination overdue | 1 day after `next_due_date` | Farm owner | "Overdue: {vaccine_name} for {flock_name} was due {date}. Please vaccinate immediately." |
| Daily log reminder | 20:00 if today unlogged | Farm owner + manager | "AGRIOS: {flock_name} has not been logged today. Log now: {link}" |
| Disease alert | Admin publishes alert targeting farmer's county | All active farms in county | "AGRIOS Alert: {disease_name} reported in {county}. {brief_guidance}. View details: {link}" |
| Weekly summary | Every Friday at 18:00 | Farm owner | "AGRIOS Weekly: {farm_name} had {survival_rate}% survival rate this week. {flock_count} active flocks. View report: {link}" |

**Total estimated SMS volume at 100 farmers:** ~2,000/month (~KES 1,600/month at KES 0.80/SMS)

---

---

# APPENDIX D — ENVIRONMENT CONFIGURATION (FINAL)

All environment variables required before Sprint 0 Day 1:

```
# Application
ENVIRONMENT=development|staging|production
SECRET_KEY=<32-char-random>
ALLOWED_ORIGINS=https://app.agrios.app,https://admin.agrios.app

# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:port/agrios

# Auth
JWT_SECRET=<64-char-random>
JWT_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Africa's Talking
AT_API_KEY=<key>
AT_USERNAME=<username>
AT_SENDER_ID=AGRIOS
AT_ENVIRONMENT=sandbox|production

# AI Providers
GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-2.0-flash
CLAUDE_API_KEY=<key>
CLAUDE_MODEL=claude-haiku-4-5-20251001

# Monitoring
SENTRY_DSN=<dsn>

# Timezone
TZ=Africa/Nairobi
```

---

---

# DOCUMENT SIGN-OFF

**Document:** AGRIOS V1 Master Blueprint (Frozen)  
**Status:** FROZEN — effective immediately  
**Sections locked:** 9 (Definition · Scope · Architecture · Database · Roles · Dashboards · ARIA · Success Metric · Decision Register)  
**Appendices:** 4 (Contradictions Resolved · Subscription Plans · SMS Types · Environment Config)  
**Total frozen decisions:** 47 (AD: 14 · DB: 10 · PD: 11 · SD: 9 · RD: 5 · AR: 6 — consolidated from Decision Register)  
**Override process:** Any change requires written justification identifying the decision ID, the change, and the downstream impact on the sprint sequence  

---

> Sprint 0 begins immediately.  
> The first command is: `mkdir agrios && cd agrios && git init`  
> Every decision in this document is the law until the document is formally revised.

---
