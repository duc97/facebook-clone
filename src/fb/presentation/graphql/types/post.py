from __future__ import annotations

import strawberry


@strawberry.type
class PostType:
    id: strawberry.ID
    author_id: str
    text: str
    image: str | None
    like_count: int
    comment_count: int
    is_published: bool
