"""add performance indexes for feed, notifications, messages, reactions, shares

Revision ID: 006
Revises: 005
Create Date: 2026-03-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # posts: composite index for feed query (is_published + author_id + created_at)
    # Performance: supports get_feed_post_ids WHERE is_published AND author_id IN (...)
    # ORDER BY created_at DESC — enables Index Scan instead of Seq Scan.
    op.create_index(
        "ix_posts_published_author_created",
        "posts",
        ["is_published", "author_id", "created_at"],
    )

    # posts: composite index for global timeline (is_published + created_at)
    # Performance: supports public feed / explore queries filtering by published status
    # and ordering by creation time.
    op.create_index(
        "ix_posts_published_created",
        "posts",
        ["is_published", "created_at"],
    )

    # friendships: (user_id, friend_id) composite for bidirectional lookups.
    # Note: a unique constraint on (user_id, friend_id) already exists in migration 002
    # (uq_friendship_user_friend), which implicitly creates a unique index.
    # The ix_friendship_user_id single-column index also exists from migration 002.
    # This composite speeds up WHERE user_id = X AND friend_id = Y checks that bypass
    # the unique-constraint path.  Using if_not_exists=True for safety.
    op.create_index(
        "ix_friendships_user_friend",
        "friendships",
        ["user_id", "friend_id"],
        unique=False,
        if_not_exists=True,
    )

    # notifications: composite for unread-count + list queries
    # Performance: uses ix_notifications_user_read_created (migration 006).
    # Covers: WHERE user_id = X AND is_read = false ORDER BY created_at DESC
    op.create_index(
        "ix_notifications_user_read_created",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )

    # messages: composite for unread-count query per receiver
    # Performance: supports get_unread_count WHERE receiver_id = X AND is_seen = false
    op.create_index(
        "ix_messages_receiver_seen",
        "messages",
        ["receiver_id", "is_seen"],
    )

    # reactions: index on post_id for reaction-count queries
    op.create_index(
        "ix_reactions_post_id",
        "reactions",
        ["post_id"],
    )

    # shares: index on post_id for share-count queries
    op.create_index(
        "ix_shares_post_id",
        "shares",
        ["post_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_shares_post_id", table_name="shares")
    op.drop_index("ix_reactions_post_id", table_name="reactions")
    op.drop_index("ix_messages_receiver_seen", table_name="messages")
    op.drop_index("ix_notifications_user_read_created", table_name="notifications")
    op.drop_index("ix_friendships_user_friend", table_name="friendships", if_exists=True)
    op.drop_index("ix_posts_published_created", table_name="posts")
    op.drop_index("ix_posts_published_author_created", table_name="posts")
