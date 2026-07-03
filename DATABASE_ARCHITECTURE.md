# AGRIOS DATABASE ARCHITECTURE

**Read `AGRIOS_MASTER_CONTEXT.md` first**, particularly Section 8 (Database Philosophy) and Section 9 (Frozen Decision Register). This document is the complete mechanical explanation of every database design decision, why it was made, why the obvious alternative was rejected, and what must never change without a formal override.

---

## 1. The Base Model — `AGRIOSBase`

Every operational table in AGRIOS inherits from a single declarative base class, `AGRIOSBase` (`app/models/base.py`), which provides five columns to every table that uses it:

```python
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default="{}", nullable=False)
```

**Why a shared base class rather than repeating these columns per model:** consistency is not optional here — soft-delete correctness, audit-timestamp correctness, and the JSONB extensibility column are all frozen, project-wide guarantees (DB-01, DB-02, DB-05). Centralizing them in one base class means every new table gets them by construction rather than by developer discipline, and it means a bug fix or convention change to how soft-deletes work happens in exactly one place.

**Why the Python attribute is `metadata_` but the database column is `"metadata"`:** SQLAlchemy's declarative base already reserves the name `metadata` for its own internal `MetaData` registry object, so a model attribute literally named `metadata` would collide with SQLAlchemy internals. The `mapped_column("metadata", ...)` call is SQLAlchemy's mechanism for saying "the Python-facing attribute is `metadata_`, but map it to a physical column literally named `metadata`." Any new model, or any new migration that adds a JSONB extensibility column, must follow this exact pattern — attribute `metadata_`, physical column `"metadata"` — for consistency with every existing table, and because deviating (e.g. naming the column `metadata_` physically, or naming the attribute `metadata`) breaks that consistency for no benefit.

**A concrete failure mode this exact pattern has already caused, and the fix:** `VaccinationRecord` (Migration 017) at one point declared its own additional `mapped_column("metadata", JSONB, ...)` attribute (named `extended_metadata`) on top of the one it already inherits from `AGRIOSBase`. Because both columns mapped to the same physical `"metadata"` column name, SQLAlchemy raised `DuplicateColumnError: A column with name 'metadata' is already present in table 'vaccination_records'` at import time — confirmed via an actual Railway deployment log, not a simulation. The fix was to delete the redundant `extended_metadata` block entirely, since `VaccinationRecord` already had everything it needed via inheritance. **The lesson for any future model:** before adding a JSONB "extended metadata" field to any model that inherits `AGRIOSBase`, check whether `metadata_` already covers the need — it almost certainly does, since it is already present on every table. `DiseaseAlert` has its own, similarly named `extended_metadata` column as well; it was deliberately left untouched during that fix because the observed error was specific to `VaccinationRecord` and the instruction at the time was to fix only the error actually observed — but it is flagged here as the same latent pattern, and should be reviewed with the same lens if it is ever touched.

---

## 2. Why UUID v4 Primary Keys (AD-01 / DB-01, Frozen)

Every table uses a UUID v4 primary key, never an auto-incrementing integer. Three reasons converge here: UUIDs can be generated client-side or in application code before an insert, which simplifies patterns like creating a farm and its owner's `UserRole` row in the same transaction without needing a round trip to learn the new row's ID; UUIDs do not leak business information through sequential enumeration (an integer ID scheme would let anyone guess how many farms or users exist, or iterate over them); and UUIDs make eventual multi-region or multi-database scenarios (a real possibility once AGRIOS expands beyond Kenya) far simpler, since there is no risk of ID collision across independently-seeded databases.

---

## 3. Why Soft Deletes Everywhere (DB-02, Frozen)

Every operational table carries `deleted_at TIMESTAMPTZ NULL`. No application code path issues a hard `DELETE`. The reasoning is threefold and is described in full in `AGRIOS_MASTER_CONTEXT.md` Section 6.5: accidental-loss protection, audit trustworthiness for future investor/bank (`viewer` role) due diligence, and the explicit operational policy that banning or suspending a farmer must never destroy their history. Every list query in the codebase filters `deleted_at IS NULL`; a query that forgets this filter will silently resurface "deleted" rows, which is the most common correctness bug this pattern invites — any new query against a soft-deletable table must include this filter explicitly, since there is no database-level mechanism (like a view or a row-level security policy) currently enforcing it centrally.

