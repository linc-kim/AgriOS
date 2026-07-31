"""
Greena — BSF Harvest Engine (Module 16, Part 4)

A PURE, deterministic engine (Spec Part 4 §8). Computes harvest readiness,
expected yield, yield percentage and partial/complete-harvest validation from
recorded batch data and the species profile. No I/O, no mutation.

Harvest calculations remain deterministic and honesty-labelled; a value lacking
its recorded inputs is reported ``unknown`` rather than guessed (Spec Part 9
§17-19). Readiness is a *calculated* signal from the lifecycle stage, never a
guarantee.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

# Stage → readiness for a larvae/prepupae harvest (Spec Part 2 §6 lifecycle).
_READY_STAGES = ("mature_larvae", "prepupae")
_APPROACHING_STAGES = ("feeding_larvae",)
_PAST_STAGES = ("pupae", "adult")


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def harvest_readiness(lifecycle_stage: str | None, pacing_status: str | None = None) -> dict:
    """Deterministic harvest-readiness signal from the current lifecycle stage.

    ``ready`` at mature-larvae/prepupae (the harvest window), ``approaching`` at
    feeding-larvae, ``past_window`` at pupae/adult, else ``not_ready``. Never a
    guarantee — it is a calculated signal from recorded stage.
    """
    if lifecycle_stage in _READY_STAGES:
        status = "ready"
        detail = f"Batch is at {lifecycle_stage!r} — within the harvest window."
    elif lifecycle_stage in _APPROACHING_STAGES:
        status = "approaching"
        detail = "Batch is feeding; approaching the harvest window."
    elif lifecycle_stage in _PAST_STAGES:
        status = "past_window"
        detail = f"Batch is at {lifecycle_stage!r} — past the larvae/prepupae harvest window."
    elif lifecycle_stage in ("egg", "hatchling"):
        status = "not_ready"
        detail = f"Batch is at {lifecycle_stage!r} — too early to harvest."
    else:
        return _lbl(UNKNOWN, "unknown", "Lifecycle stage not recorded.")
    result = _lbl(CALCULATED, status, detail)
    if pacing_status == "delayed" and status == "approaching":
        result["detail"] += " Development is delayed vs the species profile."
    return result


def expected_yield_kg(biomass_g, yield_ratio) -> dict:
    """Forecast harvestable mass = current biomass × harvestable fraction.

    ``yield_ratio`` (0-1) comes from the species profile; absent → unknown.
    """
    biomass = _dec(biomass_g)
    ratio = _dec(yield_ratio)
    if biomass is None or ratio is None or ratio <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded biomass and a species harvest ratio.")
    kg = (biomass / Decimal(1000)) * ratio
    return _lbl(FORECAST, float(round(kg, 3)), "biomass × species harvest ratio; confirm by weighing.")


def yield_pct(harvested_kg, batch_biomass_g) -> dict:
    """Share of the batch's biomass taken by this harvest = harvested ÷ biomass."""
    harvested = _dec(harvested_kg)
    biomass_kg = _dec(batch_biomass_g)
    if harvested is None or biomass_kg is None or biomass_kg <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded harvest mass and batch biomass.")
    biomass_kg = biomass_kg / Decimal(1000)
    if biomass_kg <= 0:
        return _lbl(UNKNOWN, None, "Batch biomass is zero.")
    pct = (harvested / biomass_kg) * Decimal(100)
    return _lbl(CALCULATED, float(round(pct, 2)), "harvested mass ÷ batch biomass.")


def validate_harvest_quantity(harvested_kg, available_biomass_g, *, is_complete: bool) -> dict:
    """Validate a harvest quantity against the batch's recorded biomass.

    A partial harvest may not exceed available biomass; a complete harvest empties
    the batch. Unknown biomass cannot be bounded (permitted, but flagged).
    """
    harvested = _dec(harvested_kg)
    if harvested is None or harvested <= 0:
        return {"valid": False, "reason": "Harvest quantity must be greater than zero."}
    available = _dec(available_biomass_g)
    if available is None:
        return {"valid": True, "reason": "Batch biomass unknown — quantity not bounded."}
    available_kg = available / Decimal(1000)
    if not is_complete and harvested > available_kg:
        return {"valid": False,
                "reason": f"Partial harvest of {harvested}kg exceeds the batch's "
                          f"{round(available_kg, 3)}kg recorded biomass."}
    return {"valid": True, "reason": "Harvest quantity within recorded biomass."}
