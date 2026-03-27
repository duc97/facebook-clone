from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class Follow:
    """Follow relationship (unidirectional): follower follows following."""

    id: EntityId
    follower_id: EntityId
    following_id: EntityId
    created_at: datetime | None = None

    @classmethod
    def create(cls, follower_id: EntityId, following_id: EntityId) -> Follow:
        """Factory method to create a new follow."""
        return cls(
            id=EntityId.generate(),
            follower_id=follower_id,
            following_id=following_id,
        )
