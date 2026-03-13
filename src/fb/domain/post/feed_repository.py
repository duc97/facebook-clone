from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.post.entities import Post
from fb.domain.shared.entity_id import EntityId
from fb.domain.shared.pagination import CursorPage


@runtime_checkable
class FeedRepository(Protocol):
    """Protocol for feed-related data operations."""

    async def get_feed_post_ids(
        self, user_id: EntityId, friend_ids: list[EntityId], limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        """Get post IDs for user's feed (user + friends posts)."""
        ...

    async def get_feed_posts(
        self, post_ids: list[EntityId]
    ) -> list[Post]:
        """Get posts by their IDs."""
        ...

    async def get_feed_total_count(
        self, user_id: EntityId, friend_ids: list[EntityId]
    ) -> int:
        """Get total count of posts available in user's feed."""
        ...

    async def get_feed_posts_cursor(
        self, user_id: EntityId, friend_ids: list[EntityId],
        first: int = 20, after_cursor: str | None = None
    ) -> CursorPage[Post]:
        """Get feed posts using cursor-based pagination."""
        ...