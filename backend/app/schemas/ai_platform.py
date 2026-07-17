"""
Greena — ARIA AI Platform Schemas (Module 9).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import AGRIOSSchema


class ExplainFactor(AGRIOSSchema):
    factor: str
    impact: str            # e.g. "+18", "high", "-5%"
    detail: Optional[str] = None


class AIForecast(AGRIOSSchema):
    metric: str
    horizon_days: int
    projected_value: str
    unit: str
    confidence: str        # low | medium | high
    factors: list[str] = Field(default_factory=list)
    series: list[dict] = Field(default_factory=list)


class ForecastsResponse(AGRIOSSchema):
    feed: Optional[AIForecast] = None
    financial: Optional[AIForecast] = None
    inventory: Optional[AIForecast] = None
    production: Optional[AIForecast] = None


class MortalityPrediction(AGRIOSSchema):
    scope: str
    predicted_next_7d: int
    recent_7d: int
    trend: str             # rising | stable | falling
    confidence: str
    factors: list[ExplainFactor]
    explanation: str


class DiseaseRisk(AGRIOSSchema):
    score: int             # 0–100
    level: str             # low | moderate | high | critical
    factors: list[ExplainFactor]
    recommendation: str


class AskRequest(AGRIOSSchema):
    question: str = Field(..., min_length=2, max_length=1000)
    conversation_id: UUID | None = None


class AskResponse(AGRIOSSchema):
    answer: str
    provider: str
    cached: bool
    tokens: int
    cost_usd: str
    sources: list[str]
    rate_limit_remaining: int | None = None


class AIDashboard(AGRIOSSchema):
    generated_at: datetime
    providers: dict
    forecasts: ForecastsResponse
    mortality: MortalityPrediction
    disease_risk: DiseaseRisk
    recommendations: list[dict]
    insights: list[dict]
    headline: str


class AIPlatformContext(AGRIOSSchema):
    farm_id: UUID
    generated_at: datetime
    feed: dict
    finance: dict
    inventory: dict
    health: dict
    production: dict
