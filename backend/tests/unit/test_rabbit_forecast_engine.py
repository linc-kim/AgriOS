"""
Rabbit Forecast Engine (Module 17, Milestone 7) — pure determinism.

Every projection is ``forecast``-labelled with method/assumptions/confidence/
limitations; no history → ``unknown`` (never a fabricated number). Capacity
forecast derives from the herd forecast and stays a forecast.
"""

from app.services import rabbit_forecast_engine as eng


class TestProjectFlow:
    def test_projects_rate_over_horizon(self):
        out = eng.project_flow(300, 30, 90, observations=10, quantity="feed", unit="kg")
        assert out["daily_rate"]["value"] == 10.0
        assert out["forecast"]["label"] == eng.FORECAST
        assert out["forecast"]["value"] == 900.0
        assert out["confidence"] == "medium"  # 5 <= 10 < 20

    def test_no_history_unknown(self):
        out = eng.project_flow(None, 30, 90, observations=0, quantity="revenue", unit="currency")
        assert out["forecast"]["label"] == eng.UNKNOWN

    def test_low_confidence_few_observations(self):
        out = eng.project_flow(10, 30, 30, observations=2, quantity="kits", unit="kits")
        assert out["confidence"] == "low"


class TestProjectStock:
    def test_projects_net_change(self):
        out = eng.project_stock(100, 30, 30, 60, observations=6, quantity="herd size", unit="rabbits")
        assert out["net_daily_change"]["value"] == 1.0
        assert out["forecast"]["value"] == 160.0
        assert out["forecast"]["label"] == eng.FORECAST

    def test_floor_zero(self):
        out = eng.project_stock(10, -30, 30, 60, observations=6, quantity="herd size", unit="rabbits")
        assert out["forecast"]["value"] == 0.0  # 10 + (-1×60) floored at 0

    def test_missing_inputs_unknown(self):
        out = eng.project_stock(None, 5, 30, 60, observations=3, quantity="herd size", unit="rabbits")
        assert out["forecast"]["label"] == eng.UNKNOWN


class TestCapacityRequirement:
    def test_expansion_needed(self):
        out = eng.capacity_requirement(150, 100, horizon_days=30)
        assert out["shortfall"]["value"] == 50.0
        assert out["shortfall"]["label"] == eng.FORECAST
        assert out["status"]["value"] == "expansion_needed"
        assert out["current_capacity"]["label"] == eng.RECORDED

    def test_within_capacity(self):
        out = eng.capacity_requirement(80, 100, horizon_days=30)
        assert out["status"]["value"] == "within_capacity"

    def test_unknown_capacity(self):
        out = eng.capacity_requirement(80, None, horizon_days=30)
        assert out["current_capacity"]["label"] == eng.UNKNOWN
        assert out["shortfall"]["label"] == eng.UNKNOWN

    def test_unknown_headcount(self):
        out = eng.capacity_requirement(None, 100, horizon_days=30)
        assert out["status"]["label"] == eng.UNKNOWN