---

## 4. The Migration Strategy — 30 Linear Migrations (DB-10, Frozen)

Migrations are Alembic-managed, strictly linear (`down_revision` of migration N is always the `revision` of migration N-1 — no branching, no merge migrations), and the chain is frozen at exactly 30 migrations for V1, numbered 001 through 030. "Frozen at 30" does not mean the schema can never change again — it means V1's scope is sealed, and any V1.1 or V2 schema work begins a *new*, clearly demarcated sequence rather than being quietly folded into the V1 migration set. This matters for auditability: anyone can look at "migrations 001–030" and know exactly what V1 shipped with.

Every migration follows the same shape: a working `upgrade()` and a working `downgrade()` that cleanly reverses it. ENUM types created inside a migration must be dropped inside that same migration's `downgrade()` via `sa.Enum(name=...).drop(op.get_bind(), checkfirst=True)` — except where an ENUM is *shared* across migrations (see Section 4.4), in which case ownership of the create/drop lifecycle belongs to whichever migration created it, and later migrations that merely reference the type must not attempt to drop it.

### 4.1 Migration tiers, in build order

| Tier | Migrations | Domain | Reasoning for the ordering |
|---|---|---|---|
| 0 | 001–005 | `roles`, `users`, `user_roles`, `otp_requests`, `sessions` | Nothing else can exist without identity and roles existing first. |
| 1 | 006–007 | `subscription_plans`, `species_profiles` | Platform configuration that farms will immediately reference. |
| 2 | 008–011 | `farms`, `farm_members`, `farm_units`, `production_houses` | Farm structure must exist before anything can be scoped to a farm (DB-04). |
| 3 | 012–016 | `flocks`, `daily_logs`, `production_records`, `weighin_records`, `feed_purchases` | The operational core — everything downstream (health, finance, ARIA) references a flock. |
| 4 | 017–018 | `vaccination_records`, `disease_alerts` | Health tracking, layered on top of flocks. |
| 5 | 019–022 | `expense_categories`, `expenses`, `revenue_records`, `financial_snapshots` | Finance, which depends on flocks existing to attach records to. |
| 6 | 023–027 | `ai_conversations`, `ai_messages`, `ai_insights`, `ai_recommendations`, `ai_usage_log` | ARIA — deliberately last among the domain tiers, because its context compiler reads across flock, health, and finance data that must already exist. |
| 7 | 028–030 | `notifications`, `audit_logs`, `market_prices` | Platform-wide layer, added once there was real farm activity worth notifying about and auditing. |

### 4.2 Every table's non-negotiable columns

Beyond the five inherited from `AGRIOSBase` (Section 1), the project convention adds, per-table as applicable: `farm_id` (FK to `farms.id`, `ON DELETE CASCADE`, indexed) on every operational table — DB-04, frozen, with exactly two documented exceptions (`disease_alerts` and `market_prices`, both platform-wide by nature, county/species-targeted rather than farm-targeted); `species_key` (FK to `species_profiles.species_key`, `ON DELETE RESTRICT`) on every table whose data is species-specific, which in V1 defaults to `"poultry"` via `server_default`; and `created_by` (FK to `users.id`, `ON DELETE SET NULL`) on user-generated records, for audit purposes.

### 4.3 Species Extensibility — the `species_profiles` engine

`species_profiles` is the single mechanism through which AGRIOS is designed to grow beyond poultry without ever modifying an existing table. In V1 it contains one active row (`species_key = "poultry"`, `is_active = TRUE`) and can contain additional rows for species that are seeded but inactive. Activating a new species (Rabbit OS, Dairy OS, etc.) in a future version is meant to require exactly two kinds of change: `UPDATE species_profiles SET is_active = TRUE WHERE species_key = '<new_species>'`, and the addition of new, purely additive tables for that species' specific data needs. **No existing table is ever altered, no existing API is ever modified, and no migration touches a live operational table to add a new species.** This is DB-03, frozen, and it is the schema-level expression of the product's name and ambition (`AGRIOS_MASTER_CONTEXT.md` Section 1) — if a future change to add a new species requires editing `flocks` or `daily_logs`, that is a signal the extensibility model has been violated and needs architectural review before proceeding, not a signal to "just add a nullable column."

