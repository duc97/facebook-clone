from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class Share:
    id: EntityId
    post_id: EntityId
    user_id: EntityId
    content: str = ""
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        post_id: EntityId,
        user_id: EntityId,
        content: str = "",
    ) -> Share:
        return cls(
            id=EntityId.generate(),
            post_id=post_id,
            user_id=user_id,
            content=content,
        )
