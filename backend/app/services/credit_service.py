"""
Greena — Credit service (Commercial Policy layer, C6).

An **immutable** ledger. Balances change only by appending new rows; entries are
never updated or deleted. Each row stores the running ``balance_after`` for
audit, and the authoritative balance is the sum of all amounts.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commercial import CreditLedgerEntry


class CreditService:
    async def get_balance(self, db: AsyncSession, organization_id: uuid.UUID) -> int:
        total = (
            await db.execute(
                select(func.coalesce(func.sum(CreditLedgerEntry.amount_kes), 0)).where(
                    CreditLedgerEntry.organization_id == organization_id
                )
            )
        ).scalar_one()
        return int(total)

    async def add_entry(
        self,
        db: AsyncSession,
        organization_id: uuid.UUID,
        amount_kes: int,
        source: str,
        payment_reference: str | None = None,
    ) -> CreditLedgerEntry:
        """Append a ledger entry (positive = credit, negative = adjustment)."""
        balance = await self.get_balance(db, organization_id)
        entry = CreditLedgerEntry(
            organization_id=organization_id,
            amount_kes=amount_kes,
            source=source,
            payment_reference=payment_reference,
            balance_after=balance + amount_kes,
        )
        db.add(entry)
        await db.flush()
        return entry

    async def get_history(
        self, db: AsyncSession, organization_id: uuid.UUID
    ) -> list[CreditLedgerEntry]:
        return list(
            (
                await db.execute(
                    select(CreditLedgerEntry)
                    .where(CreditLedgerEntry.organization_id == organization_id)
                    .order_by(CreditLedgerEntry.created_at)
                )
            ).scalars().all()
        )


credit_service = CreditService()
