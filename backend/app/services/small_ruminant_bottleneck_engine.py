"""
Greena — Small Ruminant Bottleneck Engine (Modules 18/19, Milestone 9)

A PURE, deterministic engine shared by goats and sheep: it detects operational
constraints from already-computed deterministic metrics and ranks them by
severity, each citing evidence, impact and a recommended action (Goat Doc 6 §16,
Doc 7 §11). No I/O, no mutation.

Only metrics that were actually supplied are evaluated — an unsupplied metric is
skipped, never assumed. Actions are advisory recommendations, never directives,
and health findings remain patterns (never a diagnosis). Mission Control (M10)
consumes this detection; it is not computed there.
"""

from __future__ import annotations

from typing import Any

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def _issue(area: str, severity: str, evidence: str, impact: str, action: str,
           confidence: str = "medium") -> dict:
    return {"area": area, "severity": severity, "evidence": evidence, "impact": impact,
            "action": action, "confidence": confidence}


def _val(metric: dict | None) -> Any:
    """Pull a value from a labelled metric ({label,value}); None if unavailable."""
    if not isinstance(metric, dict):
        return None
    if metric.get("label") in ("unknown", "unavailable"):
        return None
    return metric.get("value")


def analyze(*, reproduction: dict | None = None, health: dict | None = None,
            housing: dict | None = None, feed: dict | None = None, finance: dict | None = None) -> list[dict]:
    """Return severity-ranked operational constraints from supplied deterministic
    summaries. Highest severity first; ties keep detection order."""
    issues: list[dict] = []

    # Reproduction — low birth rate.
    if reproduction:
        birth_rate = _val(reproduction.get("birth_rate_pct"))
        if birth_rate is not None and birth_rate < 60:
            issues.append(_issue(
                "reproduction", "high" if birth_rate < 40 else "medium",
                f"Birth rate {birth_rate}% of services.",
                "Fewer offspring than the herd could produce depresses growth and revenue.",
                "Review body condition, buck/ram fertility and service timing; consider a pregnancy-check routine.",
            ))

    # Health — mortality (pattern, not a diagnosis).
    if health:
        mort = _val(health.get("mortality_rate_pct"))
        if mort is not None and mort > 5:
            issues.append(_issue(
                "health", "high" if mort > 10 else "medium",
                f"Mortality {mort}% of all animals recorded (a pattern, not a diagnosis).",
                "Deaths reduce herd size and waste rearing cost.",
                "Review the recorded causes and vaccination/deworming compliance; consult a vet for clusters.",
            ))
        dew = health.get("deworming_compliance", {})
        overdue = _val(dew.get("overdue")) if isinstance(dew, dict) else None
        if overdue is not None and overdue > 0:
            issues.append(_issue(
                "parasite_control", "medium",
                f"{overdue} overdue deworming(s).",
                "Parasite burden lowers growth, fertility and can raise mortality.",
                "Action the overdue deworming reminders; check FAMACHA scores.",
            ))

    # Housing — overcrowding.
    if housing:
        for key, label in (("overcrowded_pens", "pen"), ("overcrowded_pastures", "pasture")):
            over = housing.get(key)
            if isinstance(over, list) and over:
                issues.append(_issue(
                    "housing", "medium",
                    f"{len(over)} overcrowded {label}(s) vs recorded capacity.",
                    "Overstocking harms welfare, hygiene and grazing recovery.",
                    f"Rebalance stock across {label}s or expand capacity.",
                ))

    # Feed efficiency — high FCR.
    if feed:
        fcr = _val(feed.get("feed_conversion_ratio"))
        if fcr is not None and fcr > 10:
            issues.append(_issue(
                "feed_efficiency", "medium",
                f"Feed conversion ratio {fcr} (kg feed per kg gain).",
                "Poor conversion raises the cost of every kilo of gain.",
                "Review ration quality/balance and check for parasites or ill-thrift.",
            ))

    # Finance — negative margin.
    if finance:
        pnl = finance.get("pnl", finance)
        margin = _val(pnl.get("gross_margin")) if isinstance(pnl, dict) else None
        if margin is not None and margin < 0:
            issues.append(_issue(
                "profitability", "high",
                f"Negative gross margin ({margin}).",
                "Recorded costs exceed recorded revenue.",
                "Review feed and operating costs and sale pricing; the enterprise is running at a recorded loss.",
            ))

    issues.sort(key=lambda i: _SEVERITY_RANK.get(i["severity"], 0), reverse=True)
    return issues
