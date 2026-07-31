"""
Greena — Growth Planner Models (Platform, introduced by Module 16)

The **canonical, cross-module** long-term-growth store: goals, milestones and
plan revisions for BSF today and every future Greena agricultural module. NOT
`bsf_`-prefixed — a ``module`` discriminator (``'bsf'``, ``'aviculture'``, …)
lets every module share one planner (see docs/MODULE_16_BSF_LEDGER.md → Growth
Planner Contract).

Design rules:
  * Goals/milestones/progress are **recorded domain objects**, never AI-generated
    text. ARIA may draft; what is stored is deterministic structured data.
  * Every plan mutation appends an immutable :class:`GrowthPlanRevision` snapshot
    — full version history, mirroring ``MissionRevision`` (Module 14).
  * Farm-scoped; organisation isolation flows through ``farms.organization_id``.
  * Enumerated fields are validated at the schema/service layer.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

GROWTH_PLAN_STATUS_VALUES = ("active", "achieved", "archived")
GROWTH_GOAL_STATUS_VALUES = ("open", "achieved", "abandoned")
GROWTH_MILESTONE_STATUS_VALUES = ("pending", "in_progress", "achieved", "blocked", "skipped")
GROWTH_REVISION_TRIGGER_VALUES = ("manual", "adaptive", "goal_change", "milestone_update")


class GrowthPlan(AGRIOSBase):
    """A farm's long-term growth plan for one module. Aggregate root of the planner."""

    __tablename__ = "growth_plan"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    module: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    goals: Mapped[list["GrowthGoal"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="noload")
    milestones: Mapped[list["GrowthMilestone"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="noload")
    revisions: Mapped[list["GrowthPlanRevision"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="noload")

    def __repr__(self) -> str:
        return f"<GrowthPlan '{self.title}' module={self.module} status={self.status}>"


class GrowthGoal(AGRIOSBase):
    """A measurable target within a plan (metric_key → target_value by target_date)."""

    __tablename__ = "growth_goal"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_plan.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    metric_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    plan: Mapped["GrowthPlan"] = relationship(back_populates="goals", lazy="noload")

    def __repr__(self) -> str:
        return f"<GrowthGoal {self.metric_key}→{self.target_value} status={self.status}>"


class GrowthMilestone(AGRIOSBase):
    """An ordered step toward the plan's goals."""

    __tablename__ = "growth_milestone"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_plan.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    target_metric_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_metric_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    expected_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    plan: Mapped["GrowthPlan"] = relationship(back_populates="milestones", lazy="noload")

    def __repr__(self) -> str:
        return f"<GrowthMilestone '{self.title}' seq={self.sequence} status={self.status}>"


class GrowthPlanRevision(AGRIOSBase):
    """Immutable snapshot of a plan's full state at a point in time (version history)."""

    __tablename__ = "growth_plan_revision"
    __table_args__ = (
        UniqueConstraint("plan_id", "revision_number", name="uq_growth_plan_revision_number"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_plan.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    plan: Mapped["GrowthPlan"] = relationship(back_populates="revisions", lazy="noload")

    def __repr__(self) -> str:
        return f"<GrowthPlanRevision plan={self.plan_id} #{self.revision_number}>"
