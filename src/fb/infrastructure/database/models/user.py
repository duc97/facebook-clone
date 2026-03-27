from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from fb.infrastructure.database.base import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        insert_default=uuid.uuid4,
        init=False,
    )
    user_name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    last_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        default=None,
        init=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        insert_default=True,
        nullable=False,
        init=False,
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
