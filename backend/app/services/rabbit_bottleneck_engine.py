"""
Greena — Rabbit Bottleneck Engine (Module 17, Milestone 7)

A PURE, deterministic engine (Spec Part 7 §11). Given recorded/calculated
operational metrics it identifies the constraints most limiting the rabbitry,
ranked by severity, highest-impact first. No I/O, no mutation.

Each bottleneck cites its **evidence** (the figure that triggered it), a
**business impact**, a **recommended action** and a **confidence** — never a
fabricated cause (Spec Part 7 §11, Part 9 §18). A metric that was not supplied is
simply not evaluated (no guessing). Recommendations are advisory (Spec Part 2 §14).
"""

from __future__ import annotations

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Deterministic thresholds (documented, tunable).
_LOW_KINDLING_PCT = 60.0
_CRIT_KINDLING_PCT = 40.0
_HIGH_MORTALITY_PCT = 15.0
_CRIT_MORTALITY_PCT = 25.0
_LOW_WEANING_PCT = 70.0
_HIGH_CAPACITY_PCT = 90.0
_POOR_FCR = 5.0
_CRIT_FCR = 8.0


def _bottleneck(constraint, severity, evidence, impact, action, confidence="medium") -> dict:
    return {"constraint": constraint, "severity": severity, "evidence": evidence,
            "impact": impact, "recommended_action": action, "confidence": confidence}


def analyze(
    *,
    kindling_rate_pct: float | None = None,
    mortality_rate_pct: float | None = None,
    weaning_survival_pct: float | None = None,
    capacity_utilisation_pct: float | None = None,
    overcrowded_cages: int | None = None,
    feed_conversion_ratio: float | None = None,
    overdue_vaccinations: int | None = None,
    gross_margin_pct: float | None = None,
) -> list[dict]:
    """Return severity-ranked bottlenecks from supplied metrics. Unsupplied metrics
    are not evaluated. The list is ordered highest-impact first."""
    found: list[dict] = []

    if kindling_rate_pct is not None:
        if kindling_rate_pct <= _CRIT_KINDLING_PCT:
            found.append(_bottleneck(
                "reproduction", "critical",
                f"Kindling rate {kindling_rate_pct}% ≤ {_CRIT_KINDLING_PCT}%.",
                "Very low kindling success is capping kit output.",
                "Review buck fertility, doe condition and service timing; consider replacements.",
                "high"))
        elif kindling_rate_pct < _LOW_KINDLING_PCT:
            found.append(_bottleneck(
                "reproduction", "high",
                f"Kindling rate {kindling_rate_pct}% < {_LOW_KINDLING_PCT}%.",
                "Below-target kindling is reducing production.",
                "Review breeding schedules, nutrition and repeat-service handling."))

    if mortality_rate_pct is not None:
        if mortality_rate_pct >= _CRIT_MORTALITY_PCT:
            found.append(_bottleneck(
                "mortality", "critical",
                f"Mortality {mortality_rate_pct}% ≥ {_CRIT_MORTALITY_PCT}%.",
                "Severe losses are eroding herd size and profitability.",
                "Investigate recorded mortality causes, biosecurity and housing conditions.",
                "high"))
        elif mortality_rate_pct >= _HIGH_MORTALITY_PCT:
            found.append(_bottleneck(
                "mortality", "high",
                f"Mortality {mortality_rate_pct}% ≥ {_HIGH_MORTALITY_PCT}%.",
                "Elevated mortality is reducing output.",
                "Review health records for recurring causes; tighten preventive care."))

    if weaning_survival_pct is not None and weaning_survival_pct < _LOW_WEANING_PCT:
        found.append(_bottleneck(
            "weaning_survival", "high",
            f"Weaning survival {weaning_survival_pct}% < {_LOW_WEANING_PCT}%.",
            "Kit losses before weaning are lowering saleable output.",
            "Review nest-box management, doe milk supply and fostering."))

    if overcrowded_cages:
        found.append(_bottleneck(
            "housing_overcrowding", "high",
            f"{overcrowded_cages} cage(s) over recorded capacity.",
            "Overcrowding stresses rabbits and raises disease risk.",
            "Redistribute rabbits or add cages before welfare and growth suffer."))
    elif capacity_utilisation_pct is not None and capacity_utilisation_pct >= _HIGH_CAPACITY_PCT:
        found.append(_bottleneck(
            "housing_capacity", "medium",
            f"Housing utilisation {capacity_utilisation_pct}% ≥ {_HIGH_CAPACITY_PCT}%.",
            "Little spare capacity limits expansion and isolation options.",
            "Plan housing expansion ahead of the next breeding cycle."))

    if feed_conversion_ratio is not None:
        if feed_conversion_ratio >= _CRIT_FCR:
            found.append(_bottleneck(
                "feed_efficiency", "high",
                f"Feed conversion ratio {feed_conversion_ratio} ≥ {_CRIT_FCR}.",
                "Poor feed conversion is inflating cost per kg.",
                "Review feed quality, ration and wastage; check growth records.",
                "medium"))
        elif feed_conversion_ratio >= _POOR_FCR:
            found.append(_bottleneck(
                "feed_efficiency", "medium",
                f"Feed conversion ratio {feed_conversion_ratio} ≥ {_POOR_FCR}.",
                "Above-target FCR is raising feed cost.",
                "Review ration formulation and feeding consistency."))

    if overdue_vaccinations:
        found.append(_bottleneck(
            "vaccination_compliance", "medium",
            f"{overdue_vaccinations} vaccination(s) overdue.",
            "Lapsed vaccinations raise disease-outbreak risk.",
            "Administer overdue doses; the platform reminders are already scheduled."))

    if gross_margin_pct is not None and gross_margin_pct < 0:
        found.append(_bottleneck(
            "profitability", "high",
            f"Gross margin {gross_margin_pct}% is negative.",
            "The enterprise is running at a recorded loss.",
            "Review feed and operating costs against sale prices; prioritise the biggest cost driver.",
            "high"))

    found.sort(key=lambda b: _SEVERITY_RANK.get(b["severity"], 9))
    return found
