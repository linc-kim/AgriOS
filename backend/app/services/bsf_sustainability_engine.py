"""
Greena — BSF Sustainability Engine (Module 16, Part 5)

A PURE, deterministic engine (Spec Part 4 §14, Part 7 §20). Computes the module's
sustainability metrics from recorded facts: organic waste diverted, waste-
conversion efficiency, resource efficiency and circular-economy contribution.

No I/O, no mutation. Recorded facts (waste diverted = feed consumed) are labelled
``recorded``; ratios are ``calculated``; anything requiring an unrecorded input is
``unknown``. Estimated values are always identified as estimates (Spec Part 7 §20)
— nothing is fabricated.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
ESTIMATE = "estimate"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def organic_waste_diverted_kg(feed_consumed_kg) -> dict:
    """Organic waste diverted from landfill = recorded feedstock consumed."""
    feed = _dec(feed_consumed_kg)
    if feed is None:
        return _lbl(UNKNOWN, None, "No recorded feedstock consumption.")
    return _lbl(RECORDED, float(round(feed, 3)), "Total recorded feedstock processed.")


def waste_conversion_efficiency_pct(feed_consumed_kg, biomass_kg, frass_kg) -> dict:
    """Share of input mass recovered as products = (biomass + frass) ÷ feed × 100."""
    feed = _dec(feed_consumed_kg)
    biomass = _dec(biomass_kg) or Decimal(0)
    frass = _dec(frass_kg) or Decimal(0)
    if feed is None or feed <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded feed consumed (>0).")
    recovered = biomass + frass
    return _lbl(CALCULATED, float(round((recovered / feed) * Decimal(100), 2)),
                "(harvested biomass + frass) ÷ feed consumed.")


def resource_efficiency_kg_per_kg(biomass_kg, feed_consumed_kg) -> dict:
    """Product biomass yielded per kg of organic waste input."""
    feed = _dec(feed_consumed_kg)
    biomass = _dec(biomass_kg)
    if feed is None or feed <= 0 or biomass is None:
        return _lbl(UNKNOWN, None, "Requires recorded biomass and feed consumed.")
    return _lbl(CALCULATED, float(round(biomass / feed, 4)), "harvested biomass ÷ feed consumed.")


def carbon_diversion_estimate_kg(feed_consumed_kg, factor=None) -> dict:
    """OPTIONAL CO2e-diversion ESTIMATE = waste diverted × emission factor.

    Always an ESTIMATE, never a recorded fact — and only when a factor is
    provided; otherwise ``unknown`` (no fabricated emission factor). Spec Part 4
    §14 ("carbon impact estimates, if supported"), Part 7 §20.
    """
    feed = _dec(feed_consumed_kg)
    f = _dec(factor)
    if feed is None or f is None or f <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded waste diverted and an explicit emission factor.")
    return _lbl(ESTIMATE, float(round(feed * f, 3)),
                "waste diverted × supplied emission factor — an estimate, not a measurement.")


def sustainability_summary(feed_consumed_kg, biomass_kg, frass_kg, carbon_factor=None) -> dict:
    """Compose the sustainability picture from recorded facts (Spec Part 7 §20)."""
    return {
        "organic_waste_diverted_kg": organic_waste_diverted_kg(feed_consumed_kg),
        "waste_conversion_efficiency_pct": waste_conversion_efficiency_pct(feed_consumed_kg, biomass_kg, frass_kg),
        "resource_efficiency_kg_per_kg": resource_efficiency_kg_per_kg(biomass_kg, feed_consumed_kg),
        "carbon_diversion_estimate_kg": carbon_diversion_estimate_kg(feed_consumed_kg, carbon_factor),
    }
