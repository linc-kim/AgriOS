"""
Greena — Small Ruminant species configuration (Modules 18 Goat + 19 Sheep).

The Small Ruminant subsystem is built **once** and shared by two species — goat
and sheep — instead of duplicating a parallel module per animal (the directive's
core principle). Everything that differs between a goat and a sheep is *data*, not
forked code: the differences live here as pure, declarative configuration that the
shared ``sr_*`` schema, services and deterministic engines read at runtime.

This module is PURE (no I/O, no DB, no framework imports) so it can be imported by
migrations, models, services, engines and tests alike, and unit-tested trivially.

What lives here
    * the canonical vocabulary each species uses for sex, its offspring, its birth
      event and its adult female/male (buck/doe · ram/ewe), so the same records
      read naturally in each workspace;
    * biological defaults — chiefly gestation length — used by the breeding engine
      as a **forecast** basis (goat ~150d, sheep ~147d), always overridable per
      breed via ``sr_breed.profile['gestation_days']`` (a recorded reference), so
      no value is ever hardcoded beyond a documented default;
    * capability flags (``dairy`` for goats, ``wool`` for sheep) that gate the
      species-specific workspaces and services without branching business logic.

Nothing here performs a calculation that belongs to a deterministic engine — it
only supplies the per-species constants those engines are parameterised by.
"""

from __future__ import annotations

from typing import Any

# ── Species discriminator ─────────────────────────────────────────────────────
# The single ``species`` column on every animal-scoped ``sr_*`` table. Two rows in
# the platform ``species_profiles`` extensibility engine (``goat``/``sheep``, added
# in Migration 072) surface these as two launcher workspaces over one schema.
SPECIES_GOAT = "goat"
SPECIES_SHEEP = "sheep"
SPECIES_VALUES: tuple[str, ...] = (SPECIES_GOAT, SPECIES_SHEEP)

# Canonical sex vocabulary. The column stores a species-appropriate token; the
# config restricts which tokens are valid for each species and maps them to a
# biological role for the pedigree/breeding engines (buck/ram → male,
# doe/ewe → female, wether → castrated male). "wether" is shared by both species.
SEX_MALE = "buck"          # goat intact male
SEX_FEMALE = "doe"         # goat intact female
SEX_RAM = "ram"            # sheep intact male
SEX_EWE = "ewe"            # sheep intact female
SEX_WETHER = "wether"      # castrated male (both species)
SEX_UNKNOWN = "unknown"
# Union of every valid token across species (validated per-species below).
SEX_VALUES: tuple[str, ...] = (SEX_MALE, SEX_FEMALE, SEX_RAM, SEX_EWE, SEX_WETHER, SEX_UNKNOWN)

# Biological role a sex token maps to (species-agnostic; used by the genetics /
# breeding engines that reason in male/female terms).
BIOLOGICAL_MALE = "male"
BIOLOGICAL_FEMALE = "female"


# ── Per-species configuration ─────────────────────────────────────────────────
# Default gestation lengths are widely published averages, used only as the
# forecast basis when a breed carries no override. Goat ≈ 150 days, sheep ≈ 147.
_CONFIG: dict[str, dict[str, Any]] = {
    SPECIES_GOAT: {
        "species": SPECIES_GOAT,
        "display_name": "Goats",
        "display_name_singular": "Goat",
        "collective_noun": "herd",           # goats form a HERD
        "offspring_term": "kid",             # a baby goat is a kid
        "offspring_term_plural": "kids",
        "birth_event": "kidding",            # goats KID
        "female_term": SEX_FEMALE,           # doe
        "male_term": SEX_MALE,               # buck
        "castrate_term": SEX_WETHER,         # wether
        "sex_values": (SEX_MALE, SEX_FEMALE, SEX_WETHER, SEX_UNKNOWN),
        "default_gestation_days": 150,
        # Capabilities gate species-specific workspaces/services (M6/M7).
        "capabilities": ("meat", "dairy", "fiber", "breeding"),
        "produces_milk": True,
        "produces_wool": False,
        "icon": "🐐",
        "accent_hex": "#B45309",
    },
    SPECIES_SHEEP: {
        "species": SPECIES_SHEEP,
        "display_name": "Sheep",
        "display_name_singular": "Sheep",
        "collective_noun": "flock",          # sheep form a FLOCK
        "offspring_term": "lamb",            # a baby sheep is a lamb
        "offspring_term_plural": "lambs",
        "birth_event": "lambing",            # sheep LAMB
        "female_term": SEX_EWE,              # ewe
        "male_term": SEX_RAM,                # ram
        "castrate_term": SEX_WETHER,         # wether
        "sex_values": (SEX_RAM, SEX_EWE, SEX_WETHER, SEX_UNKNOWN),
        "default_gestation_days": 147,
        "capabilities": ("meat", "wool", "dairy", "fiber", "breeding"),
        "produces_milk": True,               # dairy sheep exist (e.g. East Friesian)
        "produces_wool": True,
        "icon": "🐑",
        "accent_hex": "#6D28D9",
    },
}

