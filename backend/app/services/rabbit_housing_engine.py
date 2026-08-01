"""
Greena — Rabbit Housing Capacity Engine (Module 17, Milestone 2)

A PURE, deterministic engine (GMIS §1.3, §5): given plain recorded data it
returns honesty-labelled facts and calculations. It performs no database access,
no I/O and no mutation, so it is trivially testable and reusable by services,
Mission Control and (for explanation only) ARIA.

Every figure it returns is honesty-labelled (Spec Part 9 §17):
  recorded      — a value taken directly from a record
  calculated    — deterministically derived from records
  recommendation— a deterministic best-practice suggestion (never a promise)
  unknown       — the inputs to compute it were not recorded
  unavailable   — the concept does not apply here

The engine never invents an occupancy count, never guarantees an outcome, and
states its assumptions. Cage occupancy is always supplied as a recorded count of
active rabbits (``rabbit.cage_id``) — it is never stored on the cage.
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
    """Deterministic occupancy from the number of active rabbits housed here.

    ``occupied_count`` is a recorded fact (count of rabbits whose ``cage_id``
    points here). Capacity may be unknown; if so, availability and utilisation
    are honestly reported as unknown rather than guessed (Spec Part 3 §14).
    """
    occupied = Labelled(RECORDED, occupied_count, "Active rabbits currently housed here.")

    if capacity is None:
        return Occupancy(
            occupied=occupied,
            capacity=Labelled(UNKNOWN, None, "No capacity recorded for this cage."),
            available=Labelled(UNKNOWN, None, "Capacity unknown."),
            utilization_pct=Labelled(UNKNOWN, None, "Capacity unknown."),
            over_capacity=False,
        )

    available = capacity - occupied_count
    util = round((occupied_count / capacity) * 100, 1) if capacity > 0 else None
    return Occupancy(
        occupied=occupied,
        capacity=Labelled(RECORDED, capacity, "Maximum recommended occupancy."),
        available=Labelled(CALCULATED, available, "capacity − occupied."),
        utilization_pct=Labelled(
            CALCULATED if util is not None else UNAVAILABLE, util, "occupied ÷ capacity × 100."
        ),
        over_capacity=occupied_count > capacity,
    )


def is_overcrowded(capacity: int | None, occupied_count: int) -> bool:
    """True only when a recorded capacity is exceeded (Spec Part 4 §11).

    Unknown capacity is never treated as overcrowding — the engine does not
    fabricate a limit.
    """
    return capacity is not None and occupied_count > capacity


# ── Hierarchy roll-up ─────────────────────────────────────────────────────────

def rollup(children: list[dict]) -> dict:
    """Aggregate a housing level from its children (Spec Part 7 §8).

    ``children``: each ``{"capacity": int|None, "occupied": int}`` — e.g. the
    cages under a row, or the rows under a room. Capacity is summed only over
    children that recorded one; the count of unknown-capacity children is
    reported so the total is never silently understated.
    """
    occupied_total = sum(int(c.get("occupied", 0) or 0) for c in children)
    known = [c for c in children if c.get("capacity") is not None]
    unknown_count = len(children) - len(known)
    capacity_total = sum(int(c["capacity"]) for c in known) if known else None

    over = [c for c in children if is_overcrowded(c.get("capacity"), int(c.get("occupied", 0) or 0))]

    if capacity_total is None:
        available = Labelled(UNKNOWN, None, "No child recorded a capacity.")
        util = Labelled(UNKNOWN, None, "Capacity unknown.")
    else:
        available = Labelled(CALCULATED, capacity_total - occupied_total, "Σcapacity − Σoccupied.")
        util = Labelled(
            CALCULATED if capacity_total > 0 else UNAVAILABLE,
            round((occupied_total / capacity_total) * 100, 1) if capacity_total > 0 else None,
            "Σoccupied ÷ Σcapacity × 100.",
        )

    return {
        "unit_count": Labelled(RECORDED, len(children), "Child housing units.").as_dict(),
        "occupied": Labelled(RECORDED, occupied_total, "Σ active rabbits across children.").as_dict(),
        "capacity": (
            Labelled(CALCULATED, capacity_total, "Σ recorded child capacities.").as_dict()
            if capacity_total is not None
            else Labelled(UNKNOWN, None, "No child recorded a capacity.").as_dict()
        ),
        "capacity_unknown_units": Labelled(
            RECORDED, unknown_count, "Children with no recorded capacity (excluded from the total)."
        ).as_dict(),
        "available": available.as_dict(),
        "utilization_pct": util.as_dict(),
        "overcrowded_units": Labelled(
            CALCULATED, len(over), "Children whose recorded capacity is exceeded."
        ).as_dict(),
    }
