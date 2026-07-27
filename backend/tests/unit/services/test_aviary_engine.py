"""
Aviary Engine — the pure, deterministic facility engine (Module 15, Part 3).

The engine turns recorded aviary data into honesty-labelled facts. These tests
lock the contract that matters: occupancy is calculated correctly and labelled,
unknown capacity is reported as unknown (never guessed), environment findings are
recommendations (never diagnoses), cleaning status is derived from records only,
and housing suitability degrades to 'unknown' without a species profile. The
engine is pure — same inputs, same outputs, no I/O.
"""

from datetime import date

from app.services import aviary_engine as e


class TestOccupancy:
    def test_calculated_and_labelled(self):
        o = e.compute_occupancy(capacity=10, occupied_count=7)
        assert o.occupied.value == 7 and o.occupied.label == e.RECORDED
        assert o.available.value == 3 and o.available.label == e.CALCULATED
        assert o.utilization_pct.value == 70.0
        assert o.over_capacity is False

    def test_over_capacity_flag(self):
        o = e.compute_occupancy(capacity=5, occupied_count=8)
        assert o.over_capacity is True
        assert o.available.value == -3

    def test_unknown_capacity_is_never_guessed(self):
        o = e.compute_occupancy(capacity=None, occupied_count=4)
        assert o.occupied.value == 4
        assert o.capacity.label == e.UNKNOWN
        assert o.available.label == e.UNKNOWN
        assert o.utilization_pct.label == e.UNKNOWN
        assert o.over_capacity is False

    def test_zero_capacity_utilisation_unavailable(self):
        o = e.compute_occupancy(capacity=0, occupied_count=0)
        assert o.utilization_pct.label == e.UNAVAILABLE


class TestEnvironment:
    def test_no_readings_is_unknown(self):
        s = e.summarize_environment([], targets=None)
        assert s.reading_count == 0
        assert s.latest["label"] == e.UNKNOWN

    def test_averages_and_latest(self):
        readings = [
            {"temperature_c": 24, "humidity_pct": 55, "light_hours": 12, "recorded_at": "2026-07-26"},
            {"temperature_c": 26, "humidity_pct": 45, "light_hours": 12, "recorded_at": "2026-07-25"},
        ]
        s = e.summarize_environment(readings, targets=None)
        assert s.reading_count == 2
        assert s.averages["temperature_c"]["value"] == 25.0
        assert s.averages["temperature_c"]["label"] == e.CALCULATED

    def test_out_of_range_is_a_recommendation_not_a_diagnosis(self):
        readings = [{"temperature_c": 40, "humidity_pct": 50, "recorded_at": "2026-07-26"}]
        s = e.summarize_environment(readings, targets={"temp_min": 18, "temp_max": 30,
                                                        "humidity_min": 40, "humidity_max": 70})
        assert any(f["metric"] == "temperature_c" and f["label"] == e.RECOMMENDATION for f in s.findings)

    def test_in_range_produces_no_findings(self):
        readings = [{"temperature_c": 24, "humidity_pct": 55, "recorded_at": "2026-07-26"}]
        s = e.summarize_environment(readings, targets={"temp_min": 18, "temp_max": 30,
                                                        "humidity_min": 40, "humidity_max": 70})
        assert s.findings == []


class TestCleaning:
    def test_overdue_and_upcoming(self):
        tasks = [
            {"task_type": "cleaning", "status": "scheduled", "scheduled_for": date(2026, 7, 20), "completed_on": None},
            {"task_type": "cleaning", "status": "scheduled", "scheduled_for": date(2026, 8, 1), "completed_on": None},
            {"task_type": "maintenance", "status": "completed", "scheduled_for": date(2026, 7, 1),
             "completed_on": date(2026, 7, 2)},
        ]
        s = e.cleaning_status(tasks, today=date(2026, 7, 26))
        assert s["overdue_count"]["value"] == 1
        assert s["upcoming_count"]["value"] == 1
        assert s["last_completed"]["value"] == "2026-07-02"
        assert s["last_completed"]["label"] == e.RECORDED

    def test_no_completed_is_unknown(self):
        s = e.cleaning_status([], today=date(2026, 7, 26))
        assert s["last_completed"]["label"] == e.UNKNOWN


class TestHousing:
    def test_no_profile_is_unknown(self):
        r = e.assess_housing({"aviary_type": "indoor", "environment": {}}, species_profile=None)
        assert r["label"] == e.UNKNOWN

    def test_wrong_type_is_a_recommendation(self):
        profile = {"housing": {"aviary_types": ["flight", "walk_in"]}}
        r = e.assess_housing({"aviary_type": "cage", "environment": {}}, species_profile=profile)
        assert r["label"] == e.RECOMMENDATION
        assert any(f["metric"] == "aviary_type" for f in r["findings"])

    def test_matching_type_no_findings(self):
        profile = {"housing": {"aviary_types": ["flight"]}}
        r = e.assess_housing({"aviary_type": "flight", "environment": {}}, species_profile=profile)
        assert r["findings"] == []
