"""
Rabbit Genetics (Module 17, Milestone 3) — thin layer over the reused platform
pedigree engine (ledger CON-M3-1/2).

Verifies the reused Wright's math yields textbook values for rabbits, that the
buck/doe sex semantics are enforced (the shared engine speaks male/female), and
that inbreeding forecasts are honesty-labelled and never guarantees.
"""

from app.services import rabbit_genetics as gen


# Pedigree: S×D are founders; A and B are full siblings; C = A×B (full-sib mating).
PARENTS = {
    "S": (None, None),
    "D": (None, None),
    "A": ("S", "D"),
    "B": ("S", "D"),
    "C": ("A", "B"),
}


class TestPedigreeTree:
    def test_full_sib_offspring_inbreeding_is_quarter(self):
        tree = gen.pedigree_tree("C", PARENTS)
        assert tree["inbreeding_coefficient"]["value"] == 0.25
        assert tree["inbreeding_coefficient"]["label"] == gen.CALCULATED

    def test_unknown_parents_report_zero_as_floor(self):
        tree = gen.pedigree_tree("A", PARENTS)  # A's parents known but A itself not inbred
        assert tree["inbreeding_coefficient"]["value"] == 0.0
        founder_tree = gen.pedigree_tree("S", PARENTS)
        assert founder_tree["inbreeding_coefficient"]["label"] == gen.UNKNOWN  # no parents

    def test_founders_traced(self):
        tree = gen.pedigree_tree("C", PARENTS)
        assert set(tree["founders"]) == {"S", "D"}


class TestPairing:
    def test_full_sibs_flagged_high_risk(self):
        out = gen.assess_pairing({"id": "A", "sex": "buck"}, {"id": "B", "sex": "doe"}, PARENTS)
        assert out["relationship_coefficient"]["value"] == 0.5  # full sibs
        assert out["offspring_inbreeding"]["value"] == 0.25
        assert out["offspring_inbreeding"]["label"] == gen.FORECAST
        assert out["risk_level"] == "high"
        assert out["compatible"] is False

    def test_sex_mismatch_blocks(self):
        out = gen.assess_pairing({"id": "A", "sex": "doe"}, {"id": "B", "sex": "doe"}, PARENTS)
        assert out["blocking"] is True
        assert any(w["code"] == "sex_mismatch" for w in out["warnings"])

    def test_same_rabbit_invalid(self):
        out = gen.assess_pairing({"id": "A", "sex": "buck"}, {"id": "A", "sex": "doe"}, PARENTS)
        assert out["risk_level"] == "invalid" and out["blocking"] is True

    def test_unrelated_pair_minimal_risk_and_confidence(self):
        parents = {"X": (None, None), "Y": (None, None)}
        out = gen.assess_pairing({"id": "X", "sex": "buck"}, {"id": "Y", "sex": "doe"}, parents)
        assert out["risk_level"] == "minimal"
        assert out["compatible"] is True
        # Unknown ancestry lowers confidence and is surfaced as a limitation.
        assert out["confidence"] == "low"
        assert out["limitations"]


class TestCycleGuard:
    def test_reuses_shared_cycle_guard(self):
        # Making S a child of C would create circular ancestry (C descends from S).
        assert gen.would_create_cycle("S", "C", PARENTS) is True
        assert gen.would_create_cycle("C", "S", PARENTS) is False
