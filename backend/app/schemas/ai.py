"""
Greena — AI / ARIA Pydantic Schemas
Covers Migrations 023–027:
  AIConversation   (023)
  AIMessage        (024)
  AIInsight        (025)
  AIRecommendation (026)
  AIUsageLog       (027)

Input schemas:
  ARIAMessageCreate     — user sends a message to ARIA
  InsightDismiss        — user dismisses an insight (no body needed, action only)
  RecommendationAction  — user acts on or dismisses a recommendation

Output schemas:
  AIConversationSummary   — for list view (no messages)
  AIConversationDetail    — full conversation with messages
  AIMessageResponse       — single message (user or assistant)
  AIInsightResponse       — single insight card
  AIInsightListResponse
  AIRecommendationResponse
  AIRecommendationListResponse
  AIUsageResponse         — quota status for the current user/farm
  ARIAResponse            — wrapper for a single ARIA reply
"""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from app.schemas.base import AGRIOSSchema


# ── Message / Conversation Input ──────────────────────────────────────────────

class ARIAMessageCreate(AGRIOSSchema):
    """
    Body for POST /farms/{farm_id}/aria/chat
    User sends a message; optionally scopes to a conversation or flock.
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The farmer's question or message to ARIA.",
    )
    # If omitted, a new conversation is created automatically.
    conversation_id: Optional[uuid.UUID] = Field(
        None,
        description="Continue an existing conversation. Omit to start a new one.",
    )
    # Optional flock scope — narrows Farm Context Package
    flock_id: Optional[uuid.UUID] = Field(
        None,
        description="Scope context to a specific flock.",
    )

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message content cannot be blank.")
        return v.strip()


# ── Insight Input ─────────────────────────────────────────────────────────────

class InsightDismiss(AGRIOSSchema):
    """Body for PATCH /farms/{farm_id}/aria/insights/{insight_id}/dismiss"""
    # No fields — the action is the dismiss itself.
    # Kept as a schema for consistency with the Greena pattern.
    pass


# ── Recommendation Input ──────────────────────────────────────────────────────

class RecommendationAction(AGRIOSSchema):
    """Body for PATCH /farms/{farm_id}/aria/recommendations/{rec_id}/action"""

    action: Literal["acted", "dismissed"] = Field(
        ...,
        description="'acted': farmer performed the recommended action. 'dismissed': farmer dismissed it.",
    )


# ── Message Response ──────────────────────────────────────────────────────────

class AIMessageResponse(AGRIOSSchema):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str  # "user" | "assistant"
    content: str
    language: str
    provider: Optional[str] = None  # null for user messages
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: datetime


# ── Conversation Response ─────────────────────────────────────────────────────

class AIConversationSummary(AGRIOSSchema):
    """Condensed view for conversation list."""
    id: uuid.UUID
    farm_id: uuid.UUID
    flock_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    message_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AIConversationDetail(AGRIOSSchema):
    """Full conversation with message history."""
    id: uuid.UUID
    farm_id: uuid.UUID
    flock_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    message_count: int
    is_active: bool
    messages: list[AIMessageResponse]
    created_at: datetime
    updated_at: datetime


# ── ARIA Response ─────────────────────────────────────────────────────────────

class ARIAResponse(AGRIOSSchema):
    """
    Wrapper returned from POST /farms/{farm_id}/aria/chat.
    Contains both the assistant message and the updated conversation.
    """

    conversation_id: uuid.UUID
    # The assistant's reply message
    message: AIMessageResponse
    # Remaining quota for this month (None = unlimited)
    quota_remaining: Optional[int] = None
    # Whether the fallback provider was used
    used_fallback: bool = False


# ── Insight Response ──────────────────────────────────────────────────────────

class AIInsightResponse(AGRIOSSchema):
    id: uuid.UUID
    farm_id: uuid.UUID
    flock_id: Optional[uuid.UUID] = None
    insight_type: str
    severity: str  # "info" | "warning" | "alert" | "reminder"
    title: str
    body: str
    action_route: Optional[str] = None
    action_label: Optional[str] = None
    is_dismissed: bool
    dismissed_at: Optional[datetime] = None
    generated_at: datetime
    expires_at: Optional[datetime] = None
    created_at: datetime


class AIInsightListResponse(AGRIOSSchema):
    items: list[AIInsightResponse]
    total: int
    # Counts by severity for badge rendering
    alert_count: int
    warning_count: int
    info_count: int
    reminder_count: int


# ── Recommendation Response ───────────────────────────────────────────────────

class AIRecommendationResponse(AGRIOSSchema):
    id: uuid.UUID
    farm_id: uuid.UUID
    flock_id: Optional[uuid.UUID] = None
    recommendation_type: str
    title: str
    body: str
    action_label: Optional[str] = None
    action_route: Optional[str] = None
    status: str  # "pending" | "acted" | "dismissed" | "expired"
    acted_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AIRecommendationListResponse(AGRIOSSchema):
    items: list[AIRecommendationResponse]
    total: int
    pending_count: int


# ── Usage / Quota Response ────────────────────────────────────────────────────

class AIUsageResponse(AGRIOSSchema):
    """
    Quota status for the current farm's subscription plan.
    Shown in the ARIA settings screen (AI-04).
    """

    plan_name: str
    # Monthly query limit (None = unlimited for Pro)
    monthly_limit: Optional[int]
    # Queries used this calendar month
    queries_used_this_month: int
    # None if unlimited
    queries_remaining: Optional[int]
    # Cost this month in USD (for admin display; hidden from farmers in UI)
    cost_usd_this_month: float
    # Total all-time queries
    total_queries_all_time: int


# ── Admin Usage Log Response (admin dashboard) ────────────────────────────────

class AIUsageLogEntry(AGRIOSSchema):
    id: uuid.UUID
    farm_id: uuid.UUID
    provider: str
    model: str
    total_tokens: int
    cost_usd: float
    duration_ms: Optional[int]
    success: bool
    call_type: str
    created_at: datetime
