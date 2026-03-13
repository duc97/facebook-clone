from __future__ import annotations

import strawberry


@strawberry.type
class CommentType:
    id: strawberry.ID
    post_id: str
    author_id: str
    content: str
    created_at: str | None = None


@strawberry.type
class LikeType:
    id: strawberry.ID
    post_id: str
    user_id: str


@strawberry.type
class CommentsResponse:
    comments: list[CommentType]
    total_count: int
    has_next_page: bool