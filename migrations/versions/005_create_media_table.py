"""create media table

Revision ID: 005
Revises: 004
Create Date: 2026-03-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("entity_type", sa.String(50), nullable=False, server_default=""),
        sa.Column("original_url", sa.Text, nullable=False),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("processed_url", sa.Text, nullable=True),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_media_entity", "media", ["entity_type", "entity_id"])
    op.create_index("ix_media_owner", "media", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_media_owner", table_name="media")
    op.drop_index("ix_media_entity", table_name="media")
    op.drop_table("media")
