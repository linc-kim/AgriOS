"""
AGRIOS — Flock & Operations Pydantic Schemas
Request validation and response serialisation for:
  - Flocks (create, close, list, detail)
  - Daily Logs (submit / upsert, history, correction)
  - Production Records (eggs)
  - Weigh-In Records
  - Feed Purchases
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import AGRIOSSchema, TimestampedSchema

# ── Enums ─────────────────────────────────────────────────────────────────────

FlockStatus = Literal["active", "sold", "closed", "culled"]
CloseStatus = Literal["sold", "closed", "culled"]

COMMON_FEED_TYPES = [
    "Starter",
    "Grower",
    "Finisher",
    "Layer Mash",
    "Pre-Lay",
    "Chick Mash",
    "Growers Mash",
    "Concentrates",
]

# ── Flock Schemas ──────────────────────────────────────────────────────────────

class FlockCreate(AGRIOSSchema):
    """Request body for opening a new flock."""

    house_id: UUID = Field(..., description="Production house that will hold this flock.")
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Display name, e.g. 'Batch 3 – Broiler May 2025'",
    )
    breed: str | None = Field(
        default=None,
        max_length=100,
        description="Bird breed, e.g. Ross 308, Cobb 500, ISA Brown",
    )
    batch_number: str | None = Field(
        default=None,
        max_length=50,
        description="Optional farmer batch reference",
    )
    initial_count: int = Field(
        ...,
        ge=1,
        le=1_000_000,
        description="Number of birds placed",
    )
    placement_date: date = Field(
        ...,
        description="Date chicks/pullets were placed in the house",
    )
    expected_cycle_days: int = Field(
        default=42,
        ge=1,
        le=1000,
        description="Expected days to close. 42 for broilers, 350+ for layers.",
    )
    species_key: str = Field(
        default="poultry",
        description="Species key. Always 'poultry' in V1.",
    )

    @field_validator("placement_date")
    @classmethod
    def placement_date_not_future(cls, v: date) -> date:
        from datetime import date as _date
        if v > _date.today():
            raise ValueError("Placement date cannot be in the future.")
        return v

    @field_validator("species_key")
    @classmethod
    def species_key_is_poultry(cls, v: str) -> str:
        if v != "poultry":
            raise ValueError("Only 'poultry' is supported in V1.")
        return v


class FlockResponse(TimestampedSchema):
    """Flock as returned by the API — no computed metrics."""

    farm_id: UUID
    house_id: UUID
    species_key: str
    name: str
    breed: str | None
    batch_number: str | None
    initial_count: int
    placement_date: date
    expected_cycle_days: int
    expected_close_date: date | None
    status: FlockStatus
    close_date: date | None
    close_reason: str | None
    sale_price_per_kg: Decimal | None
    total_birds_sold: int | None
    closing_weight_kg: Decimal | None
    created_by: UUID | None


class FlockMetrics(AGRIOSSchema):
    """
    Computed operational metrics for a flock.
    Returned as a sub-object in FlockDetailResponse.
    """

    days_alive: int
    total_mortality: int
    current_count: int
    survival_rate: float = Field(description="Percentage 0.0–100.0")
    total_feed_kg: Decimal
    latest_avg_weight_kg: Decimal | None
    total_biomass_kg: Decimal | None
    fcr: Decimal | None = Field(description="Feed Conversion Ratio")
    total_eggs_collected: int | None = Field(
        description="Populated for layer flocks only"
    )
    hen_day_production: float | None = Field(
        description="Average hen-day production percentage for layer flocks"
    )


class FlockDetailResponse(TimestampedSchema):
    """Flock with computed operational metrics. Used by FL-02."""

    farm_id: UUID
    house_id: UUID
    species_key: str
    name: str
    breed: str | None
    batch_number: str | None
    initial_count: int
    placement_date: date
    expected_cycle_days: int
    expected_close_date: date | None
    status: FlockStatus
    close_date: date | None
    close_reason: str | None
    sale_price_per_kg: Decimal | None
    total_birds_sold: int | None
    closing_weight_kg: Decimal | None
    created_by: UUID | None
    metrics: FlockMetrics


class FlockClose(AGRIOSSchema):
    """Request body for closing a flock."""

    status: CloseStatus = Field(
        ...,
        description="How the flock was closed: sold | closed | culled",
    )
    close_date: date = Field(..., description="Date the flock was closed")
    close_reason: str | None = Field(default=None, max_length=1000)

    # sold-specific fields (required when status == "sold")
    sale_price_per_kg: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="KES per kg. Required when status=sold.",
    )
    total_birds_sold: int | None = Field(
        default=None,
        ge=1,
        description="Final count sold. Required when status=sold.",
    )
    closing_weight_kg: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="Average live weight at close (kg/bird).",
    )

    @model_validator(mode="after")
    def validate_sale_fields(self) -> "FlockClose":
        if self.status == "sold":
            if self.sale_price_per_kg is None:
                raise ValueError(
                    "sale_price_per_kg is required when closing with status='sold'."
                )
            if self.total_birds_sold is None:
                raise ValueError(
                    "total_birds_sold is required when closing with status='sold'."
                )
        return self


# ── Daily Log Schemas ─────────────────────────────────────────────────────────

class DailyLogSubmit(AGRIOSSchema):
    """
    Request body for submitting (or updating) a daily log.
    DB-06 Frozen: UNIQUE(flock_id, log_date) — one log per flock per day.
    Submitting again for the same date performs an upsert (update existing).
    """

    log_date: date = Field(
        ...,
        description="Date this log covers. Defaults to today if omitted.",
    )
    morning_count: int | None = Field(
        default=None,
        ge=0,
        le=1_000_000,
        description="Bird head count at morning check",
    )
    mortality_count: int = Field(
        default=0,
        ge=0,
        le=100_000,
    )
    mortality_cause: str | None = Field(
        default=None,
        max_length=100,
    )
    feed_consumed_kg: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        le=Decimal("100000"),
    )
    water_litres: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
    )
    house_temp_am: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("60"),
        description="House temperature (°C) at morning check",
    )
    house_temp_pm: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("60"),
    )
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("log_date")
    @classmethod
    def log_date_not_future(cls, v: date) -> date:
        from datetime import date as _date
        if v > _date.today():
            raise ValueError("Log date cannot be in the future.")
        return v


class DailyLogCorrect(AGRIOSSchema):
    """
    Request body for correcting an existing daily log.
    Requires OPS_LOG_CORRECT permission (farm_owner, farm_manager only).
    Sets is_corrected=True and records corrected_by/corrected_at.
    """

    morning_count: int | None = Field(default=None, ge=0)
    mortality_count: int | None = Field(default=None, ge=0)
    mortality_cause: str | None = Field(default=None, max_length=100)
    feed_consumed_kg: Decimal | None = Field(default=None, ge=Decimal("0"))
    water_litres: Decimal | None = Field(default=None, ge=Decimal("0"))
    house_temp_am: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("60"))
    house_temp_pm: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("60"))
    notes: str | None = Field(default=None, max_length=2000)
    correction_reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Required explanation for why the correction was made.",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> "DailyLogCorrect":
        fields_that_matter = [
            "morning_count", "mortality_count", "mortality_cause",
            "feed_consumed_kg", "water_litres", "house_temp_am", "house_temp_pm",
            "notes",
        ]
        if all(getattr(self, f) is None for f in fields_that_matter):
            raise ValueError("At least one field must be provided for correction.")
        return self


class DailyLogResponse(TimestampedSchema):
    """Daily log as returned by the API."""

    farm_id: UUID
    flock_id: UUID
    log_date: date
    morning_count: int | None
    mortality_count: int
    mortality_cause: str | None
    feed_consumed_kg: Decimal
    water_litres: Decimal | None
    house_temp_am: Decimal | None
    house_temp_pm: Decimal | None
    notes: str | None
    logged_by: UUID | None
    is_corrected: bool
    corrected_by: UUID | None
    corrected_at: datetime | None


# ── Production Record Schemas ─────────────────────────────────────────────────

class ProductionRecordSubmit(AGRIOSSchema):
    """Request body for logging daily egg production."""

    record_date: date = Field(...)
    eggs_collected: int = Field(default=0, ge=0, le=1_000_000)
    broken_eggs: int = Field(default=0, ge=0, le=1_000_000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("record_date")
    @classmethod
    def record_date_not_future(cls, v: date) -> date:
        from datetime import date as _date
        if v > _date.today():
            raise ValueError("Record date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def broken_not_exceed_collected(self) -> "ProductionRecordSubmit":
        if self.broken_eggs > self.eggs_collected:
            raise ValueError("broken_eggs cannot exceed eggs_collected.")
        return self


class ProductionRecordResponse(TimestampedSchema):
    """Production record as returned by the API."""

    farm_id: UUID
    flock_id: UUID
    record_date: date
    eggs_collected: int
    broken_eggs: int
    saleable_eggs: int
    hen_day_production: Decimal | None
    notes: str | None
    logged_by: UUID | None


# ── Weigh-In Schemas ──────────────────────────────────────────────────────────

class WeighinSubmit(AGRIOSSchema):
    """Request body for recording a weigh-in."""

    weighed_at: date = Field(...)
    sample_size: int = Field(..., ge=1, le=100_000)
    average_weight_kg: Decimal = Field(..., ge=Decimal("0.01"), le=Decimal("50"))
    min_weight_kg: Decimal | None = Field(default=None, ge=Decimal("0.01"))
    max_weight_kg: Decimal | None = Field(default=None, ge=Decimal("0.01"))
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("weighed_at")
    @classmethod
    def date_not_future(cls, v: date) -> date:
        from datetime import date as _date
        if v > _date.today():
            raise ValueError("Weigh-in date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def min_max_range(self) -> "WeighinSubmit":
        if (
            self.min_weight_kg is not None
            and self.max_weight_kg is not None
            and self.min_weight_kg > self.max_weight_kg
        ):
            raise ValueError("min_weight_kg cannot exceed max_weight_kg.")
        return self


class WeighinResponse(TimestampedSchema):
    """Weigh-in record as returned by the API."""

    farm_id: UUID
    flock_id: UUID
    weighed_at: date
    sample_size: int
    average_weight_kg: Decimal
    min_weight_kg: Decimal | None
    max_weight_kg: Decimal | None
    total_biomass_kg: Decimal | None
    fcr_to_date: Decimal | None
    notes: str | None
    logged_by: UUID | None


# ── Feed Purchase Schemas ─────────────────────────────────────────────────────

class FeedPurchaseCreate(AGRIOSSchema):
    """Request body for recording a feed purchase."""

    flock_id: UUID | None = Field(
        default=None,
        description="Link to active flock. Optional — can be farm-wide stock.",
    )
    purchase_date: date = Field(...)
    feed_type: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="e.g. Starter, Grower, Finisher, Layer Mash",
    )
    quantity_kg: Decimal = Field(..., ge=Decimal("0.001"), le=Decimal("100000"))
    price_per_kg: Decimal = Field(..., ge=Decimal("0"), le=Decimal("10000"))
    supplier: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("purchase_date")
    @classmethod
    def date_not_future(cls, v: date) -> date:
        from datetime import date as _date
        if v > _date.today():
            raise ValueError("Purchase date cannot be in the future.")
        return v


class FeedPurchaseResponse(TimestampedSchema):
    """Feed purchase as returned by the API."""

    farm_id: UUID
    flock_id: UUID | None
    purchase_date: date
    feed_type: str
    quantity_kg: Decimal
    price_per_kg: Decimal
    total_cost: Decimal
    supplier: str | None
    notes: str | None
    recorded_by: UUID | None
