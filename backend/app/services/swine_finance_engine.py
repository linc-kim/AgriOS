"""
Greena — Swine Finance Engine (Module 20, Milestone 8)

A PURE, deterministic engine: P&L and unit economics over recorded revenue and cost
facts. No I/O, no mutation. Revenue and costs are recorded facts; gross margin, ROI
and per-unit costs are CALCULATIONS — nothing is stored as a competing snapshot, and
a zero denominator yields ``unknown`` rather than a fabricated ratio. The shape is
species-neutral so it can back a shared production-finance engine for the other
livestock modules.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def _ratio(num: Decimal, den: Decimal, detail: str, pct: bool = False, places: str = "0.01") -> dict:
    if den == 0:
        return _lab(UNKNOWN, None, "No denominator recorded yet.")
    val = (num / den) * (Decimal("100") if pct else Decimal("1"))
    return _lab(CALCULATED, float(val.quantize(Decimal(places))), detail)


def pnl_summary(*, revenue, revenue_events: int, feed_cost, feed_events: int,
                operating_cost, operating_entries: int, currency: str | None = None) -> dict:
    """Deterministic P&L. Revenue = Σ recorded sale facts (external sales only); feed
    cost = recorded consumption allocation (already expensed at Inventory stock-in);
    operating cost = swine-tagged shared-ledger expenses. Gross/margin/ROI are
    calculated from these traceable sources — never persisted."""
    rev = _d(revenue)
    feed = _d(feed_cost)
    op = _d(operating_cost)
    total_cost = feed + op
    gross = rev - total_cost
    return {
        "currency": currency,
        "revenue": _lab(RECORDED, float(rev), f"Σ {revenue_events} recorded external sale(s)."),
        "feed_cost": _lab(RECORDED, float(feed), f"Σ {feed_events} recorded feed allocation(s) — from feed records."),
        "operating_cost": _lab(RECORDED, float(op), f"Σ {operating_entries} tagged ledger expense(s)."),
        "total_cost": _lab(CALCULATED, float(total_cost), "feed_cost + operating_cost."),
        "gross_margin": _lab(CALCULATED, float(gross), "revenue − total_cost."),
        "gross_margin_pct": _ratio(gross, rev, "gross_margin ÷ revenue × 100.", pct=True, places="0.1"),
        "roi_pct": _ratio(gross, total_cost, "gross_margin ÷ total_cost × 100.", pct=True, places="0.1"),
    }


def unit_economics(*, revenue, total_cost, feed_cost, health_cost, pig_count: int,
                   sold_weight_kg=None, sold_head: int = 0) -> dict:
    """Deterministic per-unit production costs. Only computed where the denominator is
    a recorded positive count/quantity; otherwise ``unknown``."""
    rev = _d(revenue)
    cost = _d(total_cost)
    return {
        "cost_per_pig": _ratio(cost, Decimal(pig_count), "total_cost ÷ live pigs."),
        "revenue_per_pig": _ratio(rev, Decimal(pig_count), "revenue ÷ live pigs."),
        "cost_per_kg_sold": (_ratio(cost, _d(sold_weight_kg), "total_cost ÷ kg sold.")
                             if sold_weight_kg else _lab(UNKNOWN, None, "No sold weight recorded.")),
        "revenue_per_head_sold": (_ratio(rev, Decimal(sold_head), "revenue ÷ head sold.")
                                  if sold_head else _lab(UNKNOWN, None, "No head sold recorded.")),
        "feed_cost_pct": _ratio(_d(feed_cost), cost, "feed_cost ÷ total_cost × 100.", pct=True, places="0.1"),
        "health_cost_pct": _ratio(_d(health_cost), cost, "health_cost ÷ total_cost × 100.", pct=True, places="0.1"),
    }