### 4.4 Enum ownership across migrations — a documented failure pattern

Two distinct classes of problems have appeared around PostgreSQL ENUM types, and both are worth understanding in detail because they are easy to reintroduce.

**Pattern A — ENUM shared across migrations without clear ownership.** `ai_provider` (used by both `ai_messages`, migration 024, and `ai_usage_log`, migration 027) is *owned* by migration 024: only 024's `downgrade()` drops the type; 027's `downgrade()` must drop its table but must NOT attempt to also drop `ai_provider`, or the downgrade chain would fail the second time it runs (the type would already be gone). The rule going forward: when a migration references an ENUM type it did not create, it must never include that type in its own `downgrade()` teardown.

**Pattern B — duplicate ENUM object declared, never created, silently redundant.** Migration 009 (`farm_members`) at one point declared a `postgresql.ENUM(*MEMBER_STATUSES, name="member_status", create_type=False)` object, assigned it to a local variable, and then **never called `.create()` on it** — while the column definition further down in the same file instantiated a second, separate `ENUM(...)` object with the identical name and also `create_type=False`. Because `create_type=False` on *both* objects meant neither one was responsible for actually creating the PostgreSQL type, the type creation depended entirely on some other mechanism actually running `CREATE TYPE member_status` — and if that never happened, the migration would fail against a fresh database with an undefined-type error, or, worse, if some other path did create it, you would have two independent Python objects representing the same database concept with no shared source of truth. The correct, now-documented pattern is: declare the enum object once, explicitly call `member_status_enum.create(op.get_bind(), checkfirst=True)` immediately after declaring it, and then reuse that *same Python object* in the column definition rather than instantiating a second one. `checkfirst=True` matters specifically because it makes the migration idempotent against a database where the type might already exist (for example, if a downgrade/upgrade cycle ran partially) — without it, a second `upgrade()` attempt would fail with "type already exists." Any new migration introducing a PostgreSQL ENUM should follow this exact create-once-reuse-the-object pattern, and should double check for a stray, unused debug `print()` statement left near the enum declaration in the corresponding model file — one was found and flagged as evidence this exact issue had previously been under active investigation, and should be removed the next time that file is touched for any reason.

### 4.5 A dormant schema/model mismatch — recorded for awareness, not yet fixed

Migration 028 (`notifications`) creates a column literally named `metadata_` in the database, rather than following the project's standard pattern of a physical column named `"metadata"` mapped to a Python attribute named `metadata_` (Section 1). This is inconsistent with every other table in the schema. It has not caused a production incident because `notification_service.py`'s bulk-create functions that would exercise this column are not currently called from any live code path — the mismatch is dormant, not active. It is recorded here, rather than silently fixed, specifically so that the next contributor who wires up bulk notification creation does not spend time debugging a column-name mismatch that is already known; see `KNOWN_TECHNICAL_DEBT.md` for its formal tracking entry.

---

## 5. The Snapshot Pattern — Why Financial Data Is Never Computed Live (DB-07, Frozen)

`financial_snapshots` is a pre-computed profit-and-loss table, one row per flock (and aggregated per farm/period), that is recomputed every single time an `expenses` or `revenue_records` row is created, updated, or corrected. The API's finance dashboard, P&L report, and every other financial read path reads exclusively from this table — **there is no code path anywhere in the system that aggregates raw expense/revenue rows live during an API response.** `recompute_snapshot()` is described as the single aggregate query point in the entire system, called after every relevant mutation.

**Why this exists:** the target user opens the Finance tab on a 3G connection, possibly with ten thousand historical transaction rows behind their account. Aggregating that live, on every page load, would be slow exactly where speed matters most. Precomputing on write instead of read means the read path is always a single indexed row lookup, regardless of how much history exists behind it.

**Why this must never be violated:** the temptation to add "just one more real-time aggregate" reappears with almost every new report or chart feature, because it is initially the path of least resistance for a developer building a single new screen. It is flagged explicitly here because it is the single most likely frozen decision to be accidentally broken by a well-intentioned future contributor who has not read this document.

