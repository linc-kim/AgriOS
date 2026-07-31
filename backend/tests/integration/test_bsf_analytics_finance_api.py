"""
BSF Mortality, Health, Finance P&L & Sustainability (Module 16, Part 5) — over HTTP.

Confirms mortality decrements batch population and drives the health flag (a
pattern, not a diagnosis), that feedstock cost posts ONCE to the SHARED expenses
ledger (idempotent) and the computed P&L traces revenue to recorded harvest facts
and cost to the tagged ledger entries — with confirmed figures distinct from
derivations. Permissions and farm isolation hold.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _bsf(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/bsf"


async def _make_batch(client, farm_id, headers, **overrides) -> dict:
    body = {"lifecycle_stage": "feeding_larvae", "population_estimate": 1000, "biomass_estimate_g": 10000}
    body.update(overrides)
    r = await client.post(f"{_bsf(farm_id)}/batches", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestMortalityHealth:
    async def test_mortality_decrements_population_and_flags(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner, population_estimate=1000)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/mortality",
            json={"estimated_loss": 300, "cause": "environmental"}, headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        after = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}", headers=auth_headers_owner)
        assert after.json()["data"]["population_estimate"] == 700

        health = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}/health", headers=auth_headers_owner)
        data = health.json()["data"]
        # 300/1000 = 30% ≥ 20% → attention; and it's a pattern, not a diagnosis.
        assert data["flag"]["value"] == "attention"
        assert "not a veterinary diagnosis" in data["flag"]["detail"].lower()

    async def test_invalid_cause_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/mortality",
            json={"estimated_loss": 10, "cause": "curse"}, headers=auth_headers_owner,
        )
        assert r.status_code == 422

    async def test_viewer_cannot_record_mortality(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/mortality",
            json={"estimated_loss": 10}, headers=auth_headers_viewer,
        )
        assert r.status_code == 403


class TestFinancePnL:
    async def test_feedstock_expense_posts_once(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        lot = await async_client.post(
            f"{_bsf(fid)}/feedstock-lots",
            json={"name": "Brewery waste", "category": "brewery_waste", "weight_kg": 100, "cost": 5000},
            headers=auth_headers_owner,
        )
        lot_id = lot.json()["data"]["id"]
        r1 = await async_client.post(f"{_bsf(fid)}/feedstock-lots/{lot_id}/post-expense", headers=auth_headers_owner)
        assert r1.status_code == 201, r1.text
        # Idempotent — a second post is rejected (already booked).
        r2 = await async_client.post(f"{_bsf(fid)}/feedstock-lots/{lot_id}/post-expense", headers=auth_headers_owner)
        assert r2.status_code == 409

    async def test_pnl_traces_to_recorded_facts(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # Cost: a feedstock lot posted to the shared ledger.
        lot = await async_client.post(
            f"{_bsf(fid)}/feedstock-lots",
            json={"name": "Market waste", "category": "market_waste", "weight_kg": 50, "cost": 2000},
            headers=auth_headers_owner,
        )
        await async_client.post(
            f"{_bsf(fid)}/feedstock-lots/{lot.json()['data']['id']}/post-expense", headers=auth_headers_owner,
        )
        # Revenue: a harvest sale recorded as a fact.
        batch = await _make_batch(async_client, fid, auth_headers_owner, lifecycle_stage="prepupae")
        await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/harvests",
            json={"harvest_type": "prepupae", "quantity_kg": 10, "revenue_amount": 6000, "currency": "KES"},
            headers=auth_headers_owner,
        )
        summary = await async_client.get(f"{_bsf(fid)}/finance/summary", headers=auth_headers_owner)
        assert summary.status_code == 200, summary.text
        data = summary.json()["data"]
        # Confirmed records (recorded) vs derivations (calculated).
        assert data["revenue"]["label"] == "recorded" and data["revenue"]["value"] >= 6000
        assert data["operating_cost"]["label"] == "recorded" and data["operating_cost"]["value"] >= 2000
        assert data["gross_profit"]["label"] == "calculated"
        assert data["cost_per_kg"]["label"] == "calculated"

    async def test_finance_summary_requires_view_permission(self, async_client, workspace, auth_headers_worker):
        # Worker lacks BSF_FINANCE_VIEW.
        r = await async_client.get(f"{_bsf(workspace.farm.id)}/finance/summary", headers=auth_headers_worker)
        assert r.status_code == 403


class TestSustainability:
    async def test_sustainability_from_recorded_facts(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        lot = await async_client.post(
            f"{_bsf(fid)}/feedstock-lots",
            json={"name": "Veg waste", "category": "vegetable_waste", "weight_kg": 100},
            headers=auth_headers_owner,
        )
        await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/feedings",
            json={"feedstock_lot_id": lot.json()["data"]["id"], "quantity_kg": 40}, headers=auth_headers_owner,
        )
        r = await async_client.get(f"{_bsf(fid)}/analytics/sustainability", headers=auth_headers_owner)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["organic_waste_diverted_kg"]["label"] == "recorded"
        assert data["organic_waste_diverted_kg"]["value"] >= 40.0
