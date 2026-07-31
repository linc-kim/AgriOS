"""
Greena — BSF Environment Service (Module 16, Part 3)

Owns writes for environmental readings (Spec Part 2 §10, Part 3 §13). Readings
are immutable and never overwritten. Threshold assessment is delegated to the
pure :mod:`bsf_environment_engine`, evaluated against the recommended ranges in
the relevant species' profile.

Note (Spec Part 4 §10): this service *detects* violations and returns them; the
actual Reminder/Notification emission is centralised in the BSF automation layer
(a later milestone) so alerting stays idempotent and un-duplicated.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.bsf import (
    BsfBatch,
    BsfEnvironmentalReading,
    BsfProductionUnit,
    BsfSpecies,
)
from app.schemas.bsf import EnvironmentalReadingCreate
from app.services import audit_service
from app.services import bsf_environment_engine as env_eng


async def _validate_scope(
    db: AsyncSession, farm_id: uuid.UUID,
    unit_id: uuid.UUID | None, batch_id: uuid.UUID | None,
) -> None:
    if unit_id is not None:
        ok = (await db.execute(select(BsfProductionUnit.id).where(
            BsfProductionUnit.id == unit_id, BsfProductionUnit.farm_id == farm_id,
            BsfProductionUnit.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if ok is None:
            raise NotFoundException(f"Production unit {unit_id} not found on this farm.")
    if batch_id is not None:
        ok = (await db.execute(select(BsfBatch.id).where(
            BsfBatch.id == batch_id, BsfBatch.farm_id == farm_id, BsfBatch.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if ok is None:
            raise NotFoundException(f"Batch {batch_id} not found on this farm.")


async def _species_profile_for(
    db: AsyncSession, batch_id: uuid.UUID | None, unit_id: uuid.UUID | None,
) -> dict:
    """Resolve the species profile to assess against: the reading's batch first,
    else the batch currently occupying the unit, else empty (no fabrication)."""
    species_id = None
    if batch_id is not None:
        species_id = (await db.execute(
            select(BsfBatch.species_id).where(BsfBatch.id == batch_id)
        )).scalar_one_or_none()
    if species_id is None and unit_id is not None:
        species_id = (await db.execute(
            select(BsfBatch.species_id)
            .where(BsfBatch.production_unit_id == unit_id, BsfBatch.status == "active",
                   BsfBatch.deleted_at.is_(None))
            .order_by(BsfBatch.created_at.desc()).limit(1)
        )).scalar_one_or_none()
    if species_id is None:
        return {}
    profile = (await db.execute(
        select(BsfSpecies.profile).where(BsfSpecies.id == species_id)
    )).scalar_one_or_none()
    return profile or {}


def _reading_dict(reading: BsfEnvironmentalReading) -> dict:
    return {
        "temperature_c": reading.temperature_c,
        "humidity_pct": reading.humidity_pct,
        "moisture_pct": reading.moisture_pct,
        "airflow_mps": reading.airflow_mps,
    }


async def record_reading(
    db: AsyncSession, farm_id: uuid.UUID, data: EnvironmentalReadingCreate, user: User,
) -> tuple[BsfEnvironmentalReading, dict]:
    """Record an immutable reading and return it with a deterministic assessment."""
    await _validate_scope(db, farm_id, data.production_unit_id, data.batch_id)
    reading = BsfEnvironmentalReading(
        id=uuid.uuid4(),
        farm_id=farm_id,
        production_unit_id=data.production_unit_id,
        batch_id=data.batch_id,
        recorded_at=data.recorded_at or datetime.now(timezone.utc),
        temperature_c=data.temperature_c,
        humidity_pct=data.humidity_pct,
        moisture_pct=data.moisture_pct,
        airflow_mps=data.airflow_mps,
        source=data.source,
        notes=data.notes,
        recorded_by=user.id,
    )
    db.add(reading)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.environment.record", resource_type="bsf_environmental_reading",
        resource_id=reading.id, farm_id=farm_id, user_id=user.id,
        new_value={"unit": str(data.production_unit_id) if data.production_unit_id else None},
    )
    await db.commit()
    await db.refresh(reading)

    profile = await _species_profile_for(db, data.batch_id, data.production_unit_id)
    assessment = env_eng.assess_reading(profile, _reading_dict(reading))
    return reading, assessment


async def list_readings(
    db: AsyncSession, farm_id: uuid.UUID, *,
    production_unit_id: uuid.UUID | None = None, batch_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[BsfEnvironmentalReading]:
    filters = [BsfEnvironmentalReading.farm_id == farm_id, BsfEnvironmentalReading.deleted_at.is_(None)]
    if production_unit_id:
        filters.append(BsfEnvironmentalReading.production_unit_id == production_unit_id)
    if batch_id:
        filters.append(BsfEnvironmentalReading.batch_id == batch_id)
    rows = (await db.execute(
        select(BsfEnvironmentalReading).where(*filters)
        .order_by(BsfEnvironmentalReading.recorded_at.desc()).limit(limit)
    )).scalars().all()
    return list(rows)


async def unit_assessment(
    db: AsyncSession, farm_id: uuid.UUID, unit_id: uuid.UUID,
) -> dict:
    """Latest-reading assessment + per-parameter stability for a production unit."""
    await _validate_scope(db, farm_id, unit_id, None)
    readings = await list_readings(db, farm_id, production_unit_id=unit_id, limit=50)
    if not readings:
        return {"unit_id": str(unit_id), "latest": None, "assessment": None, "stability": {}}

    profile = await _species_profile_for(db, None, unit_id)
    latest = readings[0]
    assessment = env_eng.assess_reading(profile, _reading_dict(latest))
    reading_dicts = [_reading_dict(r) for r in readings]
    stability = {
        "temperature": env_eng.stability(reading_dicts, "temperature_c"),
        "humidity": env_eng.stability(reading_dicts, "humidity_pct"),
        "moisture": env_eng.stability(reading_dicts, "moisture_pct"),
        "airflow": env_eng.stability(reading_dicts, "airflow_mps"),
    }
    return {
        "unit_id": str(unit_id),
        "latest_recorded_at": latest.recorded_at.isoformat(),
        "assessment": assessment,
        "stability": stability,
        "reading_count": len(readings),
    }