---

## 6. Append-Only Tables (DB-08 / DB-09, Frozen)

Three tables are deliberately append-only, inheriting from the bare `Base` class rather than `AGRIOSBase` — meaning they have no `updated_at`, no `deleted_at`, and by construction no soft-delete or update pathway at all:

- **`audit_logs`** — an immutable record of every significant platform action (flock created, expense logged, user suspended, etc.). No UPDATE or DELETE endpoint exists or may ever be created for it.
- **`ai_usage_log`** — an immutable per-AI-call cost/usage record, used for cost tracking and abuse detection.
- **`market_prices`** — historical price data; a price "correction" is expressed as a new row with a newer `price_date`, never as an edit to an old row.

The reasoning is that these three tables exist specifically to be *trustworthy history* — an append-only log that could silently be edited after the fact defeats its own purpose, whether the purpose is legal audit trail, AI cost accountability, or historical price transparency. If a future feature seems to need to "fix" a row in one of these tables, the correct action is always to insert a new, corrected row and let the old one stand, exactly as the farmer-facing correction pattern does (Section 8).

---

## 7. Constraints Worth Understanding by Name

| Constraint | Table | Purpose |
|---|---|---|
| `UNIQUE(flock_id, log_date)` | `daily_logs` | Enables a safe upsert pattern for daily logging — a farmer resubmitting today's log updates the same row rather than creating a duplicate. |
| `UNIQUE(farm_id, user_id)` | `farm_members` | One role per user per farm — a person cannot simultaneously hold two different roles on the same farm. |
| One active flock per production house | Application-enforced, not a DB constraint | Checked in `farm_service`/`flock_service` at `POST /flocks` time — a house's prior flock must be closed before a new one can start. |
| `species_profiles.is_active` mutation | Application permission check | Restricted to `super_admin` only — this is enforced in code, not at the schema level, because the constraint is about *who* may flip the flag, not about data shape. |

---

## 8. The Correction Pattern — Why There Is No Correction Log Table

When a farmer corrects a daily log, expense, or revenue record, the original row is never deleted or silently overwritten. Instead, the correction reason is appended to the record's `notes` field in a fixed format: `\n[Corrected by {user_id} at {ISO timestamp}: {reason}]`, the corrected value replaces the original value in its own column, and the financial snapshot (if applicable) is recomputed. This creates a full audit trail without needing a separate correction-log table for every correctable domain. Any new correctable field in a future domain should follow this exact pattern rather than introducing a bespoke correction table, both for consistency and because the `notes`-append approach has already been proven across three domains (operations, expenses, revenue).

---

## 9. Naming Conventions

Tables are `snake_case`, plural (`vaccination_records`, `farm_members`). Foreign key columns are `{referenced_table_singular}_id` (`farm_id`, `flock_id`, `user_id`). Boolean columns are affirmative and unprefixed where possible (`is_active`, `is_verified`) rather than negated (never `is_not_active`). ENUM-backed status columns are named `status` when a table has exactly one lifecycle concept (`farm_members.status`), and something more specific (`severity`, `role`) when a table could plausibly have more than one categorical dimension. Every ENUM type created in a migration is named in `snake_case` and matches the Python-side `Enum(...)` object's `name=` argument exactly, since PostgreSQL enum types are global to the database (not namespaced per table) and a mismatch between the migration's type name and the model's type name will surface as a runtime schema mismatch rather than an import-time error, making it a harder class of bug to catch early.

---

## 10. Indexes and Foreign Keys

