"""
Small Ruminant Sales & Finance (Modules 18/19, Milestone 8) — over HTTP.

Sale revenue is a recorded fact (an animal sale transitions it to sold; product
sales do not); operating costs post to the SHARED expenses ledger tagged by
species; the P&L is computed from recorded facts. DB-07 respected (revenue never
posted to the flock-scoped ledger). Permissions hold.
"""

import pytest
from sqlalchemy import select

from app.models.finance import Expense

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _animal(client, fid, headers, species="goat", sex="doe") -> str:
    r = await client.post(f"{_sr(fid, species)}/animals", json={"name": "S", "sex": sex}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestSalesAndFinance:
    async def test_animal_sale_transitions_to_sold(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/finance"
        sale = await async_client.post(f"{base}/sales",
                                       json={"sale_type": "live", "animal_id": aid, "buyer_name": "Mkt",
                                             "sale_date": "2026-03-01", "weight_kg": "35",
                                             "total_price": "150.00"}, headers=auth_headers_owner)
        assert sale.status_code == 201 and sale.json()["data"]["total_price"] == "150.00"
        detail = await async_client.get(f"{_sr(fid, 'goat')}/animals/{aid}", headers=auth_headers_owner)
        assert detail.json()["data"]["status"] == "sold"

    async def test_product_sale_keeps_animal_and_pnl_computes(self, async_client, workspace,
                                                              auth_headers_owner, integration_session):
        fid = workspace.farm.id
        base = f"{_sr(fid, 'goat')}/finance"
        # A milk product sale (no animal transition).
        milk = await async_client.post(f"{base}/sales",
                                       json={"sale_type": "milk", "sale_date": "2026-03-01", "quantity": "20",
                                             "unit": "litre", "unit_price": "0.80"}, headers=auth_headers_owner)
        assert milk.status_code == 201 and milk.json()["data"]["total_price"] == "16.00"  # 20 × 0.80

        # Post an operating cost to the SHARED ledger, tagged for the goat workspace.
        exp = await async_client.post(f"{base}/expenses",
                                      json={"category_slug": "vet_fees", "amount": "10.00",
                                            "expense_date": "2026-03-02", "description": "vet"},
                                      headers=auth_headers_owner)
        assert exp.status_code == 201
        # Verify it landed in the platform Expense ledger tagged module=goat.
        rows = await integration_session.execute(
            select(Expense).where(Expense.farm_id == fid, Expense.metadata_["module"].astext == "goat")
        )
        assert rows.scalars().first() is not None

        summary = await async_client.get(f"{base}/summary", headers=auth_headers_owner)
        pnl = summary.json()["data"]["pnl"]
        assert pnl["revenue"]["value"] == 16.0
        assert pnl["operating_cost"]["value"] == 10.0
        assert pnl["gross_margin"]["value"] == 6.0
        # vet cost % attributed via the shared category join.
        assert summary.json()["data"]["unit_economics"]["vet_cost_pct"]["value"] == 100.0

    async def test_permissions(self, async_client, workspace, auth_headers_owner, auth_headers_worker,
                               auth_headers_viewer):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/finance"
        # Worker cannot record sales (transactional/strategic) nor see finance.
        sale = await async_client.post(f"{base}/sales",
                                       json={"sale_type": "live", "animal_id": aid, "sale_date": "2026-03-01",
                                             "total_price": "10"}, headers=auth_headers_worker)
        assert sale.status_code == 403
        summ = await async_client.get(f"{base}/summary", headers=auth_headers_worker)
        assert summ.status_code == 403
        # Viewer can read finance but not record.
        vsumm = await async_client.get(f"{base}/summary", headers=auth_headers_viewer)
        assert vsumm.status_code == 200
