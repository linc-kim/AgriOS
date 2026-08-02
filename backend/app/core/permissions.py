"""
Greena — RBAC Permission System
Implements the permission matrix from the Engineering Constitution.
8 roles × ~30 permissions.

Usage:
    @router.post("/farms/{farm_id}/flocks")
    async def create_flock(
        farm_id: UUID,
        current_user: User = Depends(require_permission(Permission.FLOCK_CREATE)),
    ):
        ...
"""

from enum import StrEnum
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.auth import User


# ── Permission Definitions ────────────────────────────────────────────────────

class Permission(StrEnum):
    # Farm Management
    FARM_CREATE = "farm:create"
    FARM_EDIT = "farm:edit"
    FARM_DELETE = "farm:delete"
    FARM_MEMBER_INVITE = "farm:member:invite"
    FARM_MEMBER_REMOVE = "farm:member:remove"
    FARM_MEMBER_ROLE_CHANGE = "farm:member:role_change"
    FARM_UNIT_MANAGE = "farm:unit:manage"

    # Flock Management
    FLOCK_CREATE = "flock:create"
    FLOCK_UPDATE = "flock:update"
    FLOCK_ARCHIVE = "flock:archive"
    FLOCK_CLOSE = "flock:close"
    FLOCK_VIEW = "flock:view"

    # Daily Operations
    OPS_LOG_SUBMIT = "ops:log:submit"
    OPS_LOG_CORRECT = "ops:log:correct"
    OPS_FEED_LOG = "ops:feed:log"
    OPS_WEIGHIN_LOG = "ops:weighin:log"
    OPS_PRODUCTION_LOG = "ops:production:log"
    OPS_LOG_VIEW = "ops:log:view"

    # Health Management
    HEALTH_VACCINATION_LOG = "health:vaccination:log"
    HEALTH_VACCINATION_VIEW = "health:vaccination:view"
    HEALTH_EVENT_LOG = "health:event:log"
    HEALTH_EVENT_VIEW = "health:event:view"
    HEALTH_ALERT_VIEW = "health:alert:view"

    # Feed Management (Phase 3, Module 4)
    FEED_MANAGE = "feed:manage"   # Write: purchases, consumption, transfers, wastage, inventory, suppliers
    FEED_VIEW = "feed:view"       # Read: inventory, transactions, analytics, alerts

    # Inventory & Asset Management (Module 6)
    INVENTORY_MANAGE = "inventory:manage"   # Write: items, movements, assets, maintenance, suppliers
    INVENTORY_VIEW = "inventory:view"       # Read: items, movements, assets, analytics, alerts

    # Automation & Notifications (Module 8)
    AUTOMATION_MANAGE = "automation:manage"  # Write: rules, reminders, run engine
    AUTOMATION_VIEW = "automation:view"      # Read: rules, reminders, activity

    # Finance
    FINANCE_EXPENSE_LOG = "finance:expense:log"
    FINANCE_EXPENSE_EDIT = "finance:expense:edit"
    FINANCE_REVENUE_LOG = "finance:revenue:log"
    FINANCE_RECORD = "finance:record"   # Write: expenses + revenue + custom categories
    FINANCE_VIEW = "finance:view"

    # AI / ARIA
    AI_QUERY = "ai:query"
    AI_INSIGHT_VIEW = "ai:insight:view"

    # Notifications (Sprint 7)
    NOTIFICATION_VIEW = "notification:view"

    # Market Prices (Sprint 7)
    MARKET_VIEW = "market:view"

    # Admin (super_admin only)
    ADMIN_DASHBOARD = "admin:dashboard"
    ADMIN_ALERT_PUBLISH = "admin:alert:publish"
    ADMIN_MARKET_MANAGE = "admin:market:manage"
    ADMIN_USER_MANAGE = "admin:user:manage"
    ADMIN_FARM_MANAGE = "admin:farm:manage"
    ADMIN_AI_USAGE_VIEW = "admin:ai:usage:view"

    # Admin Platform (Module 10)
    ADMIN_ORG_MANAGE = "admin:org:manage"
    ADMIN_PLATFORM_CONFIG = "admin:platform:config"   # feature flags, system config, maintenance, jobs

    # Production Readiness (Module 11)
    PRODUCTION_VIEW = "production:view"        # Read: reports, diagnostics, status, release info
    DATA_EXPORT = "data:export"                # Export farm data (CSV / Excel / JSON / PDF)
    DATA_IMPORT = "data:import"                # Bulk-import farm data
    BACKUP_MANAGE = "backup:manage"            # Create, delete and restore backups
    DIAGNOSTICS_RUN = "diagnostics:run"        # Run diagnostic sweeps and deployment verification

    # Aviculture — Ornamental & Specialty Birds (Module 15)
    AVI_BIRD_CREATE = "avi:bird:create"        # Add birds to the collection
    AVI_BIRD_UPDATE = "avi:bird:update"        # Edit bird identity / details
    AVI_BIRD_ARCHIVE = "avi:bird:archive"      # Archive / restore birds
    AVI_BIRD_TRANSACT = "avi:bird:transact"    # Ownership events: sale, purchase, transfer, death
    AVI_BIRD_VIEW = "avi:bird:view"            # Read birds, timeline, media, documents
    AVI_AVIARY_MANAGE = "avi:aviary:manage"    # Write aviaries / housing infrastructure
    AVI_AVIARY_VIEW = "avi:aviary:view"        # Read aviaries
    AVI_BREEDING_MANAGE = "avi:breeding:manage"  # Write pairs / breeding relationships
    AVI_BREEDING_VIEW = "avi:breeding:view"      # Read pairs / pedigree
    AVI_CATALOG_MANAGE = "avi:catalog:manage"  # Write custom species / breeds / mutations
    AVI_CATALOG_VIEW = "avi:catalog:view"      # Read the species / breed / mutation catalog
    AVI_HEALTH_LOG = "avi:health:log"          # Write bird health records
    AVI_HEALTH_VIEW = "avi:health:view"        # Read bird health records
    AVI_INCUBATION_MANAGE = "avi:incubation:manage"  # Write eggs, batches, candling, hatch
    AVI_INCUBATION_VIEW = "avi:incubation:view"      # Read incubation records & statistics
    AVI_FINANCE_MANAGE = "avi:finance:manage"        # Record valuations, post aviculture costs
    AVI_FINANCE_VIEW = "avi:finance:view"            # Read valuations, finance summary, reports
    AVI_AUTOMATION_MANAGE = "avi:automation:manage"  # Generate reminders, drive workflows
    AVI_AUTOMATION_VIEW = "avi:automation:view"      # Read tasks, reminders, workflows

    # Black Soldier Fly — Insect Farming (Module 16). Spec Part 8 §5.
    # ARIA / Mission Control reuse the platform AI_QUERY / AI_INSIGHT_VIEW perms.
    BSF_BATCH_CREATE = "bsf:batch:create"        # Create production batches / colonies
    BSF_BATCH_EDIT = "bsf:batch:edit"            # Edit batches, split, merge, move, lifecycle
    BSF_BATCH_DELETE = "bsf:batch:delete"        # Terminate / archive batches
    BSF_BATCH_VIEW = "bsf:batch:view"            # Read batches, lifecycle, timeline, media
    BSF_UNIT_MANAGE = "bsf:unit:manage"          # Write production units (bins/trays/racks…)
    BSF_UNIT_VIEW = "bsf:unit:view"              # Read production units
    BSF_COLONY_MANAGE = "bsf:colony:manage"      # Write adult breeding colonies
    BSF_COLONY_VIEW = "bsf:colony:view"          # Read breeding colonies
    BSF_CATALOG_MANAGE = "bsf:catalog:manage"    # Write custom BSF species / strains
    BSF_CATALOG_VIEW = "bsf:catalog:view"        # Read the species / strain catalog
    BSF_FEED_RECORD = "bsf:feed:record"          # Record feedstock lots & feeding events
    BSF_FEED_VIEW = "bsf:feed:view"              # Read feedstock & feeding history
    BSF_HARVEST_RECORD = "bsf:harvest:record"    # Record harvests & frass collection
    BSF_HARVEST_VIEW = "bsf:harvest:view"        # Read harvest & frass records
    BSF_ENVIRONMENT_RECORD = "bsf:environment:record"  # Record environmental readings
    BSF_ENVIRONMENT_VIEW = "bsf:environment:view"      # Read environmental records
    BSF_FINANCE_VIEW = "bsf:finance:view"        # Read BSF finance summary & analytics
    BSF_REPORT_VIEW = "bsf:report:view"          # Read reports & dashboards
    BSF_REPORT_EXPORT = "bsf:report:export"      # Export reports (PDF / Excel / CSV)
    BSF_GROWTH_VIEW = "bsf:growth:view"          # Read growth plan / roadmap / progress
    BSF_GROWTH_EDIT = "bsf:growth:edit"          # Create / edit growth goals & roadmaps
    BSF_AUTOMATION_MANAGE = "bsf:automation:manage"  # Generate reminders, drive workflows
    BSF_AUTOMATION_VIEW = "bsf:automation:view"      # Read BSF tasks, reminders, workflows

    # Rabbit Management (Module 17). Spec Part 8 §5.
    # ARIA / Mission Control reuse the platform AI_QUERY / AI_INSIGHT_VIEW perms.
    RABBIT_CREATE = "rabbit:create"              # Register rabbits
    RABBIT_EDIT = "rabbit:edit"                  # Edit rabbit identity / details, move between cages
    RABBIT_ARCHIVE = "rabbit:archive"            # Archive / restore rabbits (no hard delete)
    RABBIT_TRANSACT = "rabbit:transact"          # Ownership events: sale, transfer, death
    RABBIT_VIEW = "rabbit:view"                  # Read rabbits, timeline, media, documents
    RABBIT_HOUSING_MANAGE = "rabbit:housing:manage"  # Write rabbitries/buildings/rooms/rows/cages
    RABBIT_HOUSING_VIEW = "rabbit:housing:view"      # Read housing hierarchy & occupancy
    RABBIT_CATALOG_MANAGE = "rabbit:catalog:manage"  # Write custom breeds / bloodlines
    RABBIT_CATALOG_VIEW = "rabbit:catalog:view"      # Read breed / bloodline catalog
    RABBIT_BREEDING_MANAGE = "rabbit:breeding:manage"  # Write breedings, litters, kindling, weaning
    RABBIT_BREEDING_VIEW = "rabbit:breeding:view"      # Read breeding records & litters
    RABBIT_PEDIGREE_EDIT = "rabbit:pedigree:edit"      # Edit pedigree links (authorised correction)
    RABBIT_PEDIGREE_VIEW = "rabbit:pedigree:view"      # Read pedigrees / genetics
    RABBIT_HEALTH_LOG = "rabbit:health:log"      # Write health, vaccination, mortality records
    RABBIT_HEALTH_VIEW = "rabbit:health:view"    # Read health & mortality records
    RABBIT_WEIGHT_LOG = "rabbit:weight:log"      # Record weights / growth measurements
    RABBIT_FEED_RECORD = "rabbit:feed:record"    # Record feeding events
    RABBIT_FEED_VIEW = "rabbit:feed:view"        # Read feeding history
    RABBIT_SALES_RECORD = "rabbit:sales:record"  # Record sales
    RABBIT_SALES_VIEW = "rabbit:sales:view"      # Read sales history
    RABBIT_FINANCE_VIEW = "rabbit:finance:view"  # Read rabbit finance summary & analytics
    RABBIT_REPORT_VIEW = "rabbit:report:view"    # Read reports & dashboards
    RABBIT_REPORT_EXPORT = "rabbit:report:export"  # Export reports (PDF / Excel / CSV)
    RABBIT_GROWTH_VIEW = "rabbit:growth:view"    # Read growth plan / roadmap / progress
    RABBIT_GROWTH_EDIT = "rabbit:growth:edit"    # Create / edit growth goals & roadmaps
    RABBIT_AUTOMATION_MANAGE = "rabbit:automation:manage"  # Generate reminders, drive workflows
    RABBIT_AUTOMATION_VIEW = "rabbit:automation:view"      # Read rabbit tasks, reminders, workflows

    # Small Ruminant — Goat (Module 18) + Sheep (Module 19). Goat Doc 7 §4.
    # ONE permission set covers both species workspaces (shared foundation); farm
    # isolation + the species discriminator scope the data. ARIA / Mission Control
    # reuse the platform AI_QUERY / AI_INSIGHT_VIEW perms.
    SR_CREATE = "sr:create"                        # Register goats / sheep
    SR_EDIT = "sr:edit"                            # Edit identity / details, move between groups/pens/pastures
    SR_ARCHIVE = "sr:archive"                      # Archive / restore animals (no hard delete)
    SR_TRANSACT = "sr:transact"                    # Ownership events: sale, transfer, death, culling
    SR_VIEW = "sr:view"                            # Read animals, timeline, media, documents
    SR_HOUSING_MANAGE = "sr:housing:manage"        # Write herds / groups / pens / pastures
    SR_HOUSING_VIEW = "sr:housing:view"            # Read housing/grouping hierarchy & occupancy
    SR_CATALOG_MANAGE = "sr:catalog:manage"        # Write custom breeds / bloodlines
    SR_CATALOG_VIEW = "sr:catalog:view"            # Read breed / bloodline catalog
    SR_BREEDING_MANAGE = "sr:breeding:manage"      # Write breedings, births (kidding/lambing), weaning
    SR_BREEDING_VIEW = "sr:breeding:view"          # Read breeding records & births
    SR_PEDIGREE_EDIT = "sr:pedigree:edit"          # Edit pedigree links (authorised correction)
    SR_PEDIGREE_VIEW = "sr:pedigree:view"          # Read pedigrees / genetics
    SR_HEALTH_LOG = "sr:health:log"                # Write health, vaccination, deworming, hoof, mortality
    SR_HEALTH_VIEW = "sr:health:view"              # Read health & mortality records
    SR_WEIGHT_LOG = "sr:weight:log"                # Record weights / growth measurements
    SR_FEED_RECORD = "sr:feed:record"              # Record feeding / grazing events
    SR_FEED_VIEW = "sr:feed:view"                  # Read feeding / grazing history
    SR_DAIRY_RECORD = "sr:dairy:record"            # Record milk / lactation (goat dairy, Milestone 6)
    SR_DAIRY_VIEW = "sr:dairy:view"                # Read milk / lactation records
    SR_WOOL_RECORD = "sr:wool:record"              # Record shearing / fleece (sheep wool, Milestone 7)
    SR_WOOL_VIEW = "sr:wool:view"                  # Read shearing / fleece records
    SR_SALES_RECORD = "sr:sales:record"            # Record sales
    SR_SALES_VIEW = "sr:sales:view"                # Read sales history
    SR_FINANCE_VIEW = "sr:finance:view"            # Read finance summary & analytics
    SR_REPORT_VIEW = "sr:report:view"              # Read reports & dashboards
    SR_REPORT_EXPORT = "sr:report:export"          # Export reports (PDF / Excel / CSV)
    SR_GROWTH_VIEW = "sr:growth:view"              # Read growth plan / roadmap / progress
    SR_GROWTH_EDIT = "sr:growth:edit"              # Create / edit growth goals & roadmaps
    SR_AUTOMATION_MANAGE = "sr:automation:manage"  # Generate reminders, drive workflows
    SR_AUTOMATION_VIEW = "sr:automation:view"      # Read tasks, reminders, workflows

    # ── Operations Planner (Platform Module 5) ────────────────────────────────
    # Cross-module recurring-operations engine. `ops:` is already taken by the
    # daily ops-log perms, so the routine engine namespaces under `opsplan:`.
    OPSPLAN_ROUTINE_VIEW = "opsplan:routine:view"      # Read routines / library / schedules / calendar
    OPSPLAN_ROUTINE_EDIT = "opsplan:routine:edit"      # Create / edit / version / activate routines
    OPSPLAN_MANUAL_VIEW = "opsplan:manual:view"        # Read the Operations Manual
    OPSPLAN_MANUAL_EDIT = "opsplan:manual:edit"        # Edit the Operations Manual
    OPSPLAN_MANUAL_APPROVE = "opsplan:manual:approve"  # Approve manual / routine versions (owner concern)
    OPSPLAN_SOP_VIEW = "opsplan:sop:view"              # Read SOPs & checklists
    OPSPLAN_SOP_EDIT = "opsplan:sop:edit"              # Create / edit / approve SOPs & checklists
    OPSPLAN_SCHEDULE_MANAGE = "opsplan:schedule:manage"  # Generate / recalculate schedules & calendar events
    OPSPLAN_ASSIGN_MANAGE = "opsplan:assign:manage"    # Assign workers/teams/shifts, record completions
    OPSPLAN_ANALYTICS_VIEW = "opsplan:analytics:view"  # Read performance / compliance / optimisation analytics
    OPSPLAN_SETTINGS_MANAGE = "opsplan:settings:manage"  # Manage Operations Planner settings & automation rules

    # ── Swine — Pig Framework (Module 20) ─────────────────────────────────────
    # Complete pig production: breeding/AI/pregnancy/farrowing/piglets/weaning,
    # nursery→grower→finisher production, feed, health/biosecurity, growth, sales
    # and finance (Swine Doc 3 §22, Doc 5 §15). One shared set for the module.
    SWINE_CREATE = "swine:create"                        # Register pigs
    SWINE_EDIT = "swine:edit"                            # Edit identity / details, move between groups/pens
    SWINE_ARCHIVE = "swine:archive"                      # Archive / restore pigs (no hard delete)
    SWINE_TRANSACT = "swine:transact"                    # Ownership events: sale, transfer, death, culling
    SWINE_VIEW = "swine:view"                            # Read pigs, timeline, media, documents
    SWINE_HOUSING_MANAGE = "swine:housing:manage"        # Write herds / groups / pens
    SWINE_HOUSING_VIEW = "swine:housing:view"            # Read housing/grouping hierarchy & occupancy
    SWINE_CATALOG_MANAGE = "swine:catalog:manage"        # Write custom breeds / bloodlines
    SWINE_CATALOG_VIEW = "swine:catalog:view"            # Read breed / bloodline catalog
    SWINE_BREEDING_MANAGE = "swine:breeding:manage"      # Write mating, AI, pregnancy, farrowing, weaning
    SWINE_BREEDING_VIEW = "swine:breeding:view"          # Read breeding / AI / pregnancy / farrowing records
    SWINE_PEDIGREE_EDIT = "swine:pedigree:edit"          # Edit pedigree links (authorised correction)
    SWINE_PEDIGREE_VIEW = "swine:pedigree:view"          # Read pedigrees / genetics
    SWINE_HEALTH_LOG = "swine:health:log"                # Write health, vaccination, treatment, mortality, biosecurity
    SWINE_HEALTH_VIEW = "swine:health:view"              # Read health & mortality records
    SWINE_WEIGHT_LOG = "swine:weight:log"                # Record weights / growth measurements
    SWINE_FEED_RECORD = "swine:feed:record"              # Record feeding / consumption
    SWINE_FEED_VIEW = "swine:feed:view"                  # Read feeding history
    SWINE_PRODUCTION_MANAGE = "swine:production:manage"  # Manage nursery / grower / finisher production groups
    SWINE_PRODUCTION_VIEW = "swine:production:view"      # Read production-group performance
    SWINE_SALES_RECORD = "swine:sales:record"            # Record sales
    SWINE_SALES_VIEW = "swine:sales:view"                # Read sales history
    SWINE_FINANCE_VIEW = "swine:finance:view"            # Read finance summary & analytics
    SWINE_REPORT_VIEW = "swine:report:view"              # Read reports & dashboards
    SWINE_REPORT_EXPORT = "swine:report:export"          # Export reports (PDF / Excel / CSV)
    SWINE_GROWTH_VIEW = "swine:growth:view"              # Read growth plan / roadmap / progress
    SWINE_GROWTH_EDIT = "swine:growth:edit"              # Create / edit growth goals & roadmaps
    SWINE_AUTOMATION_MANAGE = "swine:automation:manage"  # Generate reminders, drive workflows
    SWINE_AUTOMATION_VIEW = "swine:automation:view"      # Read tasks, reminders, workflows


