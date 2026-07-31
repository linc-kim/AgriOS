"""
Greena — BSF Environment Engine (Module 16, Part 3)

A PURE, deterministic engine (Spec Part 4 §10). Assesses recorded environmental
readings (temperature, humidity, moisture, airflow) against a species' recommended
ranges and flags threshold violations with a severity. It also summarises
environmental stability over a series of readings.

No I/O, no mutation. The engine only *detects*; emitting Reminder/Notification
alerts is the caller's job (Spec Part 4 §10) — centralised in the BSF automation
layer. Recommended ranges are read from the species ``profile`` (Spec Part 3 §5);
when a range is absent the parameter is reported ``unknown`` and never judged
against a fabricated threshold (Spec Part 9 §17-19).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from statistics import pstdev

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

# Parameter → (reading field, profile min key, profile max key, unit).
_PARAMETERS = {
    "temperature": ("temperature_c", "temp_min_c", "temp_max_c", "°C"),
    "humidity": ("humidity_pct", "humidity_min_pct", "humidity_max_pct", "%"),
    "moisture": ("moisture_pct", "moisture_min_pct", "moisture_max_pct", "%"),
    "airflow": ("airflow_mps", "airflow_min_mps", "airflow_max_mps", "m/s"),
}


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _env_block(profile: dict | None) -> dict:
    if not isinstance(profile, dict):
        return {}
    for key in ("environment", "environmental_ranges", "conditions"):
        block = profile.get(key)
        if isinstance(block, dict) and block:
            return block
    return profile if isinstance(profile, dict) else {}


def assess_reading(profile: dict | None, reading: dict) -> dict:
    """Assess one reading against the species' recommended ranges.

    ``reading`` is a mapping with keys ``temperature_c``/``humidity_pct``/
    ``moisture_pct``/``airflow_mps`` (any may be missing). Returns per-parameter
    status and a list of violations, each with a severity.
    """
    env = _env_block(profile)
    parameters: dict[str, dict] = {}
    violations: list[dict] = []

    for name, (field, min_key, max_key, unit) in _PARAMETERS.items():
        value = _num(reading.get(field))
        lo = _num(env.get(min_key))
        hi = _num(env.get(max_key))

        if value is None:
            parameters[name] = _lbl(UNKNOWN, None, "Not recorded in this reading.")
            continue
        if lo is None and hi is None:
            parameters[name] = _lbl(RECORDED, value, "Recorded; no recommended range for this species.")
            continue

        status = "ok"
        detail = "Within the recommended range for this species."
        if lo is not None and value < lo:
            status = "below"
            deviation = lo - value
            severity = _severity(deviation, lo, hi)
            detail = f"{value}{unit} is below the recommended minimum {lo}{unit}."
            violations.append({"parameter": name, "status": status, "severity": severity,
                               "value": value, "min": lo, "max": hi, "unit": unit, "detail": detail})
        elif hi is not None and value > hi:
            status = "above"
            deviation = value - hi
            severity = _severity(deviation, lo, hi)
            detail = f"{value}{unit} is above the recommended maximum {hi}{unit}."
            violations.append({"parameter": name, "status": status, "severity": severity,
                               "value": value, "min": lo, "max": hi, "unit": unit, "detail": detail})
        parameters[name] = _lbl(CALCULATED if status != "ok" else RECORDED, status, detail)

    overall = "ok"
    if any(v["severity"] == "critical" for v in violations):
        overall = "critical"
    elif violations:
        overall = "warning"
    return {"overall": overall, "parameters": parameters, "violations": violations}


def _severity(deviation: float, lo: float | None, hi: float | None) -> str:
    """Deterministic severity from how far a value sits outside its band.

    ``critical`` when the deviation exceeds ~25% of the band width (or 25% of the
    breached bound when only one bound is set); otherwise ``warning``.
    """
    if lo is not None and hi is not None and hi > lo:
        band = hi - lo
        return "critical" if deviation > 0.25 * band else "warning"
    bound = hi if hi is not None else lo
    if bound:
        return "critical" if deviation > 0.25 * abs(bound) else "warning"
    return "warning"


def stability(readings: list[dict], field: str) -> dict:
    """Population standard deviation of one parameter across readings (Spec
    Part 7 §9 environmental stability). Lower = more stable."""
    values = [_num(r.get(field)) for r in readings]
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return _lbl(UNKNOWN, None, "Need at least two recorded values to assess stability.")
    return _lbl(CALCULATED, round(pstdev(values), 3),
                f"Population standard deviation over {len(values)} readings; lower is more stable.")
