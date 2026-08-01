"""
Rabbit Management (Module 17, Part 1) — Foundation invariants.

Part 1 is pure database architecture: models, enumerated value contracts, and
RBAC wiring. The deterministic engines arrive in later Parts, so these tests lock
the foundation's contracts rather than any calculation:

  * the enumerated value tuples are well-formed and internally consistent;
  * the Rabbit aggregate exposes the identity / classification / lifecycle /
    pedigree surface the specification requires (Spec Part 3 §4);
  * the 5-level housing hierarchy is modelled (Spec Part 1 §6, Part 3 §14);
  * every foundation table is soft-delete capable and ``rabbit`` prefixed;
  * the Rabbit RBAC layer grants the right permissions to the right roles and
    never leaks write access to read-only roles (Spec Part 8 §5-9).
"""

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models import rabbit


# ── Enumerated value contracts ────────────────────────────────────────────────

def _no_duplicates(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def test_value_tuples_have_no_duplicates():
    for name in dir(rabbit):
        if name.endswith("_VALUES"):
            values = getattr(rabbit, name)
            assert _no_duplicates(values), f"{name} contains duplicates: {values}"


def test_sex_uses_rabbit_domain_terms():
    # Spec dashboards count Bucks and Does (Part 5 §3).
    assert rabbit.RABBIT_SEX_VALUES == ("buck", "doe", "unknown")


def test_lifecycle_stage_covers_the_life_cycle():
    # Spec Part 1 §8 — kit → weaning → growing → breeding → retirement.
    for stage in ("kit", "weaner", "grower", "breeding_candidate",
                  "breeding_adult", "retired", "unknown"):
        assert stage in rabbit.RABBIT_LIFECYCLE_STAGE_VALUES


def test_status_models_terminal_outcomes():
    # Spec Part 2 §2 — records never deleted; sold/transferred/deceased leave herd.
    for status in ("active", "sold", "transferred", "deceased", "archived"):
        assert status in rabbit.RABBIT_STATUS_VALUES
    for terminal in rabbit.RABBIT_TERMINAL_STATUSES:
        assert terminal in rabbit.RABBIT_STATUS_VALUES
    assert "active" not in rabbit.RABBIT_TERMINAL_STATUSES


def test_reproductive_status_covers_doe_cycle():
    # Spec Part 3 §4 — reproductive status through the breeding cycle.
    for st in ("not_bred", "bred", "pregnant", "lactating", "unknown"):
        assert st in rabbit.REPRODUCTIVE_STATUS_VALUES


def test_purpose_covers_production_types():
    # Spec Part 1 §7 — meat, breeding, fiber, pet, show, replacement, mixed…
    for purpose in ("meat", "breeding", "fiber", "pet", "show",
                    "replacement", "genetic_improvement", "educational", "mixed"):
        assert purpose in rabbit.RABBIT_PURPOSE_VALUES


def test_cage_types_cover_housing_variants():
    # Spec Part 2 §11 — cages, colony pens, quarantine, isolation units.
    for ctype in ("cage", "colony_pen", "quarantine", "isolation"):
        assert ctype in rabbit.CAGE_TYPE_VALUES


def test_document_types_include_pedigree_and_operational_docs():
    # Spec Part 8 §15.
    for dtype in ("pedigree_certificate", "health_certificate", "vet_report", "invoice"):
        assert dtype in rabbit.DOCUMENT_TYPE_VALUES


# ── Model surface ─────────────────────────────────────────────────────────────

def test_rabbit_table_and_core_columns():
    cols = set(rabbit.Rabbit.__table__.columns.keys())
    # Identity (Spec Part 1 §5, Part 3 §4)
    for col in ("internal_ref", "name", "ear_tag", "tattoo", "qr_code", "rfid"):
        assert col in cols, f"Rabbit missing identity column {col}"
    # Classification
    for col in ("breed_id", "bloodline_id", "variety", "color", "sex", "purpose"):
        assert col in cols, f"Rabbit missing classification column {col}"
    # Biology & lifecycle
    for col in ("date_of_birth", "birth_weight_g", "current_weight_g",
                "lifecycle_stage", "status", "reproductive_status", "fertility_status"):
        assert col in cols, f"Rabbit missing biology column {col}"
    # Deterministic pedigree links (Spec Part 3 §6) — unknown ancestry stays NULL
    assert "sire_id" in cols and "dam_id" in cols
    # Location + farm scoping (organisation isolation)
    assert "cage_id" in cols and "farm_id" in cols


def test_rabbit_identity_is_unique_per_farm():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in rabbit.Rabbit.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    # Spec Part 1 §5 — identifiers unique within an organisation (enforced per-farm).
    assert ("farm_id", "internal_ref") in uniques
    assert ("farm_id", "ear_tag") in uniques


def test_housing_hierarchy_is_five_levels():
    # Spec Part 1 §6 — Rabbitry → Building → Room → Row → Cage.
    assert "rabbitry_id" in rabbit.RabbitBuilding.__table__.columns.keys()
    assert "building_id" in rabbit.RabbitRoom.__table__.columns.keys()
    assert "room_id" in rabbit.RabbitRow.__table__.columns.keys()
    assert "row_id" in rabbit.RabbitCage.__table__.columns.keys()
    # Occupancy is derived, never stored — the cage carries capacity only.
    cage_cols = set(rabbit.RabbitCage.__table__.columns.keys())
    assert "capacity" in cage_cols
    assert "occupancy" not in cage_cols


def test_is_in_herd_property():
    r = rabbit.Rabbit(internal_ref="R-1", status="active")
    assert r.is_in_herd is True
    for terminal in ("sold", "transferred", "deceased", "archived"):
        r.status = terminal
        assert r.is_in_herd is False


def test_all_foundation_tables_are_soft_delete_capable():
    # Every rabbit table inherits AGRIOSBase → soft delete, never hard delete
    # (Spec Part 2 §2, Part 3 §21).
    models = [
        rabbit.RabbitBreed, rabbit.RabbitBloodline, rabbit.RabbitRabbitry,
        rabbit.RabbitBuilding, rabbit.RabbitRoom, rabbit.RabbitRow,
        rabbit.RabbitCage, rabbit.Rabbit, rabbit.RabbitEvent,
        rabbit.RabbitMedia, rabbit.RabbitDocument,
    ]
    for model in models:
        assert "deleted_at" in model.__table__.columns.keys()
        assert "metadata" in model.__table__.columns.keys()
        assert model.__tablename__ == "rabbit" or model.__tablename__.startswith("rabbit_")


# ── RBAC wiring (Spec Part 8 §5-9) ────────────────────────────────────────────

_RABBIT_WRITE = {
    Permission.RABBIT_CREATE, Permission.RABBIT_EDIT, Permission.RABBIT_ARCHIVE,
    Permission.RABBIT_TRANSACT, Permission.RABBIT_HOUSING_MANAGE,
    Permission.RABBIT_CATALOG_MANAGE, Permission.RABBIT_BREEDING_MANAGE,
    Permission.RABBIT_PEDIGREE_EDIT, Permission.RABBIT_HEALTH_LOG,
    Permission.RABBIT_WEIGHT_LOG, Permission.RABBIT_FEED_RECORD,
    Permission.RABBIT_SALES_RECORD, Permission.RABBIT_REPORT_EXPORT,
    Permission.RABBIT_GROWTH_EDIT, Permission.RABBIT_AUTOMATION_MANAGE,
}
_RABBIT_VIEW = {
    Permission.RABBIT_VIEW, Permission.RABBIT_HOUSING_VIEW, Permission.RABBIT_CATALOG_VIEW,
    Permission.RABBIT_BREEDING_VIEW, Permission.RABBIT_PEDIGREE_VIEW,
    Permission.RABBIT_HEALTH_VIEW, Permission.RABBIT_FEED_VIEW, Permission.RABBIT_SALES_VIEW,
    Permission.RABBIT_FINANCE_VIEW, Permission.RABBIT_REPORT_VIEW,
    Permission.RABBIT_GROWTH_VIEW, Permission.RABBIT_AUTOMATION_VIEW,
}


def test_owner_and_manager_have_full_rabbit_control():
    for role in ("farm_owner", "farm_manager", "enterprise_owner"):
        perms = ROLE_PERMISSIONS[role]
        assert _RABBIT_WRITE <= perms, f"{role} missing rabbit write perms"
        assert _RABBIT_VIEW <= perms


def test_super_admin_has_all_rabbit_permissions():
    perms = ROLE_PERMISSIONS["super_admin"]
    assert _RABBIT_WRITE <= perms and _RABBIT_VIEW <= perms


def test_worker_operates_but_cannot_transact_or_touch_strategy():
    perms = ROLE_PERMISSIONS["farm_worker"]
    # Daily operational work.
    assert Permission.RABBIT_CREATE in perms
    assert Permission.RABBIT_EDIT in perms
    assert Permission.RABBIT_BREEDING_MANAGE in perms
    assert Permission.RABBIT_HEALTH_LOG in perms
    assert Permission.RABBIT_WEIGHT_LOG in perms
    assert Permission.RABBIT_FEED_RECORD in perms
    # Archival, transactions, catalog/housing management are owner/manager concerns.
    assert Permission.RABBIT_ARCHIVE not in perms
    assert Permission.RABBIT_TRANSACT not in perms
    assert Permission.RABBIT_CATALOG_MANAGE not in perms
    assert Permission.RABBIT_HOUSING_MANAGE not in perms
    assert Permission.RABBIT_SALES_RECORD not in perms
    assert Permission.RABBIT_GROWTH_EDIT not in perms
    # Strategic/financial views are manager/owner concerns (Spec §6, §8-9).
    assert Permission.RABBIT_FINANCE_VIEW not in perms
    assert Permission.RABBIT_REPORT_VIEW not in perms
    assert Permission.RABBIT_GROWTH_VIEW not in perms
    assert Permission.RABBIT_SALES_VIEW not in perms


def test_vet_has_read_plus_clinical_write_only():
    perms = ROLE_PERMISSIONS["vet_consultant"]
    assert _RABBIT_VIEW <= perms
    assert Permission.RABBIT_HEALTH_LOG in perms
    # No non-clinical write access.
    assert not ((_RABBIT_WRITE - {Permission.RABBIT_HEALTH_LOG}) & perms)


def test_viewer_is_read_only():
    perms = ROLE_PERMISSIONS["viewer"]
    assert _RABBIT_VIEW <= perms
    assert not (_RABBIT_WRITE & perms), "viewer must not hold any rabbit write permission"
