from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.friend.entities import FriendRequest, Friendship
from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class FriendRepository(Protocol):
    """Protocol for Friend persistence."""

    async def find_request(
        self, sender_id: EntityId, receiver_id: EntityId
    ) -> FriendRequest | None:
        ...

    async def find_request_by_id(
        self, request_id: EntityId
    ) -> FriendRequest | None:
        ...

    async def save_request(self, request: FriendRequest) -> FriendRequest:
        ...

    async def update_request(self, request: FriendRequest) -> FriendRequest:
        ...

    async def save_friendship(self, friendship: Friendship) -> Friendship:
        ...

    async def delete_friendship(
        self, user_id: EntityId, friend_id: EntityId
    ) -> None:
        ...

    async def are_friends(
        self, user_id: EntityId, friend_id: EntityId
    ) -> bool:
        ...

    async def get_friends(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        ...

    async def get_pending_requests(
        self, user_id: EntityId
    ) -> list[FriendRequest]:
        ...

    async def get_mutual_friends(
        self, user_id: EntityId, other_id: EntityId
    ) -> list[EntityId]:
        ...

    async def get_friend_count(self, user_id: EntityId) -> int:
        ...