# Map every sex token to its biological role (for the genetics/breeding engines).
_SEX_TO_ROLE: dict[str, str] = {
    SEX_MALE: BIOLOGICAL_MALE,
    SEX_RAM: BIOLOGICAL_MALE,
    SEX_WETHER: BIOLOGICAL_MALE,   # castrated male — still biologically male ancestry
    SEX_FEMALE: BIOLOGICAL_FEMALE,
    SEX_EWE: BIOLOGICAL_FEMALE,
}


# ── Accessors (pure) ──────────────────────────────────────────────────────────

def is_supported(species: str | None) -> bool:
    """True if ``species`` is a Small Ruminant the subsystem manages."""
    return species in _CONFIG


def get_config(species: str) -> dict[str, Any]:
    """Return the immutable configuration dict for a species.

    Raises ``ValueError`` for an unsupported species — callers must validate the
    discriminator at the schema/service boundary, never invent a species.
    """
    try:
        return _CONFIG[species]
    except KeyError as exc:  # pragma: no cover - guarded at the service layer
        raise ValueError(
            f"Unsupported small-ruminant species {species!r}; expected one of {SPECIES_VALUES}"
        ) from exc


def allowed_sex_values(species: str) -> tuple[str, ...]:
    """The sex tokens valid for a species (goat: buck/doe/wether; sheep: ram/ewe/wether)."""
    return tuple(get_config(species)["sex_values"])


def is_valid_sex(species: str, sex: str) -> bool:
    """True if ``sex`` is a valid token for ``species``."""
    return sex in allowed_sex_values(species)


def biological_role(sex: str) -> str | None:
    """Map a sex token to ``male`` / ``female`` (``None`` when unknown).

    Used by the pedigree and breeding engines, which reason in biological terms
    regardless of the species' domain vocabulary. Never guesses — an unknown or
    unmapped token returns ``None``.
    """
    return _SEX_TO_ROLE.get(sex)


def offspring_term(species: str, *, plural: bool = False) -> str:
    """The word for this species' young: kid(s) / lamb(s)."""
    cfg = get_config(species)
    return cfg["offspring_term_plural"] if plural else cfg["offspring_term"]


def birth_event(species: str) -> str:
    """The word for this species' parturition event: kidding / lambing."""
    return get_config(species)["birth_event"]


def collective_noun(species: str) -> str:
    """The word for a managed grouping: herd (goat) / flock (sheep)."""
    return get_config(species)["collective_noun"]


def default_gestation_days(species: str) -> int:
    """The published average gestation length used as the forecast default."""
    return int(get_config(species)["default_gestation_days"])


def gestation_days(species: str, breed_profile: dict[str, Any] | None = None) -> int:
    """Resolve gestation length for a forecast.

    A breed's recorded ``profile['gestation_days']`` (reference data) overrides the
    species default when present and positive; otherwise the documented species
    average is used. The result is only ever a **forecast** basis — never a
    recorded fact about a specific pregnancy.
    """
    if breed_profile:
        override = breed_profile.get("gestation_days")
        try:
            if override is not None and int(override) > 0:
                return int(override)
        except (TypeError, ValueError):
            pass
    return default_gestation_days(species)


def has_capability(species: str, capability: str) -> bool:
    """True if the species supports a capability (e.g. ``dairy`` goat, ``wool`` sheep)."""
    return capability in get_config(species)["capabilities"]


def produces_milk(species: str) -> bool:
    """True for species whose dairy (milk/lactation) workspace applies (M6)."""
    return bool(get_config(species)["produces_milk"])


def produces_wool(species: str) -> bool:
    """True for species whose wool (shearing/fleece) workspace applies (M7)."""
    return bool(get_config(species)["produces_wool"])
