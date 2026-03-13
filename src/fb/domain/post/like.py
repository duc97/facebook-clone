from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class Like:
    id: EntityId
    post_id: EntityId
    user_id: EntityId
    created_at: datetime | None = None

    @classmethod
    def create(cls, post_id: EntityId, user_id: EntityId) -> Like:
        return cls(id=EntityId.generate(), post_id=post_id, user_id=user_id)