"""
Greena — BSF Production Engine (Module 16, Part 2)

A PURE, deterministic engine (Spec Part 4 §3, §6). Computes production metrics
from recorded batch data: biomass, growth rate, productivity, survival, capacity
utilisation and production velocity. It also provides the deterministic maths the
Batch service uses to validate splits and merges (Spec Part 4 §4).

No I/O, no mutation. Values are honesty-labelled and never fabricated: a metric
that lacks its recorded inputs is reported ``unknown`` rather than guessed
(Spec Part 9 §17-19). All figures are computed on demand and never stored
(Spec Part 3 §20).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


# ── Point metrics ─────────────────────────────────────────────────────────────

def average_weight_mg(population: int | None, biomass_g) -> dict:
    """Mean individual weight in milligrams = biomass / population.

    BSF larvae are tiny (~150-250 mg), so milligrams is the natural unit.
    """
    biomass = _dec(biomass_g)
    if not population or population <= 0 or biomass is None:
        return _lbl(UNKNOWN, None, "Requires a recorded population and biomass.")
    mg = (biomass * Decimal(1000)) / Decimal(population)
    return _lbl(CALCULATED, float(round(mg, 3)), "biomass ÷ population.")


def survival_rate_pct(initial_population: int | None, current_population: int | None) -> dict:
    """Recorded survival = current ÷ initial × 100, clamped to [0, 100]."""
    if not initial_population or initial_population <= 0 or current_population is None:
        return _lbl(UNKNOWN, None, "Requires an initial and current population.")
    pct = (Decimal(current_population) / Decimal(initial_population)) * Decimal(100)
    pct = max(Decimal(0), min(pct, Decimal(100)))
    return _lbl(CALCULATED, float(round(pct, 2)), "current ÷ initial population.")


def capacity_utilisation_pct(biomass_g, capacity_g) -> dict:
    """Share of a production unit's capacity in use = biomass ÷ capacity × 100."""
    biomass = _dec(biomass_g)
    capacity = _dec(capacity_g)
    if biomass is None or capacity is None or capacity <= 0:
        return _lbl(UNKNOWN, None, "Requires a recorded biomass and unit capacity.")
    pct = (biomass / capacity) * Decimal(100)
    return _lbl(CALCULATED, float(round(max(Decimal(0), pct), 2)), "biomass ÷ unit capacity.")


def growth_rate_g_per_day(prev_biomass_g, current_biomass_g, days: int | None) -> dict:
    """Absolute biomass gain per day between two recorded snapshots."""
    prev = _dec(prev_biomass_g)
    current = _dec(current_biomass_g)
    if prev is None or current is None or not days or days <= 0:
        return _lbl(UNKNOWN, None, "Requires two recorded biomass snapshots and the interval.")
    rate = (current - prev) / Decimal(days)
    return _lbl(CALCULATED, float(round(rate, 3)), "(current − previous biomass) ÷ days.")


def production_velocity_g_per_day(biomass_g, days_in_production: int | None) -> dict:
    """Biomass accumulated per day since the batch started (Spec Part 4 §6)."""
    biomass = _dec(biomass_g)
    if biomass is None or not days_in_production or days_in_production <= 0:
        return _lbl(UNKNOWN, None, "Requires a recorded biomass and production age in days.")
    return _lbl(CALCULATED, float(round(biomass / Decimal(days_in_production), 3)),
                "current biomass ÷ days in production.")


# ── Split / merge validation maths (Spec Part 4 §4) ───────────────────────────

def validate_split(parent_population: int | None, child_populations: list[int]) -> dict:
    """Check that split children do not exceed the parent population.

    Returns ``{"valid": bool, "reason": str, "allocated": int, "remainder": int|None}``.
    An unknown parent population cannot be validated (permitted, but flagged).
    """
    if not child_populations or any(p < 0 for p in child_populations):
        return {"valid": False, "reason": "Each split part needs a non-negative population.",
                "allocated": 0, "remainder": None}
    allocated = sum(child_populations)
    if parent_population is None:
        return {"valid": True, "reason": "Parent population unknown — allocation not bounded.",
                "allocated": allocated, "remainder": None}
    if allocated > parent_population:
        return {"valid": False,
                "reason": f"Split allocates {allocated} but parent holds only {parent_population}.",
                "allocated": allocated, "remainder": parent_population - allocated}
    return {"valid": True, "reason": "Split allocation within parent population.",
            "allocated": allocated, "remainder": parent_population - allocated}


def merge_totals(populations: list[int | None], biomasses: list) -> dict:
    """Deterministic sums for a merge. Unknown components are excluded from the
    total and reported so the result is never silently understated."""
    known_pop = [p for p in populations if p is not None]
    known_bio = [b for b in (_dec(x) for x in biomasses) if b is not None]
    total_pop = sum(known_pop) if known_pop else None
    total_bio = float(sum(known_bio)) if known_bio else None
    return {
        "total_population": _lbl(
            CALCULATED if total_pop is not None else UNKNOWN, total_pop,
            f"Sum of {len(known_pop)}/{len(populations)} recorded populations."),
        "total_biomass_g": _lbl(
            CALCULATED if total_bio is not None else UNKNOWN, total_bio,
            f"Sum of {len(known_bio)}/{len(biomasses)} recorded biomasses."),
    }


def split_child_biomass(parent_biomass_g, parent_population: int | None,
                        child_population: int) -> dict:
    """Proportional biomass estimate for a split child (by population share).

    A FORECAST, not a recorded fact — the child is weighed after the split.
    """
    parent_bio = _dec(parent_biomass_g)
    if parent_bio is None or not parent_population or parent_population <= 0:
        return _lbl(UNKNOWN, None, "Requires parent biomass and population to apportion.")
    share = Decimal(child_population) / Decimal(parent_population)
    return _lbl(FORECAST, float(round(parent_bio * share, 2)),
                "parent biomass × (child ÷ parent population); confirm by weighing.")
