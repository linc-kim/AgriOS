"""
Greena — Mission Control models (Module 14).

`Mission` is a farmer's long-term goal and the editable planning inputs around it
(metrics, constraints, priorities, assumptions, policies) plus the baseline
captured when it was created. Everything strategic — roadmap, business plan,
daily mission, progress, reports, manual — is computed live from this and the
farm's recorded facts, so nothing here stores a projection that could go stale.

`MissionRevision` is the append-only plan-revision history: the original plan is
never overwritten; each replan snapshots the assumptions it was based on.
"""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    pass

MISSION_STATUSES = ("draft", "active", "achieved", "archived")


class Mission(AGRIOSBase):
    __tablename__ = "missions"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    #: [{kind, label, target, unit}] — kind ∈ birds|profit|revenue|farms|qualitative.
    success_metrics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    constraints: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    priorities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    #: [{key, label, value, unit, source}] — the discovery interview's output, editable.
    assumptions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    #: [{key, statement, category, value}] — "No loans", "90 days cash", "max mortality 3%".
    policies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    #: {metric_kind: value} captured at creation, so progress is honest.
    baseline: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    revisions: Mapped[list["MissionRevision"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Mission '{self.name}' farm={self.farm_id} status={self.status}>"


class MissionRevision(AGRIOSBase):
    __tablename__ = "mission_revisions"
    __table_args__ = (
        UniqueConstraint("mission_id", "revision_number", name="uq_mission_revision_number"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual", server_default="manual")
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    mission: Mapped["Mission"] = relationship(back_populates="revisions")

    def __repr__(self) -> str:
        return f"<MissionRevision mission={self.mission_id} #{self.revision_number}>"
