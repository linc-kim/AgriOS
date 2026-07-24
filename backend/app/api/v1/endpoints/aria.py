"""
Greena — ARIA / AI Endpoints
Sprint 6: AI module endpoints.

Endpoint groups:
  POST   /farms/{farm_id}/aria/chat                            — Send message to ARIA
  GET    /farms/{farm_id}/aria/conversations                   — List conversations
  GET    /farms/{farm_id}/aria/conversations/{conv_id}         — Get conversation detail
  DELETE /farms/{farm_id}/aria/conversations/{conv_id}         — Delete conversation
  GET    /farms/{farm_id}/aria/insights                        — List insights
  PATCH  /farms/{farm_id}/aria/insights/{insight_id}/dismiss   — Dismiss insight
  GET    /farms/{farm_id}/aria/recommendations                 — List recommendations
  PATCH  /farms/{farm_id}/aria/recommendations/{rec_id}/action — Act/dismiss recommendation
  GET    /farms/{farm_id}/aria/usage                           — Quota + usage status

Permission matrix (Engineering Constitution Section 5):
  AI_QUERY:         farm_owner, farm_manager (send messages)
  AI_INSIGHT_VIEW:  farm_owner, farm_manager, vet_consultant, farm_worker, viewer
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.dependencies import get_current_user, require_farm_access
from app.models.auth import User
from app.schemas.ai import (
    AIConversationDetail,
    AIInsightListResponse,
    AIInsightResponse,
    AIRecommendationListResponse,
    AIRecommendationResponse,
    AIUsageResponse,
    ARIAMessageCreate,
    ARIARecordRequest,
    ARIARecordResponse,
    AIIntelligenceResponse,
    AIBriefing,
    AIAnswerRequest,
    AIAnswerResponse,
    AIKnowledgeAnswer,
    AIDecisionAnswer,
    AIAlert,
    AIMonitor,
    AIPriorityItem,
    AIReport,
    AIReportSection,
    AISupervisorBriefing,
    AISupervisorSnapshot,
    AITimelineEvent,
    ARIAResponse,
    RecommendationAction,
)
from app.schemas.base import SuccessResponse
from app.services import (
    aria_decisions,
    aria_intelligence_data,
    aria_knowledge,
    aria_record_service,
    aria_service,
)
from app.services import aria_intelligence as _intel
from app.services import aria_supervisor, aria_supervisor_data

router = APIRouter(prefix="/farms/{farm_id}", tags=["ARIA"])


# ── Conversation: Send Message ────────────────────────────────────────────────

@router.post(
    "/aria/chat",
    response_model=SuccessResponse[ARIAResponse],
    status_code=status.HTTP_200_OK,
    summary="Send a message to ARIA",
)
async def send_aria_message(
    farm_id: uuid.UUID,
    body: ARIAMessageCreate,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    """
    Send a message to ARIA. Creates or continues a conversation.
    Returns the assistant's reply and updated quota remaining.
    Respects quota limits per subscription plan.
    """
    farm, _ = access
    result = await aria_service.send_message(
        db=db,
        farm=farm,
        current_user=current_user,
        content=body.content,
        conversation_id=body.conversation_id,
        flock_id=body.flock_id,
    )
    return SuccessResponse(data=result)


# ── Conversation: List ────────────────────────────────────────────────────────

@router.get(
    "/aria/conversations",
    response_model=SuccessResponse[list],
    summary="List ARIA conversations for this farm",
)
async def list_conversations(
    farm_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    """List conversations for the current user on this farm, newest first."""
    conversations = await aria_service.list_conversations(
        db=db,
        farm_id=farm_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(data=conversations)


# ── Conversation: Detail ──────────────────────────────────────────────────────

@router.get(
    "/aria/conversations/{conversation_id}",
    response_model=SuccessResponse[AIConversationDetail],
    summary="Get a conversation with full message history",
)
async def get_conversation(
    farm_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    detail = await aria_service.get_conversation_detail(db, farm_id, conversation_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversation not found."},
        )
    return SuccessResponse(data=detail)


# ── Conversation: Delete ──────────────────────────────────────────────────────

@router.delete(
    "/aria/conversations/{conversation_id}",
    response_model=SuccessResponse[dict],
    summary="Delete (soft-delete) a conversation",
)
async def delete_conversation(
    farm_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    deleted = await aria_service.delete_conversation(db, farm_id, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversation not found."},
        )
    return SuccessResponse(data={"deleted": True})


# ── Insights: List ────────────────────────────────────────────────────────────

@router.get(
    "/aria/insights",
    response_model=SuccessResponse[AIInsightListResponse],
    summary="List ARIA insights for this farm",
)
async def list_insights(
    farm_id: uuid.UUID,
    include_dismissed: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    access=Depends(
        require_farm_access({
            "farm_owner", "farm_manager", "enterprise_owner",
            "vet_consultant", "farm_worker", "viewer",
        })
    ),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """
    Returns active, non-expired insights.
    Severity counts included for badge rendering.
    Available to all 6 farm roles (AI_INSIGHT_VIEW covers all except vet_consultant exclusions).
    """
    result = await aria_service.list_insights(
        db=db,
        farm_id=farm_id,
        include_dismissed=include_dismissed,
    )
    return SuccessResponse(data=result)


# ── Insights: Dismiss ─────────────────────────────────────────────────────────

@router.patch(
    "/aria/insights/{insight_id}/dismiss",
    response_model=SuccessResponse[AIInsightResponse],
    summary="Dismiss an insight",
)
async def dismiss_insight(
    farm_id: uuid.UUID,
    insight_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    result = await aria_service.dismiss_insight(db, farm_id, insight_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INSIGHT_NOT_FOUND", "message": "Insight not found."},
        )
    return SuccessResponse(data=result)


# ── Recommendations: List ─────────────────────────────────────────────────────

@router.get(
    "/aria/recommendations",
    response_model=SuccessResponse[AIRecommendationListResponse],
    summary="List ARIA recommendations for this farm",
)
async def list_recommendations(
    farm_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    result = await aria_service.list_recommendations(
        db=db,
        farm_id=farm_id,
        status_filter=status_filter,
    )
    return SuccessResponse(data=result)


# ── Recommendations: Act / Dismiss ───────────────────────────────────────────

@router.patch(
    "/aria/recommendations/{recommendation_id}/action",
    response_model=SuccessResponse[AIRecommendationResponse],
    summary="Act on or dismiss a recommendation",
)
async def action_recommendation(
    farm_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    body: RecommendationAction,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    result = await aria_service.action_recommendation(
        db=db,
        farm_id=farm_id,
        recommendation_id=recommendation_id,
        action=body.action,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RECOMMENDATION_NOT_FOUND",
                "message": "Recommendation not found.",
            },
        )
    return SuccessResponse(data=result)


# ── Usage / Quota ─────────────────────────────────────────────────────────────

@router.get(
    "/aria/usage",
    response_model=SuccessResponse[AIUsageResponse],
    summary="Get ARIA quota and usage status for this farm",
)
async def get_usage(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    """
    Returns monthly query usage, quota remaining, and cost for the current month.
    Used by AI-04 (ARIASettingsScreen) to render the quota progress bar.
    """
    farm, _ = access
    result = await aria_service.get_usage_status(db, farm, current_user.id)
    return SuccessResponse(data=result)


# ── Conversational recording (Module 13) ──────────────────────────────────────

@router.post(
    "/aria/record",
    response_model=SuccessResponse[ARIARecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Record farm data by talking to ARIA",
)
async def record_by_conversation(
    farm_id: uuid.UUID,
    body: ARIARecordRequest,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.OPS_LOG_SUBMIT)),
):
    """
    Take one turn of a recording conversation.

    Fully deterministic — no AI provider is consulted, so this works with no
    Gemini or Claude key configured and counts against no quota. If `handled`
    comes back False the utterance was not a record; send it to `/aria/chat`.

    Gated on OPS_LOG_SUBMIT rather than AI_QUERY, because that is what this
    actually is — submitting an operational log, in words instead of a form. It
    also means farm workers can use it, which matters: recording mortality and
    egg counts is their job, and routing them through a manager to log a dead
    bird is how farms end up with no data at all.
    """
    farm, _ = access
    result = await aria_record_service.handle_turn(
        db=db,
        farm=farm,
        current_user=current_user,
        text=body.text,
        state_raw=body.state,
    )
    return SuccessResponse(
        data=ARIARecordResponse(
            handled=result.handled,
            reply=result.reply,
            stage=result.stage,
            options=result.options,
            state=result.state,
            saved=result.saved,
            summary=result.summary,
            module=result.module,
            resource_id=result.resource_id,
        )
    )



# ── Farm intelligence (Module 13 Part 4) ──────────────────────────────────────
#
# All deterministic. These read what the farm recorded and reason over it — no
# Gemini, no Claude, no quota. They are the operations-manager brain.


def _serialise_intelligence(report: dict) -> AIIntelligenceResponse:
    b = report["briefing"]
    h = report["health"]
    return AIIntelligenceResponse(
        briefing=AIBriefing(
            farm_name=b.farm_name, as_of=b.as_of.isoformat(), greeting=b.greeting,
            lines=b.lines, priorities=b.priorities, health_score=b.health_score, notes=b.notes,
        ),
        health={
            "score": h.score, "max_score": h.max_score, "grade": h.grade,
            "factors": [
                {"key": f.key, "label": f.label, "score": f.score, "max_score": f.max_score,
                 "status": f.status.value, "explanation": f.explanation}
                for f in h.factors
            ],
        },
        insights=[
            {"key": i.key, "title": i.title, "problem": i.problem, "reason": i.reason,
             "action": i.action, "benefit": i.benefit, "confidence": i.confidence,
             "sources": i.sources, "priority": i.priority.value}
            for i in report["insights"]
        ],
        checklist=[
            {"key": c.key, "label": c.label, "done": c.done, "reason": c.reason,
             "priority": c.priority.value}
            for c in report["checklist"]
        ],
        trends=[
            {"metric": t.metric, "direction": t.direction, "change_pct": t.change_pct,
             "explanation": t.explanation, "grounded": t.grounded, "sources": t.sources}
            for t in report["trends"]
        ],
    )


@router.get(
    "/aria/intelligence",
    response_model=SuccessResponse[AIIntelligenceResponse],
    summary="ARIA's full operations view: briefing, checklist, insights, trends, health",
)
async def farm_intelligence(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """
    Everything the operations manager sees, in one deterministic call. Composed
    from the farm's own records via the domain services — never fabricated, and
    honest about anything unavailable.
    """
    farm, _ = access
    report = await aria_intelligence_data.full_report(db, farm, current_user)
    return SuccessResponse(data=_serialise_intelligence(report))


@router.get(
    "/aria/briefing",
    response_model=SuccessResponse[AIBriefing],
    summary="ARIA's daily briefing",
)
async def daily_briefing(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _ = access
    b = await aria_intelligence_data.daily_briefing(db, farm, current_user)
    return SuccessResponse(data=AIBriefing(
        farm_name=b.farm_name, as_of=b.as_of.isoformat(), greeting=b.greeting,
        lines=b.lines, priorities=b.priorities, health_score=b.health_score, notes=b.notes,
    ))


@router.post(
    "/aria/answer",
    response_model=SuccessResponse[AIAnswerResponse],
    summary="Answer a question deterministically — knowledge base or decision support",
)
async def deterministic_answer(
    farm_id: uuid.UUID,
    body: AIAnswerRequest,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """
    Deterministic Q&A: the local poultry knowledge base for husbandry questions,
    and decision support for judgement questions. No Gemini, no Claude. Returns
    type "none" when neither applies, so the client can fall back to its own
    snapshot answers — the honest edge, never a fabricated one.

    Educational only: disease entries carry a see-a-vet boundary and never
    diagnose the farmer's specific birds (§4.4).
    """
    farm, _ = access
    q = body.question

    # Decision questions first — they're more specific than knowledge lookups.
    facts = await aria_intelligence_data.gather_facts(db, farm, current_user)
    decision = aria_decisions.decide(q, facts)
    if decision is not None:
        return SuccessResponse(data=AIAnswerResponse(
            type="decision",
            decision=AIDecisionAnswer(
                question=decision.question, lean=decision.lean, headline=decision.headline,
                pros=decision.pros, cons=decision.cons, assumptions=decision.assumptions,
                risks=decision.risks, missing=decision.missing, sources=decision.sources,
            ),
        ))

    knowledge = aria_knowledge.answer(q)
    if knowledge is not None:
        return SuccessResponse(data=AIAnswerResponse(
            type="knowledge", knowledge=AIKnowledgeAnswer(**knowledge),
        ))

    return SuccessResponse(data=AIAnswerResponse(type="none"))



# ── Supervisor (Module 13 Part 5) ─────────────────────────────────────────────
#
# ARIA watching the farm rather than waiting to be asked. Every endpoint here is
# deterministic: monitors, alerts, ranking and reports are pure functions of
# recorded data. No AI provider is reachable from any of them.

_READ_ROLES = {"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer", "enterprise_owner"}


def _section(s) -> AIReportSection:
    return AIReportSection(label=s.label, value=s.value, available=s.available)


def _briefing(b) -> AISupervisorBriefing:
    return AISupervisorBriefing(
        farm_name=b.farm_name, as_of=b.as_of.isoformat(), greeting=b.greeting,
        overall=b.overall.value, health_score=b.health_score,
        sections=[_section(s) for s in b.sections],
        priorities=b.priorities, suggested_actions=b.suggested_actions, notes=b.notes,
    )


def _alert(a) -> AIAlert:
    return AIAlert(
        key=a.key, severity=a.severity.value, title=a.title, reason=a.reason,
        evidence=a.evidence, action=a.action, monitor=a.monitor,
        raised_at=a.raised_at.isoformat(),
    )


@router.get(
    "/aria/supervisor",
    response_model=SuccessResponse[AISupervisorSnapshot],
    summary="ARIA's full supervisor view: briefing, monitors, alerts, priorities",
)
async def supervisor_snapshot(
    farm_id: uuid.UUID,
    sync: bool = Query(False, description="Also persist alerts as notifications and create auto-reminders."),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """
    One deterministic supervision pass.

    Read-only by default so refreshing a dashboard never has side effects; pass
    `sync=true` to also write notifications and auto-reminders, which is
    idempotent — running it twice creates nothing the second time.
    """
    farm, _ = access
    r = await aria_supervisor_data.supervise(db, farm, current_user, sync=sync)
    return SuccessResponse(data=AISupervisorSnapshot(
        briefing=_briefing(r["briefing"]),
        overall=aria_supervisor.overall_state(r["monitors"]).value,
        health_score=r["health"].score,
        monitors=[
            AIMonitor(key=m.key, label=m.label, state=m.state.value, why=m.why,
                      evidence=m.evidence, unmeasured=m.unmeasured)
            for m in r["monitors"]
        ],
        alerts=[_alert(a) for a in r["alerts"]],
        priorities=[
            AIPriorityItem(key=p.key, rank=p.rank, label=p.label, why=p.why,
                           source=p.source, severity=p.severity.value)
            for p in r["priorities"]
        ],
    ))


@router.get(
    "/aria/alerts",
    response_model=SuccessResponse[list[AIAlert]],
    summary="Current farm alerts",
)
async def farm_alerts(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """Alerts for thresholds that are actually crossed — never general advice."""
    farm, _ = access
    r = await aria_supervisor_data.supervise(db, farm, current_user)
    return SuccessResponse(data=[_alert(a) for a in r["alerts"]])


@router.get(
    "/aria/priorities",
    response_model=SuccessResponse[list[AIPriorityItem]],
    summary="What needs attention, ranked",
)
async def farm_priorities(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _ = access
    r = await aria_supervisor_data.supervise(db, farm, current_user)
    return SuccessResponse(data=[
        AIPriorityItem(key=p.key, rank=p.rank, label=p.label, why=p.why,
                       source=p.source, severity=p.severity.value)
        for p in r["priorities"]
    ])


@router.get(
    "/aria/timeline",
    response_model=SuccessResponse[list[AITimelineEvent]],
    summary="Chronological farm activity",
)
async def farm_timeline(
    farm_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """Built from recorded rows only — never a reconstruction."""
    farm, _ = access
    events = await aria_supervisor_data.gather_timeline(db, farm, days=days, limit=limit)
    return SuccessResponse(data=[
        AITimelineEvent(at=e.at.isoformat(), kind=e.kind, title=e.title, detail=e.detail)
        for e in events
    ])


@router.get(
    "/aria/reports",
    response_model=SuccessResponse[AIReport],
    summary="Deterministic operational report",
)
async def farm_report(
    farm_id: uuid.UUID,
    period: str = Query("7d", pattern="^(today|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """Any line ARIA cannot compute from records is returned as unavailable."""
    farm, _ = access
    facts = await aria_supervisor_data.gather_facts_for_report(db, farm, current_user)
    report = aria_supervisor.build_report(facts, period)
    return SuccessResponse(data=AIReport(
        period=report.period, label=report.label,
        sections=[_section(s) for s in report.sections], notes=report.notes,
    ))
