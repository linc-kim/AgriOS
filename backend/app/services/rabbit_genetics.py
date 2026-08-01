"""
Greena — Rabbit Genetics (Module 17, Milestone 3)

A thin, PURE rabbit-domain layer over the shared platform
:mod:`app.services.pedigree_engine` (built for Aviculture, Module 15 Part 4).
The correctness-critical genetics math — Wright's inbreeding ``F``, coefficient of
relationship, ancestry, founders, cycle safety — is **reused, not reimplemented**
(ledger CON-M3-1). This module only adds rabbit-domain semantics: buck/doe sex
checks (the shared engine speaks male/female — CON-M3-2), rabbit-worded findings,
and inbreeding-risk banding.

Inputs use the same plain ``parents`` map ``{rabbit_id: (sire_id, dam_id)}`` so
the layer stays free of the database. Every outward value is honesty-labelled and
genetic outcomes are *forecasts* (probabilities), never guarantees.
"""

from __future__ import annotations

from typing import Hashable

from app.services import pedigree_engine as pe

# Reuse the shared honesty vocabulary.
RECORDED = pe.RECORDED
CALCULATED = pe.CALCULATED
FORECAST = pe.FORECAST
RECOMMENDATION = pe.RECOMMENDATION
UNKNOWN = pe.UNKNOWN

# Offspring inbreeding-coefficient (F) risk bands for rabbits.
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


# ── Pedigree tree (reuses pe.build_ancestry + pe.inbreeding_coefficient) ────────

def pedigree_tree(rabbit_id: Hashable, parents: pe.ParentMap, max_generations: int = 4) -> dict:
    """Ancestry tree plus Wright's inbreeding coefficient F for the rabbit.

    Unknown ancestry is surfaced, never invented (Spec Part 3 §6). F is a
    calculated value; it is 0 when either parent is unknown."""
    f = pe.inbreeding_coefficient(rabbit_id, parents)
    m_sire, m_dam = parents.get(rabbit_id, (None, None))
    known_parents = m_sire is not None or m_dam is not None
    return {
        "rabbit_id": rabbit_id,
        "ancestry": pe.build_ancestry(rabbit_id, parents, max_generations=max_generations),
        "inbreeding_coefficient": {
            "label": CALCULATED if known_parents else UNKNOWN,
            "value": f,
            "detail": "Wright's F — probability two alleles are identical by descent. "
                      "0 when a parent is unknown (a floor, not proof of no inbreeding).",
        },
        "founders": [str(x) for x in pe.founders(rabbit_id, parents)],
    }


# ── Pairing assessment (rabbit buck/doe semantics; reuses pe.relatedness) ───────

def assess_pairing(buck: dict, doe: dict, parents: pe.ParentMap) -> dict:
    """Deterministic breeding-compatibility assessment for a candidate buck × doe.

    ``buck``/``doe``: {"id","sex"} recorded facts. Relatedness and expected
    offspring inbreeding are reused from the shared engine; the sex check uses
    rabbit terms. Warnings are recommendations, the inbreeding figure is a
    forecast, and confidence drops when ancestry is unknown. Never a guarantee.
    """
    bid, did = buck.get("id"), doe.get("id")

    if bid is not None and bid == did:
        return {
            "compatible": False, "blocking": True, "risk_level": "invalid",
            "warnings": [{"label": RECOMMENDATION, "code": "same_rabbit",
                          "detail": "A rabbit cannot be paired with itself."}],
            "relationship_coefficient": {"label": RECORDED, "value": 1.0},
            "offspring_inbreeding": {"label": UNKNOWN, "value": None},
            "confidence": "high", "limitations": [],
        }

    warnings: list[dict] = []
    blocking = False
    if buck.get("sex") != "buck" or doe.get("sex") != "doe":
        blocking = True
        warnings.append({"label": RECOMMENDATION, "code": "sex_mismatch",
                         "detail": "A mating requires a buck (sire) and a doe (dam)."})

    r = pe.relatedness(bid, did, parents) if (bid is not None and did is not None) else 0.0
    offspring_f = round(r / 2.0, 6)  # F(offspring) = kinship(sire, dam) = relatedness / 2
    risk = _risk_band(offspring_f)
    if risk in ("high", "moderate"):
        warnings.append({"label": RECOMMENDATION, "code": f"inbreeding_{risk}",
                         "detail": f"Relatedness {r:.3f} → expected offspring inbreeding F ≈ "
                                   f"{offspring_f:.3f} ({risk} risk). Consider an out-cross."})

    limitations: list[str] = []
    b_known = any(p is not None for p in parents.get(bid, (None, None)))
    d_known = any(p is not None for p in parents.get(did, (None, None)))
    if not b_known or not d_known:
        limitations.append("One or both rabbits have unknown parents — relatedness is a floor, not a ceiling.")
    confidence = "low" if (not b_known and not d_known) else ("medium" if (not b_known or not d_known) else "high")

    return {
        "compatible": not blocking and risk != "high",
        "blocking": blocking,
        "risk_level": risk,
        "relationship_coefficient": {"label": CALCULATED, "value": r,
                                     "detail": "Wright's coefficient of relationship (2 × kinship)."},
        "offspring_inbreeding": {"label": FORECAST, "value": offspring_f,
                                 "detail": "Expected inbreeding coefficient F of offspring = kinship(buck, doe). "
                                           "A probability, never a guarantee."},
        "warnings": warnings,
        "confidence": confidence,
        "limitations": limitations,
    }


def would_create_cycle(rabbit_id: Hashable, proposed_parent: Hashable, parents: pe.ParentMap) -> bool:
    """Reuse the shared cycle guard for pedigree-link corrections."""
    return pe.would_create_cycle(rabbit_id, proposed_parent, parents)
