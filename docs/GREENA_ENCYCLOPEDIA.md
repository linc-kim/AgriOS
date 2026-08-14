# The Greena Encyclopedia

The complete picture of Greena as a product: what it is, why each part exists,
and how the whole ecosystem fits together. Written so the founder understands
Greena more completely than anyone. Grounded in the real system (203 tables, 191
permissions, 10 scheduled jobs, schema head 091).

---

## I. What Greena is
Greena is an **Agricultural Operating System** — a single platform where a farming
business runs its entire operation: the animals and their records, their health,
the feed and inventory, the money, the team, the reporting, and an AI that ties
it together. It is multi-tenant SaaS: many independent farming businesses
(organizations), each with one or more farms, each farm with its own team, data,
and subscription entitlement.

The thesis: smallholder-to-commercial farmers lack an integrated system. Spreadsheets
lose data, don't remind, don't analyse, and don't scale across species. Greena
replaces the spreadsheet, the notebook, the separate accounting app, and the
"ask an expert" phone call with one operating system.

## II. The shape of the platform
```
Organization (a farming business, owns the subscription)
 ├── Farm (a physical operation, in a Kenyan county)
 │    ├── Production houses / units
 │    ├── Flocks / herds / batches (per species module)
 │    ├── Team members (roles: owner, manager, worker, vet, viewer)
 │    └── Records: production, health, feed, finance
 ├── Referral code  ──► growth loop
 └── Credit ledger  ──► referral rewards & adjustments
```
Everything is scoped to the organization and farm; **tenant isolation** guarantees one business never sees another's data (verified: cross-org access returns 404).

## III. Why each layer exists

### 1. Identity & access (why RBAC)
Farms are teams, not individuals. An owner shouldn't hand the books to a field
worker, and a vet shouldn't edit payroll. So Greena has **8 roles** and **191
fine-grained permissions** (`farm:*`, `flock:*`, `ops:*`, `health:*`, `finance:*`,
`ai:*`, species domains…). Every endpoint checks a specific permission. Platform
roles (`super_admin`, `platform_admin`) sit above farms for administration.

### 2. The species modules (why so many, and why they're separate engines)
Different animals need genuinely different data models — an incubation batch is
nothing like a farrowing crate. So each species is a **full engine** rather than
a shared "animal" table:
- **Poultry** — the origin module: flocks, daily logs, egg/production, weigh-ins.
- **Aviculture / Ornamental Birds** — high-value birds: aviaries, pairs, breeding programs, incubation, candling, hatch, mutations, ownership, valuation.
- **Black Soldier Fly** — circular-economy insect farming: feedstock, feeding, environment, harvest, frass, growth planning.
- **Rabbit** — breeding & litters, growth, health, sales.
- **Small Ruminant** — Goat **and** Sheep unified on one schema (species discriminator): breeding/birth, growth, health, dairy, wool, sales.
- **Swine** — housed single-species livestock: breeding/AI/pregnancy, farrowing, feed, biosecurity, growth, sales.
- **Fish/Aquaculture** — roadmap.

They share cross-cutting engines (finance, health, feed, reports) so a multi-species
farm gets one coherent view. The permission counts (`sr` 31, `swine` 29, `rabbit`
27, `bsf` 23, `avi` 19) show how much depth each engine carries.

### 3. The cross-cutting engines (why they're shared)
- **Health** — vaccination schedules, disease events, alerts. Timely animal health is the difference between profit and loss; Greena schedules the reminders (upcoming 08:00, overdue 08:05).
- **Feed & Inventory** — feed is the largest cost in most operations; tracking purchases, consumption, and stock makes cost real. Assets and maintenance live here too.
- **Finance** — expenses, revenue, custom categories, profitability snapshots. Farming is a business; Greena keeps its books.
- **Automation** — rules + reminders so routine work happens without being remembered.
- **Reports & Exports** — turn records into decisions; CSV/PDF out. History depth is a plan feature.

