"""
AGRIOS — Farm API Unit Tests
Tests for all farm endpoint request/response contracts.
Uses mocked services so no database is required.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.auth import Role, User
from app.models.farm import Farm, FarmMember, FarmUnit, ProductionHouse, SubscriptionPlan


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_plan(**overrides) -> SubscriptionPlan:
    plan = MagicMock(spec=SubscriptionPlan)
    plan.id = uuid.uuid4()
    plan.name = "free"
    plan.display_name = "Free"
    plan.price_kes = 0
    plan.max_farms = 1
    plan.max_houses_per_farm = 5
    plan.max_active_flocks = 2
    plan.max_aria_queries_per_month = 20
    plan.history_days = 30
    plan.max_team_members = 5
    plan.is_active = True
    plan.created_at = datetime.now(timezone.utc)
    plan.updated_at = datetime.now(timezone.utc)
    for k, v in overrides.items():
        setattr(plan, k, v)
    return plan


def make_farm(**overrides) -> Farm:
    """
    A farm-like stand-in for endpoint smoke tests.

    A plain object (not a spec'd MagicMock) is used deliberately: the endpoints
    build their response via ``FarmResponse.model_validate({**farm.__dict__, ...})``
    and read ``farm.plan.display_name``, so ``__dict__`` must be a clean column map
    while ``.plan`` stays attribute-accessible. Reassigning ``__dict__`` on a
    MagicMock corrupts its internals, so we avoid mocks here.
    """
    farm = SimpleNamespace(
        id=uuid.uuid4(),
        name="Sunrise Farm",
        description="A test farm",
        location="Kiambu Town",
        county="Kiambu",
        owner_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        is_active=True,
        timezone="Africa/Nairobi",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    farm.plan = make_plan()
    for k, v in overrides.items():
        setattr(farm, k, v)
    return farm


# ── Farm Schema Validation Tests ──────────────────────────────────────────────

class TestFarmCreateSchema:
    """Validate FarmCreate Pydantic schema directly (no HTTP layer needed)."""

    def test_valid_farm_name(self):
        from app.schemas.farm import FarmCreate
        f = FarmCreate(name="My Farm")
        assert f.name == "My Farm"

    def test_name_strips_whitespace(self):
        from app.schemas.farm import FarmCreate
        f = FarmCreate(name="  Sunrise Farm  ")
        assert f.name == "Sunrise Farm"

    def test_empty_name_raises(self):
        from app.schemas.farm import FarmCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            FarmCreate(name="   ")

    def test_valid_county(self):
        from app.schemas.farm import FarmCreate
        f = FarmCreate(name="Farm", county="kiambu")
        assert f.county == "Kiambu"  # title-cased

    def test_invalid_county_raises(self):
        from app.schemas.farm import FarmCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            FarmCreate(name="Farm", county="Atlantis")

    def test_county_optional(self):
        from app.schemas.farm import FarmCreate
        f = FarmCreate(name="Farm")
        assert f.county is None

    def test_all_47_counties_accepted(self):
        from app.schemas.farm import FarmCreate, KENYA_COUNTIES
        for county in KENYA_COUNTIES:
            f = FarmCreate(name="Farm", county=county)
            assert f.county == county


class TestFarmMemberInviteSchema:
    """Validate FarmMemberInvite schema."""

    def test_valid_invite(self):
        from app.schemas.farm import FarmMemberInvite
        inv = FarmMemberInvite(phone="+254712345678", role_name="farm_worker")
        assert inv.phone == "+254712345678"
        assert inv.role_name == "farm_worker"

    def test_invalid_phone_prefix(self):
        from app.schemas.farm import FarmMemberInvite
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            FarmMemberInvite(phone="+255712345678", role_name="viewer")

    def test_farm_owner_not_assignable_by_invite(self):
        from app.schemas.farm import FarmMemberInvite
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            FarmMemberInvite(phone="+254712345678", role_name="farm_owner")

    def test_phone_spaces_stripped(self):
        from app.schemas.farm import FarmMemberInvite
        inv = FarmMemberInvite(phone="+254 712 345 678", role_name="viewer")
        assert " " not in inv.phone

    @pytest.mark.parametrize("role", ["farm_manager", "vet_consultant", "farm_worker", "viewer"])
    def test_all_assignable_roles(self, role):
        from app.schemas.farm import FarmMemberInvite
        inv = FarmMemberInvite(phone="+254712345678", role_name=role)
        assert inv.role_name == role


class TestFarmMemberUpdateSchema:
    """Validate FarmMemberUpdate model validator."""

    def test_requires_at_least_one_field(self):
        from app.schemas.farm import FarmMemberUpdate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            FarmMemberUpdate()

    def test_status_only(self):
        from app.schemas.farm import FarmMemberUpdate
        u = FarmMemberUpdate(status="suspended")
        assert u.status == "suspended"
        assert u.role_name is None

    def test_role_only(self):
        from app.schemas.farm import FarmMemberUpdate
        u = FarmMemberUpdate(role_name="viewer")
        assert u.role_name == "viewer"

    def test_both_fields(self):
        from app.schemas.farm import FarmMemberUpdate
        u = FarmMemberUpdate(status="active", role_name="farm_manager")
        assert u.status == "active"
        assert u.role_name == "farm_manager"


class TestProductionHouseCreateSchema:
    """Validate ProductionHouseCreate schema."""

    def test_valid_house(self):
        from app.schemas.farm import ProductionHouseCreate
        h = ProductionHouseCreate(name="House 1", capacity=500)
        assert h.capacity == 500
        assert h.house_type == "broiler"

    def test_zero_capacity_raises(self):
        from app.schemas.farm import ProductionHouseCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ProductionHouseCreate(name="House 1", capacity=0)

    def test_capacity_over_100k_raises(self):
        from app.schemas.farm import ProductionHouseCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ProductionHouseCreate(name="House 1", capacity=100_001)

    @pytest.mark.parametrize("house_type", ["broiler", "layer", "breeder", "pullet", "multi"])
    def test_all_house_types(self, house_type):
        from app.schemas.farm import ProductionHouseCreate
        h = ProductionHouseCreate(name="House", capacity=100, house_type=house_type)
        assert h.house_type == house_type


# ── Farm Service Unit Tests ───────────────────────────────────────────────────

class TestPlanLimitHelper:
    """Test the _check_limit helper directly."""

    def test_no_limit_when_unlimited(self):
        from app.services.farm_service import _check_limit
        # -1 means unlimited — should never raise
        _check_limit(current=9999, limit=-1, resource="farms")

    def test_raises_at_limit(self):
        from app.services.farm_service import _check_limit
        from app.exceptions import PlanLimitException
        with pytest.raises(PlanLimitException):
            _check_limit(current=1, limit=1, resource="farms")

    def test_ok_below_limit(self):
        from app.services.farm_service import _check_limit
        _check_limit(current=0, limit=1, resource="farms")

    def test_raises_when_exceeded(self):
        from app.services.farm_service import _check_limit
        from app.exceptions import PlanLimitException
        with pytest.raises(PlanLimitException):
            _check_limit(current=5, limit=3, resource="houses")


# ── HTTP Endpoint Smoke Tests (using mock service layer) ─────────────────────

class TestFarmEndpointContracts:
    """
    Smoke tests that verify endpoint routing and response envelope.
    Services are mocked so tests do not require a running database.
    """

    @pytest.mark.asyncio
    async def test_create_farm_returns_201(self, client: AsyncClient, auth_headers: dict):
        """POST /farms → 201 with farm data in envelope."""
        farm = make_farm()
        counts = {"member_count": 1, "unit_count": 0, "house_count": 0}

        with (
            patch("app.api.v1.endpoints.farms.farm_service.create_farm", new_callable=AsyncMock, return_value=farm),
            patch("app.api.v1.endpoints.farms.farm_service.get_farm_counts", new_callable=AsyncMock, return_value=counts),
        ):
            resp = await client.post(
                "/api/v1/farms",
                json={"name": "Sunrise Farm", "county": "Kiambu"},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Sunrise Farm"

    @pytest.mark.asyncio
    async def test_list_farms_returns_200(self, client: AsyncClient, auth_headers: dict):
        """GET /farms → 200 with list envelope."""
        farm = make_farm()
        counts = {"member_count": 1, "unit_count": 0, "house_count": 0}

        with (
            patch("app.api.v1.endpoints.farms.farm_service.list_farms_for_user", new_callable=AsyncMock, return_value=[farm]),
            patch("app.api.v1.endpoints.farms.farm_service.get_farm_counts", new_callable=AsyncMock, return_value=counts),
        ):
            resp = await client.get("/api/v1/farms", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    async def test_get_farm_inaccessible_is_denied(self, client: AsyncClient, auth_headers: dict):
        """
        GET /farms/{id} for a farm the caller cannot access is denied — never 200.

        The ``require_farm_access`` dependency guards the route: an unknown farm
        raises NotFoundException (404); an existing farm the caller isn't a member
        of raises FarmAccessException (403). Both are valid denials. (The
        member-vs-owner 403 path is covered end-to-end in the farm integration
        flow, which seeds real farms and memberships.)
        """
        farm_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/farms/{farm_id}", headers=auth_headers)
        assert resp.status_code in (403, 404)
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_create_farm_missing_name_returns_422(self, client: AsyncClient, auth_headers: dict):
        """POST /farms without name → 422 validation error."""
        resp = await client.post(
            "/api/v1/farms",
            json={"county": "Nairobi"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_invite_member_to_inaccessible_farm_is_guarded(
        self, client: AsyncClient, auth_headers: dict
    ):
        """
        POST /farms/{id}/members/invite is guarded by farm access.

        The access dependency runs before body validation, so inviting to an
        unknown farm short-circuits to 404 (never 200/401). Phone-format
        validation (422) is asserted directly against the schema in
        ``test_farm_member_invite_rejects_invalid_phone`` — that path is only
        reached once the caller has owner/manager access to a real farm.
        """
        farm_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/farms/{farm_id}/members/invite",
            json={"phone": "0712345678", "role_name": "farm_worker"},
            headers=auth_headers,
        )
        assert resp.status_code in (403, 404)

    def test_farm_member_invite_rejects_invalid_phone(self):
        """FarmMemberInvite rejects a non-E.164 Kenyan phone (the 422 source)."""
        import pydantic
        from app.schemas.farm import FarmMemberInvite

        with pytest.raises(pydantic.ValidationError):
            FarmMemberInvite(phone="0712345678", role_name="farm_worker")

    @pytest.mark.asyncio
    async def test_plans_endpoint_is_public(self, client: AsyncClient):
        """GET /plans is reachable without an auth token (public endpoint)."""
        resp = await client.get("/api/v1/plans")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
