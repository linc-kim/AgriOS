"""
Aviculture performance — no N+1 at scale (Module 15, Doc 15 §12/§14).

§12 requires the module to perform with thousands of birds/records without
unacceptable degradation. The structural guarantee behind that is that the
composed read paths issue a *bounded* number of queries regardless of collection
size — they batch with ``IN (...)`` rather than querying per bird. This test locks
that: it counts the SQL statements the collection-valuation path issues for a
small and a much larger collection and asserts the count does not grow with the
number of birds. A regression that reintroduced a per-bird query would fail here.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.models.aviculture import AviBird, AviSpecies, AviValuation
from app.services import aviculture_finance_service as fin
from app.services import aviculture_reporting_service as rep

pytestmark = pytest.mark.asyncio


class _Counter:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self, *_args) -> None:
        self.n += 1


async def _species(db) -> uuid.UUID:
    sp = AviSpecies(id=uuid.uuid4(), organization_id=None, common_name="Perf Grey", species_group="parrot")
    db.add(sp)
    await db.flush()
    return sp.id


async def _add_birds(db, farm_id, species_id, n: int, start: int) -> None:
    for i in range(start, start + n):
        bid = uuid.uuid4()
        db.add(AviBird(id=bid, farm_id=farm_id, species_id=species_id,
                       internal_ref=f"PERF-{i:05d}", status="active"))
        db.add(AviValuation(id=uuid.uuid4(), farm_id=farm_id, bird_id=bid,
                            valued_on=date.today(), amount=Decimal("1000"), method="appraised"))
    await db.flush()


async def _count(fn) -> int:
    c = _Counter()
    event.listen(Engine, "before_cursor_execute", c)
    try:
        await fn()
    finally:
        event.remove(Engine, "before_cursor_execute", c)
    return c.n


class _FarmRef:
    def __init__(self, id):  # dashboard() reads farm.id and farm.name
        self.id = id
        self.name = "Perf Farm"


class TestNoNPlusOne:
    async def test_valuation_query_count_is_constant(self, db, workspace):
        farm_id = workspace.farm.id
        sid = await _species(db)

        await _add_birds(db, farm_id, sid, 3, 0)
        small = await _count(lambda: fin.collection_valuation(db, farm_id))

        await _add_birds(db, farm_id, sid, 25, 100)  # ~9x the birds
        large = await _count(lambda: fin.collection_valuation(db, farm_id))

        assert large == small, f"N+1 detected: {small} queries for 3 birds, {large} for 28"
        assert small <= 8, f"unexpectedly many queries for a batched path: {small}"

    async def test_dashboard_query_count_does_not_scale_with_birds(self, db, workspace):
        farm = _FarmRef(workspace.farm.id)
        sid = await _species(db)

        await _add_birds(db, farm.id, sid, 4, 0)
        small = await _count(lambda: rep.dashboard(db, farm))

        await _add_birds(db, farm.id, sid, 30, 200)
        large = await _count(lambda: rep.dashboard(db, farm))

        assert large == small, f"dashboard N+1: {small} queries for 4 birds, {large} for 34"
