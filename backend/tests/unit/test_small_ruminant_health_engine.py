"""
Small Ruminant Health engine (Modules 18/19, Milestone 5) — PURE.

Locks the deterministic health/parasite/hoof patterns and the frozen §4.4
guarantee: the engine reports patterns (rates, frequencies, compliance), never a
diagnosis, and every composite carries the disclaimer.
"""

from datetime import date

from app.services import small_ruminant_health_engine as h


def test_mortality_rate_and_cause_breakdown():
    assert h.mortality_rate(0, 0)["label"] == "unknown"        # no denominator → not fabricated
    assert h.mortality_rate(2, 10)["value"] == 20.0
    causes = h.mortality_by_cause([{"cause": "parasites"}, {"cause": "parasites"}, {"cause": "injury"}])
    assert causes[0]["cause"] == "parasites" and causes[0]["count"]["value"] == 2


def test_deworming_compliance_with_famacha_distribution():
    dew = [{"next_due_on": date(2020, 1, 1), "famacha_score": 4},   # overdue
           {"next_due_on": date(2999, 1, 1), "famacha_score": 2}]   # upcoming
    c = h.deworming_compliance(dew, date(2026, 1, 1))
    assert c["total_dewormings"]["value"] == 2
    assert c["overdue"]["value"] == 1 and c["upcoming"]["value"] == 1
    # FAMACHA scores are recorded facts, surfaced as a distribution (never inferred).
    scores = {d["score"]: d["count"]["value"] for d in c["famacha_distribution"]}
    assert scores == {"2": 1, "4": 1}


def test_hoof_summary_condition_frequency_and_overdue():
    hoof = [{"condition": "foot_rot", "next_due_on": date(2020, 1, 1)},
            {"condition": "healthy", "next_due_on": None}]
    s = h.hoof_summary(hoof, date(2026, 1, 1))
    assert s["overdue_followups"]["value"] == 1
    conds = {c["condition"]: c["count"]["value"] for c in s["condition_frequency"]}
    assert conds["foot_rot"] == 1


def test_health_summary_never_diagnoses():
    summary = h.health_summary(
        deceased=1, total_ever=5, mortality_records=[{"cause": "disease", "occurred_on": date(2026, 1, 1)}],
        health_records=[{"event_type": "illness", "status": "resolved"}],
        vaccinations=[], dewormings=[], hoof_records=[], today=date(2026, 6, 1),
    )
    assert summary["disclaimer"] == "A recorded pattern, not a veterinary diagnosis."
    assert summary["recovery"]["recovery_rate_pct"]["value"] == 100.0
    # Deworming/hoof blocks present even when empty (honest zeros, not omissions).
    assert summary["deworming_compliance"]["total_dewormings"]["value"] == 0
