"""
Greena — Operations Planner: Routine Optimization Engine (deterministic, pure).

Analyses recorded operational metrics — completion rates, delays, worker
productivity, equipment utilisation, production/financial/health outcomes,
resource consumption — and emits *advisory* improvement recommendations
(spec Doc 4 §12). Every recommendation carries Evidence · Reasoning · Confidence
· Limitations. Pure and deterministic; a metric that is absent is skipped —
never fabricated.

Metrics dict (all optional)::
    {"completion_rate":0.72, "avg_delay_minutes":35, "on_time_rate":0.6,
     "worker_efficiency":0.65, "equipment_utilisation":0.4, "sample_size":120}
"""

from __future__ import annotations

from app.services import ops_common as oc


def _confidence(sample_size) -> str:
    n = sample_size or 0
    return "high" if n >= 60 else "medium" if n >= 20 else "low"


def analyze(metrics: dict, thresholds: dict | None = None) -> dict:
    """Return ``{"recommendations": [...], "evaluated": [...], "skipped": [...]}``.

    Recommendations are deterministic (fixed thresholds) and advisory — they are
    never auto-applied (spec Doc 2 §18). Missing metrics are reported as skipped,
    not assumed.
    """
    t = {
        "completion_rate_min": 0.85,
        "on_time_rate_min": 0.8,
        "worker_efficiency_min": 0.7,
        "equipment_utilisation_min": 0.5,
        "avg_delay_minutes_max": 30,
    }
    t.update(thresholds or {})
    n = metrics.get("sample_size")
    conf = _confidence(n)
    recs, evaluated, skipped = [], [], []

    def check(key: str, present_fmt):
        if metrics.get(key) is None:
            skipped.append(key)
            return None
        evaluated.append(key)
        return present_fmt(float(metrics[key]))

    check("completion_rate", lambda v: recs.append(oc.recommendation(
        "Investigate incomplete routines and simplify or reassign them",
        f"Completion rate {v:.0%} is below the {t['completion_rate_min']:.0%} target.",
        evidence={"completion_rate": v, "sample_size": n}, confidence=conf,
        limitations="Rate alone does not explain the cause; review by routine/worker.")
    ) if v < t["completion_rate_min"] else None)

    check("on_time_rate", lambda v: recs.append(oc.recommendation(
        "Rebalance schedule or shift start times to reduce late starts",
        f"On-time rate {v:.0%} is below the {t['on_time_rate_min']:.0%} target.",
        evidence={"on_time_rate": v, "sample_size": n}, confidence=conf,
        limitations="Lateness may be driven by dependencies outside this routine.")
    ) if v < t["on_time_rate_min"] else None)

    check("worker_efficiency", lambda v: recs.append(oc.recommendation(
        "Review training and task allocation for affected workers",
        f"Worker efficiency {v:.0%} is below the {t['worker_efficiency_min']:.0%} target.",
        evidence={"worker_efficiency": v, "sample_size": n}, confidence=conf,
        limitations="Efficiency metrics can penalise workers given the hardest tasks.")
    ) if v < t["worker_efficiency_min"] else None)

    check("equipment_utilisation", lambda v: recs.append(oc.recommendation(
        "Consolidate equipment use or redeploy idle units",
        f"Equipment utilisation {v:.0%} is below the {t['equipment_utilisation_min']:.0%} target.",
        evidence={"equipment_utilisation": v, "sample_size": n}, confidence=conf,
        limitations="Low utilisation may be intentional standby capacity.")
    ) if v < t["equipment_utilisation_min"] else None)

    check("avg_delay_minutes", lambda v: recs.append(oc.recommendation(
        "Add buffer time or resequence dependent tasks",
        f"Average delay {v:.0f} min exceeds the {t['avg_delay_minutes_max']} min target.",
        evidence={"avg_delay_minutes": v, "sample_size": n}, confidence=conf,
        limitations="Averages hide variance; a few outliers may dominate.")
    ) if v > t["avg_delay_minutes_max"] else None)

    # Rank recommendations by confidence so the most-evidenced surface first.
    order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: order.get(r.get("confidence", "low"), 3))
    return {
        "recommendations": recs,
        "evaluated": sorted(evaluated),
        "skipped": sorted(skipped),
        "note": oc.calculated(len(recs), "Advisory recommendations — never auto-applied."),
    }
