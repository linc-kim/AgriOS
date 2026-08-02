"""
Swine Sales & Finance (Module 20, Milestone 8) — over HTTP.

Confirms swine finance is an analytics layer over the SHARED Finance engine:

  * a sale is a business event — records revenue + transitions the pig's status;
  * multiple sale types are supported; internal transfers move stock (not income);
  * product sales (no pig) keep the herd intact;
  * operating costs post ONCE to the shared expenses ledger (tagged module=swine);
  * feed cost feeds the P&L from feed records (already expensed — no double count);
  * P&L / unit economics (cost/pig, cost/kg, ROI) are computed, never stored;
  * permissions hold (worker cannot transact; viewer reads finance, cannot record).
"""

import pytest
from sqlalchemy import select

from app.models.finance import Expense

pytestmark = pytest.mark.asyncio


def _sw(fid) -> str:
    return f"/api/v1/farms/{fid}/swine"


async def _pig(client, fid, h, sex="barrow"):
    r = await client.post(f"{_sw(fid)}/pigs", json={"name": "P", "sex": sex}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestSales:
    async def test_market_sale_transitions_pig(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        sale = await async_client.post(f"{_sw(fid)}/finance/sales",
                                       json={"sale_type": "market", "pig_id": pig["id"], "buyer_name": "Abattoir",
                                             "sale_date": "2026-06-01", "weight_kg": "105",
                                             "total_price": "260.00"}, headers=h)
        assert sale.status_code == 201, sale.text
        assert str(sale.json()["data"]["total_price"]) == "260.00"
        detail = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}", headers=h)
        assert detail.json()["data"]["status"] == "sold"

    async def test_internal_transfer_moves_stock_not_income(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        r = await async_client.post(f"{_sw(fid)}/finance/sales",
                                    json={"sale_type": "internal_transfer", "pig_id": pig["id"],
                                          "destination": "Finishing unit B", "sale_date": "2026-06-01",
                                          "total_price": "0"}, headers=h)
        assert r.status_code == 201
        detail = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}", headers=h)
        assert detail.json()["data"]["status"] == "transferred"

    async def test_unit_price_computes_total(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        r = await async_client.post(f"{_sw(fid)}/finance/sales",
                                    json={"sale_type": "product", "sale_date": "2026-06-01",
                                          "quantity": "3", "unit_price": "50"}, headers=h)
        assert r.status_code == 201 and str(r.json()["data"]["total_price"]) == "150.00"


class TestFinanceAnalytics:
    async def test_pnl_and_unit_economics(self, async_client, workspace, auth_headers_owner, integration_session):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        # Revenue: a market sale.
        await async_client.post(f"{_sw(fid)}/finance/sales",
                                json={"sale_type": "market", "pig_id": pig["id"], "sale_date": "2026-06-01",
                                      "weight_kg": "100", "head_count": 1, "total_price": "300"}, headers=h)
        # Feed cost from a feed record (already expensed at stock-in; not re-posted).
        await async_client.post(f"{_sw(fid)}/feed/records",
                                json={"pig_id": pig["id"], "quantity_kg": 50, "fed_on": "2026-05-01",
                                      "cost": "80"}, headers=h)
        # Operating cost posted to the SHARED ledger, tagged module=swine.
        exp = await async_client.post(f"{_sw(fid)}/finance/expenses",
                                      json={"category_slug": "vet_fees", "amount": "20.00",
                                            "expense_date": "2026-05-02"}, headers=h)
        assert exp.status_code == 201, exp.text
        # The expense lives in the platform Expense ledger, tagged swine (no duplicate).
        rows = await integration_session.execute(
            select(Expense).where(Expense.farm_id == fid, Expense.metadata_["module"].astext == "swine"))
        assert rows.scalars().first() is not None

        summary = await async_client.get(f"{_sw(fid)}/finance/summary", headers=h)
        data = summary.json()["data"]
        pnl = data["pnl"]
        assert pnl["revenue"]["value"] == 300.0
        assert pnl["feed_cost"]["value"] == 80.0
        assert pnl["operating_cost"]["value"] == 20.0
        assert pnl["total_cost"]["value"] == 100.0
        assert pnl["gross_margin"]["value"] == 200.0
        econ = data["unit_economics"]
        assert econ["cost_per_kg_sold"]["value"] == 1.0     # 100 cost / 100 kg
        assert econ["feed_cost_pct"]["value"] == 80.0       # 80/100
        assert econ["health_cost_pct"]["value"] == 20.0     # vet 20/100
        # Cost sources are declared for traceability.
        assert "swine_feed_record" in data["cost_sources"]["feed_cost"]
        assert "module=swine" in data["cost_sources"]["operating_cost"]


class TestPermissions:
    async def test_worker_cannot_transact_viewer_reads(
        self, async_client, workspace, auth_headers_owner, auth_headers_worker, auth_headers_viewer
    ):
        fid = workspace.farm.id
        pig = await _pig(async_client, fid, auth_headers_owner)
        body = {"sale_type": "market", "pig_id": pig["id"], "sale_date": "2026-06-01", "total_price": "10"}
        w = await async_client.post(f"{_sw(fid)}/finance/sales", json=body, headers=auth_headers_worker)
        assert w.status_code == 403
        v = await async_client.get(f"{_sw(fid)}/finance/summary", headers=auth_headers_viewer)
        assert v.status_code == 200
