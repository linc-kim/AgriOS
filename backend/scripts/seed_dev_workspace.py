"""
Seed a complete, log-in-able workspace on the local dev database.

For browser verification only — never run against a real database. Creates an
owner with a known email/password, a farm with an active flock, and a little
production/finance history so the ARIA snapshot panel has real numbers to show.

    DATABASE_URL=postgresql+asyncpg://postgres:...@127.0.0.1:5433/agrios \
        .venv/Scripts/python.exe scripts/seed_dev_workspace.py
"""

import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.auth import Role, User, UserRole
from app.models.farm import (
    Farm,
    FarmMember,
    FarmUnit,
    ProductionHouse,
    SubscriptionPlan,
)
from app.models.flock import DailyLog, Flock, ProductionRecord
from app.models.organization import Organization, OrganizationMember

EMAIL = "farmer@greena.dev"
PASSWORD = "GreenaFarm2026!"


async def main() -> None:
    async with AsyncSessionLocal() as s:
        existing = (
            await s.execute(select(User).where(User.email == EMAIL))
        ).scalar_one_or_none()
        if existing:
            print(f"already seeded — log in as {EMAIL} / {PASSWORD}")
            return

        roles = {r.name: r for r in (await s.execute(select(Role))).scalars().all()}
        plan = (
            await s.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "free"))
        ).scalar_one()

        owner = User(
            email=EMAIL,
            phone="+254799000001",
            full_name="Dev Farmer",
            password_hash=hash_password(PASSWORD),
            is_phone_verified=True,
            email_verified=True,
            is_active=True,
        )
        s.add(owner)
        await s.flush()
        s.add(UserRole(user_id=owner.id, role_id=roles["farm_owner"].id, farm_id=None))

        # The app gates onboarding on organization membership, so the workspace
        # needs a real org the owner belongs to.
        org = Organization(
            name="Greenfields Ltd",
            slug="greenfields-dev",
            owner_id=owner.id,
            plan_id=plan.id,
            country="KE",
        )
        s.add(org)
        await s.flush()
        s.add(
            OrganizationMember(
                organization_id=org.id,
                user_id=owner.id,
                role_id=roles["farm_owner"].id,
                email=owner.email,
                status="active",
                invited_by=owner.id,
                accepted_at=date.today(),
            )
        )

        farm = Farm(
            name="Greenfields Poultry",
            county="Kiambu",
            location="Ruiru",
            owner_id=owner.id,
            organization_id=org.id,
            plan_id=plan.id,
            is_active=True,
            timezone="Africa/Nairobi",
        )
        s.add(farm)
        await s.flush()
        s.add(
            FarmMember(
                farm_id=farm.id,
                user_id=owner.id,
                role_id=roles["farm_owner"].id,
                phone=owner.phone,
                status="active",
                invited_by=owner.id,
                accepted_at=date.today(),
            )
        )

        unit = FarmUnit(farm_id=farm.id, name="Block A", sort_order=0)
        s.add(unit)
        await s.flush()
        house = ProductionHouse(
            farm_id=farm.id, unit_id=unit.id, name="House 1",
            capacity=1000, house_type="layer", sort_order=0,
        )
        s.add(house)
        await s.flush()

        flock = Flock(
            farm_id=farm.id, house_id=house.id, species_key="poultry",
            name="Layers A", initial_count=500,
            placement_date=date.today() - timedelta(days=120), status="active",
        )
        s.add(flock)
        await s.flush()
        house.current_flock_id = flock.id

        # A little history so the snapshot isn't empty: a week of eggs, some
        # feed and a couple of losses.
        today = date.today()
        for i in range(7):
            d = today - timedelta(days=i)
            s.add(
                ProductionRecord(
                    farm_id=farm.id, flock_id=flock.id, record_date=d,
                    eggs_collected=420 - i * 5, broken_eggs=3,
                )
            )
            s.add(
                DailyLog(
                    farm_id=farm.id, flock_id=flock.id, log_date=d,
                    mortality_count=1 if i in (1, 3) else 0,
                    feed_consumed_kg=58,
                )
            )

        await s.commit()
        print(f"seeded farm '{farm.name}' — log in as {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
