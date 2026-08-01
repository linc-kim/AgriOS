"""
Rabbit Health Engine (Module 17, Milestone 5) — pure determinism.

Locks the honesty contract and the frozen §4.4 guarantee: the engine reports
*patterns* (rates, frequencies, compliance) with a "not a veterinary diagnosis"
disclaimer, and never fabricates a rate when the denominator is zero.
"""

from datetime import date

from app.services import rabbit_health_engine as eng


class TestMortality:
    def test_rate(self):
        assert eng.mortality_rate(2, 10)["value"] == 20.0
        assert eng.mortality_rate(0, 0)["label"] == eng.UNKNOWN

    def test_by_cause_shares(self):
        rows = eng.mortality_by_cause([{"cause": "disease"}, {"cause": "disease"}, {"cause": "injury"}])
        top = rows[0]
        assert top["cause"] == "disease" and top["count"]["value"] == 2
        assert top["share_pct"]["value"] == round(2 / 3 * 100, 1)

    def test_trend_by_month(self):
        rows = eng.mortality_trend([
            {"occurred_on": date(2026, 1, 5)}, {"occurred_on": date(2026, 1, 20)},
            {"occurred_on": date(2026, 2, 2)},
        ])
        by_month = {r["month"]: r["deaths"]["value"] for r in rows}
        assert by_month == {"2026-01": 2, "2026-02": 1}


class TestRecoveryAndConditions:
    def test_recovery_rate_excludes_open(self):
        records = [
            {"event_type": "illness", "status": "resolved"},
            {"event_type": "injury", "status": "resolved"},
            {"event_type": "treatment", "status": "ongoing"},
            {"event_type": "observation", "status": "recorded"},  # not clinical
        ]
        rr = eng.recovery_rate(records)
        assert rr["clinical_events"]["value"] == 3
        assert rr["resolved"]["value"] == 2
        assert rr["ongoing"]["value"] == 1
        assert rr["recovery_rate_pct"]["value"] == round(2 / 3 * 100, 1)

    def test_condition_frequency_counts(self):
        rows = eng.condition_frequency([
            {"event_type": "illness"}, {"event_type": "illness"}, {"event_type": "injury"},
        ])
        top = rows[0]
        assert top["event_type"] == "illness" and top["count"]["value"] == 2


class TestVaccinationCompliance:
    def test_overdue_and_upcoming(self):
        today = date(2026, 6, 1)
        vacs = [
            {"next_due_on": date(2026, 5, 1)},  # overdue
            {"next_due_on": date(2026, 7, 1)},  # upcoming
            {"next_due_on": None},              # no next dose
        ]
        c = eng.vaccination_compliance(vacs, today)
        assert c["total_vaccinations"]["value"] == 3
        assert c["scheduled_next_doses"]["value"] == 2
        assert c["overdue"]["value"] == 1
        assert c["upcoming"]["value"] == 1


class TestSummary:
    def test_summary_carries_disclaimer(self):
        s = eng.health_summary(
            deceased=1, total_ever=5, mortality_records=[{"cause": "disease", "occurred_on": date(2026, 1, 1)}],
            health_records=[{"event_type": "illness", "status": "resolved"}],
            vaccinations=[{"next_due_on": date(2026, 1, 1)}], today=date(2026, 6, 1),
        )
        assert "not a veterinary diagnosis" in s["disclaimer"].lower()
        assert s["mortality_rate_pct"]["value"] == 20.0
