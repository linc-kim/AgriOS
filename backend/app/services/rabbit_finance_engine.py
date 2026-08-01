"""
Greena — Rabbit Finance Engine (Module 17, Milestone 6)

A PURE, deterministic engine (Spec Part 4 §12, Part 7 §9). It assembles the
rabbit P&L and unit economics from figures the service has already read from
recorded facts. It performs only arithmetic — never queries, never invents a
number.

Traceability & honesty (ledger CON-M6-4):
  * CONFIRMED figures — sale revenue, feed-consumption cost, operating cost — are
    RECORDED facts (from ``rabbit_sale.total_price``, ``rabbit_feed_record.cost``
    and the rabbit-tagged shared ``expenses`` ledger). They are echoed ``recorded``
    with their source counts.
  * DERIVED figures — total cost, gross profit, margin, ROI, cost/profit per
    rabbit / litter / doe / kg, cost shares — are ``calculated`` strictly from
    those inputs and cite their formula.
  * Zero denominators yield ``unknown`` — a ratio is never fabricated.
Projections belong to the Forecast engine (a later milestone), never here, so
confirmed records and forecasts are never conflated (Spec Part 9 §17).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value) -> Decimal:
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def _ratio(num: Decimal, den: Decimal, detail: str, nd: int = 2) -> dict:
    if den <= 0:
        return _lbl(UNKNOWN, None, "No denominator recorded yet.")
    return _lbl(CALCULATED, float(round(num / den, nd)), detail)


def pnl_summary(
    *,
    revenue,
    revenue_events: int,
    feed_cost,
    feed_events: int,
    operating_cost,
    operating_entries: int,
    currency: str | None = None,
) -> dict:
    """Confirmed rabbit P&L. Feed cost is the recorded consumption allocation
    (ledger CON-M6-3, already expensed at purchase — not re-posted); operating
    cost is the rabbit-tagged shared-ledger sum; revenue is recorded sale facts."""
    rev = _dec(revenue)
    feed = _dec(feed_cost)
    opex = _dec(operating_cost)
    total_cost = feed + opex
    gross = rev - total_cost

    summary = {
        "currency": currency,
        "revenue": _lbl(RECORDED, float(round(rev, 2)),
                        f"Sum of {revenue_events} recorded sale revenue fact(s)."),
        "feed_cost": _lbl(RECORDED, float(round(feed, 2)),
                          f"Sum of {feed_events} recorded feed-consumption allocation(s)."),
        "operating_cost": _lbl(RECORDED, float(round(opex, 2)),
                               f"Sum of {operating_entries} rabbit-tagged shared-ledger expense(s)."),
        "total_cost": _lbl(CALCULATED, float(round(total_cost, 2)), "feed cost + operating cost."),
        "gross_profit": _lbl(CALCULATED, float(round(gross, 2)), "revenue − total cost."),
        "gross_margin_pct": (
            _lbl(CALCULATED, float(round(gross / rev * Decimal(100), 2)), "gross profit ÷ revenue.")
            if rev > 0 else _lbl(UNKNOWN, None, "No recorded revenue.")
        ),
        "roi_pct": (
            _lbl(CALCULATED, float(round(gross / total_cost * Decimal(100), 2)), "gross profit ÷ total cost.")
            if total_cost > 0 else _lbl(UNKNOWN, None, "No recorded cost.")
        ),
    }
    return summary


def unit_economics(
    *,
    revenue,
    total_cost,
    feed_cost,
    vet_cost,
    rabbit_count: int,
    sold_weight_kg,
    litters: int,
    breeding_does: int,
) -> dict:
    """Per-unit economics (Spec Part 7 §9). Every figure is calculated from
    recorded inputs; unknown when its denominator is zero."""
    rev = _dec(revenue)
    total = _dec(total_cost)
    feed = _dec(feed_cost)
    vet = _dec(vet_cost)
    gross = rev - total
    weight = _dec(sold_weight_kg)

    return {
        "cost_per_rabbit": _ratio(total, Decimal(rabbit_count), "total cost ÷ rabbits recorded."),
        "revenue_per_rabbit": _ratio(rev, Decimal(rabbit_count), "revenue ÷ rabbits recorded."),
        "profit_per_rabbit": _ratio(gross, Decimal(rabbit_count), "gross profit ÷ rabbits recorded."),
        "cost_per_kg_sold": _ratio(total, weight, "total cost ÷ sold live-weight (kg).", nd=4),
        "profit_per_litter": _ratio(gross, Decimal(litters), "gross profit ÷ litters recorded."),
        "profit_per_breeding_doe": _ratio(gross, Decimal(breeding_does), "gross profit ÷ breeding does."),
        "feed_cost_pct": _ratio(feed * Decimal(100), total, "feed cost ÷ total cost × 100."),
        "vet_cost_pct": _ratio(vet * Decimal(100), total, "veterinary cost ÷ total cost × 100."),
    }
