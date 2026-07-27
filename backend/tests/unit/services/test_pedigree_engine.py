"""
Pedigree Engine — the pure, deterministic genetics engine (Module 15, Part 4).

Genetics is where fabrication would be most dangerous, so these tests pin the
maths against textbook values (Wright's coefficients), prove ancestry stays
honest about the unknown, prove no circular ancestry is ever produced, and prove
every outward value is honesty-labelled and never a guarantee.
"""

from app.services import pedigree_engine as pe


# A small closed pedigree:
#   A, B, F, G are founders (unknown parents)
#   C = A×B, D = A×B  (full siblings)
#   H = A×F           (half-sibling to C/D, shares A)
#   Z = C×D           (offspring of a full-sib mating → inbred)
PARENTS = {
    "A": (None, None), "B": (None, None), "F": (None, None), "G": (None, None),
    "C": ("A", "B"), "D": ("A", "B"),
    "H": ("A", "F"),
    "Z": ("C", "D"),
}


class TestRelatedness:
    def test_full_siblings(self):
        assert pe.relatedness("C", "D", PARENTS) == 0.5

    def test_parent_offspring(self):
        assert pe.relatedness("A", "C", PARENTS) == 0.5

    def test_half_siblings(self):
        assert pe.relatedness("C", "H", PARENTS) == 0.25

    def test_unrelated_founders(self):
        assert pe.relatedness("A", "B", PARENTS) == 0.0

    def test_unknown_bird_is_zero(self):
        assert pe.relatedness("C", None, PARENTS) == 0.0


class TestInbreeding:
    def test_outbred_is_zero(self):
        assert pe.inbreeding_coefficient("C", PARENTS) == 0.0

    def test_full_sib_mating_offspring_is_quarter(self):
        assert pe.inbreeding_coefficient("Z", PARENTS) == 0.25

    def test_unknown_parent_is_zero(self):
        assert pe.inbreeding_coefficient("H", PARENTS) == 0.0  # A known, F known but unrelated → 0


class TestAncestryAndFounders:
    def test_unknown_parent_is_marked_not_omitted(self):
        tree = pe.build_ancestry("H", PARENTS, max_generations=3)
        # H = A×F; A and F are founders whose parents are unknown.
        assert tree["sire"]["id"] == "A"
        assert tree["sire"]["sire"] == {"unknown": True}

    def test_founders_are_lineage_roots(self):
        assert set(pe.founders("Z", PARENTS)) == {"A", "B"}

    def test_founder_of_itself(self):
        assert pe.founders("A", PARENTS) == ["A"]


class TestCycleSafety:
    def test_ancestor_as_child_is_a_cycle(self):
        # Making A a child of C (A is C's parent) would loop.
        assert pe.would_create_cycle("A", "C", PARENTS) is True

    def test_self_parent_is_a_cycle(self):
        assert pe.would_create_cycle("C", "C", PARENTS) is True

    def test_unrelated_parent_is_safe(self):
        assert pe.would_create_cycle("C", "G", PARENTS) is False

    def test_none_parent_is_safe(self):
        assert pe.would_create_cycle("C", None, PARENTS) is False


class TestCompatibility:
    def test_full_siblings_flag_high_risk(self):
        r = pe.compatibility({"id": "C", "sex": "male", "species_id": 1},
                             {"id": "D", "sex": "female", "species_id": 1}, PARENTS)
        assert r["risk_level"] == "high"
        assert r["relationship_coefficient"]["value"] == 0.5
        assert r["offspring_inbreeding"]["label"] == pe.FORECAST
        assert r["offspring_inbreeding"]["value"] == 0.25
        assert r["compatible"] is False

    def test_unrelated_opposite_sex_is_compatible(self):
        r = pe.compatibility({"id": "A", "sex": "male", "species_id": 1},
                             {"id": "B", "sex": "female", "species_id": 1}, PARENTS)
        assert r["risk_level"] == "minimal"
        assert r["compatible"] is True
        assert r["blocking"] is False

    def test_same_bird_is_invalid(self):
        r = pe.compatibility({"id": "C", "sex": "male", "species_id": 1},
                             {"id": "C", "sex": "female", "species_id": 1}, PARENTS)
        assert r["blocking"] is True and r["risk_level"] == "invalid"

    def test_sex_mismatch_blocks(self):
        r = pe.compatibility({"id": "A", "sex": "female", "species_id": 1},
                             {"id": "B", "sex": "female", "species_id": 1}, PARENTS)
        assert r["blocking"] is True
        assert any(w["code"] == "sex_mismatch" for w in r["warnings"])

    def test_cross_species_warns(self):
        r = pe.compatibility({"id": "A", "sex": "male", "species_id": 1},
                             {"id": "B", "sex": "female", "species_id": 2}, PARENTS)
        assert any(w["code"] == "cross_species" for w in r["warnings"])

    def test_unknown_ancestry_lowers_confidence(self):
        # Two founders → parents unknown → confidence low, limitation noted.
        r = pe.compatibility({"id": "A", "sex": "male", "species_id": 1},
                             {"id": "B", "sex": "female", "species_id": 1}, PARENTS)
        assert r["confidence"] == "low"
        assert r["limitations"]


class TestPerformance:
    def test_survival_rate_calculated(self):
        perf = pe.breeding_performance([{"status": "active"}, {"status": "active"}, {"status": "deceased"}])
        assert perf["offspring_total"]["value"] == 3
        assert perf["survival_rate_pct"]["value"] == 66.7

    def test_no_offspring_is_unknown(self):
        perf = pe.breeding_performance([])
        assert perf["survival_rate_pct"]["label"] == pe.UNKNOWN
