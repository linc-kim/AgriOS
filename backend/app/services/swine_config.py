"""
Greena — Swine configuration (Module 20, Pig Framework).

The Swine Framework is a **single-species** livestock module (unlike the unified
Small Ruminant subsystem, which carries a goat/sheep discriminator). Even so, the
pig's domain vocabulary, breeding biology and lifecycle progression are kept here
as pure, declarative configuration rather than being scattered as literals across
the ``swine_*`` schema, services and deterministic engines. Keeping them in one
place mirrors ``small_ruminant_species_config`` and gives every layer a single
source of truth for "what a pig is".

This module is PURE (no I/O, no DB, no framework imports) so it can be imported by
migrations, models, services, engines and tests alike, and unit-tested trivially.

What lives here
    * the canonical **sex / class vocabulary** — boar, sow, gilt, barrow — and each
      token's biological role, so the pedigree/breeding engines can reason in
      male/female terms without forking swine-specific logic. A *barrow* (castrated
      male) is biologically male ancestry but is NEVER a valid sire — exactly the
      role a *wether* plays for small ruminants;
    * the **production-stage progression** (piglet → weaner → nursery → grower →
      finisher, with breeding/replacement/cull branches) used to validate lifecycle
      transitions (Swine Doc 3 §4 "production stages must follow valid progression");
    * the default **gestation length** (~114 days — the classic "3 months, 3 weeks,
      3 days") used by the breeding engine as a *forecast* basis, always overridable
      per breed via ``swine_breed.profile['gestation_days']`` so no value is ever
      hardcoded beyond a documented default.

Nothing here performs a calculation that belongs to a deterministic engine — it
only supplies the constants those engines are parameterised by.
"""

from __future__ import annotations

from typing import Any

# ── Module / species identity ─────────────────────────────────────────────────
# One species. The key registers a single launcher workspace in the platform
# ``species_profiles`` extensibility engine (Migration 079, row …0010).
SPECIES_SWINE = "swine"

# ── Sex / class vocabulary (Swine Doc 2 §4, §7) ───────────────────────────────
# Pigs are classed by a single token that captures both sex and breeding role,
# the way the industry speaks: an intact male is a *boar*, a castrated male a
# *barrow*, an adult female that has farrowed a *sow*, a young unbred female a
# *gilt*. The gilt→sow transition is a reproductive milestone (first farrowing),
# resolved by the breeding milestone — never guessed here.
SEX_BOAR = "boar"          # intact male (a valid sire)
SEX_SOW = "sow"            # adult female that has farrowed
SEX_GILT = "gilt"          # young female, not yet farrowed
SEX_BARROW = "barrow"      # castrated male — biologically male, NEVER a sire
SEX_UNKNOWN = "unknown"
SEX_VALUES: tuple[str, ...] = (SEX_BOAR, SEX_SOW, SEX_GILT, SEX_BARROW, SEX_UNKNOWN)

# Biological role a class token maps to (used by the genetics / breeding engines,
# which reason in male/female terms regardless of domain vocabulary).
BIOLOGICAL_MALE = "male"
BIOLOGICAL_FEMALE = "female"
_SEX_TO_ROLE: dict[str, str] = {
    SEX_BOAR: BIOLOGICAL_MALE,
    SEX_BARROW: BIOLOGICAL_MALE,   # castrated male — still biologically male ancestry
    SEX_SOW: BIOLOGICAL_FEMALE,
    SEX_GILT: BIOLOGICAL_FEMALE,
}
# The intact male term is the only one eligible to sire (barrow is excluded even
# though its biological role is male — the same rule wethers follow for goats).
MALE_TERM = SEX_BOAR
CASTRATE_TERM = SEX_BARROW
# Both female classes can be a dam; a gilt becomes a sow at first farrowing.
FEMALE_TERMS: tuple[str, ...] = (SEX_SOW, SEX_GILT)

