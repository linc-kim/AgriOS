"""
Greena — BSF Infrastructure Service (Module 16, Part 2)

Business logic for the operational infrastructure a batch references: the species
catalog (data-driven biological reference), production units (bins/trays/racks/
incubators/dryers) and breeding colonies. Batch operations live in
:mod:`app.services.bsf_batch_service`.

Every write is farm- or organisation-scoped (organisation isolation via
``farms.organization_id``), soft-deletes only, and writes an immutable audit-log
entry. No calculations live here — those belong to the deterministic engines.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.bsf import BsfColony, BsfProductionUnit, BsfSpecies
from app.schemas.bsf import (
    ColonyCreate,
    ColonyUpdate,
    ProductionUnitCreate,
    ProductionUnitUpdate,
    SpeciesCreate,
)
from app.services import audit_service


# ── Species catalog (organisation-scoped; NULL org = global) ──────────────────

async def list_species(db: AsyncSession, org_id: uuid.UUID | None) -> list[BsfSpecies]:
    result = await db.execute(
        select(BsfSpecies)
        .where(
            BsfSpecies.deleted_at.is_(None),
            (BsfSpecies.organization_id == org_id) | (BsfSpecies.organization_id.is_(None)),
        )
        .order_by(BsfSpecies.common_name)
    )
    return list(result.scalars().all())


async def create_species(
    db: AsyncSession, org_id: uuid.UUID | None, data: SpeciesCreate, user: User
) -> BsfSpecies:
    species = BsfSpecies(
        id=uuid.uuid4(),
        organization_id=org_id,
        common_name=data.common_name,
        scientific_name=data.scientific_name,
        strain=data.strain,
        production_type=data.production_type,
        profile=data.profile,
        is_system=False,
        created_by=user.id,
    )
    db.add(species)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.species.create", resource_type="bsf_species",
        resource_id=species.id, user_id=user.id,
        new_value={"common_name": species.common_name},
    )
    await db.commit()
    await db.refresh(species)
    return species


async def get_species(db: AsyncSession, org_id: uuid.UUID | None, species_id: uuid.UUID) -> BsfSpecies:
    result = await db.execute(
        select(BsfSpecies).where(
            BsfSpecies.id == species_id,
            BsfSpecies.deleted_at.is_(None),
            (BsfSpecies.organization_id == org_id) | (BsfSpecies.organization_id.is_(None)),
        )
    )
    species = result.scalar_one_or_none()
    if species is None:
        raise NotFoundException(f"BSF species {species_id} not found.")
    return species


# ── Production units (farm-scoped) ────────────────────────────────────────────

async def _get_unit_or_404(db: AsyncSession, farm_id: uuid.UUID, unit_id: uuid.UUID) -> BsfProductionUnit:
    result = await db.execute(
        select(BsfProductionUnit).where(
            BsfProductionUnit.id == unit_id,
            BsfProductionUnit.farm_id == farm_id,
            BsfProductionUnit.deleted_at.is_(None),
        )
    )
    unit = result.scalar_one_or_none()
    if unit is None:
        raise NotFoundException(f"Production unit {unit_id} not found on this farm.")
    return unit


async def _assert_unique_code(
    db: AsyncSession, model, farm_id: uuid.UUID, code: str | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if not code:
        return
    stmt = select(func.count(model.id)).where(
        model.farm_id == farm_id, model.code == code, model.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    if (await db.execute(stmt)).scalar_one() > 0:
        raise ConflictException(f"Code {code!r} is already in use on this farm.")


async def list_units(
    db: AsyncSession, farm_id: uuid.UUID, status: str | None = None,
) -> list[BsfProductionUnit]:
    stmt = select(BsfProductionUnit).where(
        BsfProductionUnit.farm_id == farm_id, BsfProductionUnit.deleted_at.is_(None),
    )
    if status:
        stmt = stmt.where(BsfProductionUnit.status == status)
    stmt = stmt.order_by(BsfProductionUnit.name)
    return list((await db.execute(stmt)).scalars().all())


async def create_unit(
    db: AsyncSession, farm_id: uuid.UUID, data: ProductionUnitCreate, user: User
) -> BsfProductionUnit:
    await _assert_unique_code(db, BsfProductionUnit, farm_id, data.code)
    unit = BsfProductionUnit(
        id=uuid.uuid4(),
        farm_id=farm_id,
        name=data.name,
        code=data.code,
        unit_type=data.unit_type,
        facility=data.facility,
        production_area=data.production_area,
        capacity_grams=data.capacity_grams,
        environment_profile=data.environment_profile,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(unit)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.unit.create", resource_type="bsf_production_unit",
        resource_id=unit.id, farm_id=farm_id, user_id=user.id,
        new_value={"name": unit.name, "unit_type": unit.unit_type},
    )
    await db.commit()
    await db.refresh(unit)
    return unit


async def update_unit(
    db: AsyncSession, farm_id: uuid.UUID, unit_id: uuid.UUID,
    data: ProductionUnitUpdate, user: User,
) -> BsfProductionUnit:
    unit = await _get_unit_or_404(db, farm_id, unit_id)
    fields = data.model_dump(exclude_unset=True)
    if "code" in fields:
        await _assert_unique_code(db, BsfProductionUnit, farm_id, fields["code"], exclude_id=unit_id)
    for key, value in fields.items():
        setattr(unit, key, value)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.unit.update", resource_type="bsf_production_unit",
        resource_id=unit.id, farm_id=farm_id, user_id=user.id,
        new_value={k: str(v) for k, v in fields.items()},
    )
    await db.commit()
    await db.refresh(unit)
    return unit


async def get_unit(db: AsyncSession, farm_id: uuid.UUID, unit_id: uuid.UUID) -> BsfProductionUnit:
    return await _get_unit_or_404(db, farm_id, unit_id)


# ── Colonies (farm-scoped) ────────────────────────────────────────────────────

async def _get_colony_or_404(db: AsyncSession, farm_id: uuid.UUID, colony_id: uuid.UUID) -> BsfColony:
    result = await db.execute(
        select(BsfColony).where(
            BsfColony.id == colony_id,
            BsfColony.farm_id == farm_id,
            BsfColony.deleted_at.is_(None),
        )
    )
    colony = result.scalar_one_or_none()
    if colony is None:
        raise NotFoundException(f"Colony {colony_id} not found on this farm.")
    return colony


async def list_colonies(
    db: AsyncSession, farm_id: uuid.UUID, status: str | None = None,
) -> list[BsfColony]:
    stmt = select(BsfColony).where(
        BsfColony.farm_id == farm_id, BsfColony.deleted_at.is_(None),
    )
    if status:
        stmt = stmt.where(BsfColony.status == status)
    stmt = stmt.order_by(BsfColony.name)
    return list((await db.execute(stmt)).scalars().all())


async def create_colony(
    db: AsyncSession, farm_id: uuid.UUID, data: ColonyCreate, user: User
) -> BsfColony:
    await _assert_unique_code(db, BsfColony, farm_id, data.code)
    if data.production_unit_id is not None:
        await _get_unit_or_404(db, farm_id, data.production_unit_id)
    colony = BsfColony(
        id=uuid.uuid4(),
        farm_id=farm_id,
        species_id=data.species_id,
        production_unit_id=data.production_unit_id,
        name=data.name,
        code=data.code,
        source=data.source,
        established_on=data.established_on,
        population_estimate=data.population_estimate,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(colony)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.colony.create", resource_type="bsf_colony",
        resource_id=colony.id, farm_id=farm_id, user_id=user.id,
        new_value={"name": colony.name},
    )
    await db.commit()
    await db.refresh(colony)
    return colony


async def update_colony(
    db: AsyncSession, farm_id: uuid.UUID, colony_id: uuid.UUID,
    data: ColonyUpdate, user: User,
) -> BsfColony:
    colony = await _get_colony_or_404(db, farm_id, colony_id)
    fields = data.model_dump(exclude_unset=True)
    if "code" in fields:
        await _assert_unique_code(db, BsfColony, farm_id, fields["code"], exclude_id=colony_id)
    if fields.get("production_unit_id") is not None:
        await _get_unit_or_404(db, farm_id, fields["production_unit_id"])
    if fields.get("status") == "retired" and colony.retired_on is None and "retired_on" not in fields:
        fields["retired_on"] = date.today()
    for key, value in fields.items():
        setattr(colony, key, value)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.colony.update", resource_type="bsf_colony",
        resource_id=colony.id, farm_id=farm_id, user_id=user.id,
        new_value={k: str(v) for k, v in fields.items()},
    )
    await db.commit()
    await db.refresh(colony)
    return colony


async def get_colony(db: AsyncSession, farm_id: uuid.UUID, colony_id: uuid.UUID) -> BsfColony:
    return await _get_colony_or_404(db, farm_id, colony_id)
