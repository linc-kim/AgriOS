"""
Greena — Swine Genetics (Module 20, Milestone 3)

A thin, PURE layer over the shared platform :mod:`app.services.pedigree_engine`
(built for Aviculture, reused by Rabbit and Small Ruminant). The correctness-
critical genetics math — Wright's inbreeding ``F``, coefficient of relationship,
ancestry, founders, cycle safety — is **reused, not reimplemented**. This module
only adds swine domain semantics: the sex check maps each pig's class token
(boar/sow/gilt/barrow) to a breeding role via :mod:`swine_config`, so a "sire must
be an intact boar, dam must be a breeding female" rule is expressed once.

Inputs use the plain ``parents`` map ``{pig_id: (sire_id, dam_id)}`` so the layer
stays free of the database. Every outward value is honesty-labelled and genetic
outcomes are *forecasts* (probabilities), never guarantees.
"""

from __future__ import annotations

from typing import Hashable

from app.services import pedigree_engine as pe
from app.services import swine_config as cfg

RECORDED = pe.RECORDED
CALCULATED = pe.CALCULATED
FORECAST = pe.FORECAST
RECOMMENDATION = pe.RECOMMENDATION
UNKNOWN = pe.UNKNOWN

# Offspring inbreeding-coefficient (F) risk bands (same thresholds as other species).
_F_HIGH = 0.25       # full-sib / parent–offspring mating
_F_MODERATE = 0.125  # half-sib mating
_F_LOW = 0.0625      # first cousins


def _risk_band(offspring_f: float) -> str:
    if offspring_f >= _F_HIGH:
        return "high"
    if offspring_f >= _F_MODERATE:
        return "moderate"
    if offspring_f >= _F_LOW:
        return "low"
    return "minimal"


def pedigree_tree(pig_id: Hashable, parents: pe.ParentMap, max_generations: int = 5) -> dict:
    """Ancestry tree plus Wright's inbreeding coefficient F for the pig.

    Unknown ancestry is surfaced, never invented (Swine Doc 2 §18). F is 0 when
    either parent is unknown (a floor, not proof of no inbreeding)."""
    f = pe.inbreeding_coefficient(pig_id, parents)
    sire, dam = parents.get(pig_id, (None, None))
    known_parents = sire is not None or dam is not None
    return {
        "pig_id": pig_id,
        "ancestry": pe.build_ancestry(pig_id, parents, max_generations=max_generations),
        "inbreeding_coefficient": {
            "label": CALCULATED if known_parents else UNKNOWN,
            "value": f,
            "detail": "Wright's F — probability two alleles are identical by descent. "
                      "0 when a parent is unknown (a floor, not proof of no inbreeding).",
        },
        "founders": [str(x) for x in pe.founders(pig_id, parents)],
    }


def assess_pairing(sire: dict, dam: dict, parents: pe.ParentMap) -> dict:
    """Deterministic breeding-compatibility assessment for a candidate boar × dam.

    ``sire``/``dam``: {"id","sex"} recorded facts. A mating requires an intact
    **boar** and a breeding female (**sow** or **gilt**) — a barrow is never a valid
    sire. Relatedness and expected offspring inbreeding are reused from the shared
    engine. Warnings are recommendations, the inbreeding figure is a forecast, and
    confidence drops when ancestry is unknown. Never a guarantee.
    """
    sid, did = sire.get("id"), dam.get("id")

    if sid is not None and sid == did:
        return {
            "compatible": False, "blocking": True, "risk_level": "invalid",
            "warnings": [{"label": RECOMMENDATION, "code": "same_animal",
                          "detail": "A pig cannot be paired with itself."}],
            "relationship_coefficient": {"label": RECORDED, "value": 1.0},
            "offspring_inbreeding": {"label": UNKNOWN, "value": None},
            "confidence": "high", "limitations": [],
        }

    warnings: list[dict] = []
    blocking = False
    if not cfg.is_intact_male(sire.get("sex")) or not cfg.is_breeding_female(dam.get("sex")):
        blocking = True
        warnings.append({"label": RECOMMENDATION, "code": "sex_mismatch",
                         "detail": "A mating requires an intact boar (sire) and a sow or gilt (dam)."})

    r = pe.relatedness(sid, did, parents) if (sid is not None and did is not None) else 0.0
    offspring_f = round(r / 2.0, 6)  # F(offspring) = kinship(sire, dam) = relatedness / 2
    risk = _risk_band(offspring_f)
    if risk in ("high", "moderate"):
        warnings.append({"label": RECOMMENDATION, "code": f"inbreeding_{risk}",
                         "detail": f"Relatedness {r:.3f} → expected offspring inbreeding F ≈ "
                                   f"{offspring_f:.3f} ({risk} risk). Consider an out-cross."})

    limitations: list[str] = []
    s_known = any(p is not None for p in parents.get(sid, (None, None)))
    d_known = any(p is not None for p in parents.get(did, (None, None)))
    if not s_known or not d_known:
        limitations.append("One or both pigs have unknown parents — relatedness is a floor, not a ceiling.")
    confidence = "low" if (not s_known and not d_known) else ("medium" if (not s_known or not d_known) else "high")

    return {
        "compatible": not blocking and risk != "high",
        "blocking": blocking,
        "risk_level": risk,
        "relationship_coefficient": {"label": CALCULATED, "value": r,
                                     "detail": "Wright's coefficient of relationship (2 × kinship)."},
        "offspring_inbreeding": {"label": FORECAST, "value": offspring_f,
                                 "detail": "Expected inbreeding coefficient F of offspring = kinship(sire, dam). "
                                           "A probability, never a guarantee."},
        "warnings": warnings,
        "confidence": confidence,
        "limitations": limitations,
    }
