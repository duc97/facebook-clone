from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from fb.infrastructure.database.base import Base


class ProfileModel(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        insert_default=uuid.uuid4,
        init=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    bio: Mapped[str] = mapped_column(
        Text,
        insert_default="",
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        init=False,
        default=None,
    )
    cover_photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        init=False,
        default=None,
    )
    location: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        init=False,
        default=None,
    )
    website: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        init=False,
        default=None,
    )
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        init=False,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        init=False,
    )
