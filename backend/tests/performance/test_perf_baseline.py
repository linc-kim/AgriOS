"""
Gate 5 — Phase 1 baseline profiler (evidence collection, not a pass/fail test).

Runs representative farm-scoped GET endpoints through the in-process ASGI harness
and records, per endpoint, the number of SQL statements issued and the local wall
time. The **query count is the environment-independent signal**: an endpoint whose
count is high (or would grow with row count) is an N+1 / round-trip suspect worth
optimizing. Wall time here is local-dev only (in-process, tiny seeded dataset) and
must NOT be read as production latency — that needs the Phase 2 load test on a
production-like deploy.

Run:
    pytest tests/performance/test_perf_baseline.py -s -q

It always "passes"; the value is the printed table (captured into the Gate 5
baseline report).
"""

import statistics
import time

import pytest
from sqlalchemy import event

from tests.conftest import test_engine

pytestmark = pytest.mark.asyncio

# Query log populated by the listener while it is attached (scoped to the test
# below so it never grows during the rest of the suite).
_QUERIES: list[str] = []


def _record_query(conn, cursor, statement, params, context, executemany):
    _QUERIES.append(statement)


# Representative read surface across the launch modules (farm_id-only GETs).
_ENDPOINTS = [
    ("core:farm", "/api/v1/farms/{fid}"),
    ("core:flocks", "/api/v1/farms/{fid}/flocks"),
    ("core:production-dashboard", "/api/v1/farms/{fid}/production-dashboard"),
    ("finance:overview", "/api/v1/farms/{fid}/finance/overview"),
    ("finance:transactions", "/api/v1/farms/{fid}/finance/transactions"),
    ("finance:analytics", "/api/v1/farms/{fid}/finance/analytics"),
    ("health:summary", "/api/v1/farms/{fid}/health/summary"),
    ("health:alerts", "/api/v1/farms/{fid}/health/alerts"),
    ("ai:dashboard", "/api/v1/farms/{fid}/ai/dashboard"),
    ("aria:insights", "/api/v1/farms/{fid}/aria/insights"),
    ("automation:reminders", "/api/v1/farms/{fid}/automation/reminders"),
    ("aviculture:birds", "/api/v1/farms/{fid}/aviculture/birds"),
    ("bsf:batches", "/api/v1/farms/{fid}/bsf/batches"),
    ("rabbit:breeds", "/api/v1/farms/{fid}/rabbit/breeds"),
    ("operations:routines", "/api/v1/farms/{fid}/operations/routines"),
    ("data:exports", "/api/v1/farms/{fid}/data/exports"),
]

_ITERATIONS = 5


async def test_collect_endpoint_query_and_latency_baseline(
    async_client, workspace, auth_headers_owner
):
    fid = str(workspace.farm.id)
    event.listen(test_engine.sync_engine, "before_cursor_execute", _record_query)
    try:
        rows = await _profile(async_client, auth_headers_owner, fid)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _record_query)

    rows.sort(key=lambda r: r[2], reverse=True)  # worst query-count first
    print("\n\n=== GATE 5 BASELINE - query count + local latency (dev, in-process) ===")
    print(f"{'endpoint':<32}{'http':>6}{'q_median':>10}{'q_max':>8}{'ms_median':>12}")
    for label, status, qmed, qmax, ms in rows:
        print(f"{label:<32}{status:>6}{qmed:>10}{qmax:>8}{ms:>12}")
    print("=== end baseline ===\n")

    # Not a performance assertion — just that the surface responded, so the counts
    # above are meaningful (a 5xx would make a row's numbers noise).
    assert all(r[1] in (200, 403, 404, 422) for r in rows)


async def _profile(async_client, auth_headers_owner, fid):
    rows = []
    for label, template in _ENDPOINTS:
        path = template.replace("{fid}", fid)
        counts, times, status = [], [], None
        for _ in range(_ITERATIONS):
            _QUERIES.clear()
            t0 = time.perf_counter()
            resp = await async_client.get(path, headers=auth_headers_owner)
            times.append((time.perf_counter() - t0) * 1000)
            counts.append(len(_QUERIES))
            status = resp.status_code
        rows.append((
            label,
            status,
            int(statistics.median(counts)),
            max(counts),
            round(statistics.median(times), 1),
        ))
    return rows
