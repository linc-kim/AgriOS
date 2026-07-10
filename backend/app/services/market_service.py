"""
Greena — Market Price Service (Sprint 7)
Manages market price data: creation (admin only), listing, latest prices.

DB-09 (Frozen): market_prices is historical — new rows only, no updates.
Correction = new row with same commodity + valid_date.

Platform-wide (no farm_id). Admin creates, all authenticated farmers read.
"""

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.platform import MarketPrice
from app.schemas.platform import (
    CommodityListResponse,
    MarketPriceCreate,
    MarketPriceListResponse,
    MarketPriceResponse,
)


# ── Commodity catalogue (extensible — not an ENUM) ────────────────────────────

KNOWN_COMMODITIES = [
    "broiler_live",
    "layer_egg_tray",
    "day_old_chick_broiler",
    "day_old_chick_layer",
    "feed_growers_50kg",
    "feed_layers_50kg",
    "feed_broilers_50kg",
    "maize_90kg",
]


# ── Create ────────────────────────────────────────────────────────────────────

async def create_market_price(
    db: AsyncSession,
    payload: MarketPriceCreate,
    recorded_by: User,
) -> MarketPriceResponse:
    """
    Admin creates a new market price entry.
    DB-09: new row only — no update path exists.
    """
    price = MarketPrice(
        commodity=payload.commodity,
        price_kes=payload.price_kes,
        unit=payload.unit,
        county=payload.county,
        source=payload.source,
        valid_date=payload.valid_date,
        recorded_by_id=recorded_by.id,
    )
    db.add(price)
    await db.commit()
    await db.refresh(price)
    return MarketPriceResponse.from_orm_with_decimal(price)


# ── List: latest per commodity ────────────────────────────────────────────────

async def list_latest_prices(
    db: AsyncSession,
    commodity: Optional[str] = None,
    county: Optional[str] = None,
    as_of_date: Optional[date] = None,
) -> MarketPriceListResponse:
    """
    Return the most recent price per commodity (and optionally county).
    Farmers call this to see today's market snapshot.

    Strategy: subquery to get max valid_date per commodity, then join back.
    """
    target_date = as_of_date or date.today()

    # Subquery: most recent valid_date per commodity (and county if filtered)
    sub_filters = [MarketPrice.valid_date <= target_date]
    if commodity:
        sub_filters.append(MarketPrice.commodity == commodity)
    if county:
        sub_filters.append(MarketPrice.county == county)

    subq = (
        select(
            MarketPrice.commodity,
            MarketPrice.county,
            func.max(MarketPrice.valid_date).label("max_date"),
        )
        .where(*sub_filters)
        .group_by(MarketPrice.commodity, MarketPrice.county)
        .subquery()
    )

    # Main query: join back to get full rows
    q = select(MarketPrice).join(
        subq,
        (MarketPrice.commodity == subq.c.commodity)
        & (MarketPrice.valid_date == subq.c.max_date)
        & (
            (MarketPrice.county == subq.c.county)
            | (MarketPrice.county.is_(None) & subq.c.county.is_(None))
        ),
    ).order_by(MarketPrice.commodity, MarketPrice.county)

    rows = await db.execute(q)
    prices = rows.scalars().all()

    total_q = await db.execute(select(func.count()).where(*sub_filters))
    total = total_q.scalar_one()

    return MarketPriceListResponse(
        prices=[MarketPriceResponse.from_orm_with_decimal(p) for p in prices],
        as_of_date=target_date,
        total=total,
    )


# ── List: price history for a commodity ──────────────────────────────────────

async def list_price_history(
    db: AsyncSession,
    commodity: str,
    county: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
) -> MarketPriceListResponse:
    """
    Return price history for a single commodity (newest first).
    Used by the FR-02 Price History screen.
    """
    filters = [MarketPrice.commodity == commodity]
    if county:
        filters.append(MarketPrice.county == county)

    total_q = await db.execute(select(func.count()).where(*filters))
    total = total_q.scalar_one()

    rows = await db.execute(
        select(MarketPrice)
        .where(*filters)
        .order_by(desc(MarketPrice.valid_date))
        .limit(limit)
        .offset(offset)
    )
    prices = rows.scalars().all()

    return MarketPriceListResponse(
        prices=[MarketPriceResponse.from_orm_with_decimal(p) for p in prices],
        as_of_date=None,
        total=total,
    )


# ── Commodity list ────────────────────────────────────────────────────────────

async def list_commodities(db: AsyncSession) -> CommodityListResponse:
    """Return the list of commodities that have at least one price entry."""
    rows = await db.execute(
        select(MarketPrice.commodity).distinct().order_by(MarketPrice.commodity)
    )
    commodities = [r[0] for r in rows.all()]
    # Include known commodities even if not yet priced
    all_commodities = sorted(set(KNOWN_COMMODITIES) | set(commodities))
    return CommodityListResponse(commodities=all_commodities)
