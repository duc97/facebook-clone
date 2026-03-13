from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from fb.domain.friend.value_objects import FriendRequestStatus
from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class FriendRequest:
    """Friend request domain entity."""

    id: EntityId
    sender_id: EntityId
    receiver_id: EntityId
    status: FriendRequestStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls, sender_id: EntityId, receiver_id: EntityId
    ) -> FriendRequest:
        """Factory method to create a new pending friend request."""
        return cls(
            id=EntityId.generate(),
            sender_id=sender_id,
            receiver_id=receiver_id,
            status=FriendRequestStatus.PENDING,
        )

    def accept(self) -> FriendRequest:
        """Return a new FriendRequest with status ACCEPTED."""
        return replace(self, status=FriendRequestStatus.ACCEPTED)

    def reject(self) -> FriendRequest:
        """Return a new FriendRequest with status REJECTED."""
        return replace(self, status=FriendRequestStatus.REJECTED)

    def block(self) -> FriendRequest:
        """Return a new FriendRequest with status BLOCKED."""
        return replace(self, status=FriendRequestStatus.BLOCKED)


@dataclass(frozen=True, slots=True)
class Friendship:
    """Friendship domain entity (one direction)."""

    id: EntityId
    user_id: EntityId
    friend_id: EntityId
    created_at: datetime | None = None

    @classmethod
    def create_pair(
        cls, user_id: EntityId, friend_id: EntityId
    ) -> tuple[Friendship, Friendship]:
        """Create bi-directional friendship (2 rows)."""
        return (
            cls(id=EntityId.generate(), user_id=user_id, friend_id=friend_id),
            cls(id=EntityId.generate(), user_id=friend_id, friend_id=user_id),
        )
