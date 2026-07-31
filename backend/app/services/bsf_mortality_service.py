"""
Greena — BSF Mortality Service (Module 16, Part 5)

Owns writes for mortality events (Spec Part 3 §17). Recording mortality decrements
the batch's recorded population estimate and appends an immutable batch event.
Deterministic health analytics are delegated to the pure
:mod:`bsf_health_engine`. Farm-scoped, soft-delete, audit-logged.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.bsf import (
    BsfBatch,
    BsfBatchEvent,
    BsfLifecycleEvent,
    BsfMortalityEvent,
)
from app.schemas.bsf import MortalityEventCreate
from app.services import audit_service
from app.services import bsf_health_engine as health_eng

_TERMINAL_STATUSES = ("harvested", "completed", "split", "merged", "terminated", "archived")


async def _get_batch_or_404(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> BsfBatch:
    result = await db.execute(
        select(BsfBatch).where(
            BsfBatch.id == batch_id, BsfBatch.farm_id == farm_id, BsfBatch.deleted_at.is_(None),
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise NotFoundException(f"Batch {batch_id} not found on this farm.")
    return batch


async def record_mortality(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID, data: MortalityEventCreate, user: User,
) -> BsfMortalityEvent:
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    if batch.status in _TERMINAL_STATUSES:
        raise ConflictException(f"Batch {batch.batch_number} is {batch.status}; mortality cannot be recorded.")
    if data.estimated_loss <= 0:
        raise ValidationException("Estimated loss must be greater than zero.")

    event = BsfMortalityEvent(
        id=uuid.uuid4(),
        farm_id=farm_id,
        batch_id=batch_id,
        occurred_on=data.occurred_on or date.today(),
        estimated_loss=data.estimated_loss,
        cause=data.cause,
        observations=data.observations,
        operator_id=user.id,
    )
    db.add(event)

    # Decrement the batch's recorded population (clamped at zero).
    if batch.population_estimate is not None:
        batch.population_estimate = max(0, batch.population_estimate - data.estimated_loss)

    db.add(BsfBatchEvent(
        id=uuid.uuid4(), batch_id=batch_id, event_type="note",
        occurred_at=datetime.now(timezone.utc),
        summary=f"Mortality: {data.estimated_loss} lost ({data.cause}).",
        details={"kind": "mortality", "estimated_loss": data.estimated_loss, "cause": data.cause},
        operator_id=user.id,
    ))
    await audit_service.log_action(
        db, action="bsf.mortality.record", resource_type="bsf_mortality_event",
        resource_id=event.id, farm_id=farm_id, user_id=user.id,
        new_value={"batch": batch.batch_number, "loss": data.estimated_loss, "cause": data.cause},
    )
    await db.commit()
    await db.refresh(event)
    return event


async def list_mortality(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> list[BsfMortalityEvent]:
    await _get_batch_or_404(db, farm_id, batch_id)
    rows = (await db.execute(
        select(BsfMortalityEvent)
        .where(BsfMortalityEvent.batch_id == batch_id, BsfMortalityEvent.deleted_at.is_(None))
        .order_by(BsfMortalityEvent.occurred_on.desc(), BsfMortalityEvent.created_at.desc())
    )).scalars().all()
    return list(rows)


async def health_summary(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> dict:
    """Deterministic batch health picture from recorded mortality (Spec Part 4 §15)."""
    await _get_batch_or_404(db, farm_id, batch_id)

    events = (await db.execute(
        select(BsfMortalityEvent)
        .where(BsfMortalityEvent.batch_id == batch_id, BsfMortalityEvent.deleted_at.is_(None))
        .order_by(BsfMortalityEvent.occurred_on, BsfMortalityEvent.created_at)
    )).scalars().all()
    loss_series = [e.estimated_loss for e in events]
    total_loss = sum(loss_series) if loss_series else None

    # Initial population = first recorded lifecycle snapshot.
    first = (await db.execute(
        select(BsfLifecycleEvent.population_estimate)
        .where(BsfLifecycleEvent.batch_id == batch_id, BsfLifecycleEvent.deleted_at.is_(None))
        .order_by(BsfLifecycleEvent.occurred_on, BsfLifecycleEvent.created_at)
        .limit(1)
    )).scalar_one_or_none()

    summary = health_eng.health_summary(total_loss, first, loss_series)
    summary["event_count"] = {"label": "recorded", "value": len(events),
                              "detail": "Count of recorded mortality events."}
    return summary
