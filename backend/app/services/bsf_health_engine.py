"""
Greena — BSF Health Monitoring Engine (Module 16, Part 5)

A PURE, deterministic engine (Spec Part 4 §15). Computes mortality rate and trend
and flags abnormal operational patterns. **It does not diagnose disease** — it
identifies patterns requiring attention (Spec Part 4 §15). No I/O, no mutation.

Every output is honesty-labelled; missing inputs yield ``unknown`` rather than a
guess. Any flag carries a disclaimer that it is an operational pattern, not a
veterinary diagnosis.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

_DISCLAIMER = "Operational pattern only — not a veterinary diagnosis."
# Cumulative loss above this share of the initial population is flagged for review.
_ABNORMAL_MORTALITY_PCT = Decimal("20")


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def mortality_rate_pct(total_loss: int | None, initial_population: int | None) -> dict:
    """Cumulative mortality = total loss ÷ initial population × 100."""
    if not initial_population or initial_population <= 0 or total_loss is None:
        return _lbl(UNKNOWN, None, "Requires recorded total loss and initial population.")
    pct = (Decimal(total_loss) / Decimal(initial_population)) * Decimal(100)
    pct = max(Decimal(0), min(pct, Decimal(100)))
    return _lbl(CALCULATED, float(round(pct, 2)), "total recorded loss ÷ initial population.")


def mortality_trend(loss_series: list[int | None]) -> dict:
    """Direction of mortality across ordered recorded events. Needs ≥2 points."""
    points = [p for p in loss_series if p is not None]
    if len(points) < 2:
        return _lbl(UNKNOWN, None, "Need at least two recorded mortality events to assess a trend.")
    first_half = points[: len(points) // 2] or points[:1]
    second_half = points[len(points) // 2:]
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    if avg_second > avg_first:
        direction = "rising"
    elif avg_second < avg_first:
        direction = "falling"
    else:
        direction = "stable"
    return _lbl(CALCULATED, direction,
                f"Mean recorded loss moved from {round(avg_first, 1)} to {round(avg_second, 1)} per event.")


def health_flag(total_loss: int | None, initial_population: int | None) -> dict:
    """Deterministic health flag from cumulative mortality (never a diagnosis)."""
    rate = mortality_rate_pct(total_loss, initial_population)
    if rate["label"] == UNKNOWN:
        return _lbl(UNKNOWN, "unknown", f"Insufficient data. {_DISCLAIMER}")
    value = _dec(rate["value"])
    if value is not None and value >= _ABNORMAL_MORTALITY_PCT:
        return _lbl(CALCULATED, "attention",
                    f"Cumulative mortality {rate['value']}% ≥ {int(_ABNORMAL_MORTALITY_PCT)}% review "
                    f"threshold. {_DISCLAIMER}")
    return _lbl(CALCULATED, "normal", f"Cumulative mortality {rate['value']}% within range. {_DISCLAIMER}")


def health_summary(total_loss: int | None, initial_population: int | None,
                  loss_series: list[int | None]) -> dict:
    """Compose the batch health picture (Spec Part 4 §15)."""
    return {
        "mortality_rate_pct": mortality_rate_pct(total_loss, initial_population),
        "mortality_trend": mortality_trend(loss_series),
        "flag": health_flag(total_loss, initial_population),
        "total_loss": _lbl(RECORDED if total_loss is not None else UNKNOWN, total_loss,
                           "Sum of recorded mortality events."),
    }
