"""
Greena — Swine Pregnancy Service (Module 20, Milestone 3)

Pregnancy is a lifecycle stage confirmed from a breeding service, not a breeding
event — so it has its own table and service. This module owns the pregnancy
lifecycle: confirmation from a breeding, rechecks, pregnancy loss (abortion /
resorption), false pregnancy, and the reads the Pregnancy workspace needs
(confirmed pregnancies, due dates, gestation progress). Farrowing (Milestone 4)
resolves a pregnancy to ``farrowed``.

Gestation math is delegated to the PURE :mod:`swine_breeding_engine`. Every mutation
appends the dam's timeline event + an audit-log entry.
"""

import uuid
from datetime import date

from sqlalchemy import select

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import SwineBreeding, SwinePregnancy
from app.schemas.swine import (
    PregnancyCheckInput,
    PregnancyLossInput,
    PregnancyRecheckInput,
)
from app.services import audit_service
from app.services import swine_breeding_engine as engine
from app.services.swine_service import _append_event, _get_pig_or_404


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_breeding_or_404(db, farm_id, breeding_id) -> SwineBreeding:
    result = await db.execute(
        select(SwineBreeding).where(
            SwineBreeding.id == breeding_id, SwineBreeding.farm_id == farm_id,
            SwineBreeding.deleted_at.is_(None),
        )
    )
    b = result.scalar_one_or_none()
    if b is None:
        raise NotFoundException(f"Breeding {breeding_id} not found on this farm.")
    return b


async def _get_pregnancy_or_404(db, farm_id, pregnancy_id) -> SwinePregnancy:
    result = await db.execute(
        select(SwinePregnancy).where(
            SwinePregnancy.id == pregnancy_id, SwinePregnancy.farm_id == farm_id,
            SwinePregnancy.deleted_at.is_(None),
        )
    )
    p = result.scalar_one_or_none()
    if p is None:
        raise NotFoundException(f"Pregnancy {pregnancy_id} not found on this farm.")
    return p


