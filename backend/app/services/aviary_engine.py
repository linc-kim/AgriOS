"""
Greena — Aviary Engine (Module 15, Part 3)

A PURE, deterministic engine (Doc 14 §2-3): given plain recorded data it returns
labelled facts and calculations. It performs no database access, no I/O and no
mutation, so it is trivially testable and reusable by services, Mission Control
and (for explanation only) ARIA.

Every figure it returns is honesty-labelled (Doc 04 §16, Doc 15 §15):
  recorded      — a value taken directly from a record
  calculated    — deterministically derived from records
  recommendation— a deterministic best-practice suggestion (never a promise)
  unknown       — the inputs to compute it were not recorded
  unavailable    — the concept does not apply here

The engine never invents an environmental reading, never guarantees an outcome,
and states its assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
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
    """Deterministic occupancy from the number of active birds housed here.

    ``occupied_count`` is a recorded fact (count of birds whose ``aviary_id``
    points here). Capacity may be unknown; if so, availability and utilisation
    are honestly reported as unknown rather than guessed.
    """
    occupied = Labelled(RECORDED, occupied_count, "Active birds currently housed here.")

    if capacity is None:
        return Occupancy(
            occupied=occupied,
            capacity=Labelled(UNKNOWN, None, "No capacity recorded for this aviary."),
            available=Labelled(UNKNOWN, None, "Capacity unknown."),
            utilization_pct=Labelled(UNKNOWN, None, "Capacity unknown."),
            over_capacity=False,
        )

    available = capacity - occupied_count
    util = round((occupied_count / capacity) * 100, 1) if capacity > 0 else None
    return Occupancy(
        occupied=occupied,
        capacity=Labelled(RECORDED, capacity, "Recommended maximum occupancy."),
        available=Labelled(CALCULATED, available, "capacity − occupied."),
        utilization_pct=Labelled(
            CALCULATED if util is not None else UNAVAILABLE, util, "occupied ÷ capacity × 100."
        ),
        over_capacity=occupied_count > capacity,
    )


# ── Environmental monitoring ──────────────────────────────────────────────────

@dataclass(frozen=True)
class EnvironmentSummary:
    reading_count: int
    latest: dict
    averages: dict
    findings: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "reading_count": self.reading_count,
            "latest": self.latest,
            "averages": self.averages,
            "findings": self.findings,
        }


def _avg(values: list[Decimal | float | int]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    return round(sum(nums) / len(nums), 2) if nums else None


def summarize_environment(readings: list[dict], targets: dict | None = None) -> EnvironmentSummary:
    """Summarise recorded environmental readings and flag out-of-range values
    against species targets (Doc 16 §8). No reading is ever invented.

    ``readings`` newest-first, each: {temperature_c, humidity_pct, light_hours,...}.
    ``targets`` optional: {temp_min, temp_max, humidity_min, humidity_max} from the
    species profile — findings are recommendations, never diagnoses.
    """
    if not readings:
        return EnvironmentSummary(
            reading_count=0,
            latest={"label": UNKNOWN, "detail": "No environmental readings recorded."},
            averages={},
            findings=[],
        )

    latest = readings[0]
    averages = {
        "temperature_c": _avg([r.get("temperature_c") for r in readings]),
        "humidity_pct": _avg([r.get("humidity_pct") for r in readings]),
        "light_hours": _avg([r.get("light_hours") for r in readings]),
    }

    findings: list[dict] = []
    if targets:
        temp = latest.get("temperature_c")
        if temp is not None and targets.get("temp_min") is not None and targets.get("temp_max") is not None:
            t = float(temp)
            if t < float(targets["temp_min"]):
                findings.append({"label": RECOMMENDATION, "metric": "temperature_c",
                                 "detail": f"Latest {t}°C is below the {targets['temp_min']}°C target — consider warming."})
            elif t > float(targets["temp_max"]):
                findings.append({"label": RECOMMENDATION, "metric": "temperature_c",
                                 "detail": f"Latest {t}°C is above the {targets['temp_max']}°C target — consider cooling/ventilation."})
        hum = latest.get("humidity_pct")
        if hum is not None and targets.get("humidity_min") is not None and targets.get("humidity_max") is not None:
            h = float(hum)
            if h < float(targets["humidity_min"]):
                findings.append({"label": RECOMMENDATION, "metric": "humidity_pct",
                                 "detail": f"Latest {h}% humidity is below the {targets['humidity_min']}% target."})
            elif h > float(targets["humidity_max"]):
                findings.append({"label": RECOMMENDATION, "metric": "humidity_pct",
                                 "detail": f"Latest {h}% humidity is above the {targets['humidity_max']}% target."})

    return EnvironmentSummary(
        reading_count=len(readings),
        latest={"label": RECORDED, "value": {
            "temperature_c": _num(latest.get("temperature_c")),
            "humidity_pct": _num(latest.get("humidity_pct")),
            "light_hours": _num(latest.get("light_hours")),
            "recorded_at": latest.get("recorded_at"),
        }},
        averages={k: (Labelled(CALCULATED, v).as_dict() if v is not None else Labelled(UNKNOWN, None).as_dict())
                  for k, v in averages.items()},
        findings=findings,
    )


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


# ── Cleaning & maintenance status ─────────────────────────────────────────────

def cleaning_status(tasks: list[dict], today: date) -> dict:
    """Deterministic cleaning/maintenance status from recorded tasks.

    ``tasks``: each {task_type, status, scheduled_for (date|None), completed_on}.
    Returns counts of overdue / upcoming and the last completed date — all
    recorded/calculated facts, never a forecast.
    """
    overdue = [
        t for t in tasks
        if t.get("status") == "scheduled" and t.get("scheduled_for") and t["scheduled_for"] < today
    ]
    upcoming = [
        t for t in tasks
        if t.get("status") == "scheduled" and t.get("scheduled_for") and t["scheduled_for"] >= today
    ]
    completed = [t["completed_on"] for t in tasks if t.get("completed_on")]
    return {
        "overdue_count": Labelled(CALCULATED, len(overdue), "Scheduled tasks past their date.").as_dict(),
        "upcoming_count": Labelled(CALCULATED, len(upcoming), "Scheduled tasks still ahead.").as_dict(),
        "last_completed": Labelled(
            RECORDED if completed else UNKNOWN,
            max(completed).isoformat() if completed else None,
            "Most recent completed task.",
        ).as_dict(),
    }


# ── Species housing suitability ───────────────────────────────────────────────

def assess_housing(aviary: dict, species_profile: dict | None) -> dict:
    """Compare an aviary's recorded environment/type against a species' housing
    requirements from its data-driven profile (Doc 16 §4, §8).

    Findings are deterministic best-practice recommendations — never guarantees,
    never diagnoses. When the profile lacks a requirement, the result is unknown
    rather than a fabricated judgement.
    """
    if not species_profile:
        return {"label": UNKNOWN, "findings": [],
                "detail": "No species profile recorded — cannot assess suitability."}

    findings: list[dict] = []
    housing = species_profile.get("housing", {}) if isinstance(species_profile.get("housing"), dict) else {}

    required_types = housing.get("aviary_types")
    if isinstance(required_types, list) and required_types:
        if aviary.get("aviary_type") not in required_types:
            findings.append({"label": RECOMMENDATION, "metric": "aviary_type",
                             "detail": f"Species prefers {required_types}; this aviary is '{aviary.get('aviary_type')}'."})

    env = aviary.get("environment", {}) or {}
    tmin, tmax = housing.get("temp_min"), housing.get("temp_max")
    if tmin is not None and env.get("temp_min") is not None and float(env["temp_min"]) < float(tmin):
        findings.append({"label": RECOMMENDATION, "metric": "temperature",
                         "detail": f"Aviary minimum {env['temp_min']}°C is below the species' {tmin}°C floor."})
    if tmax is not None and env.get("temp_max") is not None and float(env["temp_max"]) > float(tmax):
        findings.append({"label": RECOMMENDATION, "metric": "temperature",
                         "detail": f"Aviary maximum {env['temp_max']}°C is above the species' {tmax}°C ceiling."})

    return {
        "label": RECOMMENDATION if findings else RECORDED,
        "findings": findings,
        "detail": "Deterministic comparison of recorded aviary settings against the species profile."
        if findings else "No housing concerns found against the recorded species profile.",
    }