# ── Role → Permission Mapping ─────────────────────────────────────────────────
# Derived from Engineering Constitution Section 5 RBAC matrix.

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "super_admin": set(Permission),  # All permissions

    "platform_admin": {
        Permission.ADMIN_ORG_MANAGE,
        Permission.ADMIN_PLATFORM_CONFIG,
        Permission.ADMIN_DASHBOARD,
        Permission.ADMIN_ALERT_PUBLISH,
        Permission.ADMIN_MARKET_MANAGE,
        Permission.ADMIN_USER_MANAGE,
        Permission.ADMIN_FARM_MANAGE,
        Permission.ADMIN_AI_USAGE_VIEW,
        Permission.FARM_VIEW if hasattr(Permission, "FARM_VIEW") else Permission.FLOCK_VIEW,
    },

    "enterprise_owner": {
        # V1: seeded but no user-facing flows. Same as farm_owner for now.
        Permission.FARM_CREATE,
        Permission.FARM_EDIT,
        Permission.FARM_MEMBER_INVITE,
        Permission.FARM_MEMBER_REMOVE,
        Permission.FARM_MEMBER_ROLE_CHANGE,
        Permission.FARM_UNIT_MANAGE,
        Permission.FLOCK_CREATE,
        Permission.FLOCK_UPDATE,
        Permission.FLOCK_ARCHIVE,
        Permission.FLOCK_CLOSE,
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_LOG_CORRECT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_EVENT_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_EVENT_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_EXPENSE_LOG,
        Permission.FINANCE_EXPENSE_EDIT,
        Permission.FINANCE_REVENUE_LOG,
        Permission.FINANCE_RECORD,
        Permission.FINANCE_VIEW,
        Permission.AI_QUERY,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "farm_owner": {
        Permission.FARM_CREATE,
        Permission.FARM_EDIT,
        Permission.FARM_MEMBER_INVITE,
        Permission.FARM_MEMBER_REMOVE,
        Permission.FARM_MEMBER_ROLE_CHANGE,
        Permission.FARM_UNIT_MANAGE,
        Permission.FLOCK_CREATE,
        Permission.FLOCK_UPDATE,
        Permission.FLOCK_ARCHIVE,
        Permission.FLOCK_CLOSE,
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_LOG_CORRECT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_EVENT_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_EVENT_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_EXPENSE_LOG,
        Permission.FINANCE_EXPENSE_EDIT,
        Permission.FINANCE_REVENUE_LOG,
        Permission.FINANCE_RECORD,
        Permission.FINANCE_VIEW,
        Permission.AI_QUERY,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "farm_manager": {
        Permission.FARM_EDIT,
        Permission.FARM_MEMBER_INVITE,
        Permission.FARM_UNIT_MANAGE,
        Permission.FLOCK_CREATE,
        Permission.FLOCK_UPDATE,
        Permission.FLOCK_ARCHIVE,
        Permission.FLOCK_CLOSE,
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_LOG_CORRECT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_EVENT_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_EVENT_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_EXPENSE_LOG,
        Permission.FINANCE_EXPENSE_EDIT,
        Permission.FINANCE_REVENUE_LOG,
        Permission.FINANCE_RECORD,
        Permission.FINANCE_VIEW,
        Permission.AI_QUERY,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "vet_consultant": {
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_EVENT_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_EVENT_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "farm_worker": {
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_EVENT_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "viewer": {
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_EVENT_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_VIEW,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },
}


# Feed Management (Phase 3, Module 4) permissions layered onto the base matrix.
# Operational roles manage feed stock; read-only roles can view it. super_admin
# already holds every permission via set(Permission).
for _feed_writer in ("enterprise_owner", "farm_owner", "farm_manager", "farm_worker"):
    ROLE_PERMISSIONS[_feed_writer] |= {Permission.FEED_MANAGE, Permission.FEED_VIEW}
for _feed_reader in ("vet_consultant", "viewer"):
    ROLE_PERMISSIONS[_feed_reader].add(Permission.FEED_VIEW)

# Inventory & Asset Management (Module 6) permissions.
for _inv_writer in ("enterprise_owner", "farm_owner", "farm_manager", "farm_worker"):
    ROLE_PERMISSIONS[_inv_writer] |= {Permission.INVENTORY_MANAGE, Permission.INVENTORY_VIEW}
for _inv_reader in ("vet_consultant", "viewer"):
    ROLE_PERMISSIONS[_inv_reader].add(Permission.INVENTORY_VIEW)

# Automation & Notifications (Module 8) permissions. Managing rules is an
# owner/manager concern; everyone can view their activity + reminders.
for _auto_writer in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_auto_writer] |= {Permission.AUTOMATION_MANAGE, Permission.AUTOMATION_VIEW}
for _auto_reader in ("farm_worker", "vet_consultant", "viewer"):
    ROLE_PERMISSIONS[_auto_reader].add(Permission.AUTOMATION_VIEW)

# Production Readiness (Module 11) permissions.
#
# Graded by blast radius rather than seniority alone:
#   view      — anyone who can see the farm may read status and reports.
#   export    — data leaves the system, so it stops at owner/manager.
#   import    — writes bulk records, same bar as export.
#   backups   — restoring overwrites live data, so owners only.
#   diagnostics — read-only sweeps, but they surface configuration detail.
for _prod_reader in (
    "enterprise_owner", "farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer",
):
    ROLE_PERMISSIONS[_prod_reader].add(Permission.PRODUCTION_VIEW)
for _data_mover in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_data_mover] |= {
        Permission.DATA_EXPORT, Permission.DATA_IMPORT, Permission.DIAGNOSTICS_RUN,
    }
for _backup_admin in ("enterprise_owner", "farm_owner"):
    ROLE_PERMISSIONS[_backup_admin].add(Permission.BACKUP_MANAGE)

# Aviculture (Module 15) permissions, layered onto the base matrix.
#
# Graded by responsibility:
#   full write   — owner/manager/enterprise run the collection end to end.
#   care write   — workers add/edit birds, log health, but never transact
#                  ownership (sale/purchase/transfer/death) or archive records.
#   clinical     — the vet consultant reads birds and writes health records.
#   read-only    — viewers see everything, change nothing.
_AVI_VIEW = {
    Permission.AVI_BIRD_VIEW,
    Permission.AVI_AVIARY_VIEW,
    Permission.AVI_BREEDING_VIEW,
    Permission.AVI_CATALOG_VIEW,
    Permission.AVI_HEALTH_VIEW,
    Permission.AVI_INCUBATION_VIEW,
    Permission.AVI_FINANCE_VIEW,
    Permission.AVI_AUTOMATION_VIEW,
}
_AVI_FULL = _AVI_VIEW | {
    Permission.AVI_BIRD_CREATE,
    Permission.AVI_BIRD_UPDATE,
    Permission.AVI_BIRD_ARCHIVE,
    Permission.AVI_BIRD_TRANSACT,
    Permission.AVI_AVIARY_MANAGE,
    Permission.AVI_BREEDING_MANAGE,
    Permission.AVI_CATALOG_MANAGE,
    Permission.AVI_HEALTH_LOG,
    Permission.AVI_INCUBATION_MANAGE,
    Permission.AVI_FINANCE_MANAGE,
    Permission.AVI_AUTOMATION_MANAGE,
}
for _avi_full in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_avi_full] |= _AVI_FULL
ROLE_PERMISSIONS["farm_worker"] |= _AVI_VIEW | {
    Permission.AVI_BIRD_CREATE,
    Permission.AVI_BIRD_UPDATE,
    Permission.AVI_HEALTH_LOG,
    Permission.AVI_INCUBATION_MANAGE,
    Permission.AVI_AUTOMATION_MANAGE,
}
ROLE_PERMISSIONS["vet_consultant"] |= _AVI_VIEW | {Permission.AVI_HEALTH_LOG}
ROLE_PERMISSIONS["viewer"] |= _AVI_VIEW

# ── Black Soldier Fly RBAC (Module 16). Spec Part 8 §5-9. ─────────────────────
# Graded by responsibility, mirroring the platform role model:
#   full        — owner/manager/enterprise run BSF production end to end.
#   operational — workers create/edit batches, record feeding/harvest/environment
#                 and drive automation, but never delete batches, edit the growth
#                 plan or touch finance.
#   read-only   — viewers see everything, change nothing.
_BSF_VIEW = {
    Permission.BSF_BATCH_VIEW,
    Permission.BSF_UNIT_VIEW,
    Permission.BSF_COLONY_VIEW,
    Permission.BSF_CATALOG_VIEW,
    Permission.BSF_FEED_VIEW,
    Permission.BSF_HARVEST_VIEW,
    Permission.BSF_ENVIRONMENT_VIEW,
    Permission.BSF_FINANCE_VIEW,
    Permission.BSF_REPORT_VIEW,
    Permission.BSF_GROWTH_VIEW,
    Permission.BSF_AUTOMATION_VIEW,
}
_BSF_FULL = _BSF_VIEW | {
    Permission.BSF_BATCH_CREATE,
    Permission.BSF_BATCH_EDIT,
    Permission.BSF_BATCH_DELETE,
    Permission.BSF_UNIT_MANAGE,
    Permission.BSF_COLONY_MANAGE,
    Permission.BSF_CATALOG_MANAGE,
    Permission.BSF_FEED_RECORD,
    Permission.BSF_HARVEST_RECORD,
    Permission.BSF_ENVIRONMENT_RECORD,
    Permission.BSF_REPORT_EXPORT,
    Permission.BSF_GROWTH_EDIT,
    Permission.BSF_AUTOMATION_MANAGE,
}
for _bsf_full in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_bsf_full] |= _BSF_FULL
# Workers operate production but do not see strategic/financial data (Spec §6):
# finance, reports and growth-plan views are manager/owner concerns (Spec §8-9).
_BSF_WORKER_VIEW = _BSF_VIEW - {
    Permission.BSF_FINANCE_VIEW,
    Permission.BSF_REPORT_VIEW,
    Permission.BSF_GROWTH_VIEW,
}
ROLE_PERMISSIONS["farm_worker"] |= _BSF_WORKER_VIEW | {
    Permission.BSF_BATCH_CREATE,
    Permission.BSF_BATCH_EDIT,
    Permission.BSF_UNIT_MANAGE,
    Permission.BSF_COLONY_MANAGE,
    Permission.BSF_FEED_RECORD,
    Permission.BSF_HARVEST_RECORD,
    Permission.BSF_ENVIRONMENT_RECORD,
    Permission.BSF_AUTOMATION_MANAGE,
}
ROLE_PERMISSIONS["vet_consultant"] |= _BSF_VIEW
ROLE_PERMISSIONS["viewer"] |= _BSF_VIEW


