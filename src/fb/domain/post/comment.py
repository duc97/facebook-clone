from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class Comment:
    id: EntityId
    post_id: EntityId
    author_id: EntityId
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, post_id: EntityId, author_id: EntityId, content: str) -> Comment:
        if not content or not content.strip():
            raise ValueError("Comment content cannot be empty")
        if len(content) > 2000:
            raise ValueError("Comment content exceeds 2000 characters")
        return cls(id=EntityId.generate(), post_id=post_id, author_id=author_id, content=content)

    def update_content(self, new_content: str) -> Comment:
        return replace(self, content=new_content)