"""
Greena — AI Assistant endpoints (Module 13 Part 8).

The final ARIA surface: the router (made transparent), the multimodal assistant
(text, transcribed voice, images, documents), retrieval over uploaded documents,
and the AI settings + cost dashboard.

Every route is deterministic-first. The assistant consults Gemini only when the
router says a deterministic engine cannot answer, and degrades to a grounded
offline reply when no provider is configured — so the whole surface works with no
API key at all.

Permissions are deliberately conservative (capability 14 — never bypass
permissions): the assistant and uploads require AI_QUERY (owner/manager), because
the record path can write farm data and vision/documents can incur model cost.
Workers keep their dedicated deterministic recording endpoint (`/aria/record`).
Reads (settings, usage, documents) require AI_INSIGHT_VIEW.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.dependencies import require_farm_access
from app.models.auth import User
from app.schemas.ai_assistant import (
    AISettingsOut,
    AISettingsUpdate,
    AIUsageOut,
    AssistRequest,
    AssistResponse,
    CitationOut,
    DocumentIngestOut,
    DocumentOut,
    RetrievalOut,
    RouteDecisionOut,
    RouteRequest,
)
from app.schemas.base import SuccessResponse
from app.services import ai_provider, ai_settings_service, aria_assistant_service, aria_router
from app.exceptions import ValidationException

router = APIRouter(prefix="/farms/{farm_id}", tags=["ARIA Assistant"])

_WRITE_ROLES = {"farm_owner", "farm_manager", "enterprise_owner"}
_READ_ROLES = {"farm_owner", "farm_manager", "enterprise_owner", "vet_consultant", "viewer"}

# Uploads are capped so a request can't exhaust memory.
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024


# ── 1. Router (transparent) ───────────────────────────────────────────────────


@router.post("/aria/route", response_model=SuccessResponse[RouteDecisionOut],
             summary="Explain how a request would be routed (deterministic vs Gemini)")
async def route_request(
    farm_id: uuid.UUID,
    body: RouteRequest,
    access=Depends(require_farm_access(_READ_ROLES)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    attachments = [aria_router.Attachment(a.filename, a.mime, a.size_bytes) for a in body.attachments]
    d = aria_router.route(body.text, attachments=attachments)
    return SuccessResponse(data=RouteDecisionOut(
        target=d.target.value, engine=d.engine.value, modality=d.modality.value,
        needs_gemini=d.needs_gemini, deterministic_first=d.deterministic_first,
        reason=d.reason, language=d.language.primary.value,
        mixed_language=d.language.mixed, safety=[s.value for s in d.safety],
        confidence=d.confidence,
    ))


# ── Assistant (text / transcribed voice) ──────────────────────────────────────


@router.post("/aria/assistant", response_model=SuccessResponse[AssistResponse],
             summary="Ask ARIA anything — routed deterministic-first")
async def assistant(
    farm_id: uuid.UUID,
    body: AssistRequest,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    settings = await ai_settings_service.get_or_create(db, farm.id)
    result = await aria_assistant_service.assist(
        db, farm, current_user, body.text, settings=settings, state=body.state,
    )
    return SuccessResponse(data=_assist_out(result))


# ── Image (capability 5, 11) ──────────────────────────────────────────────────


@router.post("/aria/assistant/image", response_model=SuccessResponse[AssistResponse],
             summary="Upload an image for ARIA to analyse (Gemini Vision)")
async def assistant_image(
    farm_id: uuid.UUID,
    file: UploadFile = File(...),
    caption: str = Form(""),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    data = await _read_capped(file)
    settings = await ai_settings_service.get_or_create(db, farm.id)
    result = await aria_assistant_service.analyze_image_upload(
        db, farm, current_user, filename=file.filename or "image",
        mime=file.content_type or "image/jpeg", data=data, caption=caption, settings=settings,
    )
    return SuccessResponse(data=_assist_out(result))


# ── Documents (capability 6, 7, 11) ───────────────────────────────────────────


@router.post("/aria/assistant/document", response_model=SuccessResponse[DocumentIngestOut],
             summary="Upload a document for extraction + retrieval")
async def assistant_document(
    farm_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    data = await _read_capped(file)
    settings = await ai_settings_service.get_or_create(db, farm.id)
    result = await aria_assistant_service.ingest_document(
        db, farm, current_user, filename=file.filename or "document",
        mime=file.content_type or "", data=data, settings=settings,
    )
    return SuccessResponse(data=DocumentIngestOut(**result))


@router.get("/aria/documents", response_model=SuccessResponse[list[DocumentOut]],
            summary="List uploaded documents")
async def list_documents(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    docs = await aria_assistant_service.list_documents(db, farm)
    return SuccessResponse(data=[
        DocumentOut(id=str(d.id), filename=d.filename, kind=d.kind,
                    table_count=d.table_count, size_bytes=d.size_bytes,
                    created_at=d.created_at.isoformat())
        for d in docs
    ])


@router.get("/aria/documents/search", response_model=SuccessResponse[RetrievalOut],
            summary="Search uploaded documents — cited, never invented")
async def search_documents(
    farm_id: uuid.UUID,
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    cites = await aria_assistant_service.search_documents(db, farm, q)
    return SuccessResponse(data=RetrievalOut(
        query=q,
        citations=[CitationOut(doc_id=c.doc_id, filename=c.filename,
                               snippet=c.snippet, score=c.score) for c in cites],
    ))


# ── Settings + usage (capability 13) ──────────────────────────────────────────


@router.get("/aria/settings", response_model=SuccessResponse[AISettingsOut],
            summary="Get AI settings for this farm")
async def get_settings(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    s = await ai_settings_service.get_or_create(db, farm.id)
    return SuccessResponse(data=_settings_out(s))


@router.put("/aria/settings", response_model=SuccessResponse[AISettingsOut],
            summary="Update AI settings")
async def update_settings(
    farm_id: uuid.UUID,
    body: AISettingsUpdate,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE_ROLES)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    try:
        s = await ai_settings_service.update(db, farm.id, body.model_dump(exclude_none=True), current_user.id)
    except ValueError as e:
        raise ValidationException(str(e))
    return SuccessResponse(data=_settings_out(s))


@router.get("/aria/settings/usage", response_model=SuccessResponse[AIUsageOut],
            summary="AI usage and cost dashboard")
async def usage_dashboard(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ_ROLES)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    s = await ai_settings_service.get_or_create(db, farm.id)
    summary = await ai_settings_service.usage_summary(db, farm.id)
    return SuccessResponse(data=AIUsageOut(
        total=summary["total"], this_month=summary["this_month"],
        by_provider=summary["by_provider"],
        monthly_budget_usd=float(s.monthly_budget_usd) if s.monthly_budget_usd is not None else None,
    ))


# ── Serialisers / helpers ─────────────────────────────────────────────────────


def _assist_out(r) -> AssistResponse:
    return AssistResponse(
        handled=r.handled, route=r.route, engine=r.engine, provider=r.provider,
        answer=r.answer, language=r.language, mixed_language=r.mixed_language,
        safety=r.safety, sources=r.sources, needs_confirmation=r.needs_confirmation, data=r.data,
    )


def _settings_out(s) -> AISettingsOut:
    return AISettingsOut(
        farm_id=str(s.farm_id), ai_enabled=s.ai_enabled, model=s.model,
        temperature=float(s.temperature), max_output_tokens=s.max_output_tokens,
        allow_vision=s.allow_vision, allow_documents=s.allow_documents,
        monthly_budget_usd=float(s.monthly_budget_usd) if s.monthly_budget_usd is not None else None,
        providers=ai_provider.providers_available(),
    )


async def _read_capped(file: UploadFile) -> bytes:
    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(data) > _MAX_UPLOAD_BYTES:
        raise ValidationException("File too large — 8 MB maximum.")
    return data
