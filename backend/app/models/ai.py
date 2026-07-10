"""
Greena — AI / ARIA Models
Covers Migrations 023–027:
  AIConversation   (023)
  AIMessage        (024)
  AIInsight        (025)
  AIRecommendation (026)
  AIUsageLog       (027)

Engineering Constitution constraints:
  AR-01: Farm Context Package compiled server-side (service layer)
  AR-02: 8,000 token context cap (service layer)
  DB-07 analogue: ai_usage_log is append-only — no update/delete methods
  DB-08: AIUsageLog has no soft_delete and no is_deleted — it is immutable
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase
from app.database import Base


# ── Enum type references ──────────────────────────────────────────────────────
# These match the PostgreSQL ENUMs created in migrations 024 and 025.

MessageRoleEnum = SAEnum(
    "user", "assistant",
    name="message_role",
    create_constraint=True,
)

AIProviderEnum = SAEnum(
    "gemini", "claude",
    name="ai_provider",
    create_constraint=True,
)

InsightSeverityEnum = SAEnum(
    "info", "warning", "alert", "reminder",
    name="insight_severity",
    create_constraint=True,
)

RecommendationStatusEnum = SAEnum(
    "pending", "acted", "dismissed", "expired",
    name="recommendation_status",
    create_constraint=True,
)


# ── AIConversation ────────────────────────────────────────────────────────────

class AIConversation(AGRIOSBase):
    """
    A conversation thread between a farmer and ARIA.
    Farm-scoped and user-scoped; optionally flock-scoped for context narrowing.
    Migration 023.
    """

    __tablename__ = "ai_conversations"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    flock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    messages: Mapped[list["AIMessage"]] = relationship(
        "AIMessage",
        back_populates="conversation",
        lazy="select",
        order_by="AIMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<AIConversation id={self.id} farm={self.farm_id} msgs={self.message_count}>"


# ── AIMessage ─────────────────────────────────────────────────────────────────

class AIMessage(AGRIOSBase):
    """
    A single message within a conversation.
    role: "user" | "assistant"
    Messages are effectively immutable after creation.
    Migration 024.
    """

    __tablename__ = "ai_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(MessageRoleEnum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")

    # AI provider info (null for user messages)
    provider: Mapped[str | None] = mapped_column(AIProviderEnum, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    conversation: Mapped["AIConversation"] = relationship(
        "AIConversation",
        back_populates="messages",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<AIMessage id={self.id} role={self.role} conv={self.conversation_id}>"


# ── AIInsight ─────────────────────────────────────────────────────────────────

class AIInsight(AGRIOSBase):
    """
    A proactively generated farm insight from one of the 8 insight types.
    Generated at 06:00 Nairobi time by the background job scheduler.
    Farmers can dismiss insights; they also expire automatically.
    Migration 025.
    """

    __tablename__ = "ai_insights"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    flock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(InsightSeverityEnum, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    action_route: Mapped[str | None] = mapped_column(String(300), nullable=True)
    action_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def dismiss(self) -> None:
        """Dismiss this insight. Sets is_dismissed and dismissed_at."""
        self.is_dismissed = True
        self.dismissed_at = datetime.utcnow()

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<AIInsight id={self.id} type={self.insight_type} severity={self.severity}>"


# ── AIRecommendation ──────────────────────────────────────────────────────────

class AIRecommendation(AGRIOSBase):
    """
    A structured action recommendation.
    Status lifecycle: pending → acted | dismissed | expired.
    Migration 026.
    """

    __tablename__ = "ai_recommendations"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    flock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    action_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_route: Mapped[str | None] = mapped_column(String(300), nullable=True)

    status: Mapped[str] = mapped_column(
        RecommendationStatusEnum,
        nullable=False,
        default="pending",
    )
    acted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def mark_acted(self) -> None:
        self.status = "acted"
        self.acted_at = datetime.utcnow()

    def mark_dismissed(self) -> None:
        self.status = "dismissed"
        self.dismissed_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<AIRecommendation id={self.id} type={self.recommendation_type} status={self.status}>"


# ── AIUsageLog ────────────────────────────────────────────────────────────────

class AIUsageLog(Base):
    """
    Immutable, append-only cost and usage record per AI call.
    Engineering Constitution DB-08: no UPDATE or DELETE.

    Does NOT inherit from AGRIOSBase:
      - No soft delete (immutable by constitution)
      - No metadata JSONB (fixed-schema financial record)
      - No updated_at (immutable after creation)
    """

    __tablename__ = "ai_usage_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    provider: Mapped[str] = mapped_column(AIProviderEnum, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(14, 8), nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    call_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="conversation",
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    @property
    def is_deleted(self) -> bool:
        """AIUsageLog is never deleted — immutable by constitution."""
        return False

    def __repr__(self) -> str:
        return (
            f"<AIUsageLog id={self.id} provider={self.provider} "
            f"tokens={self.total_tokens} cost=${self.cost_usd:.6f}>"
        )
