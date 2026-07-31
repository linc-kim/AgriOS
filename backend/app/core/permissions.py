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
ROLE_PERMISSIONS["farm_worker"] |= _BSF_VIEW | {
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

# platform_admin is an explicit set rather than a farm role, so it is granted
# the production permissions directly.
ROLE_PERMISSIONS["platform_admin"] |= {
    Permission.PRODUCTION_VIEW,
    Permission.DATA_EXPORT,
    Permission.DATA_IMPORT,
    Permission.BACKUP_MANAGE,
    Permission.DIAGNOSTICS_RUN,
}


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
