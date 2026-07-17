"""
Greena — Automation & Notifications Endpoints (Module 8).

Farm-scoped under /farms/{farm_id}/automation.

  Rules       POST/GET/PATCH/DELETE  /automation/rules
  Reminders   POST/GET/PATCH/DELETE  /automation/reminders
  Engine      POST /automation/run
  Activity    GET /automation/activity ; POST /automation/activity/{id}/archive
  Triggers    GET /automation/triggers

RBAC: AUTOMATION_MANAGE (rules/reminders/run) · AUTOMATION_VIEW (activity/read).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.models.automation import TRIGGER_TYPES
from app.schemas.automation import (
    ActivityNotification,
    AutomationRuleCreate,
    AutomationRuleResponse,
    AutomationRuleUpdate,
    EngineRunResult,
    ReminderCreate,
    ReminderResponse,
    ReminderUpdate,
)
from app.schemas.base import SuccessResponse
from app.services import automation_service

router = APIRouter()

_WRITE = {"enterprise_owner", "farm_owner", "farm_manager"}


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/automation/rules", response_model=SuccessResponse[AutomationRuleResponse],
             status_code=status.HTTP_201_CREATED, summary="Create automation rule", tags=["Automation"])
async def create_rule(farm_id: str, body: AutomationRuleCreate, db: DBSession, current_user: CurrentUser,
                      access: tuple = Depends(require_farm_access(_WRITE)),
                      _p=Depends(require_permission(Permission.AUTOMATION_MANAGE))):
    farm, _ = access
    rule = await automation_service.create_rule(db, farm, body, current_user)
    return SuccessResponse(data=AutomationRuleResponse.model_validate(rule))


@router.get("/farms/{farm_id}/automation/rules", response_model=SuccessResponse[list[AutomationRuleResponse]],
            summary="List automation rules", tags=["Automation"])
async def list_rules(farm_id: str, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access()),
                     _p=Depends(require_permission(Permission.AUTOMATION_VIEW))):
    farm, _ = access
    rules = await automation_service.list_rules(db, farm.id)
    return SuccessResponse(data=[AutomationRuleResponse.model_validate(r) for r in rules])


@router.patch("/farms/{farm_id}/automation/rules/{rule_id}", response_model=SuccessResponse[AutomationRuleResponse],
              summary="Update automation rule", tags=["Automation"])
async def update_rule(farm_id: str, rule_id: str, body: AutomationRuleUpdate, db: DBSession, current_user: CurrentUser,
                      access: tuple = Depends(require_farm_access(_WRITE)),
                      _p=Depends(require_permission(Permission.AUTOMATION_MANAGE))):
    farm, _ = access
    rule = await automation_service.update_rule(db, farm.id, UUID(rule_id), body)
    return SuccessResponse(data=AutomationRuleResponse.model_validate(rule))


@router.delete("/farms/{farm_id}/automation/rules/{rule_id}", response_model=SuccessResponse[dict],
               summary="Delete automation rule", tags=["Automation"])
async def delete_rule(farm_id: str, rule_id: str, db: DBSession, current_user: CurrentUser,
                      access: tuple = Depends(require_farm_access(_WRITE)),
                      _p=Depends(require_permission(Permission.AUTOMATION_MANAGE))):
    farm, _ = access
    await automation_service.delete_rule(db, farm.id, UUID(rule_id))
    return SuccessResponse(data={"deleted": True})


# ── Reminders ─────────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/automation/reminders", response_model=SuccessResponse[ReminderResponse],
             status_code=status.HTTP_201_CREATED, summary="Create reminder", tags=["Automation"])
async def create_reminder(farm_id: str, body: ReminderCreate, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.AUTOMATION_VIEW))):
    farm, _ = access
    rem = await automation_service.create_reminder(db, farm, body, current_user)
    return SuccessResponse(data=ReminderResponse.model_validate(rem))


@router.get("/farms/{farm_id}/automation/reminders", response_model=SuccessResponse[list[ReminderResponse]],
            summary="List reminders", tags=["Automation"])
async def list_reminders(farm_id: str, db: DBSession, current_user: CurrentUser,
                         access: tuple = Depends(require_farm_access()),
                         _p=Depends(require_permission(Permission.AUTOMATION_VIEW)),
                         include_done: bool = Query(default=False)):
    farm, _ = access
    rems = await automation_service.list_reminders(db, farm.id, include_done)
    return SuccessResponse(data=[ReminderResponse.model_validate(r) for r in rems])


@router.patch("/farms/{farm_id}/automation/reminders/{reminder_id}", response_model=SuccessResponse[ReminderResponse],
              summary="Update / complete reminder", tags=["Automation"])
async def update_reminder(farm_id: str, reminder_id: str, body: ReminderUpdate, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.AUTOMATION_VIEW))):
    farm, _ = access
    rem = await automation_service.update_reminder(db, farm.id, UUID(reminder_id), body)
    return SuccessResponse(data=ReminderResponse.model_validate(rem))


@router.delete("/farms/{farm_id}/automation/reminders/{reminder_id}", response_model=SuccessResponse[dict],
               summary="Delete reminder", tags=["Automation"])
async def delete_reminder(farm_id: str, reminder_id: str, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.AUTOMATION_VIEW))):
    farm, _ = access
    await automation_service.delete_reminder(db, farm.id, UUID(reminder_id))
    return SuccessResponse(data={"deleted": True})


# ── Engine ────────────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/automation/run", response_model=SuccessResponse[EngineRunResult],
             summary="Run the automation engine (triggers + reminders + rules)", tags=["Automation"])
async def run_engine(farm_id: str, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access(_WRITE)),
                     _p=Depends(require_permission(Permission.AUTOMATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=await automation_service.run_engine(db, farm, current_user))


@router.get("/farms/{farm_id}/automation/triggers", response_model=SuccessResponse[list[str]],
            summary="List available trigger types", tags=["Automation"])
async def list_triggers(farm_id: str, db: DBSession, current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access()),
                        _p=Depends(require_permission(Permission.AUTOMATION_VIEW))):
    return SuccessResponse(data=list(TRIGGER_TYPES))


# ── Activity Center ───────────────────────────────────────────────────────────

@router.get("/farms/{farm_id}/automation/activity", response_model=SuccessResponse[list[ActivityNotification]],
            summary="Activity Center (unread/read/archived, search, priority)", tags=["Automation"])
async def activity(farm_id: str, db: DBSession, current_user: CurrentUser,
                   access: tuple = Depends(require_farm_access()),
                   _p=Depends(require_permission(Permission.AUTOMATION_VIEW)),
                   status_filter: str = Query(default="all", alias="status"),
                   q: str | None = Query(default=None), priority: str | None = Query(default=None),
                   limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    farm, _ = access
    rows = await automation_service.list_activity(db, farm.id, current_user.id, status_filter, q, priority, limit, offset)
    return SuccessResponse(data=[ActivityNotification.model_validate(n) for n in rows])


@router.post("/farms/{farm_id}/automation/activity/{notif_id}/archive", response_model=SuccessResponse[ActivityNotification],
             summary="Archive / unarchive a notification", tags=["Automation"])
async def archive(farm_id: str, notif_id: str, db: DBSession, current_user: CurrentUser,
                  access: tuple = Depends(require_farm_access()),
                  _p=Depends(require_permission(Permission.AUTOMATION_VIEW)),
                  archived: bool = Query(default=True)):
    farm, _ = access
    n = await automation_service.archive_notification(db, farm.id, current_user.id, UUID(notif_id), archived)
    return SuccessResponse(data=ActivityNotification.model_validate(n))
