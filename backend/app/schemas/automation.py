"""
Greena — Automation & Notifications Schemas (Module 8).
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import AGRIOSSchema, TimestampedSchema

TriggerType = Literal[
    "low_feed", "low_inventory", "vaccination_due", "health_alert",
    "mortality_spike", "maintenance_due", "financial_anomaly", "tasks_overdue",
]
Recurrence = Literal["none", "daily", "weekly", "monthly"]
Priority = Literal["low", "normal", "high", "critical"]


# ── Automation rules ──────────────────────────────────────────────────────────

class AutomationRuleCreate(AGRIOSSchema):
    name: str = Field(..., min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    trigger_type: TriggerType
    conditions: dict = Field(default_factory=dict)
    # actions: [{"type": "notify", "priority": "high", "message": "..."},
    #           {"type": "create_reminder", "title": "...", "in_days": 1}]
    actions: list[dict] = Field(default_factory=list)
    priority: Priority = "normal"
    is_active: bool = True


class AutomationRuleUpdate(AGRIOSSchema):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    conditions: dict | None = None
    actions: list[dict] | None = None
    priority: Priority | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "AutomationRuleUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class AutomationRuleResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    description: str | None
    trigger_type: str
    conditions: dict
    actions: list[dict]
    priority: str
    is_active: bool
    last_run_at: datetime | None
    run_count: int
    created_by: UUID | None


# ── Reminders ─────────────────────────────────────────────────────────────────

class ReminderCreate(AGRIOSSchema):
    title: str = Field(..., min_length=2, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    due_at: datetime
    recurrence: Recurrence = "none"
    priority: Priority = "normal"


class ReminderUpdate(AGRIOSSchema):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None
    recurrence: Recurrence | None = None
    priority: Priority | None = None
    is_done: bool | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "ReminderUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class ReminderResponse(TimestampedSchema):
    farm_id: UUID
    user_id: UUID | None
    title: str
    notes: str | None
    due_at: datetime
    recurrence: str
    priority: str
    is_done: bool
    done_at: datetime | None
    next_fire_at: datetime | None
    is_overdue: bool
    created_by: UUID | None


# ── Engine run result ─────────────────────────────────────────────────────────

class EngineRunResult(AGRIOSSchema):
    triggers_fired: int
    notifications_created: int
    reminders_fired: int
    rules_evaluated: int
    rules_matched: int
    details: list[dict]


# ── Notification (Activity Center extensions) ─────────────────────────────────

class ActivityNotification(AGRIOSSchema):
    id: UUID
    notification_type: str
    title: str
    body: str
    action_route: str | None
    is_read: bool
    is_archived: bool
    priority: str
    source: str | None
    created_at: datetime
    read_at: datetime | None

    model_config = {"from_attributes": True}
