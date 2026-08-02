"""
Small Ruminant — Goat + Sheep (Modules 18/19, Milestone 1) — Foundation invariants.

Milestone 1 is pure database architecture: models, enumerated value contracts, the
shared species configuration, and RBAC wiring. The deterministic engines arrive in
later milestones, so these tests lock the foundation's contracts rather than any
calculation:

  * the enumerated value tuples are well-formed and internally consistent;
  * the species configuration parameterises goat vs sheep correctly (the core of
    the "build once, extend" design) without forking code;
  * the SmallRuminant aggregate exposes the identity / classification / lifecycle /
    pedigree surface the specification requires (Goat Doc 2 §5);
  * the Farm → Herd → Group → Pen/Pasture → Individual hierarchy is modelled
    (Goat Doc 1 §5, Doc 2 §3), with occupancy derived (never stored);
  * every foundation table is soft-delete capable and ``sr`` prefixed;
  * the Small Ruminant RBAC layer grants the right permissions to the right roles
    and never leaks write access to read-only roles (Goat Doc 7 §4-5).
"""

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models import small_ruminant as sr
from app.services import small_ruminant_species_config as cfg


# ── Enumerated value contracts ────────────────────────────────────────────────

def _no_duplicates(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def test_value_tuples_have_no_duplicates():
    for name in dir(sr):
        if name.endswith("_VALUES"):
            values = getattr(sr, name)
            assert _no_duplicates(values), f"{name} contains duplicates: {values}"


def test_species_discriminator_is_goat_and_sheep():
    assert sr.SPECIES_VALUES == ("goat", "sheep")
    assert cfg.SPECIES_VALUES == ("goat", "sheep")


def test_sex_union_covers_both_species_domains():
    # Goat dashboards count bucks/does; sheep count rams/ewes; wether is shared.
    for token in ("buck", "doe", "ram", "ewe", "wether", "unknown"):
        assert token in sr.SEX_VALUES


def test_lifecycle_stage_covers_the_life_cycle():
    # Goat Doc 1 §9 — birth → weaning → growing → breeding → maturity → retirement.
    for stage in ("newborn", "weaner", "grower", "breeding_adult",
                  "mature", "retired", "unknown"):
        assert stage in sr.LIFECYCLE_STAGE_VALUES


def test_status_models_terminal_outcomes():
    # Goat Doc 2 §2 — records never deleted; sale/transfer/death/culling leave herd.
    for status in ("active", "sold", "transferred", "deceased", "culled", "archived"):
        assert status in sr.STATUS_VALUES
    for terminal in sr.TERMINAL_STATUSES:
        assert terminal in sr.STATUS_VALUES
    assert "active" not in sr.TERMINAL_STATUSES


def test_reproductive_status_covers_female_cycle():
    # Goat Doc 2 §5 — reproductive status through the breeding + dairy cycle.
    for st in ("not_bred", "bred", "pregnant", "lactating", "dry", "unknown"):
        assert st in sr.REPRODUCTIVE_STATUS_VALUES


def test_purpose_covers_goat_and_sheep_production():
    # Goat (meat/dairy/fiber) + sheep (wool/meat/dairy) production purposes.
    for purpose in ("meat", "dairy", "fiber", "wool", "breeding",
                    "show", "replacement", "mixed"):
        assert purpose in sr.PURPOSE_VALUES


def test_birth_type_covers_multiples():
    # Goat Doc 2 §9 — singles, twins, triplets and larger are common in small ruminants.
    for bt in ("single", "twin", "triplet", "quadruplet", "unknown"):
        assert bt in sr.BIRTH_TYPE_VALUES


def test_pen_types_cover_housing_variants():
    # Goat Doc 2 §14 — barns, pens, paddocks, quarantine, isolation, kidding/lambing pens.
    for ptype in ("barn", "pen", "paddock", "quarantine", "isolation",
                  "kidding_pen", "lambing_pen"):
        assert ptype in sr.PEN_TYPE_VALUES


def test_group_types_cover_dynamic_categories():
    # Goat Doc 1 §8 — breeding, milking, dry, quarantine, isolation, sale groups.
    for gtype in ("breeding", "milking", "dry", "quarantine", "isolation", "sale"):
        assert gtype in sr.GROUP_TYPE_VALUES


def test_event_types_include_species_specific_births():
    # One shared timeline covers kidding (goat) and lambing (sheep) + shearing/milk.
    for etype in ("kidded", "lambed", "sheared", "milk_recorded", "weaned", "died", "culled"):
        assert etype in sr.EVENT_TYPE_VALUES


def test_document_types_include_pedigree_and_movement():
    # Goat Doc 2 §17, Doc 7 §16 (movement records for compliance).
    for dtype in ("pedigree_certificate", "health_certificate", "movement_record", "invoice"):
        assert dtype in sr.DOCUMENT_TYPE_VALUES


# ── Species configuration (the "build once, extend" contract) ─────────────────

def test_goat_and_sheep_configs_differ_where_they_should():
    goat = cfg.get_config("goat")
    sheep = cfg.get_config("sheep")
    assert goat["collective_noun"] == "herd" and sheep["collective_noun"] == "flock"
    assert goat["offspring_term"] == "kid" and sheep["offspring_term"] == "lamb"
    assert goat["birth_event"] == "kidding" and sheep["birth_event"] == "lambing"
    assert goat["male_term"] == "buck" and sheep["male_term"] == "ram"
    assert goat["female_term"] == "doe" and sheep["female_term"] == "ewe"


def test_allowed_sex_values_are_species_restricted():
    assert cfg.allowed_sex_values("goat") == ("buck", "doe", "wether", "unknown")
    assert cfg.allowed_sex_values("sheep") == ("ram", "ewe", "wether", "unknown")
    assert cfg.is_valid_sex("goat", "buck")
    assert not cfg.is_valid_sex("goat", "ram")   # a goat is never a ram
    assert cfg.is_valid_sex("sheep", "ewe")
    assert not cfg.is_valid_sex("sheep", "doe")  # a sheep is never a doe


def test_biological_role_maps_species_tokens():
    assert cfg.biological_role("buck") == "male"
    assert cfg.biological_role("ram") == "male"
    assert cfg.biological_role("wether") == "male"
    assert cfg.biological_role("doe") == "female"
    assert cfg.biological_role("ewe") == "female"
    assert cfg.biological_role("unknown") is None   # never guessed


def test_gestation_defaults_and_breed_override():
    assert cfg.default_gestation_days("goat") == 150
    assert cfg.default_gestation_days("sheep") == 147
    # A breed's recorded profile overrides the species default when valid.
    assert cfg.gestation_days("goat", {"gestation_days": 148}) == 148
    # Invalid / missing overrides fall back to the documented default (never guessed).
    assert cfg.gestation_days("goat", {"gestation_days": 0}) == 150
    assert cfg.gestation_days("sheep", None) == 147
    assert cfg.gestation_days("sheep", {"foo": "bar"}) == 147


def test_capability_flags_gate_species_workspaces():
    assert cfg.produces_milk("goat") and cfg.has_capability("goat", "dairy")
    assert cfg.produces_wool("sheep") and cfg.has_capability("sheep", "wool")
    assert not cfg.produces_wool("goat")


def test_unsupported_species_raises_and_is_reported():
    assert cfg.is_supported("goat") and cfg.is_supported("sheep")
    assert not cfg.is_supported("rabbit")
    assert not cfg.is_supported(None)
    try:
        cfg.get_config("rabbit")
    except ValueError as exc:
        assert "Unsupported" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("get_config must reject an unsupported species")


# ── Model surface ─────────────────────────────────────────────────────────────

def test_animal_table_and_core_columns():
    cols = set(sr.SmallRuminant.__table__.columns.keys())
    # Discriminator — the heart of the shared schema.
    assert "species" in cols
    # Identity (Goat Doc 1 §6, Doc 2 §5) — multiple simultaneous identifiers.
    for col in ("internal_ref", "name", "ear_tag", "tattoo", "qr_code", "rfid", "visual_id"):
        assert col in cols, f"SmallRuminant missing identity column {col}"
    # Classification
    for col in ("breed_id", "bloodline_id", "variety", "color", "sex", "purpose",
                "horn_status", "registration_status"):
        assert col in cols, f"SmallRuminant missing classification column {col}"
    # Biology & lifecycle
    for col in ("date_of_birth", "birth_type", "birth_weight_kg", "current_weight_kg",
                "lifecycle_stage", "status", "reproductive_status", "fertility_status"):
        assert col in cols, f"SmallRuminant missing biology column {col}"
    # Deterministic pedigree links (Goat Doc 2 §19) — unknown ancestry stays NULL.
    assert "sire_id" in cols and "dam_id" in cols
    # Location (management + physical) + farm scoping (organisation isolation).
    for col in ("herd_id", "group_id", "pen_id", "pasture_id", "farm_id"):
        assert col in cols


def test_animal_identity_is_unique_per_farm():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in sr.SmallRuminant.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("farm_id", "internal_ref") in uniques
    assert ("farm_id", "ear_tag") in uniques


def test_grouping_and_housing_hierarchy():
    # Goat Doc 2 §3 — Herd → Group; physical Pen / Pasture.
    assert "herd_id" in sr.SmallRuminantGroup.__table__.columns.keys()
    # Species-scoping is on animal-and-genetics tables...
    for model in (sr.SmallRuminantBreed, sr.SmallRuminantBloodline,
                  sr.SmallRuminantHerd, sr.SmallRuminantGroup, sr.SmallRuminant):
        assert "species" in model.__table__.columns.keys()
    # ...but physical infrastructure is species-neutral (shareable across species).
    for model in (sr.SmallRuminantPen, sr.SmallRuminantPasture):
        assert "species" not in model.__table__.columns.keys()
    # Occupancy is derived, never stored — pens carry capacity only.
    pen_cols = set(sr.SmallRuminantPen.__table__.columns.keys())
    assert "capacity" in pen_cols
    assert "occupancy" not in pen_cols


def test_is_in_herd_property():
    a = sr.SmallRuminant(species="goat", internal_ref="G-1", status="active")
    assert a.is_in_herd is True
    for terminal in ("sold", "transferred", "deceased", "culled", "archived"):
        a.status = terminal
        assert a.is_in_herd is False


def test_all_foundation_tables_are_soft_delete_capable_and_prefixed():
    models = [
        sr.SmallRuminantBreed, sr.SmallRuminantBloodline, sr.SmallRuminantHerd,
        sr.SmallRuminantGroup, sr.SmallRuminantPen, sr.SmallRuminantPasture,
        sr.SmallRuminant, sr.SmallRuminantEvent, sr.SmallRuminantMedia,
        sr.SmallRuminantDocument,
    ]
    for model in models:
        assert "deleted_at" in model.__table__.columns.keys()
        assert "metadata" in model.__table__.columns.keys()
        assert model.__tablename__ == "sr_animal" or model.__tablename__.startswith("sr_")


# ── RBAC wiring (Goat Doc 7 §4-5) ─────────────────────────────────────────────

_SR_WRITE = {
    Permission.SR_CREATE, Permission.SR_EDIT, Permission.SR_ARCHIVE,
    Permission.SR_TRANSACT, Permission.SR_HOUSING_MANAGE, Permission.SR_CATALOG_MANAGE,
    Permission.SR_BREEDING_MANAGE, Permission.SR_PEDIGREE_EDIT, Permission.SR_HEALTH_LOG,
    Permission.SR_WEIGHT_LOG, Permission.SR_FEED_RECORD, Permission.SR_DAIRY_RECORD,
    Permission.SR_WOOL_RECORD, Permission.SR_SALES_RECORD, Permission.SR_REPORT_EXPORT,
    Permission.SR_GROWTH_EDIT, Permission.SR_AUTOMATION_MANAGE,
}
_SR_VIEW = {
    Permission.SR_VIEW, Permission.SR_HOUSING_VIEW, Permission.SR_CATALOG_VIEW,
    Permission.SR_BREEDING_VIEW, Permission.SR_PEDIGREE_VIEW, Permission.SR_HEALTH_VIEW,
    Permission.SR_FEED_VIEW, Permission.SR_DAIRY_VIEW, Permission.SR_WOOL_VIEW,
    Permission.SR_SALES_VIEW, Permission.SR_FINANCE_VIEW, Permission.SR_REPORT_VIEW,
    Permission.SR_GROWTH_VIEW, Permission.SR_AUTOMATION_VIEW,
}


def test_owner_and_manager_have_full_control():
    for role in ("farm_owner", "farm_manager", "enterprise_owner"):
        perms = ROLE_PERMISSIONS[role]
        assert _SR_WRITE <= perms, f"{role} missing small-ruminant write perms"
        assert _SR_VIEW <= perms


def test_super_admin_has_all_permissions():
    perms = ROLE_PERMISSIONS["super_admin"]
    assert _SR_WRITE <= perms and _SR_VIEW <= perms


def test_worker_operates_but_cannot_transact_or_touch_strategy():
    perms = ROLE_PERMISSIONS["farm_worker"]
    # Daily operational work across both species.
    for p in (Permission.SR_CREATE, Permission.SR_EDIT, Permission.SR_BREEDING_MANAGE,
              Permission.SR_HEALTH_LOG, Permission.SR_WEIGHT_LOG, Permission.SR_FEED_RECORD,
              Permission.SR_DAIRY_RECORD, Permission.SR_WOOL_RECORD):
        assert p in perms
    # Archival, transactions, catalog/housing management are owner/manager concerns.
    for p in (Permission.SR_ARCHIVE, Permission.SR_TRANSACT, Permission.SR_CATALOG_MANAGE,
              Permission.SR_HOUSING_MANAGE, Permission.SR_SALES_RECORD, Permission.SR_GROWTH_EDIT):
        assert p not in perms
    # Strategic/financial views are manager/owner concerns (Goat Doc 7 §5, Doc 4).
    for p in (Permission.SR_FINANCE_VIEW, Permission.SR_REPORT_VIEW,
              Permission.SR_GROWTH_VIEW, Permission.SR_SALES_VIEW):
        assert p not in perms


def test_vet_has_read_plus_clinical_write_only():
    perms = ROLE_PERMISSIONS["vet_consultant"]
    assert _SR_VIEW <= perms
    assert Permission.SR_HEALTH_LOG in perms
    # No non-clinical write access.
    assert not ((_SR_WRITE - {Permission.SR_HEALTH_LOG}) & perms)


def test_viewer_is_read_only():
    perms = ROLE_PERMISSIONS["viewer"]
    assert _SR_VIEW <= perms
    assert not (_SR_WRITE & perms), "viewer must not hold any small-ruminant write permission"
