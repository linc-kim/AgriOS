"""
AGRIOS — Platform Layer Unit Tests (Sprint 7)
Schema validation + pure-function logic — no database required.

Tests:
  TestNotificationCreate       (6 tests) — input schema validation
  TestNotificationListResponse (3 tests) — list response structure
  TestAuditLogCreate           (5 tests) — append-only audit log schemas
  TestAuditLogResponse         (2 tests) — nullable fields
  TestMarketPriceCreate        (8 tests) — price input validation (validators)
  TestMarketPriceResponse      (4 tests) — decimal-to-string serialisation
  TestCommodityListResponse    (2 tests) — commodity list schema

Total: 30 tests
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.platform import (
    AuditLogCreate,
    AuditLogListResponse,
    AuditLogResponse,
    CommodityListResponse,
    MarketPriceCreate,
    MarketPriceListResponse,
    MarketPriceResponse,
    NotificationCreate,
    NotificationListResponse,
    NotificationResponse,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _farm_id() -> uuid.UUID:
    return uuid.uuid4()


def _user_id() -> uuid.UUID:
    return uuid.uuid4()


def _today() -> date:
    return date.today()


def _tomorrow() -> date:
    return date.today() + timedelta(days=1)


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


# ── NotificationCreate ────────────────────────────────────────────────────────

class TestNotificationCreate:
    def test_valid_minimal(self):
        n = NotificationCreate(
            farm_id=_farm_id(),
            user_id=_user_id(),
            notification_type="daily_log_reminder",
            title="Don't forget your daily log",
            body="You haven't logged today. Tap to log now.",
        )
        assert n.notification_type == "daily_log_reminder"
        assert n.action_route is None
        assert n.source is None

    def test_valid_with_optional_fields(self):
        n = NotificationCreate(
            farm_id=_farm_id(),
            user_id=_user_id(),
            notification_type="vaccination_reminder",
            title="Vaccination due in 3 days",
            body="Your flock needs Newcastle vaccination.",
            action_route="/farms/:farmId/health/schedule",
            source="scheduler",
        )
        assert n.action_route == "/farms/:farmId/health/schedule"
        assert n.source == "scheduler"

    def test_notification_type_max_length(self):
        with pytest.raises(ValidationError):
            NotificationCreate(
                farm_id=_farm_id(),
                user_id=_user_id(),
                notification_type="a" * 51,  # max 50
                title="Title",
                body="Body",
            )

    def test_title_max_length(self):
        with pytest.raises(ValidationError):
            NotificationCreate(
                farm_id=_farm_id(),
                user_id=_user_id(),
                notification_type="disease_alert",
                title="A" * 201,  # max 200
                body="Body",
            )

    def test_action_route_max_length(self):
        with pytest.raises(ValidationError):
            NotificationCreate(
                farm_id=_farm_id(),
                user_id=_user_id(),
                notification_type="farm_invite",
                title="You have been invited",
                body="Accept to join the farm.",
                action_route="/farms/" + "x" * 300,  # max 300
            )

    def test_source_max_length(self):
        with pytest.raises(ValidationError):
            NotificationCreate(
                farm_id=_farm_id(),
                user_id=_user_id(),
                notification_type="weekly_summary",
                title="Your weekly summary",
                body="Here is how your farm performed.",
                source="s" * 51,  # max 50
            )


# ── NotificationListResponse ──────────────────────────────────────────────────

class TestNotificationListResponse:
    def test_empty_list(self):
        r = NotificationListResponse(notifications=[], total=0, unread_count=0)
        assert r.total == 0
        assert r.unread_count == 0
        assert r.notifications == []

    def test_unread_count_independent_of_list(self):
        # unread_count can be 0 even when list has items (e.g. filter applied)
        r = NotificationListResponse(notifications=[], total=5, unread_count=0)
        assert r.total == 5
        assert r.unread_count == 0

    def test_total_and_unread_are_ints(self):
        r = NotificationListResponse(notifications=[], total=100, unread_count=42)
        assert isinstance(r.total, int)
        assert isinstance(r.unread_count, int)


# ── AuditLogCreate ────────────────────────────────────────────────────────────

class TestAuditLogCreate:
    def test_valid_minimal(self):
        log = AuditLogCreate(
            action="create",
            resource_type="flock",
        )
        assert log.action == "create"
        assert log.farm_id is None
        assert log.user_id is None
        assert log.old_value is None
        assert log.new_value is None

    def test_valid_full(self):
        rid = uuid.uuid4()
        log = AuditLogCreate(
            farm_id=_farm_id(),
            user_id=_user_id(),
            action="update",
            resource_type="vaccination_record",
            resource_id=rid,
            old_value={"dose_ml": "0.5"},
            new_value={"dose_ml": "1.0"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert log.resource_id == rid
        assert log.old_value == {"dose_ml": "0.5"}

    def test_action_max_length(self):
        with pytest.raises(ValidationError):
            AuditLogCreate(
                action="a" * 101,  # max 100
                resource_type="flock",
            )

    def test_resource_type_max_length(self):
        with pytest.raises(ValidationError):
            AuditLogCreate(
                action="delete",
                resource_type="r" * 51,  # max 50
            )

    def test_ip_address_max_length(self):
        with pytest.raises(ValidationError):
            AuditLogCreate(
                action="create",
                resource_type="farm",
                ip_address="1" * 46,  # max 45
            )


# ── AuditLogResponse (nullable fields) ────────────────────────────────────────

class TestAuditLogResponse:
    def test_nullable_farm_and_user_are_optional(self):
        from datetime import datetime

        r = AuditLogResponse(
            id=uuid.uuid4(),
            farm_id=None,
            user_id=None,
            action="system_event",
            resource_type="platform",
            resource_id=None,
            old_value=None,
            new_value=None,
            ip_address=None,
            user_agent=None,
            created_at=datetime.utcnow(),
        )
        assert r.farm_id is None
        assert r.user_id is None

    def test_with_jsonb_values(self):
        from datetime import datetime

        r = AuditLogResponse(
            id=uuid.uuid4(),
            farm_id=_farm_id(),
            user_id=_user_id(),
            action="update",
            resource_type="expense",
            resource_id=uuid.uuid4(),
            old_value={"amount": "500.00", "category": "feed"},
            new_value={"amount": "600.00", "category": "feed"},
            ip_address="10.0.0.1",
            user_agent="AGRIOS/1.0",
            created_at=datetime.utcnow(),
        )
        assert r.old_value["amount"] == "500.00"
        assert r.new_value["amount"] == "600.00"


# ── MarketPriceCreate ─────────────────────────────────────────────────────────

class TestMarketPriceCreate:
    def test_valid_price(self):
        p = MarketPriceCreate(
            commodity="broiler_chick",
            price_kes=Decimal("55.00"),
            unit="per chick",
            valid_date=_today(),
        )
        assert p.commodity == "broiler_chick"
        assert p.price_kes == Decimal("55.00")

    def test_optional_county_and_source(self):
        p = MarketPriceCreate(
            commodity="maize",
            price_kes=Decimal("4500.00"),
            unit="per 90kg bag",
            valid_date=_yesterday(),
            county="Nakuru",
            source="Kenya Farmers Portal",
        )
        assert p.county == "Nakuru"
        assert p.source == "Kenya Farmers Portal"

    def test_future_date_rejected(self):
        with pytest.raises(ValidationError) as exc:
            MarketPriceCreate(
                commodity="broiler_chick",
                price_kes=Decimal("55.00"),
                unit="per chick",
                valid_date=_tomorrow(),
            )
        assert "future" in str(exc.value).lower()

    def test_today_is_valid(self):
        p = MarketPriceCreate(
            commodity="broiler_chick",
            price_kes=Decimal("55.00"),
            unit="per chick",
            valid_date=_today(),
        )
        assert p.valid_date == _today()

    def test_zero_price_rejected(self):
        with pytest.raises(ValidationError):
            MarketPriceCreate(
                commodity="broiler_chick",
                price_kes=Decimal("0.00"),
                unit="per chick",
                valid_date=_today(),
            )

    def test_negative_price_rejected(self):
        with pytest.raises(ValidationError):
            MarketPriceCreate(
                commodity="broiler_chick",
                price_kes=Decimal("-10.00"),
                unit="per chick",
                valid_date=_today(),
            )

    def test_commodity_max_length(self):
        with pytest.raises(ValidationError):
            MarketPriceCreate(
                commodity="c" * 101,
                price_kes=Decimal("55.00"),
                unit="per chick",
                valid_date=_today(),
            )

    def test_county_max_length(self):
        with pytest.raises(ValidationError):
            MarketPriceCreate(
                commodity="broiler_chick",
                price_kes=Decimal("55.00"),
                unit="per chick",
                valid_date=_today(),
                county="C" * 101,
            )


# ── MarketPriceResponse ───────────────────────────────────────────────────────

class TestMarketPriceResponse:
    def test_price_kes_is_string(self):
        """price_kes must be serialised as string (Decimal → str per project standard)."""
        from datetime import datetime
        r = MarketPriceResponse(
            id=uuid.uuid4(),
            commodity="broiler_chick",
            price_kes="55.00",
            unit="per chick",
            county=None,
            source=None,
            valid_date=_today(),
            recorded_by_id=None,
            created_at=datetime.utcnow(),
        )
        assert isinstance(r.price_kes, str)
        assert r.price_kes == "55.00"

    def test_county_optional(self):
        from datetime import datetime
        r = MarketPriceResponse(
            id=uuid.uuid4(),
            commodity="maize",
            price_kes="4500.00",
            unit="per 90kg bag",
            county=None,
            source="Market survey",
            valid_date=_today(),
            recorded_by_id=None,
            created_at=datetime.utcnow(),
        )
        assert r.county is None

    def test_from_orm_with_decimal_converts_decimal_to_str(self):
        """from_orm_with_decimal() converts Python Decimal to string."""
        from datetime import datetime

        class FakeOrm:
            id = uuid.uuid4()
            commodity = "broiler_chick"
            price_kes = Decimal("55.50")
            unit = "per chick"
            county = "Nairobi"
            source = None
            valid_date = _today()
            recorded_by_id = None
            created_at = datetime.utcnow()

        r = MarketPriceResponse.from_orm_with_decimal(FakeOrm())
        # str(Decimal("55.50")) preserves the scale → "55.50" (not "55.5").
        assert r.price_kes == "55.50"
        assert isinstance(r.price_kes, str)

    def test_market_price_list_response_structure(self):
        from datetime import datetime
        price = MarketPriceResponse(
            id=uuid.uuid4(),
            commodity="broiler_chick",
            price_kes="55.00",
            unit="per chick",
            county="Nairobi",
            source=None,
            valid_date=_today(),
            recorded_by_id=None,
            created_at=datetime.utcnow(),
        )
        r = MarketPriceListResponse(
            prices=[price],
            as_of_date=_today(),
            total=1,
        )
        assert r.total == 1
        assert r.as_of_date == _today()
        assert len(r.prices) == 1


# ── CommodityListResponse ─────────────────────────────────────────────────────

class TestCommodityListResponse:
    def test_empty_list(self):
        r = CommodityListResponse(commodities=[])
        assert r.commodities == []

    def test_with_commodities(self):
        r = CommodityListResponse(
            commodities=["broiler_chick", "maize", "soya_meal", "poultry_mash"]
        )
        assert "broiler_chick" in r.commodities
        assert len(r.commodities) == 4