# Rabbit Management (Module 17) permissions layered onto the base matrix.
# Spec Part 8 §5-9: owner/manager hold full control; workers operate but cannot
# archive, transact, manage catalog/housing or see strategic finance/reports/
# growth views; vets get clinical write; viewers are read-only.
_RABBIT_VIEW = {
    Permission.RABBIT_VIEW,
    Permission.RABBIT_HOUSING_VIEW,
    Permission.RABBIT_CATALOG_VIEW,
    Permission.RABBIT_BREEDING_VIEW,
    Permission.RABBIT_PEDIGREE_VIEW,
    Permission.RABBIT_HEALTH_VIEW,
    Permission.RABBIT_FEED_VIEW,
    Permission.RABBIT_SALES_VIEW,
    Permission.RABBIT_FINANCE_VIEW,
    Permission.RABBIT_REPORT_VIEW,
    Permission.RABBIT_GROWTH_VIEW,
    Permission.RABBIT_AUTOMATION_VIEW,
}
_RABBIT_FULL = _RABBIT_VIEW | {
    Permission.RABBIT_CREATE,
    Permission.RABBIT_EDIT,
    Permission.RABBIT_ARCHIVE,
    Permission.RABBIT_TRANSACT,
    Permission.RABBIT_HOUSING_MANAGE,
    Permission.RABBIT_CATALOG_MANAGE,
    Permission.RABBIT_BREEDING_MANAGE,
    Permission.RABBIT_PEDIGREE_EDIT,
    Permission.RABBIT_HEALTH_LOG,
    Permission.RABBIT_WEIGHT_LOG,
    Permission.RABBIT_FEED_RECORD,
    Permission.RABBIT_SALES_RECORD,
    Permission.RABBIT_REPORT_EXPORT,
    Permission.RABBIT_GROWTH_EDIT,
    Permission.RABBIT_AUTOMATION_MANAGE,
}
for _rabbit_full in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_rabbit_full] |= _RABBIT_FULL

