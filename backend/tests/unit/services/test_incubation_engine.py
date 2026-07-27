"""
Incubation Engine — the pure, deterministic hatch engine (Module 15, Part 5).

Tests lock the honesty contract: species-driven schedules are computed from the
profile (and reported unknown when it is silent), progress places the right phase,
and hatch statistics are only reported when their denominator is recorded —
otherwise "not enough recorded data", never a fabricated rate.
"""

from datetime import date

from app.services import incubation_engine as ie

CHICKEN = {"incubation": {"incubation_days": 21, "temp_c": 37.5, "humidity_pct": 55, "turning_per_day": 5}}


class TestSchedule:
    def test_species_driven_dates(self):
        s = ie.incubation_schedule(CHICKEN, date(2026, 7, 1))
        assert s["incubation_days"]["value"] == 21 and s["incubation_days"]["label"] == ie.RECORDED
        assert s["expected_hatch_on"]["value"] == "2026-07-22"
        assert s["expected_hatch_on"]["label"] == ie.CALCULATED
        assert s["expected_lockdown_on"]["value"] == "2026-07-19"
        assert s["target_temperature_c"]["value"] == 37.5

    def test_unknown_profile_is_not_guessed(self):
        s = ie.incubation_schedule({}, date(2026, 7, 1))
        assert s["incubation_days"]["label"] == ie.UNKNOWN
        assert s["expected_hatch_on"]["label"] == ie.UNKNOWN
        assert s["expected_hatch_on"]["value"] is None

    def test_manual_override_wins(self):
        s = ie.incubation_schedule({}, date(2026, 7, 1), override_days=28)
        assert s["incubation_days"]["value"] == 28
        assert s["expected_hatch_on"]["value"] == "2026-07-29"

    def test_no_set_date_no_dates(self):
        s = ie.incubation_schedule(CHICKEN, None)
        assert s["expected_hatch_on"]["value"] is None
        assert s["incubation_days"]["value"] == 21  # period still known


class TestProgress:
    def test_incubating_phase(self):
        p = ie.incubation_progress(date(2026, 7, 1), 21, date(2026, 7, 10), "incubating")
        assert p["day_number"]["value"] == 9
        assert p["phase"]["value"] == "incubating"
        assert p["days_remaining"]["value"] == 12

    def test_lockdown_phase(self):
        p = ie.incubation_progress(date(2026, 7, 1), 21, date(2026, 7, 19), "incubating")
        assert p["phase"]["value"] == "lockdown"
        assert p["lockdown_due"] is True

    def test_hatch_due(self):
        p = ie.incubation_progress(date(2026, 7, 1), 21, date(2026, 7, 22), "incubating")
        assert p["phase"]["value"] == "hatch_due"
        assert p["hatch_due"] is True

    def test_unknown_days_cannot_place_phase(self):
        p = ie.incubation_progress(date(2026, 7, 1), None, date(2026, 7, 10), "incubating")
        assert p["day_number"]["value"] == 9
        assert p["phase"]["label"] == ie.UNKNOWN

    def test_not_set_is_unknown(self):
        p = ie.incubation_progress(None, 21, date(2026, 7, 10), "setting")
        assert p["phase"]["label"] == ie.UNKNOWN


class TestCandlingDay:
    def test_day_number(self):
        assert ie.candling_day(date(2026, 7, 1), date(2026, 7, 8)) == 7

    def test_unset_is_none(self):
        assert ie.candling_day(None, date(2026, 7, 8)) is None


class TestStatistics:
    def _eggs(self, fertile, infertile, hatched, failed):
        eggs = []
        eggs += [{"status": "hatched", "fertility_status": "fertile"} for _ in range(hatched)]
        eggs += [{"status": "failed", "fertility_status": "fertile"} for _ in range(failed)]
        eggs += [{"status": "set", "fertility_status": "fertile"} for _ in range(fertile - hatched - failed)]
        eggs += [{"status": "set", "fertility_status": "infertile"} for _ in range(infertile)]
        return eggs

    def test_rates(self):
        # 10 set: 8 fertile (6 hatched, 1 failed, 1 still set), 2 infertile.
        eggs = self._eggs(fertile=8, infertile=2, hatched=6, failed=1)
        s = ie.hatch_statistics(eggs)
        assert s["eggs_set"]["value"] == 10
        assert s["fertile"]["value"] == 8
        assert s["fertility_rate_pct"]["value"] == 80.0        # 8/10
        assert s["hatch_rate_pct"]["value"] == 60.0            # 6/10
        assert s["hatch_of_fertile_pct"]["value"] == 75.0      # 6/8

    def test_empty_is_not_enough_data(self):
        s = ie.hatch_statistics([])
        assert s["fertility_rate_pct"]["label"] == ie.UNKNOWN
        assert s["hatch_rate_pct"]["label"] == ie.UNKNOWN
        assert s["eggs_total"]["value"] == 0
