"""
Aviculture Automation Engine — pure deterministic engine (Module 15, Part 9).

Locks the contract: each operational item carries Priority/Reason/Evidence/
Suggested-Due (Doc 11 §6) and a stable dedup_key; overdue items rank first;
the horizon filters far-future items; and workflow stage templates/transitions
are deterministic and terminal-aware.
"""

from datetime import date, timedelta

from app.services import aviculture_automation_engine as ae

TODAY = date(2026, 7, 27)


def _state(**kw):
    base = {"health_due": [], "documents_expiring": [], "incubation_batches": [], "aviary_tasks": []}
    base.update(kw)
    return base


class TestOperationalItems:
    def test_overdue_health_is_high_priority(self):
        items = ae.compute_operational_items(
            today=TODAY, **_state(health_due=[
                {"bird_ref": "AV-1", "record_type": "vaccination",
                 "next_due_on": TODAY - timedelta(days=3), "bird_id": "b1"}]))
        assert len(items) == 1
        it = items[0]
        assert it["kind"] == "health_due" and it["priority"] == ae.HIGH
        assert it["evidence"]["record_type"] == "vaccination"
        assert it["suggested_due_on"] == (TODAY - timedelta(days=3)).isoformat()
        assert it["dedup_key"].startswith("avi:health_due:b1")

    def test_expiring_permit_soon_is_high_overdue_is_critical(self):
        soon = ae.compute_operational_items(today=TODAY, **_state(documents_expiring=[
            {"bird_ref": "AV-1", "document_type": "export_permit",
             "expires_on": TODAY + timedelta(days=5), "document_id": "d1"}]))[0]
        assert soon["priority"] == ae.HIGH
        overdue = ae.compute_operational_items(today=TODAY, **_state(documents_expiring=[
            {"bird_ref": "AV-1", "document_type": "export_permit",
             "expires_on": TODAY - timedelta(days=1), "document_id": "d1"}]))[0]
        assert overdue["priority"] == ae.CRITICAL

    def test_horizon_filters_far_future(self):
        items = ae.compute_operational_items(today=TODAY, horizon_days=30, **_state(aviary_tasks=[
            {"aviary_name": "Flight1", "task_type": "cleaning",
             "scheduled_for": TODAY + timedelta(days=90), "task_id": "t1", "aviary_id": "a1"}]))
        assert items == []

    def test_incubation_lockdown_and_hatch(self):
        items = ae.compute_operational_items(today=TODAY, **_state(incubation_batches=[
            {"name": "BatchA", "batch_id": "ba",
             "expected_lockdown_on": TODAY + timedelta(days=3),
             "expected_hatch_on": TODAY + timedelta(days=6)}]))
        kinds = {i["kind"] for i in items}
        assert "incubation_lockdown" in kinds and "incubation_hatch" in kinds

    def test_overdue_ranks_before_upcoming(self):
        items = ae.compute_operational_items(today=TODAY, **_state(
            health_due=[{"bird_ref": "AV-2", "record_type": "deworming",
                         "next_due_on": TODAY - timedelta(days=1), "bird_id": "b2"}],
            aviary_tasks=[{"aviary_name": "A", "task_type": "cleaning",
                           "scheduled_for": TODAY + timedelta(days=2), "task_id": "t2", "aviary_id": "a2"}]))
        assert items[0]["priority"] == ae.HIGH  # overdue health first
        assert items[-1]["priority"] == ae.NORMAL

    def test_empty_state_yields_nothing(self):
        assert ae.compute_operational_items(today=TODAY, **_state()) == []


class TestWorkflowTemplates:
    def test_intake_template(self):
        assert ae.first_stage("intake") == "received"
        assert ae.next_stage("intake", "received") == "quarantine"
        assert ae.is_terminal("intake", "in_collection") is True
        assert ae.is_terminal("intake", "received") is False

    def test_terminal_has_no_next(self):
        assert ae.next_stage("incubation", "hatched") is None

    def test_unknown_type(self):
        assert ae.first_stage("nope") is None
        assert ae.workflow_stages("nope") == []