# ── Production stage progression (Swine Doc 1 §5-6, Doc 3 §4) ──────────────────
# The commercial pig lifecycle. "nursery" is the post-weaning phase that precedes
# the grower barn; some operations fold it into "weaner", so the progression
# tolerates either path. Breeding / replacement / cull are terminal branches an
# animal is *assigned* to rather than flowing through linearly.
STAGE_PIGLET = "piglet"          # unweaned, on the sow
STAGE_WEANER = "weaner"          # just weaned
STAGE_NURSERY = "nursery"        # nursery/post-weaning phase
STAGE_GROWER = "grower"          # growing herd
STAGE_FINISHER = "finisher"      # finishing to market weight
STAGE_BREEDING = "breeding"      # kept for the breeding herd (boar/sow)
STAGE_REPLACEMENT = "replacement"  # replacement gilt in development
STAGE_CULL = "cull"              # designated for culling
STAGE_RETIRED = "retired"        # retired breeding stock
STAGE_UNKNOWN = "unknown"
PRODUCTION_STAGE_VALUES: tuple[str, ...] = (
    STAGE_PIGLET, STAGE_WEANER, STAGE_NURSERY, STAGE_GROWER, STAGE_FINISHER,
    STAGE_BREEDING, STAGE_REPLACEMENT, STAGE_CULL, STAGE_RETIRED, STAGE_UNKNOWN,
)

# The linear market path a growing pig follows. Forward progression along this
# ordering is "normal"; the breeding engine / lifecycle service uses it to flag an
# invalid backwards jump (e.g. finisher → piglet). Branch stages are reachable
# from any point and are not part of the linear order.
_LINEAR_STAGES: tuple[str, ...] = (
    STAGE_PIGLET, STAGE_WEANER, STAGE_NURSERY, STAGE_GROWER, STAGE_FINISHER,
)
_BRANCH_STAGES: tuple[str, ...] = (
    STAGE_BREEDING, STAGE_REPLACEMENT, STAGE_CULL, STAGE_RETIRED,
)

# ── Biology defaults (Swine Doc 2 §7, Doc 3 §9) ───────────────────────────────
# The published pig gestation average — "3 months, 3 weeks and 3 days" ≈ 114 days.
# Used only as the forecast default when a breed carries no override.
DEFAULT_GESTATION_DAYS = 114

# ── Growth / market targets (Swine Doc 3 §16, Doc 6 §9) — Milestone 7 ──────────
# Documented defaults for the market-readiness assessment, ALWAYS overridable per
# breed via ``swine_breed.profile`` (``target_market_weight_kg`` /
# ``target_market_age_days``) or per call — never hardcoded thresholds. A typical
# finisher markets around 100–120 kg at roughly 24–26 weeks.
DEFAULT_MARKET_WEIGHT_KG = 110.0
DEFAULT_MARKET_AGE_DAYS = 180
# Fraction of target weight at/above which a pig is "approaching" market.
MARKET_APPROACHING_FRACTION = 0.9
# Body condition score scale for pigs (1 emaciated … 5 obese).
BODY_CONDITION_MIN = 1
BODY_CONDITION_MAX = 5


def market_targets(breed_profile: dict[str, Any] | None = None,
                   *, target_weight_kg: float | None = None,
                   target_age_days: int | None = None) -> dict[str, Any]:
    """Resolve market-readiness targets: explicit call value → breed profile →
    documented species default. Returns ``{"target_weight_kg", "target_age_days",
    "source"}`` so the assessment can state where each threshold came from."""
    weight_source = "default"
    age_source = "default"
    weight = DEFAULT_MARKET_WEIGHT_KG
    age = DEFAULT_MARKET_AGE_DAYS
    if breed_profile:
        bw = breed_profile.get("target_market_weight_kg")
        ba = breed_profile.get("target_market_age_days")
        try:
            if bw is not None and float(bw) > 0:
                weight, weight_source = float(bw), "breed"
        except (TypeError, ValueError):
            pass
        try:
            if ba is not None and int(ba) > 0:
                age, age_source = int(ba), "breed"
        except (TypeError, ValueError):
            pass
    if target_weight_kg is not None and target_weight_kg > 0:
        weight, weight_source = float(target_weight_kg), "override"
    if target_age_days is not None and target_age_days > 0:
        age, age_source = int(target_age_days), "override"
    return {"target_weight_kg": weight, "target_age_days": age,
            "weight_source": weight_source, "age_source": age_source}

