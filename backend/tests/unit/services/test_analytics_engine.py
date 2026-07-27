"""
Analytics Engine — pure collection analytics & forecast (Module 15, Part 8).

Locks the honesty contract: composition is recorded-fact counts; the population
forecast states method/assumptions/confidence/limitations, is labelled FORECAST
(never a promise), floors at zero, and degrades to unknown without a window.
"""

from app.services import analytics_engine as ae


class TestComposition:
    def test_tallies(self):
        birds = [
            {"species_name": "Silkie", "status": "active", "sex": "male", "lifecycle_stage": "adult"},
            {"species_name": "Silkie", "status": "active", "sex": "female", "lifecycle_stage": "adult"},
            {"species_name": "Canary", "status": "sold", "sex": "unknown", "lifecycle_stage": "chick"},
        ]
        c = ae.collection_composition(birds)
        assert c["total"]["value"] == 3 and c["total"]["label"] == ae.RECORDED
        assert c["by_species"]["Silkie"] == 2
        assert c["by_status"]["active"] == 2 and c["by_status"]["sold"] == 1
        assert c["by_sex"]["male"] == 1

    def test_missing_fields_bucket_unknown(self):
        c = ae.collection_composition([{"status": "active"}])
        assert c["by_species"]["unknown"] == 1


class TestForecast:
    def test_growth_projection(self):
        f = ae.population_forecast(current_active=10, births_in_window=6, deaths_in_window=2,
                                   window_days=30, horizon_days=90)
        # net_daily = 4/30; +90 days ≈ +12 → 22
        assert f["forecast"]["value"] == 22 and f["forecast"]["label"] == ae.FORECAST
        assert f["net_daily_change"]["label"] == ae.CALCULATED
        assert f["assumptions"] and f["limitations"]

    def test_decline_floors_at_zero(self):
        f = ae.population_forecast(current_active=3, births_in_window=0, deaths_in_window=20,
                                   window_days=10, horizon_days=90)
        assert f["forecast"]["value"] == 0  # cannot go negative

    def test_confidence_scales_with_events(self):
        low = ae.population_forecast(current_active=5, births_in_window=1, deaths_in_window=0,
                                     window_days=30, horizon_days=90)
        high = ae.population_forecast(current_active=50, births_in_window=15, deaths_in_window=10,
                                      window_days=30, horizon_days=90)
        assert low["confidence"] == "low" and high["confidence"] == "high"

    def test_no_window_is_unknown(self):
        f = ae.population_forecast(current_active=5, births_in_window=0, deaths_in_window=0,
                                   window_days=0, horizon_days=90)
        assert f["forecast"]["label"] == ae.UNKNOWN