# Workers do the daily operational work but not strategic/transactional actions.
_RABBIT_WORKER_VIEW = _RABBIT_VIEW - {
    Permission.RABBIT_SALES_VIEW,
    Permission.RABBIT_FINANCE_VIEW,
    Permission.RABBIT_REPORT_VIEW,
    Permission.RABBIT_GROWTH_VIEW,
}
ROLE_PERMISSIONS["farm_worker"] |= _RABBIT_WORKER_VIEW | {
    Permission.RABBIT_CREATE,
    Permission.RABBIT_EDIT,
    Permission.RABBIT_BREEDING_MANAGE,
    Permission.RABBIT_HEALTH_LOG,
    Permission.RABBIT_WEIGHT_LOG,
    Permission.RABBIT_FEED_RECORD,
    Permission.RABBIT_AUTOMATION_MANAGE,
}
ROLE_PERMISSIONS["vet_consultant"] |= _RABBIT_VIEW | {Permission.RABBIT_HEALTH_LOG}
ROLE_PERMISSIONS["viewer"] |= _RABBIT_VIEW


# Small Ruminant — Goat + Sheep (Modules 18/19) permissions layered onto the base
# matrix. Goat Doc 7 §4-5: owner/manager hold full control; workers operate but
# cannot archive, transact, manage catalog/housing or see strategic finance/reports/
# growth views; vets get clinical write; viewers are read-only. One shared set
# covers both species (goat & sheep run on the same foundation).
_SR_VIEW = {
    Permission.SR_VIEW,
    Permission.SR_HOUSING_VIEW,
    Permission.SR_CATALOG_VIEW,
    Permission.SR_BREEDING_VIEW,
    Permission.SR_PEDIGREE_VIEW,
    Permission.SR_HEALTH_VIEW,
    Permission.SR_FEED_VIEW,
    Permission.SR_DAIRY_VIEW,
    Permission.SR_WOOL_VIEW,
    Permission.SR_SALES_VIEW,
    Permission.SR_FINANCE_VIEW,
    Permission.SR_REPORT_VIEW,
    Permission.SR_GROWTH_VIEW,
    Permission.SR_AUTOMATION_VIEW,
}
_SR_FULL = _SR_VIEW | {
    Permission.SR_CREATE,
    Permission.SR_EDIT,
    Permission.SR_ARCHIVE,
    Permission.SR_TRANSACT,
    Permission.SR_HOUSING_MANAGE,
    Permission.SR_CATALOG_MANAGE,
    Permission.SR_BREEDING_MANAGE,
    Permission.SR_PEDIGREE_EDIT,
    Permission.SR_HEALTH_LOG,
    Permission.SR_WEIGHT_LOG,
    Permission.SR_FEED_RECORD,
    Permission.SR_DAIRY_RECORD,
    Permission.SR_WOOL_RECORD,
    Permission.SR_SALES_RECORD,
    Permission.SR_REPORT_EXPORT,
    Permission.SR_GROWTH_EDIT,
    Permission.SR_AUTOMATION_MANAGE,
}
for _sr_full in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_sr_full] |= _SR_FULL

