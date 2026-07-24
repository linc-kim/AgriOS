"""
ARIA — the write path.

This is the only module in the ARIA stack that touches the database, and it does
so by calling the existing domain services rather than the ORM directly. That is
deliberate: every validation, snapshot recompute and business rule those services
enforce keeps applying, so a mortality recorded by talking to ARIA is byte-for-byte
the same record as one entered on the Livestock screen. There is no second,
weaker path into a farmer's data.

On AR-01. The frozen decision says ARIA never gets database access, and Module 13
overrides it — but narrowly. What gained write capability is the deterministic
pipeline: `aria_nlu` parses, `aria_dialogue` fills slots and takes an explicit
confirmation, and this module maps the confirmed payload onto a domain schema.
Gemini and Claude are not in that chain at any point. They cannot reach this
module, cannot cause a write, and cannot influence one. The security property
AR-01 was protecting — that a model cannot be prompted into touching Postgres —
is intact; what changed is that a farmer can now say "three birds died" instead
of tapping through four screens.

Everything here is also why operational recording works with no AI provider
configured at all.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.farm import Farm
from app.models.flock import DailyLog, Flock
from app.models.auth import User
from app.schemas.automation import ReminderCreate
from app.schemas.flock import DailyLogSubmit, ProductionRecordSubmit, WeighinSubmit
from app.schemas.health import VaccinationRecordCreate
from app.services import audit_service, automation_service, flock_service, health_service
from app.services.aria_nlu import Intent


# ── Flock resolution ─────────────────────────────────────────────────────────


@dataclass
class FlockCandidate:
    id: uuid.UUID
    label: str


async def list_active_flocks(db: AsyncSession, farm_id: uuid.UUID) -> list[FlockCandidate]:
    result = await db.execute(
        select(Flock)
        .where(
            Flock.farm_id == str(farm_id),
            Flock.status == "active",
            Flock.deleted_at.is_(None),
        )
        .order_by(Flock.placement_date.desc())
    )
    return [FlockCandidate(id=f.id, label=f.name) for f in result.scalars().all()]


async def resolve_flock(
    db: AsyncSession,
    farm_id: uuid.UUID,
    reference: str | None,
) -> tuple[FlockCandidate | None, list[FlockCandidate]]:
    """
    Turn "2" / "alpha" / "flock alpha" into an actual flock.

    Returns (match, candidates). A match is returned only when it is
    unambiguous; anything else comes back as candidates for the dialogue to ask
    about. Two flocks whose names both contain "alpha" is a question, not a
    coin flip — writing a mortality to the wrong flock is precisely the failure
    this whole design exists to prevent.

    The one convenience: a farm with exactly one active flock and no reference
    resolves to that flock. There is nothing to be ambiguous about, and asking
    "which flock?" of someone who has one flock is the kind of friction that
    makes people go back to the forms.
    """
    flocks = await list_active_flocks(db, farm_id)

    if not reference:
        if len(flocks) == 1:
            return flocks[0], flocks
        return None, flocks

    ref = reference.strip().lower()

    exact = [f for f in flocks if f.label.lower() == ref]
    if len(exact) == 1:
        return exact[0], flocks

    # "flock 2" → the flock whose name ends in or contains the token.
    partial = [f for f in flocks if ref in f.label.lower()]
    if len(partial) == 1:
        return partial[0], flocks

    # A bare ordinal — "2" meaning the second flock — only when nothing else
    # matched and the index is real.
    if ref.isdigit():
        idx = int(ref)
        numbered = [f for f in flocks if ref in f.label.lower().split()]
        if len(numbered) == 1:
            return numbered[0], flocks
        if 1 <= idx <= len(flocks) and len(flocks) > 1:
            # Deliberately NOT resolved: "flock 2" on a farm with flocks named
            # "Batch A"/"Batch B" almost certainly means a name, not a position.
            return None, flocks

    return None, flocks


# ── Result ───────────────────────────────────────────────────────────────────


@dataclass
class ActionResult:
    """What a write actually did, for the summary ARIA gives back."""

    ok: bool
    summary: str
    module: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ── Executor ─────────────────────────────────────────────────────────────────


async def execute(
    db: AsyncSession,
    farm: Farm,
    current_user: User,
    payload: dict[str, Any],
) -> ActionResult:
    """
    Write a confirmed payload.

    `payload` comes from `aria_dialogue.build_payload` and has already been
    through slot filling and an explicit farmer confirmation. This function
    assumes neither — it revalidates through the domain schemas, so a malformed
    payload fails the same way a malformed API request would.
    """
    intent = Intent(payload["intent"])
    slots = _typed(payload.get("slots", {}))

    handler = _HANDLERS.get(intent)
    if handler is None:
        return ActionResult(
            ok=False,
            summary="I can't record that yet.",
            module="none",
            resource_type="none",
            error=f"No writer for intent {intent.value}",
        )

    try:
        result = await handler(db, farm, current_user, slots)
    except Exception as exc:  # noqa: BLE001 — surfaced to the farmer, not swallowed
        return ActionResult(
            ok=False,
            summary="I couldn't save that — nothing was changed.",
            module="none",
            resource_type="none",
            error=str(exc),
        )

    if result.ok:
        # Audit is how a farmer (or support) can later answer "who recorded
        # this, and how?". Conversational writes are exactly the ones that need
        # that provenance, since there is no form submission to point at.
        await audit_service.log_action_safe(
            db,
            action=f"{result.resource_type}.create",
            resource_type=result.resource_type,
            resource_id=result.resource_id,
            farm_id=farm.id,
            user_id=current_user.id,
            new_value={"via": "aria_conversation", **result.changes},
        )

    return result


def _typed(slots: dict[str, Any]) -> dict[str, Any]:
    """Restore JSON-ed slots to the types the domain schemas expect."""
    out = dict(slots)
    for date_key in ("date", "due_date"):
        if isinstance(out.get(date_key), str):
            try:
                out[date_key] = date.fromisoformat(out[date_key])
            except ValueError:
                out.pop(date_key, None)
    for key in ("quantity_kg", "amount", "unit_price", "average_weight_kg"):
        if key in out and not isinstance(out[key], Decimal):
            try:
                out[key] = Decimal(str(out[key]))
            except Exception:
                out.pop(key, None)
    return out


def _flock_id(slots: dict[str, Any]) -> uuid.UUID:
    raw = slots.get("flock_id")
    if not raw:
        raise ValueError("flock_id missing — the dialogue must resolve a flock first")
    return raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))


# ── Per-intent writers ───────────────────────────────────────────────────────


async def _write_mortality(db, farm, user, slots) -> ActionResult:
    """
    Mortality goes onto the daily log, which is upserted per (flock, date).

    Reads the existing log first and *adds* to it rather than replacing. A
    farmer who loses two birds in the morning and one in the afternoon has lost
    three that day; overwriting would silently discard the earlier record.
    """
    flock_id = _flock_id(slots)
    when = slots.get("date") or date.today()
    count = int(slots["count"])

    # Read the existing log directly rather than via
    # `flock_service.get_daily_log_by_date`, which raises NotFound when there is
    # no log for the day. "No log yet" is the normal first-report-of-the-day
    # case here, not an error.
    existing = (
        await db.execute(
            select(DailyLog).where(
                DailyLog.flock_id == str(flock_id),
                DailyLog.log_date == when,
                DailyLog.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    already = int(existing.mortality_count or 0) if existing else 0

    cause = slots.get("cause")
    notes = _clinical_notes(slots)

    log = await flock_service.submit_daily_log(
        db,
        farm.id,
        flock_id,
        DailyLogSubmit(
            log_date=when,
            mortality_count=already + count,
            mortality_cause=(cause or None) if cause else None,
            notes=notes or None,
        ),
        user,
    )
    return ActionResult(
        ok=True,
        summary=f"Recorded {count} bird(s) lost on {when.isoformat()}.",
        module="livestock",
        resource_type="daily_log",
        resource_id=getattr(log, "id", None),
        changes={"mortality_count": already + count, "added": count, "date": when.isoformat()},
    )


def _clinical_notes(slots: dict[str, Any]) -> str | None:
    """Fold probe answers into a note. Only what the farmer actually said."""
    parts = []
    for key, prefix in (
        ("symptoms", "Symptoms"),
        ("sudden", "Onset"),
        ("others_affected", "Others affected"),
    ):
        value = slots.get(key)
        if value:
            parts.append(f"{prefix}: {value}")
    return " | ".join(parts) if parts else None


async def _write_eggs(db, farm, user, slots) -> ActionResult:
    flock_id = _flock_id(slots)
    when = slots.get("date") or date.today()
    count = int(slots["count"])
    broken = int(slots.get("broken") or 0)

    record = await flock_service.submit_production_record(
        db,
        farm.id,
        flock_id,
        ProductionRecordSubmit(record_date=when, eggs_collected=count, broken_eggs=broken),
        user,
    )
    return ActionResult(
        ok=True,
        summary=f"Recorded {count} eggs collected on {when.isoformat()}.",
        module="production",
        resource_type="production_record",
        resource_id=getattr(record, "id", None),
        changes={"eggs_collected": count, "broken_eggs": broken, "date": when.isoformat()},
    )


async def _write_weight(db, farm, user, slots) -> ActionResult:
    flock_id = _flock_id(slots)
    when = slots.get("date") or date.today()

    record = await flock_service.submit_weighin(
        db,
        farm.id,
        flock_id,
        WeighinSubmit(
            weighed_at=when,
            sample_size=int(slots["sample_size"]),
            average_weight_kg=Decimal(str(slots["average_weight_kg"])),
        ),
        user,
    )
    return ActionResult(
        ok=True,
        summary=(
            f"Recorded a weigh-in of {slots['sample_size']} birds "
            f"averaging {slots['average_weight_kg']}kg."
        ),
        module="livestock",
        resource_type="weighin_record",
        resource_id=getattr(record, "id", None),
        changes={
            "sample_size": int(slots["sample_size"]),
            "average_weight_kg": str(slots["average_weight_kg"]),
            "date": when.isoformat(),
        },
    )


async def _write_vaccination(db, farm, user, slots) -> ActionResult:
    flock_id = _flock_id(slots)
    when = slots.get("date") or date.today()

    record = await health_service.log_vaccination(
        db,
        farm,
        flock_id,
        VaccinationRecordCreate(
            vaccine_name=str(slots["vaccine_name"])[:200],
            administered_date=when,
            dose_number=int(slots.get("dose_number") or 1),
            route=slots.get("route") or None,
        ),
        user,
    )
    return ActionResult(
        ok=True,
        summary=f"Recorded {slots['vaccine_name']} given on {when.isoformat()}.",
        module="health",
        resource_type="vaccination_record",
        resource_id=getattr(record, "id", None),
        changes={"vaccine_name": str(slots["vaccine_name"]), "date": when.isoformat()},
    )


async def _write_feed_consumption(db, farm, user, slots) -> ActionResult:
    """Feed use belongs on the daily log alongside mortality."""
    flock_id = _flock_id(slots)
    when = slots.get("date") or date.today()
    kg = Decimal(str(slots["quantity_kg"]))

    log = await flock_service.submit_daily_log(
        db,
        farm.id,
        flock_id,
        DailyLogSubmit(log_date=when, feed_consumed_kg=kg),
        user,
    )
    return ActionResult(
        ok=True,
        summary=f"Recorded {kg}kg of feed used on {when.isoformat()}.",
        module="feed",
        resource_type="daily_log",
        resource_id=getattr(log, "id", None),
        changes={"feed_consumed_kg": str(kg), "date": when.isoformat()},
    )


async def _write_reminder(db, farm, user, slots) -> ActionResult:
    """
    A reminder goes to the existing Reminder module — not a flock record. Same
    parse-confirm-write pipeline, different destination. The due date is stored
    at 06:00 local so a "remind me Tuesday" fires before the morning farm walk.
    """
    from datetime import datetime, time

    title = str(slots["title"]).strip()[:200]
    due = slots.get("due_date")
    if not isinstance(due, date):
        raise ValueError("due_date missing — the dialogue must collect a time first")
    due_at = datetime.combine(due, time(hour=6, minute=0))
    recurrence = slots.get("recurrence") or "none"

    reminder = await automation_service.create_reminder(
        db,
        farm,
        ReminderCreate(title=title, due_at=due_at, recurrence=recurrence, priority="normal"),
        user,
    )
    recur_txt = f" ({recurrence})" if recurrence != "none" else ""
    return ActionResult(
        ok=True,
        summary=f"Reminder set: {title} on {due.isoformat()}{recur_txt}.",
        module="reminders",
        resource_type="reminder",
        resource_id=getattr(reminder, "id", None),
        changes={"title": title, "due_at": due_at.isoformat(), "recurrence": recurrence},
    )


_HANDLERS = {
    Intent.RECORD_MORTALITY: _write_mortality,
    Intent.RECORD_EGGS: _write_eggs,
    Intent.RECORD_WEIGHT: _write_weight,
    Intent.RECORD_VACCINATION: _write_vaccination,
    Intent.RECORD_FEED_CONSUMPTION: _write_feed_consumption,
    Intent.CREATE_REMINDER: _write_reminder,
}


#: Intents the parser understands but that have no writer yet. Kept explicit so
#: ARIA can say "I understood, I can't file it yet" rather than failing opaquely
#: — feed purchases and sales need a supplier and a category the dialogue does
#: not collect, and guessing either would put a wrong row in someone's books.
UNSUPPORTED_INTENTS = {
    Intent.RECORD_FEED_PURCHASE,
    Intent.RECORD_SALE,
    Intent.RECORD_EXPENSE,
}
