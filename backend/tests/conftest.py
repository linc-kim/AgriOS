"""
Greena Test Configuration.

Test database strategy
----------------------
The test database (``agrios_test``) is built by running the **Alembic migrations**
once per session, not ``Base.metadata.create_all``. This is deliberate:

* The migrations also seed the reference data the app depends on — 8 roles,
  3 subscription plans, 17 system expense categories, 5 species profiles — so
  integration tests exercise a production-shaped database.
* ``create_all`` cannot reproduce that seed data, and it also collides with the
  native ENUM types the migrations create.

Unit tests use the function-scoped ``db``/``client`` fixtures (rolled back after
each test). Integration tests use ``async_client`` and the session-scoped
``workspace`` harness, which commits a shared farm/flock/team so the ordered
flow tests can build on each other.
"""

import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.security import create_access_token
from app.database import Base, get_db
from app.database import engine as app_engine
from app.main import app
from app.models.auth import Role, User, UserRole
from app.models.farm import (
    Farm,
    FarmMember,
    FarmUnit,
    ProductionHouse,
    SubscriptionPlan,
)
from app.models.flock import DailyLog, Flock

BACKEND_DIR = Path(__file__).resolve().parents[1]

# ── Test Database ─────────────────────────────────────────────────────────────
# An explicit TEST_DATABASE_URL wins; otherwise derive it from the app URL by
# swapping only the database name. rsplit avoids corrupting a username that also
# contains "agrios" (e.g. postgresql+asyncpg://agrios:pw@host/agrios).
_default_test_url = settings.DATABASE_URL.rsplit("/agrios", 1)[0] + "/agrios_test"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", _default_test_url)


def _assert_disposable(url: str) -> None:
    """
    Refuse to run against anything that is not obviously a test database.

    setup_test_database drops and recreates the public schema. The default URL
    is derived by rewriting "/agrios" to "/agrios_test", which silently yields
    the *original* database when the name does not match — a Supabase URL ends
    in "/postgres", so the rewrite collapses and the suite would point at the
    live database it was handed. That failure mode ends with the production
    schema dropped, so it is checked rather than trusted.
    """
    from sqlalchemy.engine.url import make_url

    name = (make_url(url).database or "").lower()

    # A database name containing "/" means the rewrite above matched nothing and
    # simply appended — the URL is malformed and points at the original host and
    # database, not a test one.
    if "/" in name:
        raise RuntimeError(
            f"Refusing to run tests: derived test database {name!r} is malformed. "
            "The default is built by rewriting '/agrios' in DATABASE_URL, which "
            "matched nothing here. Set TEST_DATABASE_URL explicitly."
        )

    if not (name.endswith("_test") or name.startswith("test")):
        raise RuntimeError(
            f"Refusing to run tests against database {name!r}: the suite drops "
            "and recreates the public schema, so it only runs against a database "
            "whose name marks it as disposable (…_test). Set TEST_DATABASE_URL "
            "to a dedicated test database."
        )


_assert_disposable(TEST_DATABASE_URL)