# Workers do the daily operational work but not strategic/transactional actions.
_SR_WORKER_VIEW = _SR_VIEW - {
    Permission.SR_SALES_VIEW,
    Permission.SR_FINANCE_VIEW,
    Permission.SR_REPORT_VIEW,
    Permission.SR_GROWTH_VIEW,
}
ROLE_PERMISSIONS["farm_worker"] |= _SR_WORKER_VIEW | {
    Permission.SR_CREATE,
    Permission.SR_EDIT,
    Permission.SR_BREEDING_MANAGE,
    Permission.SR_HEALTH_LOG,
    Permission.SR_WEIGHT_LOG,
    Permission.SR_FEED_RECORD,
    Permission.SR_DAIRY_RECORD,
    Permission.SR_WOOL_RECORD,
    Permission.SR_AUTOMATION_MANAGE,
}
ROLE_PERMISSIONS["vet_consultant"] |= _SR_VIEW | {Permission.SR_HEALTH_LOG}
ROLE_PERMISSIONS["viewer"] |= _SR_VIEW


# platform_admin is an explicit set rather than a farm role, so it is granted
# the production permissions directly.
ROLE_PERMISSIONS["platform_admin"] |= {
    Permission.PRODUCTION_VIEW,
    Permission.DATA_EXPORT,
    Permission.DATA_IMPORT,
    Permission.BACKUP_MANAGE,
    Permission.DIAGNOSTICS_RUN,
}


