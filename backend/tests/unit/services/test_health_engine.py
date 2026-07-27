"""
Health Engine — the pure, deterministic individual-bird health engine (Part 6).

Tests lock the honesty contract: weight trends are derived from recorded points
(direction is a plain comparison), coverage/mortality rates are only reported
when their denominator is recorded (otherwise "not enough recorded data"), and
preventive-care-due is computed from ``next_due_on`` — nothing is diagnosed or
fabricated.
"""

from datetime import date

from app.services import health_engine as he


class TestWeightTrend:
    def test_increasing(self):
        t = he.weight_trend([
            {"recorded_on": date(2026, 7, 1), "weight_grams": 90},
            {"recorded_on": date(2026, 7, 20), "weight_grams": 110},
        ])
        assert t["latest"]["value"] == 110.0
        assert t["change_grams"]["value"] == 20.0
        assert t["direction"]["value"] == "up"
        assert len(t["series"]) == 2

    def test_decreasing(self):
        t = he.weight_trend([
            {"recorded_on": date(2026, 7, 1), "weight_grams": 120},
            {"recorded_on": date(2026, 7, 20), "weight_grams": 100},
        ])
        assert t["direction"]["value"] == "down"
        assert t["change_grams"]["value"] == -20.0

    def test_unordered_input_is_sorted(self):
        t = he.weight_trend([
            {"recorded_on": date(2026, 7, 20), "weight_grams": 110},
            {"recorded_on": date(2026, 7, 1), "weight_grams": 90},
        ])
        assert t["first"]["value"] == 90.0 and t["latest"]["value"] == 110.0

    def test_empty_is_unknown(self):
        t = he.weight_trend([])
        assert t["latest"]["label"] == he.UNKNOWN
        assert t["count"]["value"] == 0


class TestRates:
    def test_vaccination_coverage(self):
        assert he.vaccination_coverage(10, 7)["value"] == 70.0
        assert he.vaccination_coverage(10, 7)["label"] == he.CALCULATED

    def test_coverage_no_birds_is_unknown(self):
        assert he.vaccination_coverage(0, 0)["label"] == he.UNKNOWN

    def test_mortality_rate(self):
        assert he.mortality_rate(2, 20)["value"] == 10.0

    def test_mortality_no_birds_is_unknown(self):
        assert he.mortality_rate(0, 0)["label"] == he.UNKNOWN


class TestDueSoon:
    def test_counts_due_and_overdue(self):
        recs = [
            {"next_due_on": date(2026, 7, 20), "status": "recorded"},   # overdue (today 26th)
            {"next_due_on": date(2026, 8, 1), "status": "recorded"},    # due within window
            {"next_due_on": date(2026, 9, 1), "status": "recorded"},    # outside window
            {"next_due_on": date(2026, 7, 21), "status": "resolved"},   # resolved → excluded
            {"next_due_on": None, "status": "recorded"},                # no due date → excluded
        ]
        d = he.due_soon(recs, today=date(2026, 7, 26), window_days=14)
        assert d["due_count"]["value"] == 2
        assert d["overdue_count"]["value"] == 1


class TestSummary:
    def test_composes_labelled_summary(self):
        recs = [
            {"record_type": "vaccination", "next_due_on": date(2026, 8, 1), "status": "recorded"},
            {"record_type": "weight", "next_due_on": None, "status": "recorded"},
        ]
        s = he.health_summary(records=recs, active_birds=10, total_ever=12, deceased=2,
                              vaccinated_birds=6, active_quarantines=1, active_diseases=0,
                              today=date(2026, 7, 26))
        assert s["records_total"]["value"] == 2
        assert s["records_by_type"]["vaccination"] == 1
        assert s["mortality_rate_pct"]["value"] == round(2 / 12 * 100, 1)
        assert s["vaccination_coverage_pct"]["value"] == 60.0
        assert s["active_quarantines"]["value"] == 1
