from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from fb.domain.shared.entity_id import EntityId


class ReactionType(Enum):
    LIKE = "LIKE"
    LOVE = "LOVE"
    HAHA = "HAHA"
    WOW = "WOW"
    SAD = "SAD"
    ANGRY = "ANGRY"


@dataclass(frozen=True, slots=True)
class Reaction:
    id: EntityId
    post_id: EntityId
    user_id: EntityId
    reaction_type: ReactionType
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        post_id: EntityId,
        user_id: EntityId,
        reaction_type: ReactionType,
    ) -> Reaction:
        return cls(
            id=EntityId.generate(),
            post_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