# ── Operations Planner RBAC (Platform Module 5) ───────────────────────────────
# Graded by blast radius (spec Doc 4 §21), mirroring the platform role model:
#   full     — owner/manager/enterprise run the operational rhythm end to end.
#   execute  — workers see routines/SOPs/calendar and record completions, but do
#              not author routines, edit the manual, or approve changes.
#   read     — viewers/vets see the operating rhythm, change nothing.
# Approving the manual and routine versions is an owner/enterprise concern.
_OPSPLAN_VIEW = {
    Permission.OPSPLAN_ROUTINE_VIEW,
    Permission.OPSPLAN_MANUAL_VIEW,
    Permission.OPSPLAN_SOP_VIEW,
    Permission.OPSPLAN_ANALYTICS_VIEW,
}
_OPSPLAN_FULL = _OPSPLAN_VIEW | {
    Permission.OPSPLAN_ROUTINE_EDIT,
    Permission.OPSPLAN_MANUAL_EDIT,
    Permission.OPSPLAN_MANUAL_APPROVE,
    Permission.OPSPLAN_SOP_EDIT,
    Permission.OPSPLAN_SCHEDULE_MANAGE,
    Permission.OPSPLAN_ASSIGN_MANAGE,
    Permission.OPSPLAN_SETTINGS_MANAGE,
}
for _ops_full in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_ops_full] |= _OPSPLAN_FULL
# Managers author but only owners/enterprise approve the manual (owner concern):
ROLE_PERMISSIONS["farm_manager"] -= {Permission.OPSPLAN_MANUAL_APPROVE}
# Workers execute the rhythm and record completions, nothing strategic:
ROLE_PERMISSIONS["farm_worker"] |= {
    Permission.OPSPLAN_ROUTINE_VIEW,
    Permission.OPSPLAN_MANUAL_VIEW,
    Permission.OPSPLAN_SOP_VIEW,
    Permission.OPSPLAN_ASSIGN_MANAGE,
}
for _ops_reader in ("vet_consultant", "viewer"):
    ROLE_PERMISSIONS[_ops_reader] |= _OPSPLAN_VIEW


