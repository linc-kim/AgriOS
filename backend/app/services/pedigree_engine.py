"""
Greena — Pedigree & Breeding Engine (Module 15, Part 4)

A PURE, deterministic genetics engine (Doc 14 §2-3, Doc 04 §1). Given only
recorded parentage it computes ancestry, relatedness (Wright's coefficient),
inbreeding coefficients, cycle safety and pair compatibility. It performs no
I/O and no mutation, so the same inputs always yield the same result.

Constitutional guarantees honoured here (Doc 01 §12, Doc 04 §4, Doc 07 §12):
  * Unknown ancestry stays unknown — never invented.
  * No circular ancestry is ever produced (``would_create_cycle`` guards writes).
  * Every outward value is honesty-labelled; genetic outcomes are *calculated
    probabilities*, never guarantees.

Inputs use a plain ``parents`` map ``{bird_id: (sire_id | None, dam_id | None)}``
so the engine stays free of the database.
"""

from __future__ import annotations

from typing import Hashable

# Honesty labels (shared vocabulary with the aviary engine).
RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
RECOMMENDATION = "recommendation"
UNKNOWN = "unknown"

ParentMap = dict[Hashable, tuple]

# Relatedness (coefficient of relationship) risk thresholds.
_RISK_HIGH = 0.5      # full siblings, parent–offspring
_RISK_MODERATE = 0.25  # half siblings, grandparent–grandchild
_RISK_LOW = 0.0625     # first cousins and closer-than-random


def _parents(bird: Hashable, parents: ParentMap) -> tuple:
    sire, dam = parents.get(bird, (None, None))
    return sire, dam


# ── Ancestry ──────────────────────────────────────────────────────────────────

def collect_ancestors(bird: Hashable, parents: ParentMap) -> set:
    """All known ancestors of ``bird`` (excludes the bird). Cycle-safe."""
    seen: set = set()
    stack = [bird]
    while stack:
        cur = stack.pop()
        sire, dam = _parents(cur, parents)
        for p in (sire, dam):
            if p is not None and p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def build_ancestry(bird: Hashable, parents: ParentMap, max_generations: int = 5) -> dict:
    """Nested ancestry tree with generation depth. Unknown parents are surfaced
    as ``{"unknown": True}`` rather than omitted (Doc 04 §4)."""

    def _node(b: Hashable, gen: int) -> dict:
        if b is None:
            return {"unknown": True}
        if gen >= max_generations:
            sire, dam = _parents(b, parents)
            return {"id": b, "generation": gen,
                    "has_more": sire is not None or dam is not None}
        sire, dam = _parents(b, parents)
        return {
            "id": b,
            "generation": gen,
            "sire": _node(sire, gen + 1),
            "dam": _node(dam, gen + 1),
        }

    return _node(bird, 0)


def founders(bird: Hashable, parents: ParentMap) -> list:
    """Founder ancestors (individuals with no recorded parents) — the roots of a
    bird's bloodlines. Deterministic and order-stable."""
    result: set = set()
    for anc in ({bird} | collect_ancestors(bird, parents)):
        sire, dam = _parents(anc, parents)
        if sire is None and dam is None:
            result.add(anc)
    return sorted(result, key=str)


# ── Cycle safety ──────────────────────────────────────────────────────────────

def would_create_cycle(bird: Hashable, proposed_parent: Hashable, parents: ParentMap) -> bool:
    """True if assigning ``proposed_parent`` as a parent of ``bird`` would create
    circular ancestry — i.e. the bird is itself, or is an ancestor of the parent."""
    if proposed_parent is None:
        return False
    if proposed_parent == bird:
        return True
    return bird in collect_ancestors(proposed_parent, parents)


# ── Kinship / inbreeding / relatedness ────────────────────────────────────────

def _depth(bird: Hashable, parents: ParentMap, cache: dict) -> int:
    if bird is None:
        return -1
    if bird in cache:
        return cache[bird]
    sire, dam = _parents(bird, parents)
    d = 0 if (sire is None and dam is None) else 1 + max(_depth(sire, parents, cache), _depth(dam, parents, cache))
    cache[bird] = d
    return d


def _kinship(a, b, parents: ParentMap, kmemo: dict, fmemo: dict, dcache: dict) -> float:
    """Coancestry (kinship) coefficient f(a,b) via the recursive tabular method.
    Acyclic pedigree guarantees termination."""
    if a is None or b is None:
        return 0.0
    if a == b:
        return 0.5 * (1.0 + _inbreeding(a, parents, kmemo, fmemo, dcache))
    key = (a, b) if str(a) <= str(b) else (b, a)
    if key in kmemo:
        return kmemo[key]
    # Recurse on the parents of the deeper individual.
    if _depth(a, parents, dcache) < _depth(b, parents, dcache):
        a, b = b, a
    sire, dam = _parents(a, parents)
    val = 0.5 * (_kinship(sire, b, parents, kmemo, fmemo, dcache)
                 + _kinship(dam, b, parents, kmemo, fmemo, dcache))
    kmemo[key] = val
    return val


