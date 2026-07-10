"""
Greena — SQLAlchemy Base Model
All models inherit from AGRIOSBase which provides:
  - UUID primary key (v4)
  - created_at / updated_at timestamps
  - deleted_at for soft deletes (Engineering Constitution: no hard deletes in production)
  - metadata JSONB for future extensibility
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AGRIOSBase(Base):
    """
    Abstract base for all Greena models.
    Provides: UUID PK, timestamps, soft delete, JSONB metadata.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )

    def soft_delete(self) -> None:
        """Mark this record as deleted. Never call session.delete() on Greena models."""
        self.deleted_at = datetime.utcnow()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
