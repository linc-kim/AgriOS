"""
Greena — BSF Bottleneck Engine (Module 16, Part 6)

A PURE, deterministic engine (Spec Part 4 §13, Part 7 §12). Given recorded/
calculated operational metrics it identifies the constraints most limiting the
farm, ranked by severity. Only meaningful constraints are returned, highest-
impact first (Spec Part 4 §13 "only the highest-impact bottlenecks shall be
prioritized"). No I/O, no mutation.

Each bottleneck cites its **evidence** (the recorded/calculated figure that
triggered it), a **business impact**, a **recommended action** and a
**confidence** — never a fabricated cause (Spec Part 7 §12, §17). A metric that
was not supplied is simply not evaluated (no guessing).
"""

from __future__ import annotations

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Deterministic thresholds (documented, tunable).
_LOW_SURVIVAL_PCT = 60.0
_CRIT_SURVIVAL_PCT = 40.0
_HIGH_CAPACITY_PCT = 90.0
_LOW_FEEDSTOCK_KG = 10.0
_POOR_FCR = 4.0
_CRIT_FCR = 6.0


def _bottleneck(constraint, severity, evidence, impact, action, confidence="medium") -> dict:
    return {"constraint": constraint, "severity": severity, "evidence": evidence,
            "impact": impact, "recommended_action": action, "confidence": confidence}


def analyze(
    *,
    survival_rate_pct: float | None = None,
    capacity_utilisation_pct: float | None = None,
    feedstock_available_kg: float | None = None,
    feed_conversion_ratio: float | None = None,
    environmental_violations: int | None = None,
) -> list[dict]:
    """Return severity-ranked bottlenecks from supplied metrics. Unsupplied metrics
    are not evaluated. The list is ordered highest-impact first."""
    found: list[dict] = []

    if survival_rate_pct is not None:
        if survival_rate_pct <= _CRIT_SURVIVAL_PCT:
            found.append(_bottleneck(
                "survival", "critical",
                f"Survival {survival_rate_pct}% ≤ {_CRIT_SURVIVAL_PCT}%.",
                "Severe population loss is capping biomass output.",
                "Investigate environment, feed quality and handling; review mortality causes.",
                "high"))
        elif survival_rate_pct < _LOW_SURVIVAL_PCT:
            found.append(_bottleneck(
                "survival", "high",
                f"Survival {survival_rate_pct}% < {_LOW_SURVIVAL_PCT}%.",
                "Below-target survival is reducing yield.",
                "Review feeding consistency and environmental stability."))

    if feedstock_available_kg is not None and feedstock_available_kg <= _LOW_FEEDSTOCK_KG:
        found.append(_bottleneck(
            "feedstock_supply", "high",
            f"Only {feedstock_available_kg}kg feedstock available (≤ {_LOW_FEEDSTOCK_KG}kg).",
            "Low feedstock will interrupt feeding and stall growth.",
            "Secure additional feedstock supply before the shortfall halts production."))

    if capacity_utilisation_pct is not None and capacity_utilisation_pct >= _HIGH_CAPACITY_PCT:
        found.append(_bottleneck(
            "production_capacity", "medium",
            f"Capacity utilisation {capacity_utilisation_pct}% ≥ {_HIGH_CAPACITY_PCT}%.",
            "Units are near capacity, limiting new batches / expansion.",
            "Add production units or split batches to relieve capacity."))

    if feed_conversion_ratio is not None:
        if feed_conversion_ratio >= _CRIT_FCR:
            found.append(_bottleneck(
                "feed_conversion", "high",
                f"FCR {feed_conversion_ratio} ≥ {_CRIT_FCR} (poor).",
                "Excess feed per unit biomass is inflating cost and cutting margin.",
                "Review feed type, moisture and feeding rate; compare high-performing batches."))
        elif feed_conversion_ratio >= _POOR_FCR:
            found.append(_bottleneck(
                "feed_conversion", "medium",
                f"FCR {feed_conversion_ratio} ≥ {_POOR_FCR}.",
                "Feed efficiency is below target.",
                "Tune feeding rate and feedstock mix."))

    if environmental_violations is not None and environmental_violations > 0:
        sev = "high" if environmental_violations >= 3 else "medium"
        found.append(_bottleneck(
            "environmental_stability", sev,
            f"{environmental_violations} recent environmental threshold violation(s).",
            "Unstable conditions depress growth and survival.",
            "Stabilise temperature/humidity/moisture toward the species range."))

    found.sort(key=lambda b: _SEVERITY_RANK.get(b["severity"], 9))
    return found


def top_bottleneck(bottlenecks: list[dict]) -> dict | None:
    """The single highest-impact constraint, or None when nothing is limiting."""
    return bottlenecks[0] if bottlenecks else None