def _inbreeding(x, parents: ParentMap, kmemo: dict, fmemo: dict, dcache: dict) -> float:
    if x is None:
        return 0.0
    if x in fmemo:
        return fmemo[x]
    fmemo[x] = 0.0  # guard against self-reference during recursion
    sire, dam = _parents(x, parents)
    f = _kinship(sire, dam, parents, kmemo, fmemo, dcache) if (sire is not None and dam is not None) else 0.0
    fmemo[x] = f
    return f


def inbreeding_coefficient(bird: Hashable, parents: ParentMap) -> float:
    """Wright's inbreeding coefficient F — the probability that two alleles at a
    locus are identical by descent. 0 when either parent is unknown."""
    return round(_inbreeding(bird, parents, {}, {}, {}), 6)


def relatedness(a: Hashable, b: Hashable, parents: ParentMap) -> float:
    """Coefficient of relationship (additive relationship, 2·kinship). For
    non-inbred individuals: full sibs / parent-offspring ≈ 0.5, half sibs ≈ 0.25."""
    if a is None or b is None or a == b:
        return 1.0 if (a is not None and a == b) else 0.0
    return round(2.0 * _kinship(a, b, parents, {}, {}, {}), 6)


# ── Pair compatibility ────────────────────────────────────────────────────────

def _risk_level(r: float) -> str:
    if r >= _RISK_HIGH:
        return "high"
    if r >= _RISK_MODERATE:
        return "moderate"
    if r >= _RISK_LOW:
        return "low"
    return "minimal"


def compatibility(male: dict, female: dict, parents: ParentMap) -> dict:
    """Deterministic breeding-compatibility assessment for a candidate pair.

    ``male``/``female``: {"id","sex","species_id"} recorded facts.
    Returns honesty-labelled findings — warnings are *recommendations*, the
    inbreeding figure is a *calculated* value, and confidence is lowered when
    ancestry is unknown. The engine never guarantees an outcome (Doc 01 §12).
    """
    warnings: list[dict] = []
    blocking = False

    mid, fid = male.get("id"), female.get("id")

    # 1. Same individual.
    if mid is not None and mid == fid:
        return {
            "compatible": False, "blocking": True, "risk_level": "invalid",
            "warnings": [{"label": RECOMMENDATION, "code": "same_bird",
                          "detail": "A bird cannot be paired with itself."}],
            "relationship_coefficient": {"label": RECORDED, "value": 1.0},
            "offspring_inbreeding": {"label": UNKNOWN, "value": None},
            "confidence": "high", "limitations": [],
        }

    # 2. Sex.
    if male.get("sex") == "female" or female.get("sex") == "male":
        blocking = True
        warnings.append({"label": RECOMMENDATION, "code": "sex_mismatch",
                         "detail": "Recorded sexes are not male × female."})
    sex_unknown = male.get("sex") not in ("male",) or female.get("sex") not in ("female",)

    # 3. Species.
    if male.get("species_id") is not None and female.get("species_id") is not None \
            and male["species_id"] != female["species_id"]:
        warnings.append({"label": RECOMMENDATION, "code": "cross_species",
                         "detail": "Birds are recorded as different species — hybrid pairing is usually inadvisable."})

    # 4. Relatedness / inbreeding.
    r = relatedness(mid, fid, parents) if (mid is not None and fid is not None) else 0.0
    offspring_f = round(_kinship(mid, fid, parents, {}, {}, {}), 6) if (mid is not None and fid is not None) else 0.0
    risk = _risk_level(r)
    if risk in ("high", "moderate"):
        warnings.append({"label": RECOMMENDATION, "code": f"inbreeding_{risk}",
                         "detail": f"Relatedness {r:.3f} indicates {risk} inbreeding risk; "
                                   f"expected offspring inbreeding coefficient ≈ {offspring_f:.3f}."})

    # 5. Ancestry completeness → confidence / limitations.
    limitations: list[str] = []
    m_known = any(p is not None for p in _parents(mid, parents))
    f_known = any(p is not None for p in _parents(fid, parents))
    if not m_known or not f_known:
        limitations.append("One or both birds have unknown parents — relatedness is a floor, not a ceiling.")
    confidence = "low" if (not m_known and not f_known) else ("medium" if (not m_known or not f_known) else "high")
    if sex_unknown and not blocking:
        limitations.append("Sex is not confirmed for at least one bird.")

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


# ── Breeding performance (aggregation of recorded facts) ──────────────────────

def breeding_performance(offspring: list[dict]) -> dict:
    """Aggregate recorded offspring into deterministic performance facts.

    ``offspring``: each {"status": ...}. Counts only — hatch/fertility rates that
    depend on egg/incubation records arrive with Part 5; here we report what is
    recorded and mark the rest unavailable rather than fabricating a rate."""
    total = len(offspring)
    living = sum(1 for o in offspring if o.get("status") == "active")
    deceased = sum(1 for o in offspring if o.get("status") == "deceased")
    return {
        "offspring_total": {"label": RECORDED, "value": total, "detail": "Recorded offspring of this pair/bird."},
        "offspring_living": {"label": RECORDED, "value": living},
        "offspring_deceased": {"label": RECORDED, "value": deceased},
        "survival_rate_pct": (
            {"label": CALCULATED, "value": round(living / total * 100, 1)}
            if total else {"label": UNKNOWN, "value": None, "detail": "No offspring recorded yet."}
        ),
    }
