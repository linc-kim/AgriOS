"""
Greena — Small Ruminant Housing / Grazing Capacity Engine (Modules 18/19, Milestone 2)

A PURE, deterministic engine (no DB, no I/O, no mutation) shared by goats and
sheep. Given plain recorded counts it returns honesty-labelled facts and
calculations for pens (head capacity) and pastures (carrying capacity), reusable
by services, Mission Control and — for explanation only — ARIA.

Every figure is honesty-labelled (Goat Doc 8 §15):
  recorded      — a value taken directly from a record
  calculated    — deterministically derived from records
  recommendation— a deterministic best-practice suggestion (never a promise)
  unknown       — the inputs to compute it were not recorded
  unavailable   — the concept does not apply here

Occupancy is ALWAYS supplied as a recorded count of active animals located here
(``sr_animal.pen_id`` / ``.pasture_id``) — it is never stored on the pen/pasture.
The engine never invents a capacity, never guarantees an outcome, and states its
assumptions. It is species-neutral: overstocking a paddock is the same arithmetic
for a herd of goats or a flock of sheep.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── Value labelling ───────────────────────────────────────────────────────────

RECORDED = "recorded"
CALCULATED = "calculated"
RECOMMENDATION = "recommendation"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Labelled:
    """A single value plus how it is known (the honesty contract)."""

    label: str
    value: Any
    detail: str = ""

    def as_dict(self) -> dict:
        return {"label": self.label, "value": self.value, "detail": self.detail}


# ── Occupancy & capacity ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Occupancy:
    occupied: Labelled
    capacity: Labelled
    available: Labelled
    utilization_pct: Labelled
    over_capacity: bool

    def as_dict(self) -> dict:
        return {
            "occupied": self.occupied.as_dict(),
            "capacity": self.capacity.as_dict(),
            "available": self.available.as_dict(),
            "utilization_pct": self.utilization_pct.as_dict(),
            "over_capacity": self.over_capacity,
        }


def compute_occupancy(capacity: int | None, occupied_count: int) -> Occupancy:
    """Deterministic occupancy from the number of active animals housed here.

    ``occupied_count`` is a recorded fact (count of animals located here). Capacity
    may be unknown; if so, availability and utilisation are honestly reported as
    unknown rather than guessed (Goat Doc 2 §14).
    """
    occupied = Labelled(RECORDED, occupied_count, "Active animals currently located here.")

    if capacity is None:
        return Occupancy(
            occupied=occupied,
            capacity=Labelled(UNKNOWN, None, "No capacity recorded for this location."),
            available=Labelled(UNKNOWN, None, "Capacity unknown."),
            utilization_pct=Labelled(UNKNOWN, None, "Capacity unknown."),
            over_capacity=False,
        )

    available = capacity - occupied_count
    util = round((occupied_count / capacity) * 100, 1) if capacity > 0 else None
    return Occupancy(
        occupied=occupied,
        capacity=Labelled(RECORDED, capacity, "Maximum recommended head / carrying capacity."),
        available=Labelled(CALCULATED, available, "capacity − occupied."),
        utilization_pct=Labelled(
            CALCULATED if util is not None else UNAVAILABLE, util, "occupied ÷ capacity × 100."
        ),
        over_capacity=occupied_count > capacity,
    )


def is_overcrowded(capacity: int | None, occupied_count: int) -> bool:
    """True only when a recorded capacity is exceeded (Goat Doc 6 §10 overstock).

    Unknown capacity is never treated as overcrowding — the engine does not
    fabricate a limit.
    """
    return capacity is not None and occupied_count > capacity


# ── Farm-level roll-up ────────────────────────────────────────────────────────

def rollup(children: list[dict]) -> dict:
    """Aggregate a set of locations (pens or pastures) into one summary.

    ``children``: each ``{"capacity": int|None, "occupied": int}``. Capacity is
    summed only over children that recorded one; the count of unknown-capacity
    children is reported so the total is never silently understated.
    """
    occupied_total = sum(int(c.get("occupied", 0) or 0) for c in children)
    known = [c for c in children if c.get("capacity") is not None]
    unknown_count = len(children) - len(known)
    capacity_total = sum(int(c["capacity"]) for c in known) if known else None

    over = [c for c in children if is_overcrowded(c.get("capacity"), int(c.get("occupied", 0) or 0))]

    if capacity_total is None:
        available = Labelled(UNKNOWN, None, "No location recorded a capacity.")
        util = Labelled(UNKNOWN, None, "Capacity unknown.")
    else:
        available = Labelled(CALCULATED, capacity_total - occupied_total, "Σcapacity − Σoccupied.")
        util = Labelled(
            CALCULATED if capacity_total > 0 else UNAVAILABLE,
            round((occupied_total / capacity_total) * 100, 1) if capacity_total > 0 else None,
            "Σoccupied ÷ Σcapacity × 100.",
        )

    return {
        "unit_count": Labelled(RECORDED, len(children), "Housing / grazing units.").as_dict(),
        "occupied": Labelled(RECORDED, occupied_total, "Σ active animals across locations.").as_dict(),
        "capacity": (
            Labelled(CALCULATED, capacity_total, "Σ recorded capacities.").as_dict()
            if capacity_total is not None
            else Labelled(UNKNOWN, None, "No location recorded a capacity.").as_dict()
        ),
        "capacity_unknown_units": Labelled(
            RECORDED, unknown_count, "Locations with no recorded capacity (excluded from the total)."
        ).as_dict(),
        "available": available.as_dict(),
        "utilization_pct": util.as_dict(),
        "overcrowded_units": Labelled(
            CALCULATED, len(over), "Locations whose recorded capacity is exceeded."
        ).as_dict(),
    }
