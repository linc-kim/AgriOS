"""
AGRIOS — Base Pydantic Schemas
Standard response envelopes for all API responses.
All responses follow: { success: bool, data: ..., meta: ... } or { success: false, error: ... }
"""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class AGRIOSSchema(BaseModel):
    """Base schema with shared configuration for all AGRIOS schemas."""

    model_config = ConfigDict(
        from_attributes=True,       # Enable ORM mode
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class PaginationMeta(AGRIOSSchema):
    """Pagination metadata included with list responses."""

    total: int
    page: int
    limit: int
    pages: int


class SuccessResponse(AGRIOSSchema, Generic[T]):
    """Standard success envelope for single-item responses."""

    success: bool = True
    data: T
    meta: dict[str, Any] | None = None


class ListResponse(AGRIOSSchema, Generic[T]):
    """Standard success envelope for list responses."""

    success: bool = True
    data: list[T]
    meta: PaginationMeta


class ErrorDetail(AGRIOSSchema):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(AGRIOSSchema):
    """Standard error envelope."""

    success: bool = False
    error: ErrorDetail


class TimestampedSchema(AGRIOSSchema):
    """Base for schemas that expose created_at and updated_at."""

    id: UUID
    created_at: datetime
    updated_at: datetime
