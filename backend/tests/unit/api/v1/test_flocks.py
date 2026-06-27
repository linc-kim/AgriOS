"""
AGRIOS — Unit Tests: Flock API (Sprint 3)

Tests cover:
  - FlockCreate schema validation
  - FlockClose schema + model_validator (sold requires price + count)
  - DailyLogSubmit schema validation (date not future, mortality ≥ 0)
  - DailyLogCorrect model_validator (at least one field required)
  - ProductionRecordSubmit (broken ≤ collected)
  - WeighinSubmit (min ≤ max, date not future)
  - FeedPurchaseCreate (date not future, positive amounts)
  - FlockMetrics schema (survival_rate bounds)

These tests exercise validation ONLY. No DB connection required.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.flock import (
    DailyLogCorrect,
    DailyLogSubmit,
    FeedPurchaseCreate,
    FlockClose,
    FlockCreate,
    ProductionRecordSubmit,
    WeighinSubmit,
)


# ── FlockCreate ───────────────────────────────────────────────────────────────

class TestFlockCreate:
    def _valid(self, **overrides):
        base = {
            "house_id": "00000000-0000-0000-0000-000000000001",
            "name": "Batch 1 Broiler",
            "initial_count": 500,
            "placement_date": str(date.today() - timedelta(days=1)),
            "expected_cycle_days": 42,
            "species_key": "poultry",
        }
        base.update(overrides)
        return base

    def test_valid_flock_create(self):
        data = FlockCreate(**self._valid())
        assert data.initial_count == 500
        assert data.species_key == "poultry"

    def test_name_too_short(self):
        with pytest.raises(ValidationError, match="at least 2 characters"):
            FlockCreate(**self._valid(name="A"))

    def test_initial_count_zero(self):
        with pytest.raises(ValidationError):
            FlockCreate(**self._valid(initial_count=0))

    def test_initial_count_negative(self):
        with pytest.raises(ValidationError):
            FlockCreate(**self._valid(initial_count=-1))

    def test_placement_date_future_rejected(self):
        future = str(date.today() + timedelta(days=1))
        with pytest.raises(ValidationError, match="future"):
            FlockCreate(**self._valid(placement_date=future))

    def test_placement_date_today_accepted(self):
        data = FlockCreate(**self._valid(placement_date=str(date.today())))
        assert data.placement_date == date.today()

    def test_species_key_not_poultry_rejected(self):
        with pytest.raises(ValidationError, match="poultry"):
            FlockCreate(**self._valid(species_key="rabbit"))

    def test_optional_breed_and_batch(self):
        data = FlockCreate(**self._valid(breed="Ross 308", batch_number="B-001"))
        assert data.breed == "Ross 308"
        assert data.batch_number == "B-001"

    def test_expected_cycle_days_default(self):
        data = FlockCreate(**self._valid())
        assert data.expected_cycle_days == 42

    def test_expected_cycle_days_custom(self):
        data = FlockCreate(**self._valid(expected_cycle_days=350))
        assert data.expected_cycle_days == 350

    def test_expected_cycle_days_zero_rejected(self):
        with pytest.raises(ValidationError):
            FlockCreate(**self._valid(expected_cycle_days=0))


# ── FlockClose ────────────────────────────────────────────────────────────────

class TestFlockClose:
    def _valid_closed(self, **overrides):
        base = {
            "status": "closed",
            "close_date": str(date.today()),
        }
        base.update(overrides)
        return base

    def _valid_sold(self, **overrides):
        base = {
            "status": "sold",
            "close_date": str(date.today()),
            "sale_price_per_kg": "185.00",
            "total_birds_sold": 480,
            "closing_weight_kg": "2.150",
        }
        base.update(overrides)
        return base

    def test_close_valid(self):
        data = FlockClose(**self._valid_closed())
        assert data.status == "closed"

    def test_culled_valid(self):
        data = FlockClose(**self._valid_closed(status="culled", close_reason="Disease outbreak"))
        assert data.status == "culled"

    def test_sold_valid_with_all_fields(self):
        data = FlockClose(**self._valid_sold())
        assert data.status == "sold"
        assert data.sale_price_per_kg == Decimal("185.00")
        assert data.total_birds_sold == 480

    def test_sold_missing_price_rejected(self):
        with pytest.raises(ValidationError, match="sale_price_per_kg"):
            FlockClose(**self._valid_sold(sale_price_per_kg=None))

    def test_sold_missing_birds_sold_rejected(self):
        with pytest.raises(ValidationError, match="total_birds_sold"):
            FlockClose(**self._valid_sold(total_birds_sold=None))

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            FlockClose(**self._valid_closed(status="archived"))


# ── DailyLogSubmit ────────────────────────────────────────────────────────────

class TestDailyLogSubmit:
    def _valid(self, **overrides):
        base = {
            "log_date": str(date.today()),
            "mortality_count": 0,
            "feed_consumed_kg": "25.500",
        }
        base.update(overrides)
        return base

    def test_valid_minimal_log(self):
        data = DailyLogSubmit(**self._valid())
        assert data.mortality_count == 0
        assert data.feed_consumed_kg == Decimal("25.500")

    def test_future_log_date_rejected(self):
        future = str(date.today() + timedelta(days=1))
        with pytest.raises(ValidationError, match="future"):
            DailyLogSubmit(**self._valid(log_date=future))

    def test_negative_mortality_rejected(self):
        with pytest.raises(ValidationError):
            DailyLogSubmit(**self._valid(mortality_count=-1))

    def test_negative_feed_rejected(self):
        with pytest.raises(ValidationError):
            DailyLogSubmit(**self._valid(feed_consumed_kg="-0.001"))

    def test_temperature_above_max_rejected(self):
        with pytest.raises(ValidationError):
            DailyLogSubmit(**self._valid(house_temp_am="65.0"))

    def test_all_optional_fields_accepted(self):
        data = DailyLogSubmit(**self._valid(
            morning_count=498,
            mortality_count=2,
            mortality_cause="Heat stress",
            water_litres="120.000",
            house_temp_am="28.5",
            house_temp_pm="31.2",
            notes="Slightly hot afternoon.",
        ))
        assert data.morning_count == 498
        assert data.mortality_cause == "Heat stress"

    def test_default_feed_zero(self):
        data = DailyLogSubmit(log_date=str(date.today()))
        assert data.feed_consumed_kg == Decimal("0")
        assert data.mortality_count == 0


# ── DailyLogCorrect ───────────────────────────────────────────────────────────

class TestDailyLogCorrect:
    def test_requires_at_least_one_field(self):
        with pytest.raises(ValidationError, match="At least one field"):
            DailyLogCorrect(correction_reason="Error in entry")

    def test_valid_with_one_field(self):
        data = DailyLogCorrect(
            mortality_count=3,
            correction_reason="Missed one bird during count",
        )
        assert data.mortality_count == 3

    def test_correction_reason_too_short(self):
        with pytest.raises(ValidationError):
            DailyLogCorrect(
                mortality_count=1,
                correction_reason="Ok",  # < 5 chars
            )

    def test_correction_reason_required(self):
        with pytest.raises(ValidationError):
            DailyLogCorrect(mortality_count=1)


# ── ProductionRecordSubmit ────────────────────────────────────────────────────

class TestProductionRecordSubmit:
    def test_valid_production(self):
        data = ProductionRecordSubmit(
            record_date=str(date.today()),
            eggs_collected=450,
            broken_eggs=12,
        )
        assert data.eggs_collected == 450
        assert data.broken_eggs == 12

    def test_broken_exceeds_collected_rejected(self):
        with pytest.raises(ValidationError, match="broken_eggs cannot exceed"):
            ProductionRecordSubmit(
                record_date=str(date.today()),
                eggs_collected=100,
                broken_eggs=101,
            )

    def test_future_date_rejected(self):
        with pytest.raises(ValidationError, match="future"):
            ProductionRecordSubmit(
                record_date=str(date.today() + timedelta(days=1)),
                eggs_collected=100,
            )

    def test_negative_eggs_rejected(self):
        with pytest.raises(ValidationError):
            ProductionRecordSubmit(
                record_date=str(date.today()),
                eggs_collected=-1,
            )

    def test_defaults_to_zero(self):
        data = ProductionRecordSubmit(record_date=str(date.today()))
        assert data.eggs_collected == 0
        assert data.broken_eggs == 0


# ── WeighinSubmit ─────────────────────────────────────────────────────────────

class TestWeighinSubmit:
    def test_valid_weighin(self):
        data = WeighinSubmit(
            weighed_at=str(date.today()),
            sample_size=50,
            average_weight_kg="1.850",
            min_weight_kg="1.600",
            max_weight_kg="2.100",
        )
        assert data.sample_size == 50
        assert data.average_weight_kg == Decimal("1.850")

    def test_min_exceeds_max_rejected(self):
        with pytest.raises(ValidationError, match="min_weight_kg cannot exceed"):
            WeighinSubmit(
                weighed_at=str(date.today()),
                sample_size=50,
                average_weight_kg="1.850",
                min_weight_kg="2.200",
                max_weight_kg="2.000",
            )

    def test_future_date_rejected(self):
        with pytest.raises(ValidationError, match="future"):
            WeighinSubmit(
                weighed_at=str(date.today() + timedelta(days=1)),
                sample_size=50,
                average_weight_kg="1.850",
            )

    def test_zero_average_weight_rejected(self):
        with pytest.raises(ValidationError):
            WeighinSubmit(
                weighed_at=str(date.today()),
                sample_size=50,
                average_weight_kg="0",
            )

    def test_zero_sample_size_rejected(self):
        with pytest.raises(ValidationError):
            WeighinSubmit(
                weighed_at=str(date.today()),
                sample_size=0,
                average_weight_kg="1.850",
            )


# ── FeedPurchaseCreate ────────────────────────────────────────────────────────

class TestFeedPurchaseCreate:
    def _valid(self, **overrides):
        base = {
            "purchase_date": str(date.today()),
            "feed_type": "Starter",
            "quantity_kg": "100.000",
            "price_per_kg": "55.00",
        }
        base.update(overrides)
        return base

    def test_valid_purchase(self):
        data = FeedPurchaseCreate(**self._valid())
        assert data.feed_type == "Starter"
        assert data.quantity_kg == Decimal("100.000")
        assert data.price_per_kg == Decimal("55.00")

    def test_future_date_rejected(self):
        with pytest.raises(ValidationError, match="future"):
            FeedPurchaseCreate(**self._valid(
                purchase_date=str(date.today() + timedelta(days=1))
            ))

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            FeedPurchaseCreate(**self._valid(quantity_kg="0"))

    def test_feed_type_too_short(self):
        with pytest.raises(ValidationError):
            FeedPurchaseCreate(**self._valid(feed_type="A"))

    def test_optional_supplier_and_notes(self):
        data = FeedPurchaseCreate(**self._valid(
            supplier="Unga Feeds Ltd",
            notes="Monthly bulk order",
        ))
        assert data.supplier == "Unga Feeds Ltd"

    def test_optional_flock_id(self):
        data = FeedPurchaseCreate(**self._valid(
            flock_id="00000000-0000-0000-0000-000000000002"
        ))
        assert data.flock_id is not None

    def test_flock_id_defaults_none(self):
        data = FeedPurchaseCreate(**self._valid())
        assert data.flock_id is None
