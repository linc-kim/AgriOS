"""
AGRIOS — Market Price Endpoints (Sprint 7)

Endpoint groups:
  GET  /market/prices          — Latest price per commodity (farmer-facing, auth required)
  GET  /market/prices/history  — Price history for a commodity
  GET  /market/commodities     — List of known commodity types
  POST /market/prices          — Admin-only: publish a new price entry

DB-09 (Frozen): market_prices is historical — no PATCH/PUT/DELETE endpoints exist.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth import User
from app.schemas.base import SuccessResponse
from app.schemas.platform import (
    CommodityListResponse,
    MarketPriceCreate,
    MarketPriceListResponse,
    MarketPriceResponse,
)
from app.services import market_service

router = APIRouter(prefix="/market", tags=["Market"])


@router.get(
    "/prices",
    response_model=SuccessResponse[MarketPriceListResponse],
    summary="Get latest market prices per commodity",
)
async def list_latest_prices(
    commodity: Optional[str] = Query(None, description="Filter by commodity type"),
    county: Optional[str] = Query(None, description="Filter by county (null = national)"),
    as_of_date: Optional[date] = Query(None, description="Price date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MARKET_VIEW)),
):
    """
    Returns the most recent price entry per commodity, optionally filtered.
    Used by the farmer FR-01 market prices board.
    All authenticated users can access market prices.
    """
    result = await market_service.list_latest_prices(
        db=db,
        commodity=commodity,
        county=county,
        as_of_date=as_of_date,
    )
    return SuccessResponse(data=result)


@router.get(
    "/prices/history",
    response_model=SuccessResponse[MarketPriceListResponse],
    summary="Get price history for a commodity",
)
async def list_price_history(
    commodity: str = Query(..., description="Commodity type e.g. broiler_live"),
    county: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MARKET_VIEW)),
):
    """
    Returns price history for a single commodity, newest first.
    Used by FR-02 price history screen.
    """
    result = await market_service.list_price_history(
        db=db,
        commodity=commodity,
        county=county,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(data=result)


@router.get(
    "/commodities",
    response_model=SuccessResponse[CommodityListResponse],
    summary="List available commodity types",
)
async def list_commodities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MARKET_VIEW)),
):
    """Returns all known commodity types for FR-01 filter dropdown."""
    result = await market_service.list_commodities(db)
    return SuccessResponse(data=result)


@router.post(
    "/prices",
    response_model=SuccessResponse[MarketPriceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Admin: publish a new market price",
)
async def create_market_price(
    body: MarketPriceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ADMIN_MARKET_MANAGE)),
):
    """
    Admin-only endpoint for publishing market price data.
    DB-09: Creates a new row — never updates existing rows.
    super_admin only via ADMIN_MARKET_MANAGE permission.
    """
    result = await market_service.create_market_price(
        db=db,
        payload=body,
        recorded_by=current_user,
    )
    return SuccessResponse(data=result)
