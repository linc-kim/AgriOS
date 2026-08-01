"""
Rabbit Housing Capacity Engine (Module 17, Milestone 2) — pure determinism.

The engine performs no I/O; these tests lock its honesty contract: known inputs
yield labelled facts/calculations, unknown capacity is reported as unknown (never
guessed), and overcrowding is flagged only against a recorded capacity.
"""

from app.services import rabbit_housing_engine as eng


class TestOccupancy:
    def test_known_capacity_computes_available_and_utilization(self):
        occ = eng.compute_occupancy(capacity=10, occupied_count=6)
        assert occ.occupied.value == 6 and occ.occupied.label == eng.RECORDED
        assert occ.capacity.value == 10 and occ.capacity.label == eng.RECORDED
        assert occ.available.value == 4 and occ.available.label == eng.CALCULATED
        assert occ.utilization_pct.value == 60.0
        assert occ.over_capacity is False

    def test_unknown_capacity_is_never_guessed(self):
        occ = eng.compute_occupancy(capacity=None, occupied_count=5)
        assert occ.occupied.value == 5
        assert occ.capacity.label == eng.UNKNOWN and occ.capacity.value is None
        assert occ.available.label == eng.UNKNOWN
        assert occ.utilization_pct.label == eng.UNKNOWN
        assert occ.over_capacity is False

    def test_over_capacity_flagged_and_available_negative(self):
        occ = eng.compute_occupancy(capacity=4, occupied_count=6)
        assert occ.over_capacity is True
        assert occ.available.value == -2  # honest, not clamped

    def test_zero_capacity_utilization_unavailable(self):
        occ = eng.compute_occupancy(capacity=0, occupied_count=0)
        assert occ.utilization_pct.label == eng.UNAVAILABLE
        assert occ.utilization_pct.value is None


class TestOvercrowding:
    def test_overcrowded_only_against_recorded_capacity(self):
        assert eng.is_overcrowded(4, 5) is True
        assert eng.is_overcrowded(5, 5) is False
        assert eng.is_overcrowded(None, 999) is False  # no fabricated limit


class TestRollup:
    def test_sums_capacity_and_occupancy_and_counts_unknowns(self):
        children = [
            {"capacity": 10, "occupied": 8},
            {"capacity": 5, "occupied": 6},   # overcrowded
            {"capacity": None, "occupied": 3},  # unknown capacity, excluded from total
        ]
        out = eng.rollup(children)
        assert out["unit_count"]["value"] == 3
        assert out["occupied"]["value"] == 17           # 8 + 6 + 3
        assert out["capacity"]["value"] == 15           # 10 + 5 (unknown excluded)
        assert out["capacity_unknown_units"]["value"] == 1
        assert out["available"]["value"] == -2          # 15 - 17
        assert out["overcrowded_units"]["value"] == 1

    def test_all_unknown_capacity_reports_unknown_total(self):
        out = eng.rollup([{"capacity": None, "occupied": 2}, {"capacity": None, "occupied": 1}])
        assert out["occupied"]["value"] == 3
        assert out["capacity"]["label"] == eng.UNKNOWN
        assert out["available"]["label"] == eng.UNKNOWN

    def test_empty_is_zeroed(self):
        out = eng.rollup([])
        assert out["unit_count"]["value"] == 0
        assert out["occupied"]["value"] == 0
        assert out["overcrowded_units"]["value"] == 0
