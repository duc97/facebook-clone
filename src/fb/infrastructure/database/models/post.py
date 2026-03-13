from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from fb.infrastructure.database.base import Base


class PostModel(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, insert_default=uuid.uuid4, init=False)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list] = mapped_column(ARRAY(String(500)), insert_default=list, nullable=False, init=False)
    like_count: Mapped[int] = mapped_column(Integer, insert_default=0, nullable=False, init=False)
    comment_count: Mapped[int] = mapped_column(Integer, insert_default=0, nullable=False, init=False)
    is_published: Mapped[bool] = mapped_column(Boolean, insert_default=True, nullable=False, init=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, init=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, init=False)