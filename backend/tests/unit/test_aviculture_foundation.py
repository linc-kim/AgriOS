"""
Aviculture (Module 15, Part 1) — Foundation invariants.

Part 1 is pure database architecture: models, enumerated value contracts, and
RBAC wiring. There are no business engines yet (those arrive in later parts), so
these tests lock the foundation's contracts rather than any calculation:

  * the enumerated value tuples are well-formed and internally consistent;
  * the bird aggregate exposes the identity / lifecycle / pedigree surface the
    constitution requires (Doc 02 §5, §4; Doc 03 §3);
  * the Aviculture RBAC layer grants the right permissions to the right roles
    and never leaks write access to read-only roles (Doc 10 §3).
"""

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models import aviculture as avi


# ── Enumerated value contracts ────────────────────────────────────────────────

def _no_duplicates(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def test_value_tuples_have_no_duplicates():
    for name in dir(avi):
        if name.endswith("_VALUES"):
            values = getattr(avi, name)
            assert _no_duplicates(values), f"{name} contains duplicates: {values}"


def test_bird_terminal_statuses_are_valid_statuses():
    # A terminal status (removed from the live collection) must be a real status.
    for status in avi.BIRD_TERMINAL_STATUSES:
        assert status in avi.BIRD_STATUS_VALUES
    # "active" is never terminal.
    assert "active" not in avi.BIRD_TERMINAL_STATUSES


def test_sex_and_dna_contracts():
    assert set(avi.BIRD_SEX_VALUES) == {"male", "female", "unknown"}
    # Doc 02 §9 — supported sex-determination methods.
    assert set(avi.BIRD_SEX_METHOD_VALUES) == {
        "visual", "dna", "surgical", "estimated", "unknown",
    }


def test_lifecycle_stage_covers_the_full_life_cycle():
    # Doc 02 §4 — Chick → Juvenile → Adult → Breeding → Retired (+ unknown).
    for stage in ("chick", "juvenile", "adult", "breeding", "retired", "unknown"):
        assert stage in avi.BIRD_LIFECYCLE_STAGE_VALUES


def test_document_types_include_regulatory_docs():
    # Doc 07 §6 / Doc 10 §7 — DNA reports, permits, lab reports must be modelled.
    for dtype in ("dna_certificate", "import_permit", "export_permit", "lab_report"):
        assert dtype in avi.DOCUMENT_TYPE_VALUES


# ── Model surface ─────────────────────────────────────────────────────────────

def test_bird_table_and_identity_columns():
    cols = set(avi.AviBird.__table__.columns.keys())
    # Identity (Doc 02 §5)
    for col in ("internal_ref", "ring_number", "band_number", "microchip", "name",
                "sex", "sex_method", "dna_status", "colour_description", "hatch_date"):
        assert col in cols, f"AviBird missing identity column {col}"
    # Deterministic pedigree links (Doc 04 §4)
    assert "sire_id" in cols and "dam_id" in cols
    # Lifecycle (Doc 02 §4)
    assert "status" in cols and "lifecycle_stage" in cols
    # Farm scoping (organisation isolation via farms.organization_id)
    assert "farm_id" in cols


def test_bird_internal_ref_is_unique_per_farm():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in avi.AviBird.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("farm_id", "internal_ref") in uniques


def test_is_in_collection_property():
    bird = avi.AviBird(internal_ref="B-1", status="active")
    assert bird.is_in_collection is True
    for terminal in avi.BIRD_TERMINAL_STATUSES + ("archived",):
        bird.status = terminal
        assert bird.is_in_collection is False


def test_all_foundation_tables_are_soft_delete_capable():
    # Every aviculture table inherits AGRIOSBase → soft delete, never hard delete
    # (Doc 02 §26, Doc 03 §2, Doc 04 §6).
    models = [
        avi.AviSpecies, avi.AviBreed, avi.AviMutation, avi.AviAviary, avi.AviBird,
        avi.AviBirdMutation, avi.AviPair, avi.AviBirdMedia, avi.AviBirdDocument,
        avi.AviHealthRecord,
    ]
    for model in models:
        assert "deleted_at" in model.__table__.columns.keys()
        assert "metadata" in model.__table__.columns.keys()
        assert model.__tablename__.startswith("avi_")


# ── RBAC wiring (Doc 10 §3) ───────────────────────────────────────────────────

_AVI_WRITE = {
    Permission.AVI_BIRD_CREATE, Permission.AVI_BIRD_UPDATE, Permission.AVI_BIRD_ARCHIVE,
    Permission.AVI_BIRD_TRANSACT, Permission.AVI_AVIARY_MANAGE, Permission.AVI_BREEDING_MANAGE,
    Permission.AVI_CATALOG_MANAGE, Permission.AVI_HEALTH_LOG,
}
_AVI_VIEW = {
    Permission.AVI_BIRD_VIEW, Permission.AVI_AVIARY_VIEW, Permission.AVI_BREEDING_VIEW,
    Permission.AVI_CATALOG_VIEW, Permission.AVI_HEALTH_VIEW,
}


def test_owner_and_manager_have_full_aviculture_control():
    for role in ("farm_owner", "farm_manager", "enterprise_owner"):
        perms = ROLE_PERMISSIONS[role]
        assert _AVI_WRITE <= perms, f"{role} missing aviculture write perms"
        assert _AVI_VIEW <= perms


def test_super_admin_has_all_aviculture_permissions():
    perms = ROLE_PERMISSIONS["super_admin"]
    assert _AVI_WRITE <= perms and _AVI_VIEW <= perms


def test_worker_can_care_but_not_transact_or_archive():
    perms = ROLE_PERMISSIONS["farm_worker"]
    assert Permission.AVI_BIRD_CREATE in perms
    assert Permission.AVI_BIRD_UPDATE in perms
    assert Permission.AVI_HEALTH_LOG in perms
    # Ownership events and archival are owner/manager concerns.
    assert Permission.AVI_BIRD_TRANSACT not in perms
    assert Permission.AVI_BIRD_ARCHIVE not in perms
    assert Permission.AVI_CATALOG_MANAGE not in perms


def test_vet_consultant_is_clinical_only():
    perms = ROLE_PERMISSIONS["vet_consultant"]
    assert Permission.AVI_HEALTH_LOG in perms
    assert _AVI_VIEW <= perms
    assert Permission.AVI_BIRD_CREATE not in perms
    assert Permission.AVI_BIRD_TRANSACT not in perms


def test_viewer_is_read_only():
    perms = ROLE_PERMISSIONS["viewer"]
    assert _AVI_VIEW <= perms
    assert not (_AVI_WRITE & perms), "viewer must not hold any aviculture write permission"
