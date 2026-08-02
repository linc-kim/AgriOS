"""
Swine Growth Engine (Module 20, Milestone 7) — pure, deterministic invariants.

Growth figures are computed from immutable weight records; market readiness is an
explainable assessment against configurable targets (never a stored boolean).
"""

from datetime import date

from app.services import swine_config as cfg
from app.services import swine_growth_engine as eng


class TestGrowthMath:
    def test_adg_between_first_and_last(self):
        weights = [
            {"recorded_on": date(2026, 1, 1), "weight_kg": 20},
            {"recorded_on": date(2026, 1, 31), "weight_kg": 50},
        ]
        assert eng.average_daily_gain(weights)["value"] == 1.0  # 30 kg / 30 days
        assert eng.total_gain_kg(weights) == 30.0

    def test_adg_unknown_with_single_weight(self):
        assert eng.average_daily_gain([{"recorded_on": date(2026, 1, 1), "weight_kg": 20}])["label"] == eng.UNKNOWN

    def test_curve_is_sorted_oldest_first(self):
        weights = [
            {"recorded_on": date(2026, 2, 1), "weight_kg": 50},
            {"recorded_on": date(2026, 1, 1), "weight_kg": 20},
        ]
        curve = eng.growth_curve(weights)
        assert [c["weight_kg"] for c in curve] == [20.0, 50.0]


class TestMarketReadiness:
    def _targets(self):
        return cfg.market_targets(None)  # default 110 kg / 180 d

    def test_ready_at_target_weight(self):
        a = eng.market_readiness(latest_weight_kg=112, age_days=185, targets=self._targets(), health_ok=True)
        assert a["status"] == "ready"
        assert a["weight_pct_of_target"] > 100

    def test_approaching_near_target(self):
        a = eng.market_readiness(latest_weight_kg=100, age_days=170, targets=self._targets(),
                                 adg_kg=0.9, health_ok=True)
        assert a["status"] == "approaching"
        assert a["days_to_target_weight"] is not None  # forecast from ADG

    def test_not_ready_below_target(self):
        assert eng.market_readiness(latest_weight_kg=40, age_days=90, targets=self._targets())["status"] == "not_ready"

    def test_withdrawal_always_withholds(self):
        a = eng.market_readiness(latest_weight_kg=120, age_days=190, targets=self._targets(),
                                 active_withdrawal=True, health_ok=True)
        assert a["status"] == "withheld"

    def test_unknown_without_weight(self):
        a = eng.market_readiness(latest_weight_kg=None, age_days=None, targets=self._targets())
        assert a["status"] == "unknown"


class TestConfigTargets:
    def test_breed_override_and_source(self):
        t = cfg.market_targets({"target_market_weight_kg": 95})
        assert t["target_weight_kg"] == 95.0 and t["weight_source"] == "breed"

    def test_explicit_override_wins(self):
        t = cfg.market_targets({"target_market_weight_kg": 95}, target_weight_kg=130)
        assert t["target_weight_kg"] == 130.0 and t["weight_source"] == "override"

    def test_default_when_absent(self):
        t = cfg.market_targets(None)
        assert t["target_weight_kg"] == cfg.DEFAULT_MARKET_WEIGHT_KG and t["weight_source"] == "default"


def test_cohort_summary_averages():
    members = [
        {"latest_weight_kg": 50.0, "adg_kg": 0.8},
        {"latest_weight_kg": 60.0, "adg_kg": 1.0},
        {"latest_weight_kg": None, "adg_kg": None},
    ]
    s = eng.cohort_summary(members)
    assert s["count"]["value"] == 3 and s["weighed_count"]["value"] == 2
    assert s["avg_weight_kg"]["value"] == 55.0
    assert s["avg_daily_gain_kg"]["value"] == 0.9
