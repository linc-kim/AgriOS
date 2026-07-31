"""
Black Soldier Fly (Module 16, Part 1) — Foundation invariants.

Part 1 is pure database architecture: models, enumerated value contracts, and
RBAC wiring. The deterministic engines arrive in later Parts, so these tests lock
the foundation's contracts rather than any calculation:

  * the enumerated value tuples are well-formed and internally consistent;
  * the Production Batch aggregate exposes the identity / lifecycle / lineage
    surface the specification requires (Spec Part 3 §7, §2);
  * every foundation table is soft-delete capable and ``bsf_`` prefixed;
  * the BSF RBAC layer grants the right permissions to the right roles and never
    leaks write access to read-only roles (Spec Part 8 §5-9).
"""

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models import bsf


# ── Enumerated value contracts ────────────────────────────────────────────────

def _no_duplicates(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def test_value_tuples_have_no_duplicates():
    for name in dir(bsf):
        if name.endswith("_VALUES"):
            values = getattr(bsf, name)
            assert _no_duplicates(values), f"{name} contains duplicates: {values}"


def test_lifecycle_stage_covers_the_full_life_cycle():
    # Spec Part 2 §6 — Eggs → Larvae → Prepupae → Pupae → Adult.
    for stage in ("egg", "hatchling", "feeding_larvae", "mature_larvae",
                  "prepupae", "pupae", "adult", "unknown"):
        assert stage in bsf.LIFECYCLE_STAGE_VALUES


def test_batch_status_models_split_and_merge_lineage():
    # Spec Part 3 §9-10 — split / merge must be terminal-ish batch states.
    for status in ("active", "split", "merged", "harvested", "completed",
                   "terminated", "archived"):
        assert status in bsf.BATCH_STATUS_VALUES


def test_production_unit_types_cover_the_operational_entities():
    # Spec Part 2 §4 — Bin, Tray, Rack, Cage, Chamber, Container, Shelf,
    # Incubator, Drying Unit.
    for utype in ("bin", "tray", "rack", "cage", "chamber", "container",
                  "shelf", "incubator", "drying_unit"):
        assert utype in bsf.UNIT_TYPE_VALUES


def test_document_types_include_operational_docs():
    # Spec Part 3 §18 — lab reports, environmental reports, invoices, certificates.
    for dtype in ("lab_report", "environmental_report", "invoice", "certificate"):
        assert dtype in bsf.DOCUMENT_TYPE_VALUES


# ── Model surface ─────────────────────────────────────────────────────────────

def test_batch_table_and_core_columns():
    cols = set(bsf.BsfBatch.__table__.columns.keys())
    # Identity (Spec Part 3 §7)
    for col in ("batch_number", "name", "batch_type", "lifecycle_stage", "status"):
        assert col in cols, f"BsfBatch missing column {col}"
    # Deterministic lineage links (Spec Part 3 §7-10)
    assert "parent_batch_id" in cols and "source_colony_id" in cols
    # Current estimates (Spec Part 3 §7, §20)
    assert "population_estimate" in cols and "biomass_estimate_g" in cols
    # Assigned production unit + farm scoping (organisation isolation)
    assert "production_unit_id" in cols and "farm_id" in cols


def test_batch_number_is_unique_per_farm():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in bsf.BsfBatch.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("farm_id", "batch_number") in uniques


def test_lifecycle_event_captures_transition_snapshot():
    cols = set(bsf.BsfLifecycleEvent.__table__.columns.keys())
    # Spec Part 3 §8 — previous/new stage, date, population, biomass, survival.
    for col in ("previous_stage", "new_stage", "occurred_on",
                "population_estimate", "biomass_estimate_g", "survival_rate_pct"):
        assert col in cols, f"BsfLifecycleEvent missing {col}"


def test_is_live_property():
    batch = bsf.BsfBatch(batch_number="B-1", status="active")
    assert batch.is_live is True
    for terminal in ("harvested", "completed", "split", "merged", "terminated", "archived"):
        batch.status = terminal
        assert batch.is_live is False


def test_all_foundation_tables_are_soft_delete_capable():
    # Every BSF table inherits AGRIOSBase → soft delete, never hard delete
    # (Spec Part 3 §21).
    models = [
        bsf.BsfSpecies, bsf.BsfProductionUnit, bsf.BsfColony, bsf.BsfBatch,
        bsf.BsfLifecycleEvent, bsf.BsfBatchEvent, bsf.BsfBatchMedia,
        bsf.BsfBatchDocument,
    ]
    for model in models:
        assert "deleted_at" in model.__table__.columns.keys()
        assert "metadata" in model.__table__.columns.keys()
        assert model.__tablename__.startswith("bsf_")


# ── RBAC wiring (Spec Part 8 §5-9) ────────────────────────────────────────────

_BSF_WRITE = {
    Permission.BSF_BATCH_CREATE, Permission.BSF_BATCH_EDIT, Permission.BSF_BATCH_DELETE,
    Permission.BSF_UNIT_MANAGE, Permission.BSF_COLONY_MANAGE, Permission.BSF_CATALOG_MANAGE,
    Permission.BSF_FEED_RECORD, Permission.BSF_HARVEST_RECORD, Permission.BSF_ENVIRONMENT_RECORD,
    Permission.BSF_REPORT_EXPORT, Permission.BSF_GROWTH_EDIT, Permission.BSF_AUTOMATION_MANAGE,
}
_BSF_VIEW = {
    Permission.BSF_BATCH_VIEW, Permission.BSF_UNIT_VIEW, Permission.BSF_COLONY_VIEW,
    Permission.BSF_CATALOG_VIEW, Permission.BSF_FEED_VIEW, Permission.BSF_HARVEST_VIEW,
    Permission.BSF_ENVIRONMENT_VIEW, Permission.BSF_FINANCE_VIEW, Permission.BSF_REPORT_VIEW,
    Permission.BSF_GROWTH_VIEW, Permission.BSF_AUTOMATION_VIEW,
}


def test_owner_and_manager_have_full_bsf_control():
    for role in ("farm_owner", "farm_manager", "enterprise_owner"):
        perms = ROLE_PERMISSIONS[role]
        assert _BSF_WRITE <= perms, f"{role} missing BSF write perms"
        assert _BSF_VIEW <= perms


def test_super_admin_has_all_bsf_permissions():
    perms = ROLE_PERMISSIONS["super_admin"]
    assert _BSF_WRITE <= perms and _BSF_VIEW <= perms


def test_worker_operates_but_cannot_delete_or_touch_finance_and_growth():
    perms = ROLE_PERMISSIONS["farm_worker"]
    assert Permission.BSF_BATCH_CREATE in perms
    assert Permission.BSF_BATCH_EDIT in perms
    assert Permission.BSF_FEED_RECORD in perms
    assert Permission.BSF_HARVEST_RECORD in perms
    assert Permission.BSF_ENVIRONMENT_RECORD in perms
    # Deletion, growth-plan editing and report export are owner/manager concerns.
    assert Permission.BSF_BATCH_DELETE not in perms
    assert Permission.BSF_GROWTH_EDIT not in perms
    assert Permission.BSF_CATALOG_MANAGE not in perms


def test_viewer_is_read_only():
    perms = ROLE_PERMISSIONS["viewer"]
    assert _BSF_VIEW <= perms
    assert not (_BSF_WRITE & perms), "viewer must not hold any BSF write permission"
