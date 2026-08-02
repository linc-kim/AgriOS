"""
Greena — Swine Housing Capacity Engine (Module 20, Milestone 2)

A PURE, deterministic engine (no DB, no I/O, no mutation). Given plain recorded
counts it returns honesty-labelled facts and calculations for pens (head capacity),
reusable by services, Mission Control and — for explanation only — ARIA.

Every figure is honesty-labelled (Swine Doc 6 §5):
  recorded      — a value taken directly from a record
  calculated    — deterministically derived from records
  unknown       — the inputs to compute it were not recorded
  unavailable   — the concept does not apply here

Occupancy is ALWAYS supplied as a recorded count of active pigs located here
(``swine_pig.pen_id``) — it is never stored on the pen. The engine never invents a
capacity and never guarantees an outcome. Biosecurity status is a recorded pen
assessment; the roll-up counts pens whose status flags attention so the Housing
workspace and Mission Control can surface it — it is never inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── Value labelling ───────────────────────────────────────────────────────────

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

# Biosecurity statuses that flag attention in the roll-up (Swine Doc 2 §6).
BIOSECURITY_FLAGGED = ("restricted", "quarantine", "compromised")


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
    """Deterministic occupancy from the number of active pigs housed here.

    ``occupied_count`` is a recorded fact (count of pigs located here). Capacity may
    be unknown; if so, availability and utilisation are honestly reported as unknown
    rather than guessed (Swine Doc 2 §6).
    """
    occupied = Labelled(RECORDED, occupied_count, "Active pigs currently located here.")

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
        capacity=Labelled(RECORDED, capacity, "Maximum recommended head."),
        available=Labelled(CALCULATED, available, "capacity − occupied."),
        utilization_pct=Labelled(
            CALCULATED if util is not None else UNAVAILABLE, util, "occupied ÷ capacity × 100."
        ),
        over_capacity=occupied_count > capacity,
    )


def is_overcrowded(capacity: int | None, occupied_count: int) -> bool:
    """True only when a recorded capacity is exceeded.

    Unknown capacity is never treated as overcrowding — the engine does not
    fabricate a limit.
    """
    return capacity is not None and occupied_count > capacity


# ── Farm-level roll-up ────────────────────────────────────────────────────────

def rollup(children: list[dict]) -> dict:
    """Aggregate a set of pens into one summary.

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
        available = Labelled(UNKNOWN, None, "No pen recorded a capacity.")
        util = Labelled(UNKNOWN, None, "Capacity unknown.")
    else:
        available = Labelled(CALCULATED, capacity_total - occupied_total, "Σcapacity − Σoccupied.")
        util = Labelled(
            CALCULATED if capacity_total > 0 else UNAVAILABLE,
            round((occupied_total / capacity_total) * 100, 1) if capacity_total > 0 else None,
            "Σoccupied ÷ Σcapacity × 100.",
        )

    return {
        "unit_count": Labelled(RECORDED, len(children), "Housing units.").as_dict(),
        "occupied": Labelled(RECORDED, occupied_total, "Σ active pigs across pens.").as_dict(),
        "capacity": (
            Labelled(CALCULATED, capacity_total, "Σ recorded capacities.").as_dict()
            if capacity_total is not None
            else Labelled(UNKNOWN, None, "No pen recorded a capacity.").as_dict()
        ),
        "capacity_unknown_units": Labelled(
            RECORDED, unknown_count, "Pens with no recorded capacity (excluded from the total)."
        ).as_dict(),
        "available": available.as_dict(),
        "utilization_pct": util.as_dict(),
        "overcrowded_units": Labelled(
            CALCULATED, len(over), "Pens whose recorded capacity is exceeded."
        ).as_dict(),
    }


def biosecurity_rollup(statuses: list[str]) -> dict:
    """Count pens by biosecurity status and flag those needing attention.

    ``statuses``: the recorded ``biosecurity_status`` of each pen. Purely a tally of
    recorded assessments — never inferred (Swine Doc 2 §6).
    """
    counts: dict[str, int] = {}
    for st in statuses:
        counts[st] = counts.get(st, 0) + 1
    flagged = sum(counts.get(st, 0) for st in BIOSECURITY_FLAGGED)
    return {
        "by_status": counts,
        "flagged": Labelled(
            CALCULATED, flagged,
            "Pens recorded as restricted / quarantine / compromised.",
        ).as_dict(),
    }
