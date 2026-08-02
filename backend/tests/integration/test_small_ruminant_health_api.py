"""
Small Ruminant Health (Modules 18/19, Milestone 5) — over HTTP.

Health records, vaccination, deworming (with FAMACHA), hoof care and mortality for
both species. Vaccination/deworming with a next-due date create a platform Reminder
(reused, not a new table). Mortality is authoritative and one-per-animal. The
summary emits patterns with a §4.4 disclaimer. Vets can log clinical records.
"""

import pytest
from sqlalchemy import select

from app.models.automation import Reminder

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _animal(client, fid, species, headers, sex="doe") -> str:
    r = await client.post(f"{_sr(fid, species)}/animals",
                          json={"name": "Patient", "sex": sex, "date_of_birth": "2025-06-01"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestHealthRecords:
    async def test_vaccination_reuses_platform_reminder(self, async_client, workspace, auth_headers_owner,
                                                        integration_session):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/health"
        r = await async_client.post(
            f"{base}/animals/{aid}/vaccinations",
            json={"vaccine": "CDT", "administered_on": "2026-01-01", "next_due_on": "2026-07-01"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 201 and r.json()["data"]["reminder_id"] is not None
        # A platform Reminder tagged for the goat workspace was created — no SR table.
        rows = await integration_session.execute(
            select(Reminder).where(Reminder.farm_id == fid, Reminder.metadata_["module"].astext == "goat")
        )
        reminders = rows.scalars().all()
        assert any(rm.metadata_.get("kind") == "vaccination" for rm in reminders)

    async def test_deworming_with_famacha_and_summary(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "sheep", auth_headers_owner, sex="ewe")
        base = f"{_sr(fid, 'sheep')}/health"
        dw = await async_client.post(
            f"{base}/animals/{aid}/deworming",
            json={"product": "Ivermectin", "method": "oral_drench", "famacha_score": 4,
                  "administered_on": "2026-01-01", "next_due_on": "2026-02-01", "withdrawal_until": "2026-01-14"},
            headers=auth_headers_owner,
        )
        assert dw.status_code == 201 and dw.json()["data"]["famacha_score"] == 4
        summ = await async_client.get(f"{base}/summary", headers=auth_headers_owner)
        s = summ.json()["data"]
        assert s["disclaimer"] == "A recorded pattern, not a veterinary diagnosis."
        assert s["deworming_compliance"]["total_dewormings"]["value"] == 1

    async def test_hoof_care_records_condition(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/health"
        hc = await async_client.post(
            f"{base}/animals/{aid}/hoof-care",
            json={"action": "trimming", "condition": "overgrown", "lameness_score": 2, "performed_on": "2026-01-01"},
            headers=auth_headers_owner,
        )
        assert hc.status_code == 201 and hc.json()["data"]["condition"] == "overgrown"

    async def test_invalid_famacha_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_owner)
        r = await async_client.post(
            f"{_sr(fid, 'goat')}/health/animals/{aid}/deworming",
            json={"product": "X", "famacha_score": 9, "administered_on": "2026-01-01"}, headers=auth_headers_owner,
        )
        assert r.status_code == 422  # FAMACHA is 1–5


class TestMortalityAndPermissions:
    async def test_mortality_is_authoritative_and_one_per_animal(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/health"
        m = await async_client.post(f"{base}/animals/{aid}/mortality",
                                    json={"occurred_on": "2026-03-01", "cause": "disease"}, headers=auth_headers_owner)
        assert m.status_code == 201
        # Animal is now deceased.
        detail = await async_client.get(f"{_sr(fid, 'goat')}/animals/{aid}", headers=auth_headers_owner)
        assert detail.json()["data"]["status"] == "deceased"
        # A second mortality is rejected.
        again = await async_client.post(f"{base}/animals/{aid}/mortality",
                                        json={"occurred_on": "2026-03-02", "cause": "injury"}, headers=auth_headers_owner)
        assert again.status_code == 409

    async def test_vet_can_log_viewer_cannot(self, async_client, workspace, auth_headers_owner,
                                             auth_headers_vet, auth_headers_viewer):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/health"
        vet = await async_client.post(f"{base}/animals/{aid}/records",
                                      json={"event_type": "exam", "occurred_on": "2026-01-01"},
                                      headers=auth_headers_vet)
        assert vet.status_code == 201  # vet has SR_HEALTH_LOG
        denied = await async_client.post(f"{base}/animals/{aid}/records",
                                         json={"event_type": "exam", "occurred_on": "2026-01-02"},
                                         headers=auth_headers_viewer)
        assert denied.status_code == 403