# NullPool: every AsyncSession opens a fresh connection bound to the currently
# running event loop. Without it, the session-scoped engine reuses one pooled
# asyncpg connection across pytest-asyncio's per-test loops, which raises
# "another operation is in progress" on Windows/asyncpg.
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Build the test database from the Alembic migrations (schema + seed data).

    The public schema is dropped and recreated first — this clears both tables
    and the native ENUM types migrations create — then ``alembic upgrade head``
    is run in a subprocess pointed at the test database.
    """
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True,
        capture_output=True,
    )

    yield

    await test_engine.dispose()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """
    Clear the auth rate-limit window before each test.

    The limiter is process-wide sliding-window state. Without this, a run of
    auth tests accumulates past the 20-request limit and later tests get 429s
    for reasons unrelated to what they assert. Cleared rather than disabled, so
    the middleware is still exercised on every request.
    """
    from app.core.middleware import reset_rate_limits

    reset_rate_limits()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _dispose_app_engine():
    """
    Dispose the application's own engine after every test.

    A few endpoints (notably ``/health``) open a session from
    ``app.database.AsyncSessionLocal`` directly rather than through the injected
    ``get_db``, so they bypass the test session and use the app's pooled engine.
    pytest-asyncio runs each test in a fresh event loop, and a pooled asyncpg
    connection checked out under one loop is unusable from the next — which made
    ``test_health_db_connected`` report "'NoneType' object has no attribute
    'send'" whenever any earlier test had touched that pool, while passing when
    run alone.

    Disposing between tests keeps no connection alive across loops. This is the
    same reasoning behind ``test_engine``'s NullPool; the application's pooling
    config is correct for production, where there is a single loop.
    """
    yield
    await app_engine.dispose()


# ── Unit-test fixtures (function-scoped, rolled back) ─────────────────────────

@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    An async session whose changes are undone after each test.

    Bound to a dedicated connection inside an outer transaction, with
    ``create_savepoint`` join mode — the same isolation ``integration_conn``
    gives the flow tests. A plain session was used here before, which meant any
    ``commit()`` the endpoint itself issued was a real commit that the teardown
    rollback could not undo: seeded users and farms survived into later tests and
    tripped unique constraints, and left rows that made ``test_health_db_connected``
    pass alone but fail in a full run.
    """
    conn = await test_engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired to the rolled-back ``db`` session (unit tests)."""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_roles(db: AsyncSession) -> dict[str, Role]:
    """
    The 8 roles are seeded by migration 001. Return them keyed by name.

    Idempotent: if a run ever lacks the migration seed, insert the roles so the
    fixture still yields a usable mapping.
    """
    result = await db.execute(select(Role))
    roles = {r.name: r for r in result.scalars().all()}
    if roles:
        return roles

    role_defs = [
        ("super_admin", "Super Admin", True),
        ("platform_admin", "Platform Admin", True),
        ("enterprise_owner", "Enterprise Owner", False),
        ("farm_owner", "Farm Owner", False),
        ("farm_manager", "Farm Manager", False),
        ("vet_consultant", "Vet / Consultant", False),
        ("farm_worker", "Farm Worker", False),
        ("viewer", "Viewer", False),
    ]
    for name, display_name, is_platform in role_defs:
        role = Role(name=name, display_name=display_name, is_platform_role=is_platform)
        db.add(role)
        roles[name] = role
    await db.flush()
    return roles


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, seeded_roles) -> User:
    """A basic verified user (rolled back with the ``db`` session)."""
    user = User(
        phone="+254712345678",
        full_name="Test Farmer",
        is_phone_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Authorization header carrying a valid access token for ``test_user``."""
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


# ── Integration harness (committed, session-shared) ───────────────────────────

async def _commit_session():
    """A fresh committing session on the test engine (integration seeding)."""
    return TestSessionLocal()


