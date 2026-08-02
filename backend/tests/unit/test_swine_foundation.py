"""
Swine — Pig Framework (Module 20, Milestone 1) — Foundation invariants.

Milestone 1 is pure database architecture: models, enumerated value contracts, the
swine configuration, and RBAC wiring. The deterministic engines arrive in later
milestones, so these tests lock the foundation's contracts rather than any
calculation:

  * the enumerated value tuples are well-formed and internally consistent;
  * the swine configuration parameterises the pig's sex/class vocabulary, biological
    roles, gestation default and production-stage progression correctly (Swine Doc 2
    §4, §7; Doc 3 §4, §9);
  * a barrow is biological-male ancestry but NEVER a valid sire (the wether rule);
  * the SwinePig aggregate exposes the identity / classification / lifecycle /
    pedigree surface the specification requires (Swine Doc 2 §4);
  * the Farm → Herd → Group → Pen → Individual hierarchy is modelled with occupancy
    derived (never stored), and pigs are housed (no pasture table);
  * every foundation table is soft-delete capable and ``swine`` prefixed;
  * the Swine RBAC layer grants the right permissions to the right roles and never
    leaks write access to read-only roles (Swine Doc 11 §11).
"""

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models import swine as sw
from app.services import swine_config as cfg


# ── Enumerated value contracts ────────────────────────────────────────────────

