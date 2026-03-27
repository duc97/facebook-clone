"""add user_name, first_name, last_name to users; create follows table

Revision ID: 007
Revises: 006
Create Date: 2026-03-27

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Add new columns to users table ──
    op.add_column(
        "users",
        sa.Column("user_name", sa.String(50), nullable=True, unique=True),
    )
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(50), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(50), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("date_of_birth", sa.Date, nullable=True),
    )

    # Backfill user_name from display_name (slug: lowercase, replace spaces with _)
    op.execute(
        """
        UPDATE users
        SET user_name = LOWER(REPLACE(display_name, ' ', '_')) || '_' || LEFT(id::text, 8),
            first_name = SPLIT_PART(display_name, ' ', 1),
            last_name = CASE
                WHEN POSITION(' ' IN display_name) > 0
                THEN SUBSTRING(display_name FROM POSITION(' ' IN display_name) + 1)
                ELSE ''
            END
        WHERE user_name IS NULL
        """
    )

    # Now make user_name NOT NULL
    op.alter_column("users", "user_name", nullable=False)
    op.alter_column("users", "first_name", nullable=False)
    op.alter_column("users", "last_name", nullable=False)

    op.create_index("ix_users_user_name", "users", ["user_name"], unique=True)

    # ── Create follows table (unidirectional follow model) ──
    op.create_table(
        "follows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "follower_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "following_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("follower_id", "following_id", name="uq_follow_pair"),
    )
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"])
    op.create_index("ix_follows_following_id", "follows", ["following_id"])


def downgrade() -> None:
    op.drop_index("ix_follows_following_id")
    op.drop_index("ix_follows_follower_id")
    op.drop_table("follows")
    op.drop_index("ix_users_user_name")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "user_name")