# ── Swine — Pig Framework (Module 20) RBAC ────────────────────────────────────
# Swine Doc 11 §11 / Doc 5 §15: owner/manager hold full control; workers operate
# the daily rhythm but cannot archive, transact, manage catalog/housing or see
# strategic finance/reports/growth views; vets get clinical write; viewers are
# read-only. Mirrors the Small Ruminant matrix (no dairy/wool; adds production-group
# management for the nursery/grower/finisher milestones).
_SWINE_VIEW = {
    Permission.SWINE_VIEW,
    Permission.SWINE_HOUSING_VIEW,
    Permission.SWINE_CATALOG_VIEW,
    Permission.SWINE_BREEDING_VIEW,
    Permission.SWINE_PEDIGREE_VIEW,
    Permission.SWINE_HEALTH_VIEW,
    Permission.SWINE_FEED_VIEW,
    Permission.SWINE_PRODUCTION_VIEW,
    Permission.SWINE_SALES_VIEW,
    Permission.SWINE_FINANCE_VIEW,
    Permission.SWINE_REPORT_VIEW,
    Permission.SWINE_GROWTH_VIEW,
    Permission.SWINE_AUTOMATION_VIEW,
}
_SWINE_FULL = _SWINE_VIEW | {
    Permission.SWINE_CREATE,
    Permission.SWINE_EDIT,
    Permission.SWINE_ARCHIVE,
    Permission.SWINE_TRANSACT,
    Permission.SWINE_HOUSING_MANAGE,
    Permission.SWINE_CATALOG_MANAGE,
    Permission.SWINE_BREEDING_MANAGE,
    Permission.SWINE_PEDIGREE_EDIT,
    Permission.SWINE_HEALTH_LOG,
    Permission.SWINE_WEIGHT_LOG,
    Permission.SWINE_FEED_RECORD,
    Permission.SWINE_PRODUCTION_MANAGE,
    Permission.SWINE_SALES_RECORD,
    Permission.SWINE_REPORT_EXPORT,
    Permission.SWINE_GROWTH_EDIT,
    Permission.SWINE_AUTOMATION_MANAGE,
}
for _swine_full in ("enterprise_owner", "farm_owner", "farm_manager"):
    ROLE_PERMISSIONS[_swine_full] |= _SWINE_FULL