# Domain nouns for natural-reading records/UX (kept here so services/engines and
# reports never hardcode them).
OFFSPRING_TERM = "piglet"
OFFSPRING_TERM_PLURAL = "piglets"
BIRTH_EVENT = "farrowing"
COLLECTIVE_NOUN = "herd"
DISPLAY_NAME = "Pigs"
DISPLAY_NAME_SINGULAR = "Pig"
ICON = "🐖"
ACCENT_HEX = "#BE185D"


# ── Accessors (pure) ──────────────────────────────────────────────────────────

def is_valid_sex(sex: str | None) -> bool:
    """True if ``sex`` is a valid swine class token."""
    return sex in SEX_VALUES


def biological_role(sex: str | None) -> str | None:
    """Map a class token to ``male`` / ``female`` (``None`` when unknown).

    Used by the pedigree and breeding engines. Never guesses — an unknown or
    unmapped token (including ``unknown``) returns ``None``.
    """
    return _SEX_TO_ROLE.get(sex)  # type: ignore[arg-type]


def is_intact_male(sex: str | None) -> bool:
    """True only for a boar — the sole class eligible to sire (Swine Doc 3 §7).

    A barrow is biologically male but castrated, so it is excluded here exactly as
    a wether is for small ruminants.
    """
    return sex == MALE_TERM


def is_breeding_female(sex: str | None) -> bool:
    """True for a sow or a gilt — the classes eligible to be a dam."""
    return sex in FEMALE_TERMS


def is_valid_stage(stage: str | None) -> bool:
    """True if ``stage`` is a recognised production stage."""
    return stage in PRODUCTION_STAGE_VALUES


def is_linear_stage(stage: str | None) -> bool:
    """True if ``stage`` is part of the linear market progression (not a branch)."""
    return stage in _LINEAR_STAGES


def stage_rank(stage: str | None) -> int | None:
    """Ordinal position of a stage on the linear market path (0-based).

    Returns ``None`` for branch stages (breeding/replacement/cull/retired) and
    unknown/None — those are not comparable along the linear path.
    """
    try:
        return _LINEAR_STAGES.index(stage)  # type: ignore[arg-type]
    except ValueError:
        return None


def is_forward_stage_transition(current: str | None, target: str | None) -> bool:
    """True if moving ``current`` → ``target`` is a valid non-backwards transition.

    Movement onto or off a branch stage (breeding/replacement/cull/retired) is
    always allowed — an animal can be assigned to the breeding herd or marked for
    culling from any point. Along the linear market path a pig may hold its stage
    or advance, but never regress (finisher → grower is rejected). Transitions
    involving an unknown stage are permitted so records can be corrected.
    """
    if current is None or target is None or current == STAGE_UNKNOWN or target == STAGE_UNKNOWN:
        return True
    if current in _BRANCH_STAGES or target in _BRANCH_STAGES:
        return True
    cur_rank, tgt_rank = stage_rank(current), stage_rank(target)
    if cur_rank is None or tgt_rank is None:
        return True
    return tgt_rank >= cur_rank


def gestation_days(breed_profile: dict[str, Any] | None = None) -> int:
    """Resolve gestation length for a farrowing forecast.

    A breed's recorded ``profile['gestation_days']`` (reference data) overrides the
    species default when present and positive; otherwise the documented ~114-day
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
    return DEFAULT_GESTATION_DAYS


def config() -> dict[str, Any]:
    """Return the immutable descriptor for the swine workspace (UX / registration)."""
    return {
        "species": SPECIES_SWINE,
        "display_name": DISPLAY_NAME,
        "display_name_singular": DISPLAY_NAME_SINGULAR,
        "collective_noun": COLLECTIVE_NOUN,
        "offspring_term": OFFSPRING_TERM,
        "offspring_term_plural": OFFSPRING_TERM_PLURAL,
        "birth_event": BIRTH_EVENT,
        "male_term": MALE_TERM,
        "castrate_term": CASTRATE_TERM,
        "female_terms": FEMALE_TERMS,
        "sex_values": SEX_VALUES,
        "default_gestation_days": DEFAULT_GESTATION_DAYS,
        "icon": ICON,
        "accent_hex": ACCENT_HEX,
    }
