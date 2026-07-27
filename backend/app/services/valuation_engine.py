"""
Greena — Valuation Engine (Module 15, Part 7)

A PURE, deterministic engine for collection valuation (Doc 03 §9, Doc 13 Part 7).
It does NOT duplicate the Greena Finance engine — expenses and revenue stay in
the shared finance ledger. This engine only aggregates **recorded** per-bird
values into a collection value, honesty-labelled.

A bird's value is the best available *recorded* figure, in priority order:
  recorded appraised/market/insured/breeding valuation  →  sale price (if sold)
  →  purchase price  →  unknown (never invented, Doc 04 §19).

Birds with no recorded basis are excluded from the total and reported as such;
the collection value is a calculation over recorded facts, never a guess.
"""

from __future__ import annotations

from decimal import Decimal

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"

# Manual valuation methods, most-authoritative first (all recorded facts).
_MANUAL_METHODS = ("appraised", "insured", "market", "breeding_value")


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def bird_value(
    valuations: list[dict],
    *,
    purchase_amount: Decimal | float | None = None,
    sale_amount: Decimal | float | None = None,
) -> dict:
    """Best-available recorded value for one bird.

    ``valuations``: each {"method", "amount", "valued_on"}. Returns
    {value, basis, label} — ``label`` is ``recorded`` when a basis exists, else
    ``unknown``. Nothing is fabricated for a bird with no recorded basis.
    """
    manual = [v for v in valuations if v.get("method") in _MANUAL_METHODS and v.get("amount") is not None]
    if manual:
        latest = max(manual, key=lambda v: v.get("valued_on") or "")
        return {"value": float(latest["amount"]), "basis": latest["method"], "label": RECORDED}
    if sale_amount is not None:
        return {"value": float(sale_amount), "basis": "sale", "label": RECORDED}
    if purchase_amount is not None:
        return {"value": float(purchase_amount), "basis": "purchase", "label": RECORDED}
    return {"value": None, "basis": None, "label": UNKNOWN}


def collection_valuation(bird_values: list[dict]) -> dict:
    """Aggregate per-bird recorded values into a collection value.

    ``bird_values``: output of :func:`bird_value` per bird. The total is a
    calculation over the *valued* birds; unvalued birds are counted and flagged
    as a limitation rather than assigned a fabricated value.
    """
    valued = [b for b in bird_values if b.get("value") is not None]
    total = round(sum(b["value"] for b in valued), 2)
    by_basis: dict[str, float] = {}
    for b in valued:
        by_basis[b["basis"]] = round(by_basis.get(b["basis"], 0.0) + b["value"], 2)

    unvalued = len(bird_values) - len(valued)
    detail = "Sum of best-available recorded per-bird values."
    if unvalued:
        detail += f" {unvalued} bird(s) have no recorded value and are excluded."

    return {
        "total_value": _lbl(CALCULATED if valued else UNKNOWN, total if valued else None, detail),
        "birds_valued": _lbl(RECORDED, len(valued)),
        "birds_unvalued": _lbl(RECORDED, unvalued),
        "by_basis": by_basis,
    }


def finance_summary(
    *,
    sale_income: Decimal | float,
    purchase_costs: Decimal | float,
    operational_expenses: Decimal | float,
    collection_value: dict,
) -> dict:
    """Deterministic aviculture P&L view over recorded facts. Income and purchase
    costs come from recorded sale/purchase events; operational expenses from the
    shared finance ledger. Net is a calculation; the collection value is carried
    through with its own label."""
    income = float(sale_income or 0)
    purchases = float(purchase_costs or 0)
    opex = float(operational_expenses or 0)
    net = round(income - purchases - opex, 2)
    return {
        "sale_income": _lbl(RECORDED, round(income, 2), "Sum of recorded bird-sale amounts."),
        "purchase_costs": _lbl(RECORDED, round(purchases, 2), "Sum of recorded bird-purchase amounts."),
        "operational_expenses": _lbl(RECORDED, round(opex, 2),
                                     "Aviculture-attributed expenses from the shared finance ledger."),
        "net": _lbl(CALCULATED, net, "sale income − purchase costs − operational expenses."),
        "collection_value": collection_value.get("total_value"),
    }