Every `farm_id` column is indexed, since virtually every query in the system is farm-scoped (DB-04) and an unindexed `farm_id` would make every list endpoint a full table scan as data grows. `next_due_date` on `vaccination_records` is indexed because it drives both the daily vaccination-reminder scheduler job and ARIA's proactive insight generation — both scan for "due soon" and "overdue" rows daily. `deleted_at` is indexed on tables where soft-deleted rows are expected to accumulate meaningfully over time. Foreign keys use `ON DELETE CASCADE` when the child record has no meaning without its parent (a `daily_log` without its `flock`), `ON DELETE RESTRICT` when the reference must never be allowed to dangle (a `species_key` FK — you cannot delete a species that active records still reference), and `ON DELETE SET NULL` when the reference is genuinely optional and the child record should survive its referenced row's deletion (e.g. `administered_by` on a vaccination record surviving that user's account deletion).

---

## 11. Future Scaling Strategy

At the row-count and traffic levels V1 targets (hundreds to low thousands of farms), the current single-Postgres-instance, single-Railway-service architecture is expected to comfortably hold. The documented triggers for reconsidering this, in the order they are expected to actually arise: Supabase free-tier storage limits (upgrade path: Supabase Pro, then a dedicated/self-hosted Postgres instance); read-heavy report/admin-dashboard contention with write traffic (upgrade path: a Postgres read replica dedicated to reporting queries); and, much further out, genuine multi-region requirements once AGRIOS expands beyond Kenya (`ROADMAP.md`), which would be the first point at which the single-database assumption embedded throughout this document would need to be revisited at the architecture level, not merely the infrastructure level. None of these triggers have been reached as of V1 launch, and pre-building for them now would violate the "product before infrastructure" principle in `AGRIOS_MASTER_CONTEXT.md` Section 4.1.

---

## 12. Identity Model Implications of Channel-Agnostic Authentication

**This section documents schema *implications* of the authentication philosophy in `AGRIOS_MASTER_CONTEXT.md` Section 6.1. It intentionally identifies optional future fields rather than prescribing a migration — no schema change is made by this section, and none should be inferred from it.** The frozen decision register is otherwise untouched by this section; it exists purely so that whenever a future migration does touch identity/auth, the reasoning below is available rather than needing to be re-derived.

### 12.1 What the `users` table already supports

The `users` table already carries a `phone` field and the `metadata_` JSONB extensibility column inherited from `AGRIOSBase` (Section 1). Because Email OTP is now the V1 launch mechanism, the table's identity fields should be understood as **channel identifiers a user may hold one or more of**, not as a single fixed identity key — conceptually closer to "here are the ways we can reach and verify this person" than "here is this person's one true login field." This reframing does not require touching the physical schema immediately; it changes how the existing and near-future columns should be interpreted and queried.

### 12.2 Optional future fields — recorded for whenever this area is next migrated

If and when the `users` table is next touched by a migration, the following fields are the natural, additive extension of the current schema and should be evaluated at that time — they are documented here so that decision is informed rather than improvised under time pressure:

- `email` (nullable, unique where not null) and a corresponding `is_email_verified` boolean, mirroring the existing `phone` / `is_phone_verified` pattern already used for phone. Both `email` and `phone` should remain nullable indefinitely — a user is never required to have both, only at least one verified channel.
- `preferred_contact_channel` (e.g. an enum of `email` / `sms` / `both`), most likely implemented as a `user.metadata_` key in the near term (exactly as `sms_notifications_enabled` already is, per `SYSTEM_ARCHITECTURE.md` Section 6) before it earns a first-class column, consistent with the project's general pattern of proving a preference out in `metadata_` before promoting it to a typed column once its shape has stabilized.
- `preferred_2fa_channel` and `backup_2fa_channel`, once two-factor authentication is actually built (`ROADMAP.md`) — these should reference the same verified-channel concept as `preferred_contact_channel` rather than introducing a separate channel-naming scheme.
- A future `linked_identity_providers` structure (or a dedicated child table, `user_identity_links`, if the shape becomes complex enough to warrant one) for Google/Apple/Microsoft/passkey linkage — each row or entry representing one additional verified way to reach the same single `users.id`, never a second `users` row.

### 12.3 The constraint that must govern any such migration when it happens

Whatever shape these fields eventually take, the constraint from `AGRIOS_MASTER_CONTEXT.md` Section 6.1 is absolute and should be treated as a review gate for that future migration: **no migration in this area may make it possible for verifying a second channel on an existing account to produce a second `users` row.** A migration that adds `email` as a new unique column, for instance, must include the lookup/merge logic (at the application layer, verified by an integration test) proving that an existing phone-verified user who later verifies an email is matched to their existing row, not inserted as a new one. This is the single highest-risk failure mode of any future identity-model migration and should be the first thing reviewed against it, not an afterthought.
