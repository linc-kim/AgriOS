"""
Greena — AI assistant schemas (Module 13 Part 8).

Wire shapes for the multimodal assistant: the router decision (capability 1, made
transparent), the unified assistant reply, AI settings, the usage/cost dashboard,
document ingestion and cited retrieval.
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.base import AGRIOSSchema


# ── Router (capability 1) ─────────────────────────────────────────────────────


class RouteAttachment(AGRIOSSchema):
    filename: str
    mime: str = ""
    size_bytes: int = 0


class RouteRequest(AGRIOSSchema):
    text: str = ""
    attachments: list[RouteAttachment] = Field(default_factory=list)


class RouteDecisionOut(AGRIOSSchema):
    target: str
    engine: str
    modality: str
    needs_gemini: bool
    deterministic_first: bool
    reason: str
    language: str
    mixed_language: bool
    safety: list[str]
    confidence: float


# ── Assistant ─────────────────────────────────────────────────────────────────


class AssistRequest(AGRIOSSchema):
    text: str = ""
    #: In-flight recording dialogue state (from a previous turn), if continuing.
    state: dict | None = None


class AssistResponse(AGRIOSSchema):
    handled: bool
    route: str
    engine: str
    provider: str
    answer: str
    language: str
    mixed_language: bool
    safety: list[str]
    sources: list[str]
    needs_confirmation: bool
    data: dict


# ── Settings (capability 13) ──────────────────────────────────────────────────


class AISettingsOut(AGRIOSSchema):
    farm_id: str
    ai_enabled: bool
    model: str
    temperature: float
    max_output_tokens: int
    allow_vision: bool
    allow_documents: bool
    monthly_budget_usd: float | None
    providers: dict


class AISettingsUpdate(AGRIOSSchema):
    ai_enabled: bool | None = None
    model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    allow_vision: bool | None = None
    allow_documents: bool | None = None
    monthly_budget_usd: float | None = None


class UsageBucket(AGRIOSSchema):
    tokens: int
    cost_usd: float
    calls: int


class ProviderUsage(AGRIOSSchema):
    provider: str
    calls: int
    cost_usd: float
    tokens: int


class AIUsageOut(AGRIOSSchema):
    total: UsageBucket
    this_month: UsageBucket
    by_provider: list[ProviderUsage]
    monthly_budget_usd: float | None


# ── Documents (capability 6, 7, 11) ───────────────────────────────────────────


class DocumentTable(AGRIOSSchema):
    kind: str
    headers: list[str]
    row_count: int
    preview: list[list[str]]


class DocumentIngestOut(AGRIOSSchema):
    stored: bool
    document_id: str | None = None
    filename: str | None = None
    kind: str | None = None
    deterministic: bool | None = None
    table_count: int | None = None
    tables: list[DocumentTable] = Field(default_factory=list)
    note: str = ""
    reason: str = ""


class DocumentOut(AGRIOSSchema):
    id: str
    filename: str
    kind: str
    table_count: int
    size_bytes: int
    created_at: str


class CitationOut(AGRIOSSchema):
    doc_id: str
    filename: str
    snippet: str
    score: float


class RetrievalOut(AGRIOSSchema):
    query: str
    citations: list[CitationOut]
