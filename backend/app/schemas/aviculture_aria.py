"""
Greena — Aviculture ARIA Schemas (Module 15, Part 10)

Contracts for the aviculture assistant. Every answer is honesty-labelled: the
``provider`` distinguishes a deterministic answer from an AI explanation, and
``fact_type`` marks whether the content is a recorded fact, a calculation, an AI
suggestion, or unavailable. ARIA explains; it never calculates or diagnoses.
"""

from uuid import UUID

from pydantic import Field

from app.schemas.base import AGRIOSSchema


class AskRequest(AGRIOSSchema):
    question: str = Field(..., min_length=2, max_length=1000)


class AskResponse(AGRIOSSchema):
    provider: str        # deterministic | gemini | claude | offline
    engine: str          # deterministic | ai_router
    fact_type: str       # recorded_fact | calculated | ai_suggestion | unavailable
    answer: str
    sources: list[str] = Field(default_factory=list)
    safety: list[str] = Field(default_factory=list)   # e.g. ["no_diagnosis"]
    confidence: str
    ai_enabled: bool


class ContextResponse(AGRIOSSchema):
    context: dict


class SpeciesKnowledgeResponse(AGRIOSSchema):
    species: str
    scientific_name: str | None
    group: str
    conservation_status: str | None
    profile: dict
    label: str
    detail: str
    disclaimer: str


class SpeciesKnowledgeRequest(AGRIOSSchema):
    species_id: UUID
