"""
Greena — BSF Finance Engine (Module 16, Part 5)

A PURE, deterministic engine (Spec Part 4 §16, Part 7 §10). Assembles the BSF
P&L view from figures the service has already read from stored facts. It performs
only arithmetic — it never queries, and it never invents a number.

Traceability & honesty (per the module discipline):
  * CONFIRMED figures — revenue and operating cost — are RECORDED facts sourced
    from ``bsf_harvest_event.revenue_amount`` and the shared ``expenses`` ledger.
    They are passed in and echoed with the ``recorded`` label and their source
    counts.
  * DERIVED figures — gross profit, margin, cost per kg, ROI — are ``calculated``
    strictly from those confirmed inputs and cite their formula.
  * PROJECTIONS are never produced here (they are ``forecast`` in the Forecast
    engine) so confirmed records and estimates are never conflated (Spec Part 1
    §8, Part 9 §17).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value) -> Decimal:
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def pnl_summary(
    *,
    revenue,
    revenue_events: int,
    operating_cost,
    cost_entries: int,
    harvested_kg,
    currency: str | None = None,
) -> dict:
    """Compute the confirmed BSF P&L. All inputs are recorded facts read by the
    service; outputs distinguish confirmed records from calculated derivations."""
    rev = _dec(revenue)
    cost = _dec(operating_cost)
    harvested = _dec(harvested_kg)
    gross = rev - cost

    summary = {
        "currency": currency,
        "revenue": _lbl(RECORDED, float(round(rev, 2)),
                        f"Sum of {revenue_events} recorded harvest revenue fact(s)."),
        "operating_cost": _lbl(RECORDED, float(round(cost, 2)),
                               f"Sum of {cost_entries} BSF-tagged expense(s) in the shared ledger."),
        "gross_profit": _lbl(CALCULATED, float(round(gross, 2)), "revenue − operating cost."),
    }
    # Margin.
    if rev > 0:
        summary["gross_margin_pct"] = _lbl(
            CALCULATED, float(round((gross / rev) * Decimal(100), 2)), "gross profit ÷ revenue.")
    else:
        summary["gross_margin_pct"] = _lbl(UNKNOWN, None, "No recorded revenue.")
    # Cost per kg produced.
    if harvested > 0:
        summary["cost_per_kg"] = _lbl(
            CALCULATED, float(round(cost / harvested, 4)), "operating cost ÷ recorded harvested mass.")
    else:
        summary["cost_per_kg"] = _lbl(UNKNOWN, None, "No recorded harvested mass.")
    # Return on cost.
    if cost > 0:
        summary["roi_pct"] = _lbl(
            CALCULATED, float(round((gross / cost) * Decimal(100), 2)), "gross profit ÷ operating cost.")
    else:
        summary["roi_pct"] = _lbl(UNKNOWN, None, "No recorded operating cost.")
    summary["harvested_kg"] = _lbl(RECORDED, float(round(harvested, 3)),
                                   "Sum of recorded harvest quantities.")
    return summary
