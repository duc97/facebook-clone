from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.follow.entities import Follow
from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class FollowRepository(Protocol):
    """Protocol for Follow persistence."""

    async def save(self, follow: Follow) -> Follow:
        ...

    async def delete(self, follower_id: EntityId, following_id: EntityId) -> None:
        ...

    async def is_following(self, follower_id: EntityId, following_id: EntityId) -> bool:
        ...

    async def get_following(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        """Get list of user IDs that user_id is following."""
        ...

    async def get_followers(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        """Get list of user IDs that follow user_id."""
        ...

    async def get_following_count(self, user_id: EntityId) -> int:
        ...

    async def get_followers_count(self, user_id: EntityId) -> int:
        ...
