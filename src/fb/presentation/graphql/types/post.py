from __future__ import annotations

import strawberry


@strawberry.type
class PostType:
    id: strawberry.ID
    author_id: str
    content: str
    media_urls: list[str]
    like_count: int
    comment_count: int
    is_published: bool