# Workers do the daily operational work but not strategic/transactional actions.
_SWINE_WORKER_VIEW = _SWINE_VIEW - {
    Permission.SWINE_SALES_VIEW,
    Permission.SWINE_FINANCE_VIEW,
    Permission.SWINE_REPORT_VIEW,
    Permission.SWINE_GROWTH_VIEW,
}
ROLE_PERMISSIONS["farm_worker"] |= _SWINE_WORKER_VIEW | {
    Permission.SWINE_CREATE,
    Permission.SWINE_EDIT,
    Permission.SWINE_BREEDING_MANAGE,
    Permission.SWINE_HEALTH_LOG,
    Permission.SWINE_WEIGHT_LOG,
    Permission.SWINE_FEED_RECORD,
    Permission.SWINE_PRODUCTION_MANAGE,
    Permission.SWINE_AUTOMATION_MANAGE,
}
ROLE_PERMISSIONS["vet_consultant"] |= _SWINE_VIEW | {Permission.SWINE_HEALTH_LOG}
ROLE_PERMISSIONS["viewer"] |= _SWINE_VIEW


def get_user_permissions(role_name: str) -> set[Permission]:
    """Return the set of permissions for a given role key."""
    return ROLE_PERMISSIONS.get(role_name, set())


def has_permission(role_name: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in get_user_permissions(role_name)


# ── FastAPI Dependencies ───────────────────────────────────────────────────────

def require_permission(permission: Permission):
    """
    FastAPI dependency factory.
    Usage: Depends(require_permission(Permission.FLOCK_CREATE))
    Checks the user's role for the requested permission.
    Farm-scoped permission validation happens in the service layer.
    """

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        # Collect all role names for this user
        user_role_names = {ur.role.name for ur in current_user.user_roles}

        for role_name in user_role_names:
            if has_permission(role_name, permission):
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": f"Your role does not have permission: {permission}",
            },
        )

    return _check


def require_admin():
    """Shortcut dependency for super_admin-only endpoints."""
    return require_permission(Permission.ADMIN_DASHBOARD)