class _Ref:
    """A tiny attribute bag exposing ``.id`` (and friends) for seeded rows."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


async def _make_house(session, farm_id, unit_id, name) -> ProductionHouse:
    house = ProductionHouse(
        farm_id=farm_id,
        unit_id=unit_id,
        name=name,
        capacity=1000,
        house_type="broiler",
        sort_order=0,
    )
    session.add(house)
    await session.flush()
    return house


@pytest_asyncio.fixture(scope="session")
async def workspace(setup_test_database):
    """
    Seed a shared, committed integration workspace and return its identifiers.

    Two farms are provisioned so their flock/house counts stay independent:

    * ``farm`` — used by the finance/health/aria/platform flows. It has one house
      occupied by an active ``flock`` (``test_flock``).
    * ``farm_b`` — used by the flock lifecycle flow. It starts with one empty
      house so flocks can be created against it.

    The same five users (owner, manager, worker, viewer, vet) are active members
    of both farms, so the per-role header/client fixtures work for either.
    """
    now = datetime.now(timezone.utc)
    async with TestSessionLocal() as s:
        roles = {r.name: r for r in (await s.execute(select(Role))).scalars().all()}
        free_plan = (
            await s.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "free"))
        ).scalar_one()

        # Five team members, one per role we exercise.
        user_specs = [
            ("owner", "farm_owner", "+254720000001", "Olivia Owner"),
            ("manager", "farm_manager", "+254720000002", "Mark Manager"),
            ("worker", "farm_worker", "+254720000003", "Winnie Worker"),
            ("viewer", "viewer", "+254720000004", "Vera Viewer"),
            ("vet", "vet_consultant", "+254720000005", "Victor Vet"),
        ]
        users: dict[str, User] = {}
        for key, _role, phone, name in user_specs:
            u = User(phone=phone, full_name=name, is_phone_verified=True, is_active=True)
            s.add(u)
            users[key] = u
        await s.flush()

        # Platform-level role assignment (farm_id=None) — this is what the
        # permission system (require_permission) reads, mirroring what the OTP
        # signup flow assigns to a new user.
        for key, role_name, _phone, _name in user_specs:
            s.add(
                UserRole(
                    user_id=users[key].id,
                    role_id=roles[role_name].id,
                    farm_id=None,
                )
            )
        await s.flush()

        def _new_farm(name: str) -> Farm:
            return Farm(
                name=name,
                county="Nairobi",
                location="Test Location",
                owner_id=users["owner"].id,
                plan_id=free_plan.id,
                is_active=True,
                timezone="Africa/Nairobi",
            )

        farm_a = _new_farm("Harness Farm A")
        farm_b = _new_farm("Harness Farm B")
        s.add_all([farm_a, farm_b])
        await s.flush()

        # Memberships: every user is an active member of both farms.
        for farm in (farm_a, farm_b):
            for key, role_name, _phone, _name in user_specs:
                s.add(
                    FarmMember(
                        farm_id=farm.id,
                        user_id=users[key].id,
                        role_id=roles[role_name].id,
                        phone=users[key].phone,
                        status="active",
                        invited_by=users["owner"].id,
                        accepted_at=now,
                    )
                )

        # A platform super_admin (not a farm member — used for admin-only
        # endpoints such as publishing market prices).
        admin = User(
            phone="+254720000006",
            full_name="Sam Admin",
            is_phone_verified=True,
            is_active=True,
        )
        s.add(admin)
        await s.flush()
        s.add(UserRole(user_id=admin.id, role_id=roles["super_admin"].id, farm_id=None))
        users["super_admin"] = admin

        # Farm A: a unit + one house occupied by an active flock.
        unit_a = FarmUnit(farm_id=farm_a.id, name="Unit A", sort_order=0)
        s.add(unit_a)
        await s.flush()
        house_a = await _make_house(s, farm_a.id, unit_a.id, "House A1")
        flock = Flock(
            farm_id=farm_a.id,
            house_id=house_a.id,
            species_key="poultry",
            name="Harness Flock",
            initial_count=500,
            # Placed well in the past so tests can log historical events
            # (vaccinations, weigh-ins) without tripping "before placement" checks.
            placement_date=date.today() - timedelta(days=60),
            status="active",
        )
        s.add(flock)
        await s.flush()
        house_a.current_flock_id = flock.id

        # Farm B: a unit + one empty house for the flock lifecycle flow.
        unit_b = FarmUnit(farm_id=farm_b.id, name="Unit B", sort_order=0)
        s.add(unit_b)
        await s.flush()
        house_b = await _make_house(s, farm_b.id, unit_b.id, "House B1")

        await s.commit()

        tokens = {key: create_access_token(str(u.id)) for key, u in users.items()}
        return _Ref(
            users={k: _Ref(id=u.id, phone=u.phone) for k, u in users.items()},
            tokens=tokens,
            farm=_Ref(id=farm_a.id, county="Nairobi"),
            flock=_Ref(id=flock.id, house_id=house_a.id),
            farm_b=_Ref(id=farm_b.id, house_id=house_b.id, unit_id=unit_b.id),
        )


@pytest_asyncio.fixture
async def integration_conn(workspace):
    """
    A single connection wrapped in an outer transaction that is rolled back after
    each test. Sessions built on it use ``create_savepoint`` join mode, so the
    endpoints' own ``commit()`` calls become SAVEPOINT releases — every test sees
    the committed ``workspace`` baseline but its writes are undone at teardown.
    This gives real per-test isolation despite the app committing.
    """
    conn = await test_engine.connect()
    trans = await conn.begin()
    try:
        yield conn
    finally:
        await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def integration_session(integration_conn) -> AsyncGenerator[AsyncSession, None]:
    """
    A committing session on the per-test isolated connection, for flow tests that
    need to seed extra rows (disease alerts, closed flocks, market prices, …).
    Writes are visible to ``async_client`` (same connection) and rolled back with
    it at teardown.
    """
    session = AsyncSession(
        bind=integration_conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def async_client(integration_conn) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP client whose DB dependency writes on the per-test isolated connection.

    A single session is shared across every request in the test and bound to the
    isolated connection with ``create_savepoint`` join mode. Each endpoint's
    ``commit()`` releases and restarts a SAVEPOINT, so writes from earlier
    requests are visible to later ones, yet the whole test is undone when
    ``integration_conn`` rolls back. Auth is passed per-request via the
    ``auth_headers_*`` fixtures.
    """
    session = AsyncSession(
        bind=integration_conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        await session.close()
        app.dependency_overrides.clear()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_owner(workspace) -> dict[str, str]:
    return _bearer(workspace.tokens["owner"])


@pytest.fixture
def auth_headers_manager(workspace) -> dict[str, str]:
    return _bearer(workspace.tokens["manager"])


@pytest.fixture
def auth_headers_worker(workspace) -> dict[str, str]:
    return _bearer(workspace.tokens["worker"])


@pytest.fixture
def auth_headers_viewer(workspace) -> dict[str, str]:
    return _bearer(workspace.tokens["viewer"])


@pytest.fixture
def auth_headers_vet(workspace) -> dict[str, str]:
    return _bearer(workspace.tokens["vet"])


@pytest.fixture
def auth_headers_super_admin(workspace) -> dict[str, str]:
    return _bearer(workspace.tokens["super_admin"])


@pytest.fixture
def test_farm(workspace):
    """The shared farm (with an active flock) for module flow tests."""
    return workspace.farm


@pytest.fixture
def test_flock(workspace):
    """The active flock inside ``test_farm``."""
    return workspace.flock


@pytest.fixture
def farm_with_house(workspace) -> dict:
    """Farm B identifiers (an empty house) for the flock lifecycle flow."""
    return {
        "farm_id": str(workspace.farm_b.id),
        "house_id": str(workspace.farm_b.house_id),
        "unit_id": str(workspace.farm_b.unit_id),
    }


@pytest_asyncio.fixture
async def farm_with_active_flock(integration_session, workspace) -> dict:
    """
    Farm B with an active flock already placed in its house.

    ``farm_with_house`` hands back an *empty* house, which suits the creation
    tests; the daily-log, weigh-in, feed-purchase and close-flock tests instead
    need a flock that already exists. The flock is written on the per-test
    connection, so it is visible to ``async_client`` and rolled back at teardown
    — Farm B's house is left empty for the tests that place their own flock.

    Placed 60 days back so historical events (weigh-ins, vaccinations) do not
    trip the "before placement date" validation.
    """
    flock = Flock(
        farm_id=workspace.farm_b.id,
        house_id=workspace.farm_b.house_id,
        species_key="poultry",
        name="Active Flock",
        initial_count=500,
        placement_date=date.today() - timedelta(days=60),
        status="active",
    )
    integration_session.add(flock)
    await integration_session.flush()

    house = await integration_session.get(ProductionHouse, workspace.farm_b.house_id)
    house.current_flock_id = flock.id
    await integration_session.commit()

    return {
        "farm_id": str(workspace.farm_b.id),
        "house_id": str(workspace.farm_b.house_id),
        "unit_id": str(workspace.farm_b.unit_id),
        "flock_id": str(flock.id),
    }


@pytest_asyncio.fixture
async def farm_with_logged_flock(
    integration_session, workspace, farm_with_active_flock
) -> dict:
    """
    The active flock from ``farm_with_active_flock`` plus seven days of daily
    logs, for the metric (survival rate, FCR, feed totals) and log-correction
    tests. Adds ``log_date`` — the most recent logged day — to the dict.
    """
    flock_id = uuid.UUID(farm_with_active_flock["flock_id"])
    today = date.today()

    for days_ago in range(7, 0, -1):
        integration_session.add(
            DailyLog(
                farm_id=workspace.farm_b.id,
                flock_id=flock_id,
                log_date=today - timedelta(days=days_ago),
                morning_count=500 - (7 - days_ago),
                mortality_count=1,
                feed_consumed_kg=Decimal("25.000"),
                water_litres=Decimal("50.000"),
            )
        )
    await integration_session.commit()

    return {**farm_with_active_flock, "log_date": str(today - timedelta(days=1))}


@pytest_asyncio.fixture
async def farm_with_closed_flock(integration_session, workspace) -> dict:
    """
    Farm B with a closed flock, for the tests asserting that a closed flock
    rejects further writes. The house is left unoccupied, as closing a flock
    releases it.
    """
    flock = Flock(
        farm_id=workspace.farm_b.id,
        house_id=workspace.farm_b.house_id,
        species_key="poultry",
        name="Closed Flock",
        initial_count=500,
        placement_date=date.today() - timedelta(days=90),
        status="sold",
    )
    integration_session.add(flock)
    await integration_session.commit()

    return {
        "farm_id": str(workspace.farm_b.id),
        "house_id": str(workspace.farm_b.house_id),
        "flock_id": str(flock.id),
    }


@pytest_asyncio.fixture
async def farm_at_flock_limit(integration_session, workspace) -> dict:
    """
    Farm B holding the free plan's maximum of 3 active flocks, plus one spare
    empty house. Creating a flock in ``extra_house_id`` must be rejected with
    402 PLAN_LIMIT rather than succeeding.
    """
    # Farm B's own house takes the first flock; two more houses for flocks 2-3.
    houses = [workspace.farm_b.house_id]
    for i in range(2, 4):
        h = await _make_house(
            integration_session, workspace.farm_b.id, workspace.farm_b.unit_id, f"House B{i}"
        )
        houses.append(h.id)

    for i, house_id in enumerate(houses, start=1):
        flock = Flock(
            farm_id=workspace.farm_b.id,
            house_id=house_id,
            species_key="poultry",
            name=f"Batch {i}",
            initial_count=100,
            placement_date=date.today() - timedelta(days=30),
            status="active",
        )
        integration_session.add(flock)
        await integration_session.flush()
        house = await integration_session.get(ProductionHouse, house_id)
        house.current_flock_id = flock.id

    # The spare house the 4th flock would go into.
    extra = await _make_house(
        integration_session, workspace.farm_b.id, workspace.farm_b.unit_id, "House B4"
    )
    await integration_session.commit()

    return {
        "farm_id": str(workspace.farm_b.id),
        "extra_house_id": str(extra.id),
    }


@pytest_asyncio.fixture
async def authenticated_client(
    async_client: AsyncClient, workspace
) -> AsyncGenerator[AsyncClient, None]:
    """``async_client`` pre-authenticated as the Farm B owner."""
    async_client.headers.update(_bearer(workspace.tokens["owner"]))
    yield async_client


@pytest_asyncio.fixture
async def worker_client(
    async_client: AsyncClient, workspace
) -> AsyncGenerator[AsyncClient, None]:
    """``async_client`` pre-authenticated as a farm worker."""
    async_client.headers.update(_bearer(workspace.tokens["worker"]))
    yield async_client


@pytest_asyncio.fixture
async def viewer_client(
    async_client: AsyncClient, workspace
) -> AsyncGenerator[AsyncClient, None]:
    """``async_client`` pre-authenticated as a viewer."""
    async_client.headers.update(_bearer(workspace.tokens["viewer"]))
    yield async_client
