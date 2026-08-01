"""
Rabbit Sales & Finance (Module 17, Milestone 6) — over HTTP.

Confirms sales record revenue as a fact (and transition an active rabbit to sold),
product sales without a rabbit, operating costs reusing the SHARED expenses ledger
(tagged module=rabbit), the computed P&L tracing to recorded facts (revenue from
sales, feed cost from the M4 consumption allocation, operating cost from the
ledger), and RBAC.
"""

from datetime import date

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


class TestSales:
    async def test_sale_records_revenue_and_transitions_rabbit(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        sale = await async_client.post(
            f"{_rb(fid)}/sales",
            json={"rabbit_id": r["id"], "sale_type": "breeding_stock", "buyer_name": "Jane",
                  "sale_date": date.today().isoformat(), "total_price": 2500, "currency": "KES"},
            headers=auth_headers_owner,
        )
        assert sale.status_code == 201, sale.text
        assert float(sale.json()["data"]["total_price"]) == 2500.0
        detail = await async_client.get(f"{_rb(fid)}/rabbits/{r['id']}", headers=auth_headers_owner)
        assert detail.json()["data"]["status"] == "sold"

    async def test_product_sale_without_rabbit(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        sale = await async_client.post(
            f"{_rb(fid)}/sales",
            json={"sale_type": "meat", "sale_date": date.today().isoformat(),
                  "quantity": 5, "weight_kg": 8.5, "unit_price": 600, "total_price": 3000},
            headers=auth_headers_owner,
        )
        assert sale.status_code == 201, sale.text
        assert sale.json()["data"]["rabbit_id"] is None

    async def test_total_derived_from_unit_price(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        sale = await async_client.post(
            f"{_rb(fid)}/sales",
            json={"sale_type": "meat", "sale_date": date.today().isoformat(),
                  "quantity": 4, "unit_price": 250},
            headers=auth_headers_owner,
        )
        assert sale.status_code == 201
        assert float(sale.json()["data"]["total_price"]) == 1000.0  # 4 × 250


class TestFinanceReuse:
    async def test_pnl_traces_to_recorded_facts(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        # Revenue fact.
        await async_client.post(f"{_rb(fid)}/sales",
                                json={"rabbit_id": r["id"], "sale_type": "live",
                                      "sale_date": date.today().isoformat(), "total_price": 1000},
                                headers=auth_headers_owner)
        # Feed cost allocation (M4 recorded fact).
        await async_client.post(f"{_rb(fid)}/feed",
                                json={"quantity_kg": 4, "fed_on": date.today().isoformat(), "cost": 200},
                                headers=auth_headers_owner)
        # Operating cost via the SHARED ledger (tagged module=rabbit).
        exp = await async_client.post(f"{_rb(fid)}/finance/expenses",
                                      json={"category_slug": "vet_fees", "amount": 50, "description": "Vet visit"},
                                      headers=auth_headers_owner)
        assert exp.status_code == 201, exp.text

        summary = await async_client.get(f"{_rb(fid)}/finance/summary", headers=auth_headers_owner)
        assert summary.status_code == 200, summary.text
        pnl = summary.json()["data"]["pnl"]
        assert pnl["revenue"]["value"] == 1000.0 and pnl["revenue"]["label"] == "recorded"
        assert pnl["feed_cost"]["value"] == 200.0
        assert pnl["operating_cost"]["value"] == 50.0
        assert pnl["total_cost"]["value"] == 250.0          # feed 200 + opex 50
        assert pnl["gross_profit"]["value"] == 750.0
        econ = summary.json()["data"]["unit_economics"]
        assert econ["vet_cost_pct"]["value"] == round(50 / 250 * 100, 2)

    async def test_invalid_expense_category_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.post(f"{_rb(fid)}/finance/expenses",
                                    json={"category_slug": "not_a_category", "amount": 10, "description": "x"},
                                    headers=auth_headers_owner)
        assert r.status_code == 404


class TestRBAC:
    async def test_worker_cannot_post_expense(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        r = await async_client.post(f"{_rb(fid)}/finance/expenses",
                                    json={"category_slug": "labour", "amount": 100, "description": "wages"},
                                    headers=auth_headers_worker)
        assert r.status_code == 403  # worker lacks FINANCE_RECORD

    async def test_viewer_cannot_record_sale_but_can_read_summary(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        sale = await async_client.post(f"{_rb(fid)}/sales",
                                       json={"rabbit_id": r["id"], "sale_type": "live",
                                             "sale_date": date.today().isoformat(), "total_price": 100},
                                       headers=auth_headers_viewer)
        assert sale.status_code == 403
        assert (await async_client.get(f"{_rb(fid)}/finance/summary", headers=auth_headers_viewer)).status_code == 200