### 4. ARIA (why an AI, and why deterministic-first)
Data only helps if it answers questions. ARIA makes the farm queryable in plain
language and pushes daily insights. It is **deterministic-first** (exact answers
from data), with LLM fallback (Gemini/Claude) for open questions, and an offline
fallback so it never blocks. It is tenant-safe by construction. See [ARIA_MANUAL.md](ARIA_MANUAL.md).

### 5. Operations Planner & Mission Control (why a planning layer)
Records look backward; farms need to look forward. **Operations Planner** turns
routines into concrete daily tasks (05:00), scans compliance (07:00), and
optimises weekly (Mon 04:00). **Mission Control** is the strategic layer — goals
and roadmap across farms. Together they move Greena from "system of record" to
"system of action".

### 6. The commercial system (why trial + referral, not just a paywall)
Farmers must experience value before paying, and the best acquisition channel is
another farmer. So:
- A **21-day Professional trial** on every new org — full value, no commitment.
- A **referral loop**: shareable codes, a first-payment discount (Starter 999 → 599), and a KES 100 reward to the referrer on activation. Prices end in 99 (a pricing choice). Renewals are always full price.
- Plans gate scale (farms, houses, flocks, team, ARIA queries, history) — see [ADMINISTRATOR_MANUAL.md](ADMINISTRATOR_MANUAL.md).
The money path is hardened: activation is idempotent, webhook signatures are verified and the amount re-checked against Paystack, and referral rewards are DB-guaranteed to credit once.

## IV. The user journeys
- **Farmer**: sign up → org (trial + code) → farm → structure → team → daily records → health/feed/finance → reports → ARIA → upgrade. ([FARMER_MANUAL.md](FARMER_MANUAL.md))
- **Worker**: log in → today's tasks → record as you work → vaccinations → complete the day's log. ([WORKER_MANUAL.md](WORKER_MANUAL.md))
- **Administrator**: manage plans/grants, activate modules, support tickets, audit. ([ADMINISTRATOR_MANUAL.md](ADMINISTRATOR_MANUAL.md))
- **Owner**: operate the business, control infra and pricing, watch the funnel. ([OWNER_MANUAL.md](OWNER_MANUAL.md))

## V. How the machine runs (operational philosophy)
- **Fail safe, fail loud**: bad config crashes at boot (never serves broken); `/health` returns 503 when the DB is down so traffic is never routed to a degraded instance; migrations run on boot and are idempotent.
- **One leader for background work**: the scheduler is gated by a Postgres advisory lock — jobs run exactly once across all replicas.
- **Bounded everything**: external calls (Paystack 20s, AI 15s) never hang; rate limiting protects the API.
- **Additive migrations**: schema changes only add, so rollbacks don't need schema downgrades.
- **Money correctness over convenience**: re-verify against Paystack, DB-level idempotency on rewards, tenant isolation everywhere.

## VI. The operational clock (10 scheduled jobs, Nairobi time)
01:00 subscription expiry · 02:30 backup retention · Mon 04:00 ops optimisation ·
05:00 ops task materialisation · 06:00 ARIA insights · 07:00 ops compliance ·
08:00 vaccination reminders · 08:05 vaccination overdue · 20:00 daily-log reminder ·
Fri 18:00 weekly summary. This clock is Greena's heartbeat — it's why the platform
feels proactive.

## VII. Where Greena is going
Fish/Aquaculture module; deeper Mission Control (CEO advisor); richer ARIA
(multimodal, more languages); scale-out (paid Render/Supabase, autoscaling);
custom domain; marketplace and market-price features (a `market` permission
already exists as a seam). See [ROADMAP_AND_BUSINESS.md](ROADMAP_AND_BUSINESS.md).

## VIII. The one-paragraph definition
Greena is a multi-tenant Agricultural Operating System where a farming business
runs every species it keeps, every record it needs, its health, feed, and money,
its team under fine-grained roles, its reporting, and an AI that answers from its
own data — proactively scheduled, commercially self-propagating through referrals,
and engineered to fail safe with money-grade correctness.
