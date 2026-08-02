"""
Greena — Swine Biosecurity Service (Module 20, Milestone 6)

Operational biosecurity is more than inspections: visitor and vehicle logs,
equipment disinfection, staff sanitation, pen cleaning, rodent control, dead-stock
disposal and quarantine events. Each is a recorded operational fact. ``reminder_id``
softly links a record to a Greena Operations reminder/task so recurring biosecurity
routines integrate with Operations without coupling the modules.
"""

import uuid

from sqlalchemy import func, select

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import SwineBiosecurityRecord
from app.schemas.swine import BiosecurityRecordCreate, BiosecurityRecordUpdate
from app.services import audit_service


async def create_record(db, farm: Farm, data: BiosecurityRecordCreate, user: User) -> SwineBiosecurityRecord:
    row = SwineBiosecurityRecord(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(row)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.biosecurity.create", resource_type="swine_biosecurity_record",
        resource_id=row.id, farm_id=farm.id, user_id=user.id, new_value={"type": data.record_type})
    await db.commit()
    await db.refresh(row)
    return row


async def update_record(db, farm_id, record_id, data: BiosecurityRecordUpdate, user: User) -> SwineBiosecurityRecord:
    r = await db.execute(select(SwineBiosecurityRecord).where(
        SwineBiosecurityRecord.id == record_id, SwineBiosecurityRecord.farm_id == farm_id,
        SwineBiosecurityRecord.deleted_at.is_(None)))
    row = r.scalar_one_or_none()
    if row is None:
        raise NotFoundException(f"Biosecurity record {record_id} not found on this farm.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.biosecurity.update", resource_type="swine_biosecurity_record",
        resource_id=row.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(row)
    return row


async def list_records(db, farm_id, *, record_type=None, limit=100, offset=0):
    conds = [SwineBiosecurityRecord.farm_id == farm_id, SwineBiosecurityRecord.deleted_at.is_(None)]
    if record_type:
        conds.append(SwineBiosecurityRecord.record_type == record_type)
    r = await db.execute(select(SwineBiosecurityRecord).where(*conds)
                         .order_by(SwineBiosecurityRecord.occurred_on.desc()).limit(limit).offset(offset))
    return list(r.scalars().all())


async def summary(db, farm_id) -> dict:
    """Deterministic tally of biosecurity records by type."""
    rows = await db.execute(
        select(SwineBiosecurityRecord.record_type, func.count(SwineBiosecurityRecord.id)).where(
            SwineBiosecurityRecord.farm_id == farm_id, SwineBiosecurityRecord.deleted_at.is_(None)
        ).group_by(SwineBiosecurityRecord.record_type))
    by_type = {row[0]: row[1] for row in rows}
    return {"by_type": by_type, "total": sum(by_type.values())}
