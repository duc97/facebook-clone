from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class Post:
    """Post entity representing a user's post."""

    id: EntityId
    author_id: EntityId
    content: str
    media_urls: tuple[str, ...]  # immutable tuple, not list
    like_count: int = 0
    comment_count: int = 0
    is_published: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, author_id: EntityId, content: str, media_urls: tuple[str, ...] = ()) -> Post:
        return cls(id=EntityId.generate(), author_id=author_id, content=content, media_urls=media_urls)

    def update_content(self, new_content: str) -> Post:
        return replace(self, content=new_content)

    def increment_like_count(self) -> Post:
        return replace(self, like_count=self.like_count + 1)

    def decrement_like_count(self) -> Post:
        return replace(self, like_count=max(0, self.like_count - 1))

    def increment_comment_count(self) -> Post:
        return replace(self, comment_count=self.comment_count + 1)

    def decrement_comment_count(self) -> Post:
        return replace(self, comment_count=max(0, self.comment_count - 1))

    def delete(self) -> Post:
        return replace(self, is_published=False)