async def _dam_has_active_pregnancy(db, dam_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(SwinePregnancy.id).where(
            SwinePregnancy.dam_id == dam_id,
            SwinePregnancy.status.in_(("unconfirmed", "confirmed")),
            SwinePregnancy.deleted_at.is_(None),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


# ── Pregnancy check (from a breeding) ──────────────────────────────────────────

async def record_pregnancy_check(db, farm: Farm, breeding_id, data: PregnancyCheckInput, user: User):
    """Record a pregnancy check on a breeding service.

    A positive check creates a confirmed :class:`SwinePregnancy` (unless one is
    already active for the dam) and resolves the breeding as ``pregnant``. A negative
    check resolves the breeding as ``not_pregnant`` with no pregnancy row. Returns
    ``(breeding, pregnancy_or_None)``.
    """
    b = await _get_breeding_or_404(db, farm.id, breeding_id)
    if b.status in ("closed", "cancelled") or b.outcome in ("pregnant", "not_pregnant"):
        raise ConflictException("This breeding has already been resolved.")

    pregnancy = None
    if data.result == "pregnant":
        if b.dam_id and await _dam_has_active_pregnancy(db, b.dam_id):
            raise ConflictException("The dam already has an active pregnancy.")
        expected = b.planned_farrowing_date
        pregnancy = SwinePregnancy(
            id=uuid.uuid4(), farm_id=farm.id, breeding_id=b.id, dam_id=b.dam_id,
            status="confirmed", confirmation_date=data.checked_on, confirmation_method=data.method,
            expected_farrowing_date=expected, risk_level=data.risk_level or "low",
            created_by=user.id,
        )
        db.add(pregnancy)
        b.outcome = "pregnant"
        b.status = "closed"
    elif data.result == "not_pregnant":
        b.outcome = "not_pregnant"
        b.status = "closed"

    await db.flush()
    if b.dam_id:
        dam = await _get_pig_or_404(db, farm.id, b.dam_id)
        dam.reproductive_status = "pregnant" if data.result == "pregnant" else "open"
        await _append_event(db, b.dam_id, "pregnancy_checked", f"Pregnancy check: {data.result}",
                            operator_id=user.id,
                            details={"breeding_id": str(b.id), "result": data.result, "method": data.method,
                                     "pregnancy_id": str(pregnancy.id) if pregnancy else None})
    await audit_service.log_action(
        db, action="swine.pregnancy.check", resource_type="swine_breeding",
        resource_id=b.id, farm_id=farm.id, user_id=user.id, new_value={"result": data.result},
    )
    await db.commit()
    await db.refresh(b)
    if pregnancy is not None:
        await db.refresh(pregnancy)
    return b, pregnancy


# ── Pregnancy lifecycle ────────────────────────────────────────────────────────

async def recheck(db, farm_id, pregnancy_id, data: PregnancyRecheckInput, user: User) -> SwinePregnancy:
    p = await _get_pregnancy_or_404(db, farm_id, pregnancy_id)
    if not p.is_active:
        raise ConflictException(f"Pregnancy is already {p.status}; it cannot be rechecked.")
    if data.risk_level is not None:
        p.risk_level = data.risk_level
    if data.expected_farrowing_date is not None:
        p.expected_farrowing_date = data.expected_farrowing_date
    if data.notes is not None:
        p.notes = data.notes
    await db.flush()
    if p.dam_id:
        await _append_event(db, p.dam_id, "pregnancy_checked", "Pregnancy recheck",
                            operator_id=user.id,
                            details={"pregnancy_id": str(p.id), "risk_level": p.risk_level})
    await audit_service.log_action(
        db, action="swine.pregnancy.recheck", resource_type="swine_pregnancy",
        resource_id=p.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(p)
    return p


async def record_loss(db, farm_id, pregnancy_id, data: PregnancyLossInput, user: User) -> SwinePregnancy:
    """Record a pregnancy loss (abortion / resorption / …) or a false pregnancy."""
    p = await _get_pregnancy_or_404(db, farm_id, pregnancy_id)
    if not p.is_active:
        raise ConflictException(f"Pregnancy is already {p.status}.")
    p.status = "false_pregnancy" if data.false_pregnancy else "lost"
    p.loss_reason = data.loss_reason
    p.loss_date = data.loss_date or date.today()
    if data.notes is not None:
        p.notes = data.notes
    await db.flush()
    # Resolve the originating breeding and free the dam.
    if p.breeding_id:
        b = await _get_breeding_or_404(db, farm_id, p.breeding_id)
        b.outcome = "failed"
    if p.dam_id:
        dam = await _get_pig_or_404(db, farm_id, p.dam_id)
        dam.reproductive_status = "open"
        await _append_event(db, p.dam_id, "pregnancy_checked", f"Pregnancy {p.status}",
                            operator_id=user.id,
                            details={"pregnancy_id": str(p.id), "loss_reason": data.loss_reason})
    await audit_service.log_action(
        db, action="swine.pregnancy.loss", resource_type="swine_pregnancy",
        resource_id=p.id, farm_id=farm_id, user_id=user.id, new_value={"status": p.status},
    )
    await db.commit()
    await db.refresh(p)
    return p


# ── Reads ──────────────────────────────────────────────────────────────────────

async def list_pregnancies(db, farm_id, *, status=None, risk_level=None, limit=100, offset=0):
    """The Pregnancy workspace. Defaults to the active (confirmed) pregnancies,
    ordered by soonest expected farrowing (the due calendar)."""
    conds = [SwinePregnancy.farm_id == farm_id, SwinePregnancy.deleted_at.is_(None)]
    if status:
        conds.append(SwinePregnancy.status == status)
    else:
        conds.append(SwinePregnancy.status.in_(("unconfirmed", "confirmed")))
    if risk_level:
        conds.append(SwinePregnancy.risk_level == risk_level)
    result = await db.execute(
        select(SwinePregnancy).where(*conds)
        .order_by(SwinePregnancy.expected_farrowing_date.asc().nulls_last()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def get_pregnancy_detail(db, farm_id, pregnancy_id, today: date | None = None) -> tuple[SwinePregnancy, dict]:
    p = await _get_pregnancy_or_404(db, farm_id, pregnancy_id)
    # Gestation progress relative to the expected farrowing date (deterministic).
    progress: dict = {}
    if p.expected_farrowing_date is not None:
        from datetime import timedelta
        # Reconstruct the service date from expected − gestation for a progress read.
        gest = 114
        service = p.expected_farrowing_date - timedelta(days=gest)
        progress = engine.gestation_progress(service, today or date.today(), gest)
    return p, progress
