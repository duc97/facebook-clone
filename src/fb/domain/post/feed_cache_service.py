from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FeedCacheService(Protocol):
    """Protocol for feed caching operations."""

    async def get_feed(self, user_id: str) -> list[str] | None:
        """Get cached feed post IDs for user."""
        ...

    async def set_feed(self, user_id: str, post_ids: list[str], ttl: int | None = None) -> None:
        """Cache feed post IDs for user."""
        ...

    async def invalidate(self, user_id: str) -> None:
        """Invalidate cached feed for user."""
        ...