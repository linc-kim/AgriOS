"""
Rabbit Health, Vaccination & Mortality (Module 17, Milestone 5) — over HTTP.

Confirms chronological health records, vaccinations that reuse the platform
Reminder engine (reminder created only when a next dose is due), mortality that
transitions the rabbit to deceased and is immutable (one per rabbit), the
deterministic health summary with its §4.4 disclaimer, and RBAC.
"""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"sex": "doe"}
    body.update(overrides)
    r = await client.post(f"{_rb(farm_id)}/rabbits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestHealthRecords:
    async def test_record_and_list_history(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        rec = await async_client.post(
            f"{_rb(fid)}/rabbits/{r['id']}/health",
            json={"event_type": "illness", "title": "Snuffles", "severity": "moderate",
                  "symptoms": "nasal discharge", "occurred_on": date.today().isoformat()},
            headers=auth_headers_owner,
        )
        assert rec.status_code == 201, rec.text
        history = await async_client.get(f"{_rb(fid)}/rabbits/{r['id']}/health", headers=auth_headers_owner)
        assert history.status_code == 200
        assert any(h["title"] == "Snuffles" for h in history.json()["data"])

    async def test_invalid_event_type_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        bad = await async_client.post(
            f"{_rb(fid)}/rabbits/{r['id']}/health",
            json={"event_type": "curse", "occurred_on": date.today().isoformat()},
            headers=auth_headers_owner,
        )
        assert bad.status_code == 422


class TestVaccinationReminderReuse:
    async def test_vaccination_with_due_creates_reminder(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        due = (date.today() + timedelta(days=30)).isoformat()
        vac = await async_client.post(
            f"{_rb(fid)}/rabbits/{r['id']}/vaccinations",
            json={"vaccine": "RHDV2", "administered_on": date.today().isoformat(), "next_due_on": due},
            headers=auth_headers_owner,
        )
        assert vac.status_code == 201, vac.text
        # Reusing the platform Reminder engine → a reminder id is linked.
        assert vac.json()["data"]["reminder_id"] is not None

    async def test_vaccination_without_due_has_no_reminder(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        vac = await async_client.post(
            f"{_rb(fid)}/rabbits/{r['id']}/vaccinations",
            json={"vaccine": "Myxomatosis", "administered_on": date.today().isoformat()},
            headers=auth_headers_owner,
        )
        assert vac.status_code == 201
        assert vac.json()["data"]["reminder_id"] is None


class TestMortality:
    async def test_mortality_transitions_to_deceased_and_is_immutable(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner, date_of_birth="2026-01-01")
        m = await async_client.post(
            f"{_rb(fid)}/rabbits/{r['id']}/mortality",
            json={"occurred_on": "2026-03-01", "cause": "disease", "suspected_cause": "enteritis"},
            headers=auth_headers_owner,
        )
        assert m.status_code == 201, m.text
        assert m.json()["data"]["age_days"] == 59  # 2026-01-01 → 2026-03-01
        detail = await async_client.get(f"{_rb(fid)}/rabbits/{r['id']}", headers=auth_headers_owner)
        assert detail.json()["data"]["status"] == "deceased"
        # Only one mortality record per rabbit.
        again = await async_client.post(
            f"{_rb(fid)}/rabbits/{r['id']}/mortality",
            json={"occurred_on": "2026-03-02", "cause": "unknown"}, headers=auth_headers_owner,
        )
        assert again.status_code == 409

    async def test_health_summary_carries_disclaimer(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        await async_client.post(f"{_rb(fid)}/rabbits/{r['id']}/mortality",
                                json={"occurred_on": date.today().isoformat(), "cause": "injury"},
                                headers=auth_headers_owner)
        s = await async_client.get(f"{_rb(fid)}/health/summary", headers=auth_headers_owner)
        assert s.status_code == 200
        data = s.json()["data"]
        assert "not a veterinary diagnosis" in data["disclaimer"].lower()
        assert data["mortality_rate_pct"]["label"] in ("calculated", "unknown")


class TestRBAC:
    async def test_vet_and_worker_can_log_health(self, async_client, workspace, auth_headers_owner, auth_headers_vet, auth_headers_worker):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        for hdr in (auth_headers_vet, auth_headers_worker):
            rec = await async_client.post(
                f"{_rb(fid)}/rabbits/{r['id']}/health",
                json={"event_type": "exam", "occurred_on": date.today().isoformat()}, headers=hdr,
            )
            assert rec.status_code == 201

    async def test_viewer_cannot_log_but_can_read(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        rec = await async_client.post(
            f"{_rb(fid)}/rabbits/{r['id']}/health",
            json={"event_type": "exam", "occurred_on": date.today().isoformat()}, headers=auth_headers_viewer,
        )
        assert rec.status_code == 403
        assert (await async_client.get(f"{_rb(fid)}/health/summary", headers=auth_headers_viewer)).status_code == 200
