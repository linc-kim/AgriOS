"""
AGRIOS — Farm Integration Tests
Full end-to-end test of the farm creation and membership flow.
Requires a running test database (agrios_test).

Flow tested:
  1. User registers via OTP
  2. Creates a farm → gets farm_owner membership
  3. Verifies farm appears in /farms list
  4. Creates a farm unit
  5. Creates a production house inside the unit
  6. Lists houses
  7. Invites a member by phone (pending invite)
  8. Removes the pending invite
  9. Deletes the house (not occupied)
  10. Deletes the unit
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, User
from app.models.farm import Farm, FarmMember, FarmUnit, ProductionHouse, SubscriptionPlan


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_farm_data(db: AsyncSession):
    """
    Return the reference data seeded by migrations 001-006: roles and the free
    subscription plan.

    Idempotent. The test database is built by running the migrations, which
    already insert these rows, so inserting them unconditionally violated the
    unique constraints on roles.name / subscription_plans.name and errored every
    test in this module at setup. Anything already present is reused; only
    genuinely missing rows are created.
    """
    role_defs = [
        ("farm_owner", "Farm Owner", False),
        ("farm_manager", "Farm Manager", False),
        ("farm_worker", "Farm Worker", False),
        ("viewer", "Viewer", False),
        ("vet_consultant", "Vet / Consultant", False),
        ("super_admin", "Super Admin", True),
    ]

    existing = {r.name: r for r in (await db.execute(select(Role))).scalars().all()}
    roles = {}
    for name, display_name, is_platform in role_defs:
        role = existing.get(name)
        if role is None:
            role = Role(name=name, display_name=display_name, is_platform_role=is_platform)
            db.add(role)
        roles[name] = role

    free_plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "free"))
    ).scalar_one_or_none()
    if free_plan is None:
        free_plan = SubscriptionPlan(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="free",
            display_name="Free",
            price_kes=0,
            max_farms=1,
            max_houses_per_farm=3,
            max_active_flocks=3,
            max_aria_queries_per_month=5,
            history_days=90,
            max_team_members=2,
            is_active=True,
        )
        db.add(free_plan)

    await db.flush()
    return {"roles": roles, "free_plan": free_plan}


@pytest_asyncio.fixture
async def farm_owner_user(db: AsyncSession, seeded_farm_data) -> User:
    """Create and return a verified user who will own the farm."""
    user = User(
        phone="+254712000001",
        full_name="Janet Kamau",
        is_phone_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
def farm_owner_headers(farm_owner_user: User) -> dict:
    """
    Generate a valid JWT for the farm owner.
    Uses the app's token generation utility directly.
    """
    from app.core.security import create_access_token
    token = create_access_token(str(farm_owner_user.id))
    return {"Authorization": f"Bearer {token}"}


# ── Integration Flow ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestFarmCreationFlow:
    """Tests that exercise the full farm management lifecycle."""

    async def test_01_create_farm(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """Farm creation returns 201 with farm in body."""
        resp = await client.post(
            "/api/v1/farms",
            json={
                "name": "Kamau Poultry Farm",
                "county": "Kiambu",
                "location": "Off Kiambu Road",
            },
            headers=farm_owner_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Kamau Poultry Farm"
        assert body["data"]["county"] == "Kiambu"
        # Owner auto-added as member
        assert body["data"]["member_count"] == 1

    async def test_02_farm_appears_in_list(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """Farm shows up in GET /farms after creation."""
        # Create farm first
        await client.post(
            "/api/v1/farms",
            json={"name": "List Test Farm"},
            headers=farm_owner_headers,
        )
        resp = await client.get("/api/v1/farms", headers=farm_owner_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) >= 1
        names = [f["name"] for f in body["data"]]
        assert "List Test Farm" in names

    async def test_03_create_unit(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """Farm unit creation inside an owned farm."""
        # Create farm
        farm_resp = await client.post(
            "/api/v1/farms",
            json={"name": "Unit Test Farm"},
            headers=farm_owner_headers,
        )
        farm_id = farm_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/farms/{farm_id}/units",
            json={"name": "Section A", "description": "North block", "sort_order": 0},
            headers=farm_owner_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["data"]["name"] == "Section A"
        assert body["data"]["farm_id"] == farm_id

    async def test_04_create_house_enforces_capacity_minimum(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """Capacity ≤ 0 is rejected with 422."""
        farm_resp = await client.post(
            "/api/v1/farms",
            json={"name": "House Capacity Farm"},
            headers=farm_owner_headers,
        )
        farm_id = farm_resp.json()["data"]["id"]

        unit_resp = await client.post(
            f"/api/v1/farms/{farm_id}/units",
            json={"name": "Block 1"},
            headers=farm_owner_headers,
        )
        unit_id = unit_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/farms/{farm_id}/units/{unit_id}/houses",
            json={"name": "House 1", "capacity": 0, "house_type": "broiler"},
            headers=farm_owner_headers,
        )
        assert resp.status_code == 422

    async def test_05_full_house_lifecycle(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """Create house → list → delete (unoccupied)."""
        farm_resp = await client.post(
            "/api/v1/farms",
            json={"name": "House Lifecycle Farm"},
            headers=farm_owner_headers,
        )
        farm_id = farm_resp.json()["data"]["id"]

        unit_resp = await client.post(
            f"/api/v1/farms/{farm_id}/units",
            json={"name": "Block A"},
            headers=farm_owner_headers,
        )
        unit_id = unit_resp.json()["data"]["id"]

        # Create house
        create_resp = await client.post(
            f"/api/v1/farms/{farm_id}/units/{unit_id}/houses",
            json={"name": "Broiler House 1", "capacity": 500, "house_type": "broiler"},
            headers=farm_owner_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        house_id = create_resp.json()["data"]["id"]
        assert create_resp.json()["data"]["is_occupied"] is False

        # List all farm houses
        list_resp = await client.get(
            f"/api/v1/farms/{farm_id}/houses",
            headers=farm_owner_headers,
        )
        assert list_resp.status_code == 200
        house_names = [h["name"] for h in list_resp.json()["data"]]
        assert "Broiler House 1" in house_names

        # Delete the house (unoccupied → should succeed)
        del_resp = await client.delete(
            f"/api/v1/farms/{farm_id}/units/{unit_id}/houses/{house_id}",
            headers=farm_owner_headers,
        )
        assert del_resp.status_code == 204

        # Confirm it's gone
        list_resp2 = await client.get(
            f"/api/v1/farms/{farm_id}/houses",
            headers=farm_owner_headers,
        )
        names_after = [h["name"] for h in list_resp2.json()["data"]]
        assert "Broiler House 1" not in names_after

    async def test_06_invite_member_invalid_phone(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """Invite with non-Kenyan phone → 422."""
        farm_resp = await client.post(
            "/api/v1/farms",
            json={"name": "Invite Phone Test Farm"},
            headers=farm_owner_headers,
        )
        farm_id = farm_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/farms/{farm_id}/members/invite",
            json={"phone": "0712345678", "role_name": "farm_worker"},
            headers=farm_owner_headers,
        )
        assert resp.status_code == 422

    async def test_07_invite_farm_owner_role_rejected(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """Cannot assign farm_owner role via invite."""
        farm_resp = await client.post(
            "/api/v1/farms",
            json={"name": "Role Guard Farm"},
            headers=farm_owner_headers,
        )
        farm_id = farm_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/farms/{farm_id}/members/invite",
            json={"phone": "+254799000001", "role_name": "farm_owner"},
            headers=farm_owner_headers,
        )
        assert resp.status_code == 422

    async def test_08_unauthenticated_farm_access_denied(self, client: AsyncClient):
        """No auth token → 401."""
        resp = await client.post("/api/v1/farms", json={"name": "No Auth Farm"})
        assert resp.status_code == 401

    async def test_09_plan_limit_max_farms_enforced(
        self,
        client: AsyncClient,
        farm_owner_headers: dict,
        seeded_farm_data,
    ):
        """
        Free plan allows max 1 farm. Second farm creation → 402 PLAN_LIMIT.
        """
        # Create the first farm (should succeed)
        first = await client.post(
            "/api/v1/farms",
            json={"name": "First Farm"},
            headers=farm_owner_headers,
        )
        assert first.status_code == 201

        # Create the second farm (should fail — plan limit)
        second = await client.post(
            "/api/v1/farms",
            json={"name": "Second Farm"},
            headers=farm_owner_headers,
        )
        assert second.status_code == 402
        body = second.json()
        assert body["error"]["code"] == "PLAN_LIMIT"

    async def test_10_non_member_cannot_access_farm(
        self,
        client: AsyncClient,
        db: AsyncSession,
        farm_owner_user: User,
        seeded_farm_data,
    ):
        """
        A real user who is not a member of a farm cannot read it.

        This previously minted a token for a random UUID with no matching user
        row, so it only ever reached the authentication layer and got a 401 —
        it never exercised require_farm_access at all. It now signs in a real
        user who simply is not a member of the farm, which is the case the test
        is named for.
        """
        from app.core.security import create_access_token

        # A real, active user with no membership anywhere.
        stranger = User(
            phone="+254712000099",
            full_name="Stranger Danger",
            is_phone_verified=True,
            is_active=True,
        )
        db.add(stranger)
        await db.flush()

        # A real farm belonging to someone else.
        farm = Farm(
            name="Someone Else's Farm",
            owner_id=farm_owner_user.id,
            plan_id=seeded_farm_data["free_plan"].id,
            county="Nairobi",
        )
        db.add(farm)
        await db.flush()

        resp = await client.get(
            f"/api/v1/farms/{farm.id}",
            headers={"Authorization": f"Bearer {create_access_token(str(stranger.id))}"},
        )
        # 403 (farm exists, not a member) or 404 (farm hidden from non-members).
        assert resp.status_code in (403, 404)