def _no_duplicates(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def test_value_tuples_have_no_duplicates():
    for name in dir(sw):
        if name.endswith("_VALUES"):
            values = getattr(sw, name)
            assert _no_duplicates(values), f"{name} contains duplicates: {values}"


def test_sex_vocabulary_is_boar_sow_gilt_barrow():
    for token in ("boar", "sow", "gilt", "barrow", "unknown"):
        assert token in sw.SEX_VALUES
    assert sw.SEX_VALUES == cfg.SEX_VALUES


def test_production_stage_covers_the_lifecycle():
    # Swine Doc 1 §5-6 — piglet → weaner → nursery → grower → finisher, plus the
    # breeding / replacement / cull / retired branches.
    for stage in ("piglet", "weaner", "nursery", "grower", "finisher",
                  "breeding", "replacement", "cull", "retired", "unknown"):
        assert stage in sw.PRODUCTION_STAGE_VALUES
    assert sw.PRODUCTION_STAGE_VALUES == cfg.PRODUCTION_STAGE_VALUES


def test_status_models_terminal_outcomes():
    # Swine Doc 2 §4, §19 — records never deleted; sale/transfer/death/culling leave herd.
    for status in ("active", "sold", "transferred", "deceased", "culled", "archived"):
        assert status in sw.STATUS_VALUES
    for terminal in sw.TERMINAL_STATUSES:
        assert terminal in sw.STATUS_VALUES
    assert "active" not in sw.TERMINAL_STATUSES


def test_reproductive_status_covers_sow_cycle():
    # Swine Doc 2 §4, §7 — the sow/gilt cycle through breeding, gestation, lactation.
    for st in ("not_bred", "bred", "pregnant", "lactating", "dry", "weaned", "unknown"):
        assert st in sw.REPRODUCTIVE_STATUS_VALUES


def test_biosecurity_status_is_first_class():
    # Swine Doc 2 §6 — biosecurity is a recorded pen assessment, never inferred.
    for st in ("secure", "monitored", "restricted", "quarantine", "unknown"):
        assert st in sw.BIOSECURITY_STATUS_VALUES


def test_event_types_cover_reproductive_lifecycle():
    # Swine Doc 2 §16, §18 — append-only timeline covers the swine-specific events
    # so later milestones need no schema change to swine_event.
    for ev in ("created", "moved", "bred", "inseminated", "pregnancy_checked",
               "farrowed", "fostered", "weaned", "weight_recorded", "note"):
        assert ev in sw.EVENT_TYPE_VALUES


# ── Swine configuration (build-once vocabulary + biology) ─────────────────────

def test_config_maps_biological_roles():
    assert cfg.biological_role("boar") == cfg.BIOLOGICAL_MALE
    assert cfg.biological_role("barrow") == cfg.BIOLOGICAL_MALE
    assert cfg.biological_role("sow") == cfg.BIOLOGICAL_FEMALE
    assert cfg.biological_role("gilt") == cfg.BIOLOGICAL_FEMALE
    # Never guesses.
    assert cfg.biological_role("unknown") is None
    assert cfg.biological_role(None) is None


def test_barrow_is_male_but_never_a_sire():
    # The wether rule: a barrow is biologically male ancestry yet ineligible to sire.
    assert cfg.biological_role("barrow") == cfg.BIOLOGICAL_MALE
    assert cfg.is_intact_male("boar") is True
    assert cfg.is_intact_male("barrow") is False


def test_breeding_females_are_sow_and_gilt():
    assert cfg.is_breeding_female("sow") is True
    assert cfg.is_breeding_female("gilt") is True
    assert cfg.is_breeding_female("boar") is False
    assert cfg.is_breeding_female("barrow") is False


def test_gestation_default_is_114_days_and_breed_overridable():
    assert cfg.DEFAULT_GESTATION_DAYS == 114
    assert cfg.gestation_days() == 114
    assert cfg.gestation_days({"gestation_days": 116}) == 116
    # Invalid / non-positive overrides fall back to the default.
    assert cfg.gestation_days({"gestation_days": 0}) == 114
    assert cfg.gestation_days({"gestation_days": "bad"}) == 114
    assert cfg.gestation_days({}) == 114


def test_stage_progression_forbids_backwards_linear_jumps():
    # Along the market path a pig holds or advances, never regresses (Swine Doc 3 §4).
    assert cfg.is_forward_stage_transition("piglet", "weaner") is True
    assert cfg.is_forward_stage_transition("grower", "finisher") is True
    assert cfg.is_forward_stage_transition("weaner", "weaner") is True
    assert cfg.is_forward_stage_transition("finisher", "grower") is False
    assert cfg.is_forward_stage_transition("grower", "piglet") is False


def test_stage_progression_allows_branch_and_unknown_transitions():
    # Branch stages (breeding/cull/…) are reachable from anywhere; unknown is tolerated.
    assert cfg.is_forward_stage_transition("finisher", "cull") is True
    assert cfg.is_forward_stage_transition("grower", "breeding") is True
    assert cfg.is_forward_stage_transition("breeding", "grower") is True
    assert cfg.is_forward_stage_transition("unknown", "piglet") is True
    assert cfg.is_forward_stage_transition(None, "grower") is True


# ── Aggregate surface & housing hierarchy ─────────────────────────────────────

def test_pig_aggregate_exposes_required_surface():
    # Swine Doc 2 §4 — identity, classification, lifecycle, pedigree.
    cols = set(sw.SwinePig.__table__.columns.keys())
    for required in (
        "farm_id", "internal_ref", "ear_tag", "sex", "production_stage", "status",
        "reproductive_status", "market_status", "parity", "sire_id", "dam_id",
        "breed_id", "bloodline_id", "herd_id", "group_id", "pen_id",
        "current_weight_kg", "birth_weight_kg",
    ):
        assert required in cols, f"SwinePig missing {required}"


def test_ear_tag_and_internal_ref_are_unique_per_farm():
    constraints = {c.name for c in sw.SwinePig.__table__.constraints}
    assert "uq_swine_pig_farm_internal_ref" in constraints
    assert "uq_swine_pig_farm_ear_tag" in constraints


def test_pen_carries_capacity_and_biosecurity_but_not_occupancy():
    cols = set(sw.SwinePen.__table__.columns.keys())
    assert "capacity" in cols
    assert "biosecurity_status" in cols
    assert "building" in cols
    # Occupancy is DERIVED, never stored.
    assert "occupancy" not in cols
    assert "animal_count" not in cols


def test_pigs_are_housed_no_pasture_table():
    # Pigs are a housed species — the small-ruminant pasture concept does not apply.
    assert not hasattr(sw, "SwinePasture")


def test_all_foundation_tables_are_swine_prefixed_and_soft_deletable():
    models = [
        sw.SwineBreed, sw.SwineBloodline, sw.SwineHerd, sw.SwineGroup,
        sw.SwinePen, sw.SwinePig, sw.SwineEvent, sw.SwineMedia, sw.SwineDocument,
    ]
    for model in models:
        assert model.__tablename__.startswith("swine_"), model.__tablename__
        assert "deleted_at" in model.__table__.columns.keys(), model.__tablename__


# ── RBAC wiring (Swine Doc 11 §11) ────────────────────────────────────────────

def test_owner_and_manager_have_full_swine_control():
    for role in ("farm_owner", "farm_manager", "enterprise_owner"):
        perms = ROLE_PERMISSIONS[role]
        assert Permission.SWINE_CREATE in perms
        assert Permission.SWINE_TRANSACT in perms
        assert Permission.SWINE_FINANCE_VIEW in perms
        assert Permission.SWINE_REPORT_EXPORT in perms


def test_worker_operates_but_cannot_transact_or_see_finance():
    perms = ROLE_PERMISSIONS["farm_worker"]
    assert Permission.SWINE_CREATE in perms
    assert Permission.SWINE_HEALTH_LOG in perms
    assert Permission.SWINE_WEIGHT_LOG in perms
    # No archive/transact, no strategic finance/report/growth views.
    assert Permission.SWINE_ARCHIVE not in perms
    assert Permission.SWINE_TRANSACT not in perms
    assert Permission.SWINE_FINANCE_VIEW not in perms
    assert Permission.SWINE_REPORT_VIEW not in perms


def test_vet_gets_clinical_write_only():
    perms = ROLE_PERMISSIONS["vet_consultant"]
    assert Permission.SWINE_HEALTH_LOG in perms
    assert Permission.SWINE_VIEW in perms
    # Vets do not create/transact/manage housing.
    assert Permission.SWINE_CREATE not in perms
    assert Permission.SWINE_TRANSACT not in perms
    assert Permission.SWINE_HOUSING_MANAGE not in perms


def test_viewer_is_read_only():
    perms = ROLE_PERMISSIONS["viewer"]
    assert Permission.SWINE_VIEW in perms
    assert Permission.SWINE_FINANCE_VIEW in perms
    # No write permission of any kind.
    for write in (
        Permission.SWINE_CREATE, Permission.SWINE_EDIT, Permission.SWINE_HEALTH_LOG,
        Permission.SWINE_BREEDING_MANAGE, Permission.SWINE_TRANSACT,
    ):
        assert write not in perms
