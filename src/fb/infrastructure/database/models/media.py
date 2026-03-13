from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from fb.infrastructure.database.base import Base


class MediaModel(Base):
    __tablename__ = "media"
    __table_args__ = (
        Index("ix_media_entity", "entity_type", "entity_id"),
        Index("ix_media_owner", "owner_id"),
    )

    # Required fields first (no default) — MappedAsDataclass ordering rule.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)  # image/video/file
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    # Optional fields with defaults.
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    processed_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    # Server-managed fields (init=False) must come after all user-init fields.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, insert_default=uuid.uuid4, init=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", init=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, init=False
    )
