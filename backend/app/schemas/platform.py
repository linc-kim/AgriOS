"""
AGRIOS — Platform Schemas (Sprint 7)
Covers: Notification, AuditLog, MarketPrice

Input/output schemas for the platform layer endpoints.
All responses wrapped in SuccessResponse[T] at the endpoint layer.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Notification Schemas ──────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    """Output schema for a single notification."""
    id: uuid.UUID
    farm_id: uuid.UUID
    user_id: uuid.UUID
    notification_type: str
    title: str
    body: str
    action_route: Optional[str]
    is_read: bool
    read_at: Optional[datetime]
    source: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Paginated notification list with unread count."""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int

    model_config = {"from_attributes": True}


class NotificationMarkRead(BaseModel):
    """Body for marking a notification read (empty — action implied by route)."""
    pass


class NotificationCreate(BaseModel):
    """Internal schema for creating notifications programmatically (service use only)."""
    farm_id: uuid.UUID
    user_id: uuid.UUID
    notification_type: str = Field(..., max_length=50)
    title: str = Field(..., max_length=200)
    body: str
    action_route: Optional[str] = Field(None, max_length=300)
    source: Optional[str] = Field(None, max_length=50)


# ── AuditLog Schemas ──────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    """Output schema for a single audit log entry (admin-only)."""
    id: uuid.UUID
    farm_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID]
    old_value: Optional[dict]
    new_value: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogCreate(BaseModel):
    """Internal schema for appending audit log entries (service use only)."""
    farm_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    action: str = Field(..., max_length=100)
    resource_type: str = Field(..., max_length=50)
    resource_id: Optional[uuid.UUID] = None
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)


class AuditLogListResponse(BaseModel):
    """Paginated audit log list."""
    logs: list[AuditLogResponse]
    total: int

    model_config = {"from_attributes": True}


# ── MarketPrice Schemas ───────────────────────────────────────────────────────

class MarketPriceCreate(BaseModel):
    """Admin-only input for publishing a new market price."""
    commodity: str = Field(..., min_length=1, max_length=100)
    price_kes: Decimal = Field(..., gt=0, decimal_places=2)
    unit: str = Field(..., min_length=1, max_length=50)
    county: Optional[str] = Field(None, max_length=100)
    source: Optional[str] = Field(None, max_length=200)
    valid_date: date

    @field_validator("valid_date")
    @classmethod
    def date_not_future(cls, v: date) -> date:
        from datetime import date as dt
        if v > dt.today():
            raise ValueError("valid_date cannot be in the future")
        return v

    @field_validator("price_kes")
    @classmethod
    def price_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("price_kes must be positive")
        return v


class MarketPriceResponse(BaseModel):
    """Output schema for a single market price entry."""
    id: uuid.UUID
    commodity: str
    price_kes: str  # Decimal serialised as string per project standard
    unit: str
    county: Optional[str]
    source: Optional[str]
    valid_date: date
    recorded_by_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_decimal(cls, obj: object) -> "MarketPriceResponse":
        """Convert Decimal price_kes to string for API serialisation."""
        data = {
            "id": obj.id,
            "commodity": obj.commodity,
            "price_kes": str(obj.price_kes),
            "unit": obj.unit,
            "county": obj.county,
            "source": obj.source,
            "valid_date": obj.valid_date,
            "recorded_by_id": obj.recorded_by_id,
            "created_at": obj.created_at,
        }
        return cls(**data)


class MarketPriceListResponse(BaseModel):
    """Market prices list — latest per commodity."""
    prices: list[MarketPriceResponse]
    as_of_date: Optional[date]
    total: int

    model_config = {"from_attributes": True}


class CommodityListResponse(BaseModel):
    """List of available commodity types."""
    commodities: list[str